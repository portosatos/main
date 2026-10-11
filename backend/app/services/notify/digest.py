"""The digest letter (SPEC F10): the subject, the text and the HTML with the list of the opened
recommendations and a link to the application.

The subject agrees the noun with the number («1 новая рекомендация», «2 новые рекомендации»,
«5 новых рекомендаций»), a departure from the literal text of SPEC F10 agreed with the user
(ADR-050).
"""

from dataclasses import dataclass
from datetime import date, datetime
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from html import escape

from app.services.rules.catalog import CATALOG, TITLES

DESCRIPTIONS = {info.code: info.description for info in CATALOG}
# As on the recommendations page (frontend/src/lib/rules.ts).
DISCLAIMER = (
    "Рекомендации носят информационный характер и не заменяют консультацию врача. "
    "Если вас беспокоит самочувствие, обратитесь к специалисту."
)


@dataclass(frozen=True)
class DigestItem:
    rule_code: str
    anchor_date: date


@dataclass(frozen=True)
class Letter:
    subject: str
    text: str
    html: str


def new_recommendations(count: int) -> str:
    """«N новых рекомендаций» agreed with N."""
    if count % 10 == 1 and count % 100 != 11:
        words = "новая рекомендация"
    elif count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        words = "новые рекомендации"
    else:
        words = "новых рекомендаций"
    return f"{count} {words}"


def compose(items: list[DigestItem], app_url: str) -> Letter:
    """The letter of the open recommendations `items`, in the order they were opened."""
    link = f"{app_url.rstrip('/')}/recommendations"
    news = new_recommendations(len(items))
    lines = [f"Здравствуйте! В трекере здоровья {news}:", ""]
    for item in items:
        lines.append(f"• {TITLES[item.rule_code]} (на {item.anchor_date:%d.%m.%Y})")
        lines.append(f"  {DESCRIPTIONS[item.rule_code]}")
    lines += ["", f"Подробнее и отзыв: {link}", "", DISCLAIMER, ""]
    entries = "".join(
        f"<li><strong>{escape(TITLES[item.rule_code])}</strong>"
        f" (на {item.anchor_date:%d.%m.%Y})<br>{escape(DESCRIPTIONS[item.rule_code])}</li>"
        for item in items
    )
    html = (
        f'<!doctype html><html lang="ru"><body>'
        f"<p>Здравствуйте! В трекере здоровья {escape(news)}:</p><ul>{entries}</ul>"
        f'<p><a href="{escape(link)}">Подробнее и отзыв</a></p>'
        f"<p><small>{escape(DISCLAIMER)}</small></p></body></html>"
    )
    return Letter(f"Трекер здоровья: {news}", "\n".join(lines), html)


def message(letter: Letter, *, sender: str, to: str, now: datetime) -> EmailMessage:
    """The letter as a text and HTML e-mail; `now` (Clock) is its date."""
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = letter.subject
    msg["Date"] = format_datetime(now)
    msg["Message-ID"] = make_msgid(domain="health-tracker.local")
    msg.set_content(letter.text)
    msg.add_alternative(letter.html, subtype="html")
    return msg
