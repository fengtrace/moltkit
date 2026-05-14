"""Tests for the moltkit CLI (using typer.testing.CliRunner)."""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from moltkit_cli.main import app

runner = CliRunner()


class TestCliHelp:
    def test_help_shown_with_dash_dash_help(self):
        """--help prints usage and exits successfully."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.stdout

    def test_home_requires_auth(self):
        """`home` should fail with a friendly message when no API key."""
        result = runner.invoke(app, ["home"])
        # Without API key, it should exit with code 1
        assert result.exit_code == 1
        assert "No API key found" in result.stdout

    def test_commands_listed_in_help(self):
        """--help should list available commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # Essential commands should appear
        assert "home" in result.stdout
        assert "profile" in result.stdout
        assert "feed" in result.stdout
        assert "notifications" in result.stdout
        assert "create-post" in result.stdout
        assert "check" in result.stdout
        assert "status" in result.stdout
        assert "verify" in result.stdout
