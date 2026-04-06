# Deployment

## Overview
FastAPI meal planner deploys to Azure Container Apps with PostgreSQL backend.
See [INFRASTRUCTURE.md](INFRASTRUCTURE.md) for resource setup.

## Pre-deployment checklist
- All tests passing
- Environment variables configured (see SETUP.md)
- Database migrations up to date (`alembic upgrade head`)
- Docker image builds locally

## Docker build and run
```bash
docker build -t meal-planner:latest .
docker run -p 8000:8000 --env-file .env meal-planner:latest
```

## Deployment to Azure Container Apps
*In progress — see [INFRASTRUCTURE.md](INFRASTRUCTURE.md) for Azure setup and GitHub Actions workflow.*

## Environment variables
Required in production:
- `DATABASE_URL` – Azure PostgreSQL connection string
- `ANTHROPIC_API_KEY` – Retrieved from Key Vault
- `ANTHROPIC_MODEL` – Anthropic model selection
- `SECRET_KEY` – JWT secret from Key Vault
- `AI_PROVIDER` – Provider selection (anthropic, test)

See [SETUP.md](SETUP.md) for full list.

## Rollback
*To be documented after ACA deployment is configured.*

## Monitoring
*To be documented after Application Insights is enabled.*