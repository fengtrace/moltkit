"""Shared fixtures and helpers for moltkit tests."""
from __future__ import annotations

import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest


# ──────────────────────────
# Mock response helpers
# ──────────────────────────


class MockResponse:
    """Simulate an HTTP response for urllib."""

    def __init__(self, data: dict | str, status: int = 200):
        if isinstance(data, dict):
            self._data = json.dumps(data)
        else:
            self._data = data  # raw string, no JSON wrapping
        self._body_io = io.BytesIO(self._data.encode("utf-8"))

    def read(self) -> bytes:
        return self._data.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _make_http_error(
    status: int, body: str, headers: dict | None = None
) -> urllib.error.HTTPError:
    """Build a real urllib.error.HTTPError with the given status and body."""
    fp = io.BytesIO(body.encode("utf-8"))
    return urllib.error.HTTPError(
        url="http://mock/",
        code=status,
        msg=f"HTTP {status}",
        hdrs=headers or {},
        fp=fp,
    )


def mock_urlopen_factory(
    responses: list[tuple[int, dict | str]],
):
    """Create a urlopen mock that returns responses sequentially.

    Each element is (status_code, body_dict_or_string):
      - status < 400 → MockResponse (returned, not raised)
      - status >= 400 → raises real urllib.error.HTTPError
    Raises AssertionError if called more times than items.
    """
    iterator = iter(responses)

    def _mock(req, timeout=15):
        try:
            status, body = next(iterator)
        except StopIteration:
            raise AssertionError("urlopen called more times than expected")

        if status < 400:
            # If body is a dict, serialize to JSON. If it's a string, use as-is
            # (to simulate non-JSON responses like HTML captcha pages).
            if isinstance(body, dict):
                return MockResponse(body, status)
            else:
                return MockResponse(body, status)
        else:
            body_str = json.dumps(body) if isinstance(body, dict) else str(body)
            raise _make_http_error(status, body_str)

    return _mock


@pytest.fixture(scope="session")
def mcp_tools():
    """Load MCP server tools once per test session."""
    import asyncio

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

    async def _load():
        from moltkit_mcp.server import mcp
        return await mcp.list_tools()

    return asyncio.run(_load())
