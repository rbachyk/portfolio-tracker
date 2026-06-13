from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.routes_health import router as health_router
from app.api.routes_portfolio import router as portfolio_router
from app.config import get_settings
from app.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("backend.startup", app_name=settings.app_name, environment=settings.environment)
    yield
    logger.info("backend.shutdown", app_name=settings.app_name)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(health_router)
    app.include_router(portfolio_router, prefix=settings.api_prefix)
    return app


app = create_app()
