"""Unit tests for auth_service — no DB required (mocked)."""

from unittest.mock import MagicMock, patch

import pytest

from app.exceptions import DuplicateEmailError
from app.services.auth_service import (
    _generate_api_key,
    _hash_api_key,
    authenticate_user,
    create_user,
)


class TestApiKeyGeneration:
    def test_prefix(self):
        key = _generate_api_key()
        assert key.startswith("re_")

    def test_length(self):
        key = _generate_api_key()
        assert len(key) > 20

    def test_unique(self):
        keys = {_generate_api_key() for _ in range(50)}
        assert len(keys) == 50


class TestHashApiKey:
    def test_deterministic(self):
        assert _hash_api_key("abc") == _hash_api_key("abc")

    def test_hex_length(self):
        assert len(_hash_api_key("abc")) == 64

    def test_different_inputs(self):
        assert _hash_api_key("a") != _hash_api_key("b")


class TestCreateUser:
    def test_duplicate_email_raises(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = MagicMock()  # existing user

        with pytest.raises(DuplicateEmailError):
            create_user(db, "dup@test.com", "password123")

    def test_success(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None  # no existing

        user, api_key = create_user(db, "new@test.com", "password123")

        assert api_key.startswith("re_")
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()


class TestAuthenticateUser:
    def test_user_not_found(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        assert authenticate_user(db, "no@test.com", "pass") is None

    @patch("app.services.auth_service.pwd_context")
    def test_wrong_password(self, mock_ctx):
        db = MagicMock()
        mock_user = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_ctx.verify.return_value = False

        assert authenticate_user(db, "a@b.com", "wrong") is None

    @patch("app.services.auth_service.pwd_context")
    def test_success(self, mock_ctx):
        db = MagicMock()
        mock_user = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = mock_user
        mock_ctx.verify.return_value = True

        assert authenticate_user(db, "a@b.com", "correct") is mock_user
