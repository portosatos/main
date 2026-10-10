"""htadmin: maintenance commands. `htadmin rebuild --user <email>` rebuilds the derived minute
tables of a user from the raw records (SPEC §4).

In the image `htadmin` is a wrapper of `python -m app.cli`; locally:
`cd backend; uv run python -m app.cli rebuild --user demo@example.com`.
"""

import argparse
import asyncio
import sys
import time
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.accounts import find_user_by_email
from app.config import Settings
from app.db import create_engine, create_sessionmaker
from app.services.minutes import rebuild_user


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="htadmin", description="Health tracker maintenance.")
    commands = root.add_subparsers(dest="command", required=True)
    rebuild = commands.add_parser(
        "rebuild", help="rebuild the derived minute tables of a user from the raw records"
    )
    rebuild.add_argument("--user", required=True, metavar="EMAIL", help="the user's email")
    return root


async def run(argv: Sequence[str], sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    """Run a command; returns the process exit code."""
    args = parser().parse_args(argv)
    async with sessionmaker() as session:
        user = await find_user_by_email(session, args.user)
        if user is None:
            print(f"htadmin: no user with email {args.user}", file=sys.stderr)
            return 1
        started = time.monotonic()
        result = await rebuild_user(session, user.id)
        await session.commit()
    print(
        f"rebuilt {user.email}: {result.devices} devices, steps_minute {result.steps_minutes}, "
        f"sleep_minute {result.sleep_minutes}, coverage_minute {result.coverage_minutes} rows "
        f"in {time.monotonic() - started:.1f} s"
    )
    return 0


async def _main(argv: Sequence[str] | None) -> int:
    engine = create_engine(Settings())
    try:
        return await run(sys.argv[1:] if argv is None else argv, create_sessionmaker(engine))
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(_main(argv))


if __name__ == "__main__":
    sys.exit(main())
