"""Centralized safe HTTP errors without leaking document/provider payloads."""

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class DemoError(Exception):
    """Carry an explicitly public message and HTTP status."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def install_handlers(app: FastAPI) -> None:
    """Normalize application, validation, routing, and unexpected failures."""

    @app.exception_handler(Exception)
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = str(uuid4())
        if isinstance(exc, DemoError):
            code, message, status = exc.code, exc.message, exc.status
        elif isinstance(exc, RequestValidationError):
            code, message, status = (
                "INVALID_REQUEST",
                "Check the request fields and cursor.",
                422,
            )
        elif isinstance(exc, HTTPException):
            code, message, status = (
                "HTTP_ERROR",
                "The requested operation is unavailable.",
                exc.status_code,
            )
        else:
            code, message, status = (
                "INTERNAL_ERROR",
                "The demo server encountered an error.",
                500,
            )
            logger.error("request=%s failure_type=%s", request_id, type(exc).__name__)
        return JSONResponse(
            status_code=status,
            content={
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": request_id,
                }
            },
        )

    app.add_exception_handler(DemoError, handler)
    app.add_exception_handler(RequestValidationError, handler)
    app.add_exception_handler(HTTPException, handler)
