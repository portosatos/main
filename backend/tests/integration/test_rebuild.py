"""Full rebuild of the derived minute tables and their stability (SPEC §4, F4.3): `htadmin
rebuild` gives the incremental result, a repeated upload changes nothing."""

import shutil
import subprocess
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app import cli
from app.services import minutes
from tests.integration.ingest import derived_hashes, make_user, upload

NOT_IMPLEMENTED = pytest.mark.xfail(strict=True, reason="step 3.3: not implemented")

GENERATOR_DIR = Path(__file__).resolve().parents[3] / "generator"
# Two devices, unaligned steps, sleep, pulse, a time zone change and gaps: two days keep it fast.
HTGEN_ARGS = [
    "--start", "2026-10-01",
    "--end", "2026-10-02",
    "--seed", "5",
    "--unaligned",
    "--tz-change", "2026-10-02T12:00Z=America/New_York",
    "--gap-prob", "0.5",
    "--gap-max-hours", "6",
]  # fmt: skip
# An odd batch size: batch borders fall inside minutes and intervals.
SMALL_BATCH = 997


@pytest.fixture(scope="module")
def htgen_file(tmp_path_factory: pytest.TempPathFactory) -> bytes:
    uv = shutil.which("uv")
    if uv is None:
        pytest.fail("uv is not on PATH: it runs the generator (generator/)", pytrace=False)
    out = tmp_path_factory.mktemp("htgen") / "rebuild.ndjson"
    subprocess.run(
        [uv, "run", "--project", str(GENERATOR_DIR), "htgen", *HTGEN_ARGS, "--out", str(out)],
        check=True,
        timeout=300,
    )
    return out.read_bytes()


@pytest.fixture
async def session(
    test_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with test_sessionmaker() as session:
        yield session


async def delete_derived(session: AsyncSession, user_id: uuid.UUID) -> None:
    for table in ("steps_minute", "sleep_minute", "coverage_minute"):
        await session.execute(
            text(
                f"DELETE FROM {table} WHERE device_id IN "
                "(SELECT id FROM devices WHERE user_id = :u)"
            ),
            {"u": user_id},
        )


async def test_rebuild_equals_incremental(session: AsyncSession, htgen_file: bytes) -> None:
    user_id = await make_user(session, email="rebuild@example.com")
    other_id = await make_user(session, email="other@example.com")
    await upload(session, user_id, htgen_file, batch_size=SMALL_BATCH)
    await upload(session, other_id, htgen_file)
    incremental = await derived_hashes(session, user_id)
    other = await derived_hashes(session, other_id)
    assert all(count > 0 for count, _ in incremental.values())

    result = await minutes.rebuild_user(session, user_id)

    assert await derived_hashes(session, user_id) == incremental
    assert result == minutes.RebuildResult(
        devices=2,
        steps_minutes=incremental["steps_minute"][0],
        sleep_minutes=incremental["sleep_minute"][0],
        coverage_minutes=incremental["coverage_minute"][0],
    )
    # The cache is gone: the rebuild restores it from the raw records alone.
    await delete_derived(session, user_id)
    await minutes.rebuild_user(session, user_id)
    assert await derived_hashes(session, user_id) == incremental
    # Other users are not touched.
    assert await derived_hashes(session, other_id) == other


async def test_reupload_leaves_derived_tables_unchanged(
    session: AsyncSession, htgen_file: bytes
) -> None:
    user_id = await make_user(session)
    await upload(session, user_id, htgen_file)
    first = await derived_hashes(session, user_id)
    assert all(count > 0 for count, _ in first.values())

    _, counts = await upload(session, user_id, htgen_file, batch_size=SMALL_BATCH)

    assert counts.new == 0
    assert await derived_hashes(session, user_id) == first


# Beyond the plan: the command line of `htadmin rebuild`.
@NOT_IMPLEMENTED
async def test_cli_rebuild_by_email(
    session: AsyncSession,
    test_sessionmaker: async_sessionmaker[AsyncSession],
    htgen_file: bytes,
    capsys: pytest.CaptureFixture[str],
) -> None:
    user_id = await make_user(session, email="cli@example.com")
    await upload(session, user_id, htgen_file)
    expected = await derived_hashes(session, user_id)
    await delete_derived(session, user_id)
    await session.commit()

    code = await cli.run(["rebuild", "--user", "CLI@example.com"], test_sessionmaker)

    assert code == 0
    assert "cli@example.com" in capsys.readouterr().out
    assert await derived_hashes(session, user_id) == expected

    code = await cli.run(["rebuild", "--user", "nobody@example.com"], test_sessionmaker)

    assert code == 1
    assert "nobody@example.com" in capsys.readouterr().err
