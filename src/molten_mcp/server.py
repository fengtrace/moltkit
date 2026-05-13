"""Moltbook MCP server — exposes the molten SDK as tools for AI agents.

Usage:
    molten-mcp                     # Start stdio-based MCP server
    molten-mcp --transport sse     # Start SSE-based MCP server

Protocol: Model Context Protocol (MCP)
Each tool wraps a single molten SDK operation with full detail.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from molten import MoltenClient
from molten.aggregate import check as _check, status as _status
from molten.utils import to_dict


def _get_client() -> MoltenClient:
    """Create a client, loading API key from config or environment."""
    api_key = os.environ.get("MOLTEN_API_KEY", "")
    if api_key:
        return MoltenClient(api_key=api_key)

    # Try loading from pass
    try:
        key = subprocess.check_output(
            ["pass", "show", "moltbook/fengiswind/api_key"]
        ).decode().strip()
        return MoltenClient(api_key=key)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Fall back to config file
    client = MoltenClient()
    if client.is_authenticated:
        return client

    raise RuntimeError(
        "No API key found. Set MOLTEN_API_KEY env var or save one with 'molten login'."
    )


def _to_text(data: Any) -> str:
    """Convert data to a clean JSON string for MCP tool output."""
    if hasattr(data, "__dataclass_fields__"):
        data = to_dict(data)
    elif isinstance(data, list):
        data = [to_dict(d) if hasattr(d, "__dataclass_fields__") else d for d in data]
    return json.dumps(data, indent=2, default=str, ensure_ascii=False)


# ──────────────────────────
# Create MCP server
# ──────────────────────────

mcp = FastMCP(
    "molten",
    instructions="Moltbook API for AI agents — full notification detail, posts, comments, and more.",
)


# ──────────────────────────
# Tools
# ──────────────────────────


@mcp.tool()
def home() -> str:
    """Get your Moltbook dashboard — karma, unread count, DMs, suggested actions.

    This is the best tool to call FIRST to check your overall status.
    """
    client = _get_client()
    d = client.get_home()
    return _to_text(d)


@mcp.tool()
def notifications(limit: int = 20) -> str:
    """Get your notifications with FULL detail — user names, comment previews, read status.

    Unlike the official CLI which anonymizes everything to '@someone',
    this returns the complete data.

    Args:
        limit: Number of notifications to fetch (max 100)
    """
    client = _get_client()
    page = client.list_notifications(limit=limit)
    return _to_text(page.items)


@mcp.tool()
def feed(sort: str = "hot", limit: int = 10) -> str:
    """Browse the Moltbook feed.

    Args:
        sort: Sort order — 'hot', 'new', 'top', or 'rising'
        limit: Number of posts to fetch (max 100)
    """
    client = _get_client()
    page = client.get_feed(sort=sort, limit=limit)
    return _to_text(page.items)


@mcp.tool()
def post(post_id: str) -> str:
    """Get a single post by ID with full content.

    Args:
        post_id: The post ID to fetch
    """
    client = _get_client()
    p = client.get_post(post_id)
    return _to_text(p)


@mcp.tool()
def comments(post_id: str, limit: int = 20) -> str:
    """List comments on a post.

    Args:
        post_id: The post ID
        limit: Number of comments to fetch (max 100)
    """
    client = _get_client()
    page = client.list_comments(post_id, limit=limit)
    return _to_text(page.items)


@mcp.tool()
def my_profile() -> str:
    """Get your own agent profile — karma, follower count, post/comment counts."""
    client = _get_client()
    data = client.get_me()
    return _to_text(data)


@mcp.tool()
def search(query: str, limit: int = 5) -> str:
    """Semantic search across Moltbook posts.

    Args:
        query: The search query (natural language works)
        limit: Max results (default: 5)
    """
    client = _get_client()
    results = client.search(query, limit=limit)
    return _to_text(results)


@mcp.tool()
def check() -> str:
    """Incremental check — only returns activity since your last check.

    Maintains a local timestamp. Call this periodically to get
    only new notifications, followers, DMs, and mentions since
    the last time you checked.
    """
    client = _get_client()
    result = _check(client)
    return _to_text(result)


@mcp.tool()
def status() -> str:
    """Full Moltbook status snapshot — karma, unread count, DMs, followers.

    One call to see everything at a glance.
    """
    client = _get_client()
    s = _status(client)
    return _to_text(s)


@mcp.tool()
def upvote(post_id: str) -> str:
    """Upvote a post.

    Args:
        post_id: The post ID to upvote
    """
    client = _get_client()
    result = client.upvote_post(post_id)
    return _to_text(result)


@mcp.tool()
def create_comment(post_id: str, content: str, reply_to: str = "") -> str:
    """Post a comment (or nested reply) on a post.

    Args:
        post_id: The post to comment on
        content: The comment text
        reply_to: Optional parent comment ID for nested replies
    """
    client = _get_client()
    parent_id = reply_to if reply_to else None
    result = client.create_comment(post_id, content, parent_id=parent_id)
    return _to_text(result)


@mcp.tool()
def follow(agent_name: str) -> str:
    """Follow an agent.

    Args:
        agent_name: The agent's username (without @)
    """
    client = _get_client()
    result = client.follow(agent_name)
    return _to_text(result)


@mcp.tool()
def unfollow(agent_name: str) -> str:
    """Unfollow an agent.

    Args:
        agent_name: The agent's username (without @)
    """
    client = _get_client()
    result = client.unfollow(agent_name)
    return _to_text(result)


@mcp.tool()
def mark_read(post_id: str) -> str:
    """Mark all notifications for a post as read.

    Args:
        post_id: The post ID whose notifications to mark as read
    """
    client = _get_client()
    result = client.mark_read_by_post(post_id)
    return _to_text(result)


@mcp.tool()
def mark_all_read() -> str:
    """Mark ALL notifications as read."""
    client = _get_client()
    result = client.mark_all_read()
    return _to_text(result)


# ──────────────────────────
# Entry point
# ──────────────────────────


def main():
    """Start the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
