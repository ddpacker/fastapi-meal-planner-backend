import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.routers import auth, chat, meal_plans, recipes


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

    # Routers
    app.include_router(auth.router)
    app.include_router(meal_plans.router)
    app.include_router(recipes.router)
    app.include_router(chat.router)

    @app.get("/health", tags=["health"])
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

