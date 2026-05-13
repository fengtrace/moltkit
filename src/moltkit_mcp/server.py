"""Moltbook MCP server — exposes the moltkit SDK as tools for AI agents.

Usage:
    moltkit-mcp                     # Start stdio-based MCP server
    moltkit-mcp --transport sse     # Start SSE-based MCP server
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from moltkit import MoltenClient
from moltkit.aggregate import check as _check, status as _status
from moltkit.utils import to_dict


def _get_client() -> MoltenClient:
    """Create a client, loading API key from config or environment."""
    api_key = os.environ.get("MOLTKIT_API_KEY", "")
    if api_key:
        return MoltenClient(api_key=api_key)

    try:
        key = subprocess.check_output(
            ["pass", "show", "moltbook/fengiswind/api_key"]
        ).decode().strip()
        return MoltenClient(api_key=key)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    client = MoltenClient()
    if client.is_authenticated:
        return client

    raise RuntimeError(
        "No API key found. Set MOLTKIT_API_KEY env var or save one with 'moltkit login'."
    )


def _to_text(data: Any) -> str:
    """Convert data to a clean JSON string for MCP tool output."""
    if hasattr(data, "__dataclass_fields__"):
        data = to_dict(data)
    elif isinstance(data, list):
        data = [to_dict(d) if hasattr(d, "__dataclass_fields__") else d for d in data]
    return json.dumps(data, indent=2, default=str, ensure_ascii=False)


mcp = FastMCP(
    "moltkit",
    instructions="Moltbook API tools for AI agents — full notification detail, posts, comments, search, and more.",
)


# ──────────────────────────
# Tools
# ──────────────────────────


@mcp.tool()
def home() -> str:
    """Get your Moltbook dashboard — karma, unread count, DMs, suggested actions.
    Call this FIRST to check your overall status.
    """
    client = _get_client()
    d = client.get_home()
    return _to_text(d)


@mcp.tool()
def my_profile() -> str:
    """Get your structured agent profile — karma, follower count, post/comment counts."""
    client = _get_client()
    p = client.get_my_profile()
    return _to_text(p)


@mcp.tool()
def view_agent(agent_id: str) -> str:
    """View another agent's profile.

    Args:
        agent_id: The agent's ID or @name
    """
    client = _get_client()
    a = client.get_agent(agent_id)
    return _to_text(a)


@mcp.tool()
def notifications(limit: int = 20) -> str:
    """Get your notifications with FULL detail — user names, comment previews, read status.

    Args:
        limit: Number of notifications to fetch (max 100)
    """
    client = _get_client()
    page = client.list_notifications(limit=limit)
    return _to_text(page.items)


@mcp.tool()
def feed(sort: str = "hot", limit: int = 10) -> str:
    """Browse the Moltbook home feed.

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
def create_post(submolt_name: str, title: str, content: str = "") -> str:
    """Create a new post in a community.

    Args:
        submolt_name: The community name (e.g. 'newbots')
        title: Post title (max 300 chars)
        content: Post body text
    """
    client = _get_client()
    result = client.create_post(submolt_name=submolt_name, title=title, content=content)
    return _to_text(result)


@mcp.tool()
def delete_post(post_id: str) -> str:
    """Delete a post.

    Args:
        post_id: The post ID to delete
    """
    client = _get_client()
    result = client.delete_post(post_id)
    return _to_text(result)


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
def upvote(post_id: str) -> str:
    """Upvote a post.

    Args:
        post_id: The post ID to upvote
    """
    client = _get_client()
    result = client.upvote_post(post_id)
    return _to_text(result)


@mcp.tool()
def downvote(post_id: str) -> str:
    """Downvote a post.

    Args:
        post_id: The post ID to downvote
    """
    client = _get_client()
    result = client.downvote_post(post_id)
    return _to_text(result)


@mcp.tool()
def upvote_comment(comment_id: str) -> str:
    """Upvote a comment.

    Args:
        comment_id: The comment ID to upvote
    """
    client = _get_client()
    result = client.upvote_comment(comment_id)
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
def search(query: str, limit: int = 5, scope: str = "all") -> str:
    """Semantic search across Moltbook.

    Args:
        query: The search query (natural language works)
        limit: Max results (default: 5)
        scope: Search scope — 'all', 'posts', 'comments', or 'agents'
    """
    client = _get_client()
    if scope == "posts":
        results = client.search_posts(query, limit=limit)
    elif scope == "comments":
        results = client.search_comments(query, limit=limit)
    elif scope == "agents":
        results = client.search_agents(query, limit=limit)
    else:
        results = client.search(query, limit=limit)
    return _to_text(results)


@mcp.tool()
def list_submolts(limit: int = 20) -> str:
    """List available submolts/communities.

    Args:
        limit: Max results
    """
    client = _get_client()
    page = client.list_submolts(limit=limit)
    return _to_text(page.items)


@mcp.tool()
def mark_read(post_id: str) -> str:
    """Mark all notifications for a post as read.

    Args:
        post_id: The post ID
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


@mcp.tool()
def check() -> str:
    """Incremental check — only returns activity since your last check.
    Call this periodically to get only new notifications, followers, etc.
    """
    client = _get_client()
    result = _check(client)
    return _to_text(result)


@mcp.tool()
def status() -> str:
    """Full Moltbook status snapshot — karma, unread count, DMs, followers."""
    client = _get_client()
    s = _status(client)
    return _to_text(s)


# ──────────────────────────
# Entry point
# ──────────────────────────


def main():
    mcp.run()


if __name__ == "__main__":
    main()
