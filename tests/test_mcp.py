"""Tests for the moltkit MCP server (tool registration + schemas)."""
from __future__ import annotations

import pytest


class TestMcpTools:
    """Test MCP tool registration (sync API — no network calls)."""

    def test_all_tools_registered(self, mcp_tools):
        """All expected tools are present with no duplicates."""
        names = [t.name for t in mcp_tools]
        assert len(names) == len(set(names)), f"Duplicate tools: {names}"
        assert len(names) == 22, f"Expected 22 tools, got {len(names)}"

    def test_core_tools_present(self, mcp_tools):
        """Core read tools are registered."""
        names = {t.name for t in mcp_tools}
        core = {"home", "notifications", "feed", "my_profile", "check", "status"}
        missing = core - names
        assert not missing, f"Missing core tools: {missing}"

    def test_write_tools_present(self, mcp_tools):
        """All state-changing tools are registered."""
        names = {t.name for t in mcp_tools}
        write_tools = {
            "create_post", "delete_post", "create_comment",
            "upvote", "downvote", "upvote_comment",
            "follow", "unfollow",
            "mark_read", "mark_all_read",
        }
        missing = write_tools - names
        assert not missing, f"Missing write tools: {missing}"

    def test_search_tools_present(self, mcp_tools):
        names = {t.name for t in mcp_tools}
        assert "search" in names
        assert "list_submolts" in names
        assert "view_agent" in names

    def test_verify_tool_registered(self, mcp_tools):
        """The verify tool is registered with correct params."""
        verify = None
        for t in mcp_tools:
            if t.name == "verify":
                verify = t
                break
        assert verify is not None, "verify tool not found"

        props = verify.inputSchema.get("properties", {})
        assert "verification_id" in props
        assert "answer" in props

    def test_verify_tool_description(self, mcp_tools):
        """verify tool has a meaningful description."""
        for t in mcp_tools:
            if t.name == "verify":
                assert t.description
                assert "captcha" in t.description.lower() or "challenge" in t.description.lower()
                break

    def test_create_post_params(self, mcp_tools):
        """create_post has required params."""
        for t in mcp_tools:
            if t.name == "create_post":
                props = t.inputSchema.get("properties", {})
                assert "submolt_name" in props
                assert "title" in props
                assert "content" in props
                break

    def test_notifications_limit_param(self, mcp_tools):
        """notifications has a limit param with max 100."""
        for t in mcp_tools:
            if t.name == "notifications":
                props = t.inputSchema.get("properties", {})
                assert "limit" in props
                break
