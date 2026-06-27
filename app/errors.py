import logging
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Доменная ошибка → единый JSON-ответ {error, message, request_id}."""

    def __init__(self, error: str, message: str, status_code: int):
        self.error = error
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    rid = str(uuid.uuid4())
    logger.warning("[%s] %s: %s path=%s", rid, exc.error, exc.message, request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error, "message": exc.message, "request_id": rid},
    )
