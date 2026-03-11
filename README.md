## FastAPI Meal Planner Backend

This is a FastAPI + PostgreSQL backend for a weekly meal planning assistant that integrates with Anthropic models
to generate recipes, support per-meal chat refinement, build grocery lists, and estimate basic nutrition.

### Features

- **User auth** with JWT (email + password).
- **Weekly meal plans** with 7 planned meals.
- **Recipe generation** via Anthropic.
- **Per-meal chat sessions** to iteratively refine recipes.
- **Grocery list generation** from all ingredients in a week.
- **Basic nutrition estimates** per recipe.

### Project layout

- `app/main.py` – FastAPI application, router registration, startup.
- `app/config.py` – settings (DB URL, Anthropic API key, JWT secrets, etc.).
- `app/db/` – SQLAlchemy engine, session, and base model.
- `app/models/` – SQLAlchemy models.
- `app/schemas/` – Pydantic models for requests/responses.
- `app/routers/` – FastAPI routers for auth, meal plans, recipes, chat, grocery, and nutrition.
- `app/services/` – business logic and orchestration.
- `app/clients/` – Anthropic client wrapper.
- `app/utils/` – helpers such as prompt templates.
- `alembic/` – Alembic migration environment.

### Getting started

1. **Create a virtual environment with Python 3.12**

```bash
uv venv --python 3.12
```
2. **Activate the venv**

```bash
.venv\Scripts\activate
```

3. **Install dependencies**

```bash
uv sync
```

4. **Configure environment**

Create a `.env` file in the project root:

```bash
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/meal_planner
SECRET_KEY=change-me
ANTHROPIC_API_KEY=your-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20240620
```

5. **Run migrations**

```bash
uv run alembic upgrade head
```

6. **Run the development server**

```bash
uv run uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. Open `http://localhost:8000/docs` for the interactive
Swagger UI.

### Roadmap

**Backend API**
- [X] Project skeleton & health endpoint
- [X] Database models & Alembic migrations
- [X] Pydantic schemas & router stubs
- [ ] Anthropic integration & prompt templates
- [ ] Grocery & nutrition services
- [ ] Tests & OpenAPI documentation

**Future milestones**
- [ ] Angular web client
- [ ] Recipe rating system (thumbs up/down per generated recipe)
- [ ] RAG layer via pgvector (approved recipes embedded and retrieved as few-shot context)
- [ ] Swap Anthropic for local Llama model (provider-agnostic AI layer)
- [ ] Mobile client
