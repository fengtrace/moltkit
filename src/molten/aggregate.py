"""Aggregated/composed operations for Moltbook — the "smart layer" on top of the SDK.

These operations combine multiple API calls, maintain local state (timestamps),
and provide higher-level workflows for agents.

Usage:
    from molten import MoltenClient
    from molten.aggregate import check, status, digest

    client = MoltenClient(api_key="...")
    result = check(client)  # → {"new": [...], "summary": "..."}
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from molten import MoltenClient
from molten.models import Notification

STATE_DIR = Path.home() / ".local" / "state" / "molten"


# ──────────────────────────
# State management
# ──────────────────────────


def _ensure_state_dir() -> Path:
    """Create and return the state directory."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR


def _read_timestamp(name: str = "last-check") -> float | None:
    """Read a timestamp from the state directory.

    Returns:
        Unix timestamp as float, or None if never set.
    """
    path = _ensure_state_dir() / name
    if not path.exists():
        return None
    try:
        return float(path.read_text().strip())
    except (ValueError, OSError):
        return None


def _write_timestamp(name: str = "last-check") -> float:
    """Write the current time as a timestamp.

    Returns:
        The Unix timestamp that was written.
    """
    now = time.time()
    path = _ensure_state_dir() / name
    path.write_text(f"{now}\n")
    return now


def _format_timestamp(ts: float) -> str:
    """Format a Unix timestamp as a human-readable string."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


# ──────────────────────────
# Data types
# ──────────────────────────


@dataclass
class CheckResult:
    """Result of an incremental check."""

    new_notifications: list[Notification] = field(default_factory=list)
    new_followers: list[str] = field(default_factory=list)
    new_dms: int = 0
    new_mentions: list[Notification] = field(default_factory=list)
    last_checked: str = ""
    current_karma: int = 0

    @property
    def has_new(self) -> bool:
        return bool(
            self.new_notifications
            or self.new_followers
            or self.new_dms
            or self.new_mentions
        )

    @property
    def summary(self) -> str:
        parts = []
        unread_notifs = len([n for n in self.new_notifications if not n.is_read])
        if unread_notifs:
            parts.append(f"{unread_notifs} new notification(s)")
        if self.new_followers:
            parts.append(f"{len(self.new_followers)} new follower(s)")
        if self.new_dms:
            parts.append(f"{self.new_dms} DM request(s)")
        if self.new_mentions:
            parts.append(f"{len(self.new_mentions)} mention(s)")
        if not parts:
            return "Nothing new since last check."
        return ", ".join(parts) + "."


@dataclass
class StatusResult:
    """Full snapshot of your Moltbook status."""

    karma: int = 0
    name: str = ""
    unread_notifications: int = 0
    dm_count: int = 0
    follower_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    comments_count: int = 0
    recent_activity: list[dict] = field(default_factory=list)
    what_to_do: list[str] = field(default_factory=list)

    @property
    def summary_line(self) -> str:
        return (
            f"@{self.name} | Karma: {self.karma} | "
            f"Unread: {self.unread_notifications} | DMs: {self.dm_count} | "
            f"Followers: {self.follower_count}"
        )


# ──────────────────────────
# Aggregated operations
# ──────────────────────────


def check(client: MoltenClient) -> CheckResult:
    """Incremental check — only returns what's new since the last check.

    Call this periodically (e.g., every 30 minutes via cron) to get
    only new activity since the last time you checked.

    Maintains a timestamp file at ~/.local/state/molten/last-check.
    """
    last_ts = _read_timestamp("last-check")
    last_checked_str = (
        _format_timestamp(last_ts) if last_ts else "never"
    )

    # Get current state
    home = client.get_home()
    notif_page = client.list_notifications(limit=50)

    # Filter by timestamp (only notifications AFTER last check)
    new_notifications: list[Notification] = []
    new_followers: list[str] = []
    new_mentions: list[Notification] = []

    for n in notif_page.items:
        # Parse notification timestamp
        try:
            notif_ts = _parse_moltbook_timestamp(n.created_at)
        except (ValueError, OSError):
            # Can't parse, include it
            new_notifications.append(n)
            continue

        if last_ts is not None and notif_ts <= last_ts:
            continue  # Older than last check, skip

        new_notifications.append(n)

        if n.type == "new_follower":
            # Content looks like: "nexussim started following you"
            name = n.content.replace(" started following you", "").strip()
            if name:
                new_followers.append(name)

        if n.type == "mention":
            new_mentions.append(n)

    # Count DM requests
    new_dms = len([n for n in new_notifications if n.type == "dm_request"])

    # Update timestamp
    now_ts = _write_timestamp("last-check")

    return CheckResult(
        new_notifications=new_notifications,
        new_followers=new_followers,
        new_dms=new_dms,
        new_mentions=new_mentions,
        last_checked=_format_timestamp(now_ts),
        current_karma=home.karma,
    )


def status(client: MoltenClient) -> StatusResult:
    """Full snapshot of your Moltbook status — one call to rule them all.

    Combines /home + /agents/me into a single structured view.
    """
    home_data = client.get_home()
    me_data = client.get_me()
    agent = me_data.get("agent", me_data)

    return StatusResult(
        karma=home_data.karma,
        name=home_data.name or agent.get("name", ""),
        unread_notifications=home_data.unread_notification_count,
        dm_count=home_data.dm_count,
        follower_count=agent.get("follower_count", 0),
        following_count=agent.get("following_count", 0),
        posts_count=agent.get("posts_count", 0),
        comments_count=agent.get("comments_count", 0),
        recent_activity=home_data.activity,
        what_to_do=home_data.what_to_do_next,
    )


def reset_check_timestamp() -> float:
    """Reset the last-check timestamp to now.

    Useful after you've processed everything and want the next
    ``check()`` to start fresh.
    """
    return _write_timestamp("last-check")


# ──────────────────────────
# Helpers
# ──────────────────────────


def _parse_moltbook_timestamp(ts_str: str) -> float:
    """Parse a Moltbook timestamp string to Unix timestamp.

    Moltbook uses ISO 8601 format: '2026-05-13T01:50:07.588Z'
    """
    if not ts_str:
        return 0
    # Handle 'Z' suffix
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(ts_str)
    return dt.timestamp()
