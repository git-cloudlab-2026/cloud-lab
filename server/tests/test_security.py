import pytest

from app.core.errors import ApiError
from app.core.security import create_access_token, decode_access_token


def test_create_and_decode_access_token():
    token = create_access_token(subject=42, email="admin@giptech.ch", role="admin")

    payload = decode_access_token(token)

    assert payload["sub"] == "42"
    assert payload["email"] == "admin@giptech.ch"
    assert payload["role"] == "admin"


def test_decode_invalid_access_token_raises_api_error():
    with pytest.raises(ApiError) as exc:
        decode_access_token("not-a-valid-token")

    assert exc.value.status_code == 401
    assert exc.value.code == "invalid_token"
