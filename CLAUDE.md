# FastAPI Meal Planner — Quick Reference

## Project Overview

FastAPI + PostgreSQL backend for a weekly meal planning assistant. An abstract AI client layer (Python ABC) drives recipe generation and chat refinement; Anthropic is the first concrete provider. No frontend — pure JSON API.

## Run commands
```bash
uv sync
uv run uvicorn app.main:app --reload
uv run pytest
uv run alembic upgrade head
```

## Key files

@.cursor/rules/general.mdc
@.cursor/rules/python.mdc
@.cursor/rules/api.mdc
@.cursor/rules/testing.mdc

- `.cursor/rules` — coding standards
- `docs/ARCHITECTURE.md` — system design
- `docs/plans/` — feature roadmaps
- `pyproject.toml` — dependencies (source of truth)

## Environment
```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/meal_planner
SECRET_KEY=<SECRET-KEY>
ANTHROPIC_API_KEY=<ANTHROPIC_API_KEY>
ANTHROPIC_MODEL=<ANTHROPIC_MODEL>
AI_PROVIDER=anthropic
```

## Build order

Build order defined in the following plans:
- `docs/plans/fastapi-meal-planner-backend.plan.md`
- `docs/plans/ai-connector.plan.md`