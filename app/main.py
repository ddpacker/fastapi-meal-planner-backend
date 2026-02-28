import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings


logger = logging.getLogger("meal_planner")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context for startup/shutdown events."""
    settings = get_settings()
    # Startup
    logger.info("Meal Planner backend starting up", extra={"environment": settings.environment})
    yield
    # Shutdown (add cleanup here if needed)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Meal Planner Backend",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

