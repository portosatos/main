"""Ingest routes (SPEC F3, §6.3): file upload and the reports of the user's jobs."""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import select

from app.api.deps import ClockDep, SessionDep
from app.auth.deps import CurrentUserDep
from app.models import IngestJob
from app.schemas.ingest import IngestJobOut, UploadAccepted
from app.services.ingest.jobs import submit_file
from app.services.ingest.upload import (
    UploadError,
    UploadTooLarge,
    multipart_boundary,
    receive_file,
)

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

# Multipart framing around the file: boundaries and part headers.
MULTIPART_OVERHEAD = 64 * 1024


def too_large(max_bytes: int) -> HTTPException:
    return HTTPException(
        status.HTTP_413_CONTENT_TOO_LARGE,
        detail=f"Файл больше {max_bytes / (1024 * 1024):g} МБ",
    )


@router.post("/files", status_code=status.HTTP_202_ACCEPTED)
async def upload_file(
    request: Request, user: CurrentUserDep, session: SessionDep, clock: ClockDep
) -> UploadAccepted:
    """Multipart field `file` (NDJSON). The file is written to the ingest volume while it
    arrives, a worker processes it. 413 over the size limit."""
    settings = request.app.state.settings
    max_bytes = settings.ingest_max_bytes
    try:
        boundary = multipart_boundary(request.headers.get("content-type", ""))
    except UploadError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)) from exc
    length = request.headers.get("content-length", "")
    if length.isdigit() and int(length) > max_bytes + MULTIPART_OVERHEAD:
        raise too_large(max_bytes)

    job_id = uuid.uuid4()
    directory = settings.ingest_dir / str(user.id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{job_id}.ndjson"
    partial = path.with_suffix(".part")
    try:
        try:
            received = await receive_file(
                request.stream(), boundary=boundary, target=partial, max_bytes=max_bytes
            )
        except UploadTooLarge as exc:
            raise too_large(max_bytes) from exc
        except UploadError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        partial.replace(path)
        await submit_file(
            session,
            user_id=user.id,
            job_id=job_id,
            filename=received.filename or path.name,
            file_path=str(path),
            bytes_total=received.size,
            now=await clock.now(),
        )
        await session.commit()
    except BaseException:
        partial.unlink(missing_ok=True)
        path.unlink(missing_ok=True)
        raise
    return UploadAccepted(job_id=job_id)


@router.get("/jobs")
async def list_jobs(
    user: CurrentUserDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[IngestJobOut]:
    """The user's jobs, newest first."""
    jobs = await session.scalars(
        select(IngestJob)
        .where(IngestJob.user_id == user.id)
        .order_by(IngestJob.created_at.desc(), IngestJob.id)
        .limit(limit)
    )
    return [IngestJobOut.of(job) for job in jobs]


@router.get("/jobs/{job_id}")
async def get_job(job_id: uuid.UUID, user: CurrentUserDep, session: SessionDep) -> IngestJobOut:
    job = await session.scalar(
        select(IngestJob).where(IngestJob.id == job_id, IngestJob.user_id == user.id)
    )
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Задача не найдена")
    return IngestJobOut.of(job)
