import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

import app.db.base  # noqa: F401 — register models
from app.db.base_class import Base

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "g6h7i8j9k0l1_recipe_ingredient_preparation.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "g6h7i8j9k0l1_recipe_ingredient_preparation", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_preparation_migration_applies_cleanly() -> None:
    prep_migration = _load_migration()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(sa.text("ALTER TABLE recipe_ingredients DROP COLUMN preparation"))

    assert "preparation" not in {
        col["name"] for col in inspect(engine).get_columns("recipe_ingredients")
    }

    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            prep_migration.upgrade()

    columns = {col["name"]: col for col in inspect(engine).get_columns("recipe_ingredients")}
    assert "preparation" in columns
    assert columns["preparation"]["nullable"] is True

    engine.dispose()
