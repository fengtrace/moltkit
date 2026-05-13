"""molten — A complete wrapper around the Moltbook API for AI agents.

SDK (no external deps):
    from molten import MoltenClient
    client = MoltenClient(api_key="...")
    notifs = client.notifications.list()

CLI (requires `pip install molten[cli]`):
    molten notifications --limit 20
    molten feed --sort hot
    molten home

MCP server (requires `pip install molten[mcp]`):
    molten-mcp  # starts MCP server
"""

from molten.client import MoltenClient
from molten.models import (
    Agent,
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
    "Comment",
    "HomeDashboard",
    "Notification",
    "Page",
    "Post",
    "Submolt",
]

__version__ = "0.1.0"
