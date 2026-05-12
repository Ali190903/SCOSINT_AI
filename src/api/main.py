"""
SCOSINT_AI — FastAPI Application Factory

WHY: App factory pattern istifadə edirik ki, test-lərdə fərqli konfiqurasiya
ilə app yarada bilək. Plugin Manager burada yaradılır və app state-ə əlavə
edilir — bütün route-lar eyni manager instance-ından istifadə edir.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from src.core.plugin_manager import PluginManager
from src.utils.logger import setup_logging
from src.api.routes import scan, health, plugins as plugins_routes

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App başlayanda plugin-ləri yüklə, bağlananda təmizlə."""
    setup_logging(log_level="INFO", log_format="console")

    # Plugin Manager yarat və plugin-ləri discover et
    manager = PluginManager()
    loaded = manager.discover_plugins()
    logger.info("app_started", plugins_loaded=loaded)

    # App state-ə əlavə et — route-lar buradan oxuyacaq
    app.state.plugin_manager = manager

    yield

    logger.info("app_shutdown")


def create_app() -> FastAPI:
    """FastAPI app instance yaradır."""
    app = FastAPI(
        title="SCOSINT_AI",
        description="The most powerful modular OSINT+AI platform — find any digital footprint",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Route-ları qoş
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app.include_router(scan.router, prefix="/api/v1", tags=["Scan"])
    app.include_router(plugins_routes.router, prefix="/api/v1", tags=["Plugins"])

    return app


# Uvicorn entry point
app = create_app()
