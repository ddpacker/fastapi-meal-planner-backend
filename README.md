# FastAPI Meal Planner Backend

This is a FastAPI + PostgreSQL backend for a weekly meal planning assistant that integrates with various AI models
to generate recipes, support per-meal chat refinement, build grocery lists, and estimate basic nutrition.

## Features

- **User auth** with JWT (email + password).
- **Weekly meal plans** with AI-generated recipes
- **Per-meal chat sessions** to iteratively refine recipes.
- **Grocery list generation** from all ingredients in a week.
- **Basic nutrition estimates** per recipe.

## Tech Stack
- FastAPI, PostgreSQL, SQLAlchemy, Alembic
- Azure: Container Apps, Database for PostgreSQL, Key Vault
- CI/CD: GitHub Actions with OIDC
- Package management: uv

## Documentation
- [Architecture](docs/ARCHITECTURE.md) – System design and data model
- [Infrastructure](docs/INFRASTRUCTURE.md) – Azure setup and deployment
- [Setup Guide](docs/SETUP.md) – Development environment
- [Roadmap](docs/fastapi-meal-planner.plan.md) – Feature progress

## Quick start

1. Clone repo
2. `uv sync`
3. Configure environment (see [SETUP.md](docs/SETUP.md) for `.env` template)
4. `uv run alembic upgrade head`
5. `uv run uvicorn app.main:app --reload`
6. Open http://localhost:8000/docs

See [SETUP.md](docs/SETUP.md) for more details.

## Project layout

- `app/main.py` – FastAPI application, router registration, startup.
- `app/config.py` – settings (DB URL, API keys, JWT secrets, etc.).
- `app/db/` – SQLAlchemy engine, session, and base model.
- `app/models/` – SQLAlchemy models.
- `app/schemas/` – Pydantic models for requests/responses.
- `app/routers/` – FastAPI routers for auth, meal plans, recipes, chat, grocery, and nutrition.
- `app/services/` – business logic and orchestration.
- `app/clients/` – AI client wrappers.
- `app/utils/` – helpers such as prompt templates.
- `alembic/` – Alembic migration environment.

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design and data model.

## Infrastructure

### Cloud Hosting

- **Provider:** Azure
- **Compute:** Azure Container Apps - Scalable serverless container hosting for cost optimization
- **Database:** Azure Database for PostgreSQL - Relational storage with robust vector support. Private Link enables secure network isolation
- **Security:**
    - Azure Key Vault - Centralized secret management for API keys and database credentials
    - Managed Identity - Passwordless authentication between application and Azure resources
- **Networking:** Azure Virtual Network - Private Endpoints ensure the application, database, and Key Vault are entirely isolated from the public internet
- **Observability:** Azure Monitor and Application Insights - Tracing and performance metrics

### DevOps and Tooling

- **CI/CD:** GitHub Actions with OpenID Connect - Secretless deployment to Azure Container Registry
- **Package Management:** uv - Deterministic, high-speed dependency management
- **Containerization:** Docker - Multi-stage builds utilizing layer caching to minimize image size and reduce the production attack surface
- **Database Migrations:** Alembic - Schema versioning managed via container script. Synchronizes state between PostgreSQL schema and Pydantic models

See [INFRASTRUCTURE.md](docs/INFRASTRUCTURE.md) for Azure setup and deployment workflow details.

## Git Workflow

Conventions are actively refined over time as the project's scope and needs become clearer.

- Commit Names: `type: summary of change`
- Branch Names: `type/short-description`
- PRs Squashed to: `type: short description`