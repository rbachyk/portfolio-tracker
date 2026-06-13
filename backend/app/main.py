from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import require_current_user
from app.api.routes_auth import router as auth_router
from app.api.routes_deposits import router as deposits_router
from app.api.routes_earn import router as earn_router
from app.api.routes_health import router as health_router
from app.api.routes_lots import router as lots_router
from app.api.routes_manual_adjustments import router as manual_adjustments_router
from app.api.routes_portfolio import router as portfolio_router
from app.api.routes_settings import router as settings_router
from app.api.routes_symbols import router as symbols_router
from app.api.routes_sync import router as sync_router
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
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health_router)
    app.include_router(auth_router, prefix=settings.api_prefix)
    protected_dependencies = [Depends(require_current_user)]
    app.include_router(
        portfolio_router,
        prefix=settings.api_prefix,
        dependencies=protected_dependencies,
    )
    app.include_router(lots_router, prefix=settings.api_prefix, dependencies=protected_dependencies)
    app.include_router(earn_router, prefix=settings.api_prefix, dependencies=protected_dependencies)
    app.include_router(
        deposits_router,
        prefix=settings.api_prefix,
        dependencies=protected_dependencies,
    )
    app.include_router(
        settings_router,
        prefix=settings.api_prefix,
        dependencies=protected_dependencies,
    )
    app.include_router(
        symbols_router,
        prefix=settings.api_prefix,
        dependencies=protected_dependencies,
    )
    app.include_router(sync_router, prefix=settings.api_prefix, dependencies=protected_dependencies)
    app.include_router(
        manual_adjustments_router,
        prefix=settings.api_prefix,
        dependencies=protected_dependencies,
    )
    return app


app = create_app()
