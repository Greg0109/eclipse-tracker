"""Main web service entry point."""

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

import logging_setup
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

from eclipse_tracker.config.config import (
    initialize_logging,
    settings,
)


@asynccontextmanager
async def lifespan(instance: FastAPI) -> AsyncGenerator[None, None]:
    """Manage app lifecycle."""
    instance.settings = settings
    logging_setup.get_logger(__name__).info("application_startup_completed", app_name=settings.service.app_name)
    yield
    logging_setup.get_logger(__name__).info("application_shutdown_completed")


initialize_logging()
app = FastAPI(lifespan=lifespan)


@app.middleware("http")
async def process_request(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Middleware to perform actions before and after handling the request."""
    # Perform any necessary actions before processing the request
    # Example actions: modifying headers, checking authentication, etc.
    # ....

    response = await call_next(request)

    # Perform any necessary actions after processing the request
    # Example actions: modifying the response, adding cookies, etc.
    # ....
    return response  # noqa: RET504


def say(message: str = "Hello World!") -> None:
    """Say a message."""
    return message


@app.get("/dummy/{item_id}")
async def read_item(item_id: int) -> JSONResponse:
    """Read item."""
    content = {"item_id": item_id, "message": say()}
    return JSONResponse(content=content, status_code=status.HTTP_200_OK)


@app.get("/alive", status_code=status.HTTP_204_NO_CONTENT)
async def alive() -> None:
    """Check if service is alive."""
    return
