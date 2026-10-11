"""The digest dispatcher (SPEC F10, ADR-050): the worker's tick plans the digest of every user with
pending outbox entries (planner.plan_send) and sends one letter with all of them when it is due.

Each user in three short transactions under the user's digest lock (an advisory lock of its own,
so a long upload does not hold the letters; another dispatcher skips a locked user):

1. plan: the planned digest — the user's row of email_digests with `sent_at` NULL — gets the
   time and the reason of the plan, and is committed. Not due yet: done.
2. send: the entries whose recommendation is no longer open are `skipped`; none open → no
   letter, the planned row goes away and the daily limit is not used. Otherwise the letter is
   written into the row, the entries are linked to it (`sent`), `sent_at` is set and flushed (the
   unique index of one digest per local date checks it before SMTP), then SMTP — cut off after
   SMTP_TIMEOUT_S — and the commit with `digest.sent`.
3. a failed send rolls step 2 back, so the error is written into the planned row (committed in
   step 1) in a transaction of its own; the next tick tries again.

A user without an address for digests is not planned: the entries wait, GET /api/digests warns.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import EmailDigest, EmailOutbox, Recommendation, User
from app.services import events
from app.services.localtime import load_tz_history
from app.services.notify.digest import DigestItem, compose, message
from app.services.notify.mailer import Mailer
from app.services.notify.planner import DIGEST_MAX_DELAY, DIGEST_WINDOW, QuietHours, plan_send

log = structlog.get_logger(__name__)

# First key of the two-key advisory locks of the dispatcher (the job queue uses 32).
DIGEST_LOCK_NAMESPACE = 33
# The stored error is cut to this many characters.
ERROR_LIMIT = 500
DIGEST_SENT = "digest.sent"


@dataclass(frozen=True)
class DigestConfig:
    window: timedelta = DIGEST_WINDOW
    max_delay: timedelta = DIGEST_MAX_DELAY
    # The link in the letter.
    app_url: str = "http://localhost:5173"
    sender: str = "Трекер здоровья <noreply@health-tracker.local>"


DEFAULT_CONFIG = DigestConfig()


async def dispatch(
    sessionmaker: async_sessionmaker[AsyncSession],
    now: datetime,
    mailer: Mailer,
    config: DigestConfig = DEFAULT_CONFIG,
) -> int:
    """Plan the digests of the users with pending entries and send the due ones; the number sent."""
    async with sessionmaker() as session:
        users = list(
            await session.scalars(
                select(EmailOutbox.user_id).where(EmailOutbox.status == "pending").distinct()
            )
        )
    sent = 0
    for user_id in users:
        try:
            digest_id = await _plan(sessionmaker, user_id, now, config)
            if digest_id is not None and await _send(sessionmaker, user_id, now, mailer, config):
                sent += 1
        except Exception as exc:  # one user's failure must not stop the others
            log.warning("digest_failed", user_id=str(user_id), error=repr(exc))
    return sent


async def _lock(session: AsyncSession, user_id: uuid.UUID) -> bool:
    locked = await session.scalar(
        select(func.pg_try_advisory_xact_lock(DIGEST_LOCK_NAMESPACE, func.hashtext(str(user_id))))
    )
    return bool(locked)


async def _planned(session: AsyncSession, user_id: uuid.UUID) -> EmailDigest | None:
    return await session.scalar(
        select(EmailDigest).where(EmailDigest.user_id == user_id, EmailDigest.sent_at.is_(None))
    )


async def _plan(
    sessionmaker: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    now: datetime,
    config: DigestConfig,
) -> uuid.UUID | None:
    """Step 1: store the plan; the id of the planned digest when it is due."""
    async with sessionmaker() as session:
        if not await _lock(session, user_id):
            return None
        user = await session.get(User, user_id)
        if user is None or not user.notify_email:
            return None
        pending = list(
            await session.scalars(
                select(EmailOutbox.created_at).where(
                    EmailOutbox.user_id == user_id, EmailOutbox.status == "pending"
                )
            )
        )
        if not pending:
            return None
        history = await load_tz_history(session, user_id)
        last = await session.scalar(
            select(func.max(EmailDigest.local_date)).where(
                EmailDigest.user_id == user_id, EmailDigest.sent_at.is_not(None)
            )
        )
        quiet = QuietHours(user.quiet_enabled, user.quiet_start, user.quiet_end)
        plan = plan_send(
            pending, last, history, quiet, now, window=config.window, max_delay=config.max_delay
        )
        due = plan.at <= now
        digest = await _planned(session, user_id)
        if digest is None:
            digest = EmailDigest(user_id=user_id, created_at=now)
            session.add(digest)
        # Due: the time the last tick planned stays, unless it is still ahead (the settings
        # changed since); the letter's date is the date of the send.
        if not (due and digest.planned_at is not None and digest.planned_at <= now):
            digest.planned_at, digest.plan_reason = plan.at, plan.reason
        digest.local_date = history.local_date(plan.at)
        await session.flush()
        digest_id = digest.id
        await session.commit()
    return digest_id if due else None


async def _send(
    sessionmaker: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    now: datetime,
    mailer: Mailer,
    config: DigestConfig,
) -> bool:
    """Steps 2 and 3: the letter of the open recommendations; True when it is sent."""
    digest_id = None
    try:
        async with sessionmaker() as session:
            if not await _lock(session, user_id):
                return False
            digest = await _planned(session, user_id)
            user = await session.get(User, user_id)
            if digest is None or user is None or not user.notify_email:
                return False
            digest_id = digest.id
            rows = (
                await session.execute(
                    select(EmailOutbox, Recommendation)
                    .join(Recommendation, Recommendation.id == EmailOutbox.recommendation_id)
                    .where(EmailOutbox.user_id == user_id, EmailOutbox.status == "pending")
                    .order_by(EmailOutbox.created_at, EmailOutbox.id)
                )
            ).all()
            included = [(entry, rec) for entry, rec in rows if rec.status == "open"]
            for entry, rec in rows:
                if rec.status != "open":
                    entry.status = "skipped"
            if not included:
                await session.execute(delete(EmailDigest).where(EmailDigest.id == digest.id))
                await session.commit()
                log.info("digest_skipped", user_id=str(user_id), reason="no_open_recommendations")
                return False

            letter = compose(
                [DigestItem(r.rule_code, r.anchor_date) for _, r in included], config.app_url
            )
            digest.to_email = user.notify_email
            digest.subject, digest.body_text, digest.body_html = (
                letter.subject,
                letter.text,
                letter.html,
            )
            digest.sent_at, digest.error = now, None
            for entry, _rec in included:
                entry.status, entry.digest_id = "sent", digest.id
            await session.flush()  # the one-digest-per-date index, before the letter goes
            await mailer.send(message(letter, sender=config.sender, to=user.notify_email, now=now))
            data = {
                "id": str(digest.id),
                "local_date": digest.local_date.isoformat(),
                "count": len(included),
            }
            await events.publish(session, user_id, DIGEST_SENT, data)
            await session.commit()
    except Exception as exc:
        if digest_id is None:
            raise
        error = f"{type(exc).__name__}: {exc}"[:ERROR_LIMIT]
        async with sessionmaker() as session:
            await session.execute(
                update(EmailDigest)
                .where(EmailDigest.id == digest_id, EmailDigest.sent_at.is_(None))
                .values(error=error)
            )
            await session.commit()
        log.warning(
            "digest_send_failed", user_id=str(user_id), digest_id=str(digest_id), error=error
        )
        return False
    log.info("digest_sent", user_id=str(user_id), digest_id=str(digest_id), count=len(included))
    return True
