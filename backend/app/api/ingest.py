"""Ingest routes (SPEC F3, §6.3): file upload and the reports of the user's jobs."""

import uuid

from fastapi import APIRouter, Request

from app.auth.deps import CurrentUserDep

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/files", status_code=202)
async def upload_file(request: Request, user: CurrentUserDep) -> dict:
    raise NotImplementedError("step 3.2")


@router.get("/jobs")
async def list_jobs(user: CurrentUserDep) -> list:
    raise NotImplementedError("step 3.2")


@router.get("/jobs/{job_id}")
async def get_job(job_id: uuid.UUID, user: CurrentUserDep) -> dict:
    raise NotImplementedError("step 3.2")
