from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.api.routes import admin, experiments, faults, services
from app.core.config import get_settings
from app.core.exceptions import ChaosProbeException
from app.core.logging import logger, setup_logging
from app.database.base import Base
from app.database.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and shutdown lifecycle events."""
    settings = get_settings()
    setup_logging(level="DEBUG" if settings.DEBUG else "INFO")
    logger.info("Starting Chaos Probe engine...")

    # Ensure database tables exist (works across Postgres and SQLite)
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema verified and initialized.")

    yield

    logger.info("Shutting down Chaos Probe engine...")


def create_application() -> FastAPI:
    """Factory creating and configuring the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Controlled fault-injection and resilience testing platform for microservices.",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception Handlers
    @app.exception_handler(ChaosProbeException)
    async def chaos_probe_exception_handler(request: Request, exc: ChaosProbeException) -> JSONResponse:
        logger.warning(f"Domain exception on {request.url.path}: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": exc.__class__.__name__,
                "message": exc.message,
                "details": exc.details,
            },
        )

    # Core Health and Prometheus Endpoints
    @app.get("/health", tags=["System"])
    async def system_health() -> dict[str, str]:
        return {
            "status": "HEALTHY",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
        }

    @app.get("/metrics", tags=["System"])
    def prometheus_metrics() -> Response:
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    # Include API Routers
    app.include_router(services.router, prefix=settings.API_V1_PREFIX)
    app.include_router(experiments.router, prefix=settings.API_V1_PREFIX)
    app.include_router(faults.router, prefix=settings.API_V1_PREFIX)
    app.include_router(admin.router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()
