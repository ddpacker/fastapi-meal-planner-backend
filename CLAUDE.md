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

## Coding standards

@.cursor/rules/ai-integration.mdc
@.cursor/rules/database.mdc
@.cursor/rules/project.mdc
@.cursor/rules/schemas.mdc
@.cursor/rules/security.mdc
@.cursor/rules/testing.mdc

## Architecture
@docs/ARCHITECTURE.md` — system design

## Plan conventions
`docs/CONVENTIONS.md` — cross-cutting rules (auth/ownership, pagination, summary
schemas, metric/singular AI output, category enum, delete cascade, AI-client injection).
Domain plans reference these by stable ID (e.g. CONV-AUTH-OWNERSHIP) instead of restating
them. Change a shared decision there, not in each plan. When and how to edit conventions vs.
plans is governed by "Conventions & plan governance" in `.cursor/rules/project.mdc`.

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