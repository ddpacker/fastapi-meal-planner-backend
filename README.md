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

1. **Create and activate a virtual environment**

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Unix
```

2. **Install dependencies**

```bash
pip install -r requirements.txt
```

3. **Configure environment**

Create a `.env` file in the project root:

```bash
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/meal_planner
SECRET_KEY=change-me
ANTHROPIC_API_KEY=your-key-here
ANTHROPIC_MODEL=claude-3-5-sonnet-20240620
```

4. **Run migrations**

```bash
alembic upgrade head
```

5. **Run the development server**

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`. Open `http://localhost:8000/docs` for the interactive
Swagger UI.

