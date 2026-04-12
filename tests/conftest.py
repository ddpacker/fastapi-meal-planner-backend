import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import app.db.base  # noqa: F401 — register all models on Base.metadata
from app.db.base_class import Base
from app.models.user import User


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)


@pytest.fixture()
def user(db: Session) -> User:
    u = User(email="test@example.com", password_hash="hashed")
    db.add(u)
    db.flush()
    return u
