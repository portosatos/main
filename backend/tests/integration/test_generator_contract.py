"""Contract between the generator and the ingest: htgen output is valid and conflict-free
(SPEC F4.2, F13; docs/DATA_FORMAT.md)."""

import shutil
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.ingest.classify import ingest_records
from app.services.ingest.jobs import create_ingest_job
from app.services.ingest.parser import parse_lines
from tests.integration.ingest import NOW, make_user

pytestmark = pytest.mark.xfail(strict=True, reason="step 3.1: not implemented")

GENERATOR_DIR = Path(__file__).resolve().parents[3] / "generator"
# Unaligned steps, a time zone change in the middle of a day and random gaps: the hardest
# inputs htgen makes. Three days keep the test fast (~50 thousand records).
HTGEN_ARGS = [
    "--start", "2026-10-01",
    "--end", "2026-10-03",
    "--seed", "11",
    "--unaligned",
    "--tz-change", "2026-10-02T12:00Z=America/New_York",
    "--gap-prob", "0.5",
    "--gap-max-hours", "6",
]  # fmt: skip


@pytest.fixture
async def session(
    test_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with test_sessionmaker() as session:
        yield session


def run_htgen(out: Path) -> None:
    uv = shutil.which("uv")
    if uv is None:
        pytest.fail("uv is not on PATH: it runs the generator (generator/)", pytrace=False)
    subprocess.run(
        [uv, "run", "--project", str(GENERATOR_DIR), "htgen", *HTGEN_ARGS, "--out", str(out)],
        check=True,
        timeout=300,
    )


async def test_htgen_output_zero_invalid_zero_conflict(
    session: AsyncSession, tmp_path: Path
) -> None:
    path = tmp_path / "htgen.ndjson"
    run_htgen(path)
    data_lines = sum(1 for line in path.read_bytes().splitlines() if line.strip()) - 1  # minus meta
    user_id = await make_user(session)
    job_id = await create_ingest_job(
        session, user_id=user_id, source="file", filename=path.name, now=NOW
    )

    with path.open("rb") as stream:
        counts = await ingest_records(
            session, user_id=user_id, job_id=job_id, now=NOW, lines=parse_lines(stream)
        )

    assert counts.invalid == 0, counts.errors[:5]
    assert counts.conflict == 0, counts.errors[:5]
    assert counts.warnings == []
    assert counts.new == data_lines
    assert counts.duplicate == 0
