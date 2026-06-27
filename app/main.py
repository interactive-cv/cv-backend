from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.errors import AppError, app_error_handler
from app.routers import cv, health, projects


def create_app() -> FastAPI:
    app = FastAPI(title="CV API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(health.router)
    app.include_router(cv.router)
    app.include_router(projects.router)
    return app


app = create_app()
