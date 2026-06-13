"""FastAPI application entrypoint: CORS, router wiring, startup seeding."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.config import get_settings
from app.routers import (
    auth,
    demographics,
    exports,
    health,
    participants,
    runtime,
    sessions,
    statistics,
    studies,
    users,
)
from app.services.seed import seed_admin

API_V1_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    seed_admin()
    yield


app = FastAPI(title="Choice Reaction Time API", version="1.0.0", lifespan=lifespan)


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """Translate `pydantic.ValidationError` raised by `merge_and_validate_params`
    (task parameter merging/validation) into a 422 response, matching the
    shape FastAPI itself uses for request-body validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(exc.errors())},
    )


settings = get_settings()
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

for _router in (
    health.router,
    auth.router,
    users.router,
    studies.router,
    demographics.router,
    participants.router,
    sessions.router,
    runtime.router,
    statistics.router,
    exports.router,
):
    app.include_router(_router, prefix=API_V1_PREFIX)
