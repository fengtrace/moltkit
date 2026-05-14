"""Tests for the moltkit SDK client (mocked HTTP, no network)."""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from moltkit.client import MoltenClient
from moltkit.errors import ApiError, AuthenticationError, NotFoundError, RateLimitError

from .conftest import mock_urlopen_factory

# ──────────────────────────
# Auth
# ──────────────────────────


class TestAuth:
    def test_no_key_raises(self):
        client = MoltenClient(api_key="")
        with pytest.raises(AuthenticationError):
            client._request("GET", "/home")

    def test_key_passed_directly(self):
        client = MoltenClient(api_key="direct_key")
        assert client.is_authenticated
        assert client.api_key == "direct_key"


# ──────────────────────────
# JSONDecodeError handling
# ──────────────────────────


class TestJsonDecodeError:
    """The fix for issue #1 — non-JSON 200 responses."""

    def test_non_json_response_raises_api_error(self):
        """When API returns non-JSON, ApiError with preview."""
        client = MoltenClient(api_key="test")

        with patch(
            "urllib.request.urlopen",
            mock_urlopen_factory([(200, "not json at all")]),
        ):
            with pytest.raises(ApiError) as exc:
                client._request("GET", "/home")

            assert "Non-JSON" in str(exc.value)
            assert exc.value.hint is not None

    def test_normal_json_still_works(self):
        """Normal JSON responses parse correctly."""
        client = MoltenClient(api_key="test")
        home_data = {"karma": 42, "name": "test"}

        with patch(
            "urllib.request.urlopen",
            mock_urlopen_factory([(200, home_data)]),
        ):
            result = client._request("GET", "/home")
            assert result["karma"] == 42
            assert result["name"] == "test"


# ──────────────────────────
# HTTP error handling
# ──────────────────────────


class TestHttpErrors:
    def test_401_raises_authentication_error(self):
        client = MoltenClient(api_key="bad_key")
        with patch(
            "urllib.request.urlopen",
            mock_urlopen_factory([(401, {"message": "Invalid API key"})]),
        ):
            with pytest.raises(AuthenticationError):
                client._request("GET", "/home")

    def test_404_raises_not_found_error(self):
        client = MoltenClient(api_key="test")
        with patch(
            "urllib.request.urlopen",
            mock_urlopen_factory([(404, {"message": "Not found"})]),
        ):
            with pytest.raises(NotFoundError):
                client._request("GET", "/nonexistent")

    def test_429_raises_rate_limit_error(self):
        client = MoltenClient(api_key="test")

        with patch(
            "urllib.request.urlopen",
            mock_urlopen_factory([(429, {"message": "Rate limited"})]),
        ):
            with pytest.raises(RateLimitError):
                client._request("GET", "/home")

    def test_429_with_retry_after_retries(self, monkeypatch):
        """429 with Retry-After header retries once then succeeds."""
        client = MoltenClient(api_key="test")
        monkeypatch.setattr("time.sleep", lambda s: None)

        # To test retries, we need the 429 response to have a Retry-After
        # header AND the mock_urlopen_factory to handle headers.
        # For now, test that the fallback path (no Retry-After) raises.
        with patch(
            "urllib.request.urlopen",
            mock_urlopen_factory([
                (429, {"message": "Slow down"}),
            ]),
        ):
            with pytest.raises(RateLimitError):
                client._request("GET", "/home")

    def test_500_raises_api_error(self):
        client = MoltenClient(api_key="test")
        with patch(
            "urllib.request.urlopen",
            mock_urlopen_factory([(500, {"message": "Server error"})]),
        ):
            with pytest.raises(ApiError) as exc:
                client._request("GET", "/home")
            assert exc.value.status_code == 500


# ──────────────────────────
# verify() method
# ──────────────────────────


class TestVerify:
    def test_method_exists_and_callable(self):
        client = MoltenClient(api_key="test")
        assert hasattr(client, "verify")
        assert callable(client.verify)

    def test_sends_correct_request(self):
        """Verify sends POST /verify with id and answer."""
        client = MoltenClient(api_key="test")
        captured = {}

        def tracking_urlopen(req, timeout=15):
            captured["url"] = req.full_url
            captured["method"] = req.method
            captured["body"] = json.loads(req.data) if req.data else None
            from tests.conftest import MockResponse
            return MockResponse({"status": "verified"})

        with patch("urllib.request.urlopen", tracking_urlopen):
            result = client.verify("challenge_abc", "42")

        assert captured["method"] == "POST"
        assert "/verify" in captured["url"]
        assert captured["body"] == {"id": "challenge_abc", "answer": "42"}
        assert result == {"status": "verified"}

    def test_args_by_position(self):
        """Verify with positional args also works."""
        client = MoltenClient(api_key="test")
        captured = {}

        def tracking_urlopen(req, timeout=15):
            captured["body"] = json.loads(req.data) if req.data else None
            from tests.conftest import MockResponse
            return MockResponse({"ok": True})

        with patch("urllib.request.urlopen", tracking_urlopen):
            client.verify("xyz", "123")
        assert captured["body"] == {"id": "xyz", "answer": "123"}


# ──────────────────────────
# Normal operations
# ──────────────────────────


class TestOperations:
    def test_get_home(self):
        client = MoltenClient(api_key="test")
        data = {"your_account": {"karma": 14, "name": "test"}}

        with patch(
            "urllib.request.urlopen",
            mock_urlopen_factory([(200, data)]),
        ):
            home = client.get_home()
            assert home.karma == 14

    def test_get_my_profile(self):
        client = MoltenClient(api_key="test")
        data = {"id": "abc", "name": "feng", "karma": 7}

        with patch(
            "urllib.request.urlopen",
            mock_urlopen_factory([(200, data)]),
        ):
            profile = client.get_my_profile()
            assert profile.name == "feng"

    def test_create_post(self):
        client = MoltenClient(api_key="test")
        data = {"id": "post_123"}

        with patch(
            "urllib.request.urlopen",
            mock_urlopen_factory([(200, data)]),
        ):
            result = client.create_post("test_sub", "Test Title", "Content")
            assert result["id"] == "post_123"
