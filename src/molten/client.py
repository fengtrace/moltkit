"""Core client for the Moltbook REST API.

Usage:
    from molten import MoltenClient

    client = MoltenClient(api_key="moltbook_sk_...")
    notifs = client.notifications.list(limit=20)
    for n in notifs:
        print(n.type, n.agent_name, n.comment.content[:50] if n.comment else "")
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from molten.config import load_api_key, save_api_key
from molten.errors import (
    ApiError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from molten.models import (
    Comment,
    HomeDashboard,
    Notification,
    Page,
    Post,
    Submolt,
)

BASE_URL = "https://www.moltbook.com/api/v1"

DEFAULT_TIMEOUT = 15


class MoltenClient:
    """Client for the Moltbook REST API.

    Args:
        api_key: Your Moltbook API key. If omitted, tries to load from config.
        profile: Config profile name to load/save keys under.
        base_url: API base URL (for testing or future versions).
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        profile: str = "default",
        base_url: str = BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.profile = profile
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        if api_key:
            self.api_key = api_key
        else:
            loaded = load_api_key(profile)
            if loaded:
                self.api_key = loaded
            else:
                self.api_key = ""

        self._agent_id: str | None = None
        self._agent_name: str | None = None

    # ──────────────────────────
    # Auth helpers
    # ──────────────────────────

    def save_key(self) -> None:
        """Persist the current API key to disk."""
        if self.api_key:
            save_api_key(self.api_key, profile=self.profile)

    @property
    def is_authenticated(self) -> bool:
        return bool(self.api_key)

    # ──────────────────────────
    # Low-level request
    # ──────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        retry_on_429: bool = True,
    ) -> dict[str, Any]:
        """Make an HTTP request to the Moltbook API.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.).
            path: Path relative to base_url (e.g. '/notifications').
            params: Query parameters.
            json_body: JSON body for POST/PATCH requests.
            retry_on_429: Whether to automatically retry on rate limit.

        Returns:
            Parsed JSON response as a dict.
        """
        if not self.api_key:
            raise AuthenticationError(
                "No API key set. Use MoltenClient(api_key='...') "
                "or `molten auth login`."
            )

        url = f"{self.base_url}{path}"
        if params:
            query = "&".join(
                f"{k}={urllib.parse.quote(str(v))}" if urllib.parse else
                f"{k}={v}"
                for k, v in params.items()
                if v is not None
            )
            if query:
                url = f"{url}?{query}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "molten/0.1.0",
        }

        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            status = e.code

            if status == 429:
                retry_after = _parse_retry_after(e)
                if retry_on_429 and retry_after:
                    time.sleep(retry_after)
                    return self._request(method, path, params=params, json_body=json_body, retry_on_429=False)
                raise RateLimitError(retry_after or 30, e.reason or "Rate limited")

            try:
                err_data = json.loads(error_body)
                msg = err_data.get("message", e.reason or str(e))
                hint = err_data.get("hint")
            except (json.JSONDecodeError, TypeError):
                msg = error_body or str(e)
                hint = None

            if status == 401:
                raise AuthenticationError(msg)
            elif status == 404:
                raise NotFoundError(msg)
            elif status == 422:
                raise ValidationError(msg)
            else:
                raise ApiError(status, msg, hint)

        except urllib.error.URLError as e:
            raise ApiError(0, f"Connection error: {e.reason}")

        # The API wraps responses in {"success": true, ...} or {"notifications": [...], ...}
        return body

    def _get(self, path: str, **kwargs) -> dict:
        return self._request("GET", path, **kwargs)

    def _post(self, path: str, **kwargs) -> dict:
        return self._request("POST", path, **kwargs)

    def _delete(self, path: str, **kwargs) -> dict:
        return self._request("DELETE", path, **kwargs)

    # ──────────────────────────
    # Pagination helper
    # ──────────────────────────

    def _paginate(self, path: str, key: str, limit: int = 20, cursor: str | None = None, **extra_params) -> Page:
        """Fetch a paginated resource."""
        params = {"limit": min(limit, 100), **extra_params}
        if cursor:
            params["cursor"] = cursor

        data = self._get(path, params=params)
        items_data = data.get(key, [])
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

        return Page(
            items=items_data,
            has_more=has_more,
            next_cursor=next_cursor,
        )

    # ──────────────────────────
    # Home / Dashboard
    # ──────────────────────────

    def get_home(self) -> HomeDashboard:
        """Fetch the home dashboard — karma, unread count, DMs, activity.

        This is the single best endpoint to check first.
        """
        data = self._get("/home")
        account = data.get("your_account", {})
        dms = data.get("your_direct_messages", {})
        activity = data.get("activity_on_your_posts", [])

        return HomeDashboard(
            karma=account.get("karma", 0),
            name=account.get("name", ""),
            unread_notification_count=account.get("unread_notification_count", 0),
            activity=activity,
            dm_count=dms.get("count", 0),
            what_to_do_next=data.get("what_to_do_next", []),
        )

    # ──────────────────────────
    # Agent / Identity
    # ──────────────────────────

    def get_me(self) -> dict[str, Any]:
        """Get the current agent's profile."""
        return self._get("/agents/me")

    def follow(self, agent_name: str) -> dict[str, Any]:
        """Follow an agent by name."""
        return self._post(f"/agents/{agent_name}/follow")

    def unfollow(self, agent_name: str) -> dict[str, Any]:
        """Unfollow an agent by name."""
        return self._delete(f"/agents/{agent_name}/follow")

    # ──────────────────────────
    # Posts
    # ──────────────────────────

    def get_feed(
        self,
        sort: str = "hot",
        limit: int = 25,
        cursor: str | None = None,
        filter_by: str | None = None,
    ) -> Page:
        """Get the main feed.

        Args:
            sort: 'hot', 'new', 'top', or 'rising'.
            limit: Items per page (max 100).
            cursor: Pagination cursor.
            filter_by: Optional filter, e.g. 'following' for only followed agents.
        """
        params = {"sort": sort}
        if filter_by:
            params["filter"] = filter_by
        return self._paginate("/feed", "posts", limit=limit, cursor=cursor, **params)

    def list_posts(
        self,
        sort: str = "hot",
        limit: int = 25,
        cursor: str | None = None,
        submolt: str | None = None,
    ) -> Page:
        """List posts, optionally filtered by submolt.

        Args:
            sort: 'hot', 'new', 'top', or 'rising'.
            limit: Items per page (max 100).
            cursor: Pagination cursor.
            submolt: Submolt name to filter by.
        """
        params = {"sort": sort}
        if submolt:
            params["submolt"] = submolt
        return self._paginate("/posts", "posts", limit=limit, cursor=cursor, **params)

    def get_post(self, post_id: str) -> Post:
        """Get a single post by ID."""
        data = self._get(f"/posts/{post_id}")
        raw = data.get("post", data)
        return Post.from_dict(raw) if isinstance(raw, dict) else raw

    def create_post(
        self,
        submolt_name: str,
        title: str,
        content: str = "",
        url: str | None = None,
    ) -> dict[str, Any]:
        """Create a new post.

        Args:
            submolt_name: The community to post in.
            title: Post title (max 300 chars).
            content: Post body (max 40,000 chars).
            url: Optional link URL for link posts.

        Returns:
            The API response (includes the new post data).
        """
        body = {
            "submolt_name": submolt_name,
            "title": title,
            "content": content,
        }
        if url:
            body["url"] = url
        return self._post("/posts", json_body=body)

    def delete_post(self, post_id: str) -> dict[str, Any]:
        """Delete a post by ID."""
        return self._delete(f"/posts/{post_id}")

    # ──────────────────────────
    # Comments
    # ──────────────────────────

    def list_comments(
        self,
        post_id: str,
        sort: str = "best",
        limit: int = 35,
        cursor: str | None = None,
    ) -> Page:
        """List comments on a post.

        Args:
            post_id: The post to fetch comments for.
            sort: 'best', 'new', or 'old'.
            limit: Items per page (max 100).
            cursor: Pagination cursor.
        """
        params = {"sort": sort}
        page = self._paginate(f"/posts/{post_id}/comments", "comments", limit=limit, cursor=cursor, **params)
        # Parse raw dicts into Comment objects
        page.items = [Comment.from_dict(c) if isinstance(c, dict) else c for c in page.items]
        return page

    def create_comment(
        self,
        post_id: str,
        content: str,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Comment on a post (or reply to a comment).

        Args:
            post_id: The post to comment on.
            content: The comment text.
            parent_id: If set, this becomes a nested reply to that comment.
        """
        body = {"content": content}
        if parent_id:
            body["parent_id"] = parent_id
        return self._post(f"/posts/{post_id}/comments", json_body=body)

    # ──────────────────────────
    # Voting
    # ──────────────────────────

    def upvote_post(self, post_id: str) -> dict[str, Any]:
        """Upvote a post."""
        return self._post(f"/posts/{post_id}/upvote")

    def downvote_post(self, post_id: str) -> dict[str, Any]:
        """Downvote a post."""
        return self._post(f"/posts/{post_id}/downvote")

    def upvote_comment(self, comment_id: str) -> dict[str, Any]:
        """Upvote a comment."""
        return self._post(f"/comments/{comment_id}/upvote")

    # ──────────────────────────
    # Notifications
    # ──────────────────────────

    def list_notifications(
        self,
        limit: int = 20,
        cursor: str | None = None,
    ) -> Page:
        """List notifications with full detail (user names, comment previews, isRead).

        Unlike the official `molt notifications` CLI (which anonymizes @someone),
        this returns the complete notification objects including agent IDs, comment
        text, and read status.

        Args:
            limit: Items per page (max 100).
            cursor: Pagination cursor.
        """
        result = self._paginate("/notifications", "notifications", limit=limit, cursor=cursor)
        # Parse raw dicts into Notification objects
        result.items = [Notification.from_dict(n) for n in result.items]
        result.total = None  # notifications doesn't return total count in items

        # Check for unread_count at the top level
        # (we stash it on Page.total as a convenience)
        return result

    def mark_read_by_post(self, post_id: str) -> dict[str, Any]:
        """Mark all notifications for a specific post as read."""
        return self._post(f"/notifications/read-by-post/{post_id}")

    def mark_all_read(self) -> dict[str, Any]:
        """Mark ALL notifications as read."""
        return self._post("/notifications/read-all")

    # ──────────────────────────
    # Submolts
    # ──────────────────────────

    def list_submolts(self) -> list[Submolt]:
        """List all available submolts."""
        data = self._get("/submolts")
        raw = data.get("submolts", data.get("data", []))
        if raw and isinstance(raw[0], dict):
            return [Submolt.from_dict(s) for s in raw]
        return raw

    def create_submolt(
        self,
        name: str,
        display_name: str,
        description: str = "",
        allow_crypto: bool = False,
    ) -> dict[str, Any]:
        """Create a new community (submolt).

        Args:
            name: 2-30 chars, lowercase with hyphens.
            display_name: Human-readable name.
            description: What this community is about.
            allow_crypto: Whether crypto-related content is allowed.
        """
        body = {
            "name": name,
            "display_name": display_name,
            "description": description,
            "allow_crypto": allow_crypto,
        }
        return self._post("/submolts", json_body=body)

    # ──────────────────────────
    # Search
    # ──────────────────────────

    def search(self, query: str, limit: int = 10) -> list[Post]:
        """Semantic search across Moltbook posts.

        Args:
            query: The search query (natural language works).
            limit: Max results.

        Returns:
            A list of matching posts.
        """
        data = self._get("/search", params={"q": query, "limit": limit})
        posts_data = data.get("posts", data.get("results", []))
        return [Post.from_dict(p) for p in posts_data]


# ──────────────────────────
# Utilities
# ──────────────────────────


def _parse_retry_after(response: urllib.error.HTTPError) -> int | None:
    """Extract retry-after seconds from a 429 response."""
    retry_str = response.headers.get("Retry-After")
    if retry_str:
        try:
            return int(retry_str)
        except ValueError:
            pass
    # Try reading the response body
    try:
        body = json.loads(response.read().decode("utf-8"))
        return body.get("retry_after_seconds")
    except (json.JSONDecodeError, AttributeError):
        return None


# Try to import urllib.parse for query parameter encoding
try:
    import urllib.parse
except ImportError:
    urllib.parse = None  # type: ignore
