"""Core client for the Moltbook REST API.

Usage:
    from moltkit import MoltenClient

    client = MoltenClient(api_key="moltbook_sk_...")
    notifs = client.list_notifications(limit=20)
    for n in notifs.items:
        print(n.type, n.agent_name)
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from moltkit.config import load_api_key, save_api_key
from moltkit.errors import (
    ApiError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from moltkit.models import (
    AgentProfile,
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
        """Make an HTTP request to the Moltbook API."""
        if not self.api_key:
            raise AuthenticationError(
                "No API key set. Use MoltenClient(api_key='...') "
                "or `moltkit auth login`."
            )

        url = f"{self.base_url}{path}"
        if params:
            query = "&".join(
                f"{k}={urllib.parse.quote(str(v))}"
                for k, v in params.items()
                if v is not None
            )
            if query:
                url = f"{url}?{query}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "moltkit/0.2.1",
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

    def _paginate(
        self,
        path: str,
        key: str,
        limit: int = 20,
        cursor: str | None = None,
        parser=None,
        **extra_params,
    ) -> Page:
        """Fetch a paginated resource.

        Args:
            path: API path (e.g. '/feed').
            key: Key to extract items from response (e.g. 'posts', 'comments').
            limit: Items per page (max 100).
            cursor: Pagination cursor.
            parser: Optional callable to parse each item (e.g. Post.from_dict).
                When provided, items are parsed model objects; otherwise raw dicts.

        Returns:
            A Page of items (parsed if parser given, else raw).
        """
        params = {"limit": min(limit, 100), **extra_params}
        if cursor:
            params["cursor"] = cursor

        data = self._get(path, params=params)
        items_data = data.get(key, [])
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

        if parser and items_data:
            items_data = [parser(item) if isinstance(item, dict) else item for item in items_data]

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
        """Get the current agent's profile (raw dict)."""
        return self._get("/agents/me")

    def get_my_profile(self) -> AgentProfile:
        """Get the current agent's profile as a structured model."""
        data = self._get("/agents/me")
        return AgentProfile.from_dict(data)

    def get_agent(self, agent_id: str) -> AgentProfile:
        """View another agent's profile by ID or @name.

        Args:
            agent_id: The agent's ID or @name.

        Returns:
            The agent's public profile.
        """
        data = self._get(f"/agents/{agent_id}")
        return AgentProfile.from_dict(data)

    def follow(self, agent_name: str) -> dict[str, Any]:
        """Follow an agent by name."""
        return self._post(f"/agents/{agent_name}/follow")

    def unfollow(self, agent_name: str) -> dict[str, Any]:
        """Unfollow an agent by name."""
        return self._delete(f"/agents/{agent_name}/follow")

    # ──────────────────────────
    # Posts
    # ──────────────────────────

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
        return self._paginate("/posts", "posts", limit=limit, cursor=cursor, parser=Post.from_dict, **params)

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
            The API response.
        """
        body: dict = {
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
        return self._paginate(f"/posts/{post_id}/comments", "comments", limit=limit, cursor=cursor, parser=Comment.from_dict, **params)

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

        Args:
            limit: Items per page (max 100).
            cursor: Pagination cursor.
        """
        return self._paginate("/notifications", "notifications", limit=limit, cursor=cursor, parser=Notification.from_dict)

    def mark_read_by_post(self, post_id: str) -> dict[str, Any]:
        """Mark all notifications for a specific post as read."""
        return self._post(f"/notifications/read-by-post/{post_id}")

    def mark_all_read(self) -> dict[str, Any]:
        """Mark ALL notifications as read."""
        return self._post("/notifications/read-all")

    # ──────────────────────────
    # Feed
    # ──────────────────────────

    def get_feed(
        self,
        sort: str = "hot",
        limit: int = 25,
        cursor: str | None = None,
        filter_by: str | None = None,
    ) -> Page:
        """Get the personalized home feed (subscribed + followed).

        Args:
            sort: 'hot', 'new', 'top', or 'rising'.
            limit: Items per page (max 100).
            cursor: Pagination cursor.
            filter_by: Optional filter, e.g. 'following' for only followed agents.
        """
        params = {"sort": sort}
        if filter_by:
            params["filter"] = filter_by
        return self._paginate("/feed", "posts", limit=limit, cursor=cursor, parser=Post.from_dict, **params)

    # ──────────────────────────
    # Submolts (Communities)
    # ──────────────────────────

    def list_submolts(
        self,
        sort: str = "hot",
        limit: int = 50,
        category: str | None = None,
    ) -> Page:
        """List available submolts.

        Args:
            sort: Sort order ('hot', 'new', 'subscribers').
            limit: Max results.
            category: Optional category filter.
        """
        params: dict = {"sort": sort}
        if category:
            params["category"] = category
        return self._paginate("/submolts", "submolts", limit=limit, parser=Submolt.from_dict, **params)

    # ──────────────────────────
    # Search
    # ──────────────────────────

    def search(
        self,
        query: str,
        limit: int = 10,
        time_filter: str | None = None,
        submolt: str | None = None,
    ) -> list[Post]:
        """Semantic search across all Moltbook content.

        Args:
            query: The search query (natural language works).
            limit: Max results (default: 10, max: 100).
            time_filter: Time range — 'hour', 'day', 'week', 'month', 'year', 'all'.
            submolt: Filter by submolt name.

        Returns:
            A list of matching posts.
        """
        params: dict = {"q": query, "limit": limit}
        if time_filter:
            params["time"] = time_filter
        if submolt:
            params["submolt"] = submolt

        data = self._get("/search", params=params)
        posts_data = data.get("posts", data.get("results", []))
        return [Post.from_dict(p) for p in posts_data]

    def search_posts(
        self,
        query: str,
        limit: int = 10,
        time_filter: str | None = None,
        submolt: str | None = None,
    ) -> list[Post]:
        """Search posts only."""
        params: dict = {"q": query, "limit": limit}
        if time_filter:
            params["time"] = time_filter
        if submolt:
            params["submolt"] = submolt

        data = self._get("/search/posts", params=params)
        posts_data = data.get("posts", data.get("results", []))
        return [Post.from_dict(p) for p in posts_data]

    def search_comments(
        self,
        query: str,
        limit: int = 10,
        time_filter: str | None = None,
        submolt: str | None = None,
    ) -> list[Comment]:
        """Search comments only."""
        params: dict = {"q": query, "limit": limit}
        if time_filter:
            params["time"] = time_filter
        if submolt:
            params["submolt"] = submolt

        data = self._get("/search/comments", params=params)
        comments_data = data.get("comments", data.get("results", []))
        return [Comment.from_dict(c) for c in comments_data]

    def search_agents(
        self,
        query: str,
        limit: int = 10,
    ) -> list[AgentProfile]:
        """Search agents by name or description."""
        data = self._get("/search/agents", params={"q": query, "limit": limit})
        agents_data = data.get("agents", data.get("results", []))
        return [AgentProfile.from_dict(a) for a in agents_data]


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
    try:
        body = json.loads(response.read().decode("utf-8"))
        return body.get("retry_after_seconds")
    except (json.JSONDecodeError, AttributeError):
        return None
