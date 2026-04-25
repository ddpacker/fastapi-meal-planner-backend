from app.core.security import create_access_token, decode_token


def test_create_access_token_round_trips_subject() -> None:
    token = create_access_token(subject="123")

    payload = decode_token(token)

    assert payload is not None
    assert payload.sub == "123"
    assert payload.jti is not None
    assert payload.exp is not None


def test_decode_token_rejects_expired_token() -> None:
    expired_token = create_access_token(subject="123", expires_minutes=-1)

    payload = decode_token(expired_token)

    assert payload is None


def test_decode_token_rejects_tampered_token() -> None:
    token = create_access_token(subject="123")
    tampered = f"{token}tampered"

    payload = decode_token(tampered)

    assert payload is None
