"""FastAPI application factory. Step 0.2: stub until the feature is implemented."""

from fastapi import FastAPI

from app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    raise NotImplementedError("step 0.2: create_app is not implemented yet")
