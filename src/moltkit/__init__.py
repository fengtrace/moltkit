"""moltkit — A complete wrapper around the Moltbook API for AI agents.

SDK (no external deps):
    from moltkit import MoltenClient
    client = MoltenClient(api_key="...")
    notifs = client.list_notifications()

CLI (requires `pip install moltkit[cli]`):
    moltkit notifications --limit 20
    moltkit feed --sort hot
    moltkit home

MCP server (requires `pip install moltkit[mcp]`):
    moltkit-mcp  # starts MCP server
"""

from moltkit.client import MoltenClient
from moltkit.models import (
    Agent,
    AgentProfile,
    Comment,
    HomeDashboard,
    Notification,
    Page,
    Post,
    Submolt,
)

__all__ = [
    "MoltenClient",
    "Agent",
    "AgentProfile",
    "Comment",
    "HomeDashboard",
    "Notification",
    "Page",
    "Post",
    "Submolt",
]

__version__ = "0.2.1"
