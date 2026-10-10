"""htadmin: maintenance commands. `htadmin rebuild --user <email>` rebuilds the derived minute
tables of a user from the raw records (SPEC §4)."""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def run(argv: Sequence[str], sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    """Run a command; returns the process exit code."""
    raise NotImplementedError("step 3.3")


def main(argv: Sequence[str] | None = None) -> int:
    raise NotImplementedError("step 3.3")
