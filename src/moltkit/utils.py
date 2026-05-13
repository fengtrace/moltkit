"""Utility helpers for moltkit SDK."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any


def to_dict(obj: Any) -> dict[str, Any]:
    """Convert a dataclass to a plain dict, recursively.

    Handles nested dataclasses, lists, and None values properly.
    """
    if is_dataclass(obj):
        result = {}
        for field_name in obj.__dataclass_fields__:
            value = getattr(obj, field_name)
            result[field_name] = _convert(value)
        return result
    return obj


def _convert(value: Any) -> Any:
    """Recursively convert values for JSON serialization."""
    if is_dataclass(value):
        return to_dict(value)
    elif isinstance(value, list):
        return [_convert(item) for item in value]
    elif isinstance(value, dict):
        return {k: _convert(v) for k, v in value.items()}
    return value
