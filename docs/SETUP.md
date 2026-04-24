# Development Setup

## Prerequisites

- Python 3.12
- PostgreSQL (local install or Docker)
- Anthropic API key (get from [console.anthropic.com](https://console.anthropic.com))

## Installation

1. **Install dependencies and setup environment**

```bash
uv sync
```

---
2. **Configure environment**

Create `.env` file in the project root:

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/meal_planner
SECRET_KEY=<SECRET-KEY>
ANTHROPIC_API_KEY=<ANTHROPIC_API_KEY>
ANTHROPIC_MODEL=<ANTHROPIC_MODEL>
AI_PROVIDER=anthropic

# Optional — Google OAuth / OIDC (`GET /auth/google`, `GET /auth/google/callback`)
GOOGLE_CLIENT_ID=<GOOGLE_CLIENT_ID>
GOOGLE_CLIENT_SECRET=<GOOGLE_CLIENT_SECRET>
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

---
3. **PostgreSQL is required. Use Docker:**

```bash
docker run -d \
  --name meal-planner-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=meal_planner \
  -p 5432:5432 \
  postgres:16-alpine
```

For production Azure setup, see [INFRASTRUCTURE.md](INFRASTRUCTURE.md).

---
4. **Run schema migrations**

```bash
uv run alembic upgrade head
```

---
5. **Run the development server**

```bash
uv run uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. Open `http://localhost:8000/docs` for the interactive
Swagger UI.