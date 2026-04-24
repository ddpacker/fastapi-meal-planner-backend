import pytest
from sqlalchemy import select

from app.models.user import User
from app.services.google_oidc import upsert_user_from_google


def test_upsert_creates_user_with_google_sub(db) -> None:
    user = upsert_user_from_google(db, google_sub="sub-1", email="new@example.com")
    assert user.id is not None
    assert user.google_sub == "sub-1"
    assert user.email == "new@example.com"
    assert user.password_hash


def test_upsert_returns_same_user_by_google_sub(db) -> None:
    u1 = upsert_user_from_google(db, google_sub="sub-2", email="a@example.com")
    u2 = upsert_user_from_google(db, google_sub="sub-2", email="a@example.com")
    assert u1.id == u2.id


def test_upsert_links_existing_email_user(db, user: User) -> None:
    assert user.google_sub is None
    linked = upsert_user_from_google(db, google_sub="sub-link", email=user.email)
    assert linked.id == user.id
    db.expire(linked)
    row = db.execute(select(User).where(User.id == user.id)).scalar_one()
    assert row.google_sub == "sub-link"


def test_upsert_raises_when_email_linked_to_other_google_sub(db, user: User) -> None:
    user.google_sub = "existing-sub"
    db.commit()

    with pytest.raises(ValueError, match="google_account_mismatch"):
        upsert_user_from_google(db, google_sub="other-sub", email=user.email)
