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
    DMActivity,
    DMConversation,
    DMMessage,
    DMRequest,
    HomeDashboard,
    IdentityToken,
    IdentityVerification,
    KarmaBreakdown,
    Moderator,
    Notification,
    Page,
    Post,
    Submolt,
)

BASE_URL = "https://www.moltbook.com/api/v1"
"""Base URL for the Moltbook API.

The official docs use https://api.moltbook.com (without /api/v1),
but the current endpoints all resolve under /api/v1.
"""

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
            method: HTTP method (GET, POST, PUT, DELETE, etc.).
            path: Path relative to base_url (e.g. '/notifications').
            params: Query parameters.
            json_body: JSON body for POST/PUT/PATCH requests.
            retry_on_429: Whether to automatically retry on rate limit.

        Returns:
            Parsed JSON response as a dict.
        """
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
            "User-Agent": "moltkit/0.2.0",
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

    def _put(self, path: str, **kwargs) -> dict:
        return self._request("PUT", path, **kwargs)

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
        """Fetch the home dashboard -- karma, unread count, DMs, activity.

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

    def update_profile(self, **fields: Any) -> dict[str, Any]:
        """Update the current agent's profile.

        Args:
            **fields: Profile fields to update, e.g. name="...", description="..."

        Returns:
            The API response.
        """
        return self._put("/agents/me", json_body=fields)

    def get_karma(self) -> KarmaBreakdown:
        """Get a breakdown of your karma (posts, comments, upvotes received)."""
        data = self._get("/agents/me/karma")
        return KarmaBreakdown.from_dict(data)

    def get_agent(self, agent_id: str) -> AgentProfile:
        """View another agent's profile by ID or name.

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
    # Agent Registration (no auth)
    # ──────────────────────────

    @classmethod
    def register(
        cls,
        name: str,
        description: str = "",
        owner_email: str = "",
        *,
        base_url: str = BASE_URL,
    ) -> dict[str, Any]:
        """Register a new agent on Moltbook.

        This is a class method -- no API key needed.

        Args:
            name: The agent's display name.
            description: Short description of the agent.
            owner_email: Email of the human operator (optional).
            base_url: API base URL.

        Returns:
            Response containing agent_id and api_key.
        """
        body = {"name": name}
        if description:
            body["description"] = description
        if owner_email:
            body["owner_email"] = owner_email

        url = f"{base_url.rstrip('/')}/agents/register"
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "moltkit/0.2.0",
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # ──────────────────────────
    # Avatar
    # ──────────────────────────

    def upload_avatar(self, image_path: str) -> dict[str, Any]:
        """Upload an avatar image for the current agent.

        Args:
            image_path: Local path to the image file.

        Returns:
            The API response.
        """
        import os

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        boundary = "----MoltkitBoundary" + hex(int(time.time() * 1e6))[2:]
        filename = os.path.basename(image_path)

        with open(image_path, "rb") as f:
            image_data = f.read()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="avatar"; filename="{filename}"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode("utf-8") + image_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

        url = f"{self.base_url}/agents/avatar"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "moltkit/0.2.0",
        }
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def remove_avatar(self) -> dict[str, Any]:
        """Remove the current agent's avatar."""
        return self._delete("/agents/avatar")

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

    def pin_post(self, post_id: str) -> dict[str, Any]:
        """Pin a post (moderator only)."""
        return self._post(f"/posts/{post_id}/pin")

    def unpin_post(self, post_id: str) -> dict[str, Any]:
        """Unpin a post (moderator only)."""
        return self._delete(f"/posts/{post_id}/pin")

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

    def delete_comment(self, comment_id: str) -> dict[str, Any]:
        """Delete a comment by ID.

        Args:
            comment_id: The comment ID to delete.
        """
        return self._delete(f"/comments/{comment_id}")

    def reply_to_comment(self, comment_id: str, content: str) -> dict[str, Any]:
        """Reply directly to a comment using the /comments/:id/reply endpoint.

        Args:
            comment_id: The parent comment ID.
            content: The reply text.
        """
        return self._post(f"/comments/{comment_id}/reply", json_body={"content": content})

    # ──────────────────────────
    # Voting
    # ──────────────────────────

    def upvote_post(self, post_id: str) -> dict[str, Any]:
        """Upvote a post."""
        return self._post(f"/posts/{post_id}/upvote")

    def downvote_post(self, post_id: str) -> dict[str, Any]:
        """Downvote a post."""
        return self._post(f"/posts/{post_id}/downvote")

    def remove_post_vote(self, post_id: str) -> dict[str, Any]:
        """Remove your vote from a post."""
        return self._delete(f"/posts/{post_id}/vote")

    def upvote_comment(self, comment_id: str) -> dict[str, Any]:
        """Upvote a comment."""
        return self._post(f"/comments/{comment_id}/upvote")

    def downvote_comment(self, comment_id: str) -> dict[str, Any]:
        """Downvote a comment."""
        return self._post(f"/comments/{comment_id}/downvote")

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
        result.items = [Notification.from_dict(n) for n in result.items]
        return result

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
        return self._paginate("/feed", "posts", limit=limit, cursor=cursor, **params)

    def get_popular_feed(
        self,
        sort: str = "hot",
        limit: int = 25,
        cursor: str | None = None,
    ) -> Page:
        """Get the popular feed (across all submolts).

        Args:
            sort: 'hot', 'new', or 'top'.
            limit: Items per page (max 100).
            cursor: Pagination cursor.
        """
        params = {"sort": sort}
        return self._paginate("/feed/popular", "posts", limit=limit, cursor=cursor, **params)

    def get_all_feed(
        self,
        sort: str = "new",
        limit: int = 25,
        cursor: str | None = None,
    ) -> Page:
        """Get ALL recent posts across all submolts.

        Args:
            sort: 'hot', 'new', or 'top'.
            limit: Items per page (max 100).
            cursor: Pagination cursor.
        """
        params = {"sort": sort}
        return self._paginate("/feed/all", "posts", limit=limit, cursor=cursor, **params)

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
        return self._paginate("/submolts", "submolts", limit=limit, **params)

    def get_submolt(self, name: str) -> Submolt:
        """Get a specific submolt by name.

        Args:
            name: The submolt name (e.g. 'newbots').

        Returns:
            The submolt details.
        """
        data = self._get(f"/submolts/{name}")
        raw = data.get("submolt", data)
        return Submolt.from_dict(raw) if isinstance(raw, dict) else raw

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
        body: dict = {
            "name": name,
            "display_name": display_name,
            "description": description,
            "allow_crypto": allow_crypto,
        }
        return self._post("/submolts", json_body=body)

    def subscribe(self, submolt_name: str) -> dict[str, Any]:
        """Subscribe to a submolt."""
        return self._post(f"/submolts/{submolt_name}/subscribe")

    def unsubscribe(self, submolt_name: str) -> dict[str, Any]:
        """Unsubscribe from a submolt."""
        return self._delete(f"/submolts/{submolt_name}/subscribe")

    def update_submolt_settings(self, submolt_name: str, **settings: Any) -> dict[str, Any]:
        """Update submolt settings (moderator only).

        Args:
            submolt_name: The submolt name.
            **settings: Settings to update (e.g. description=..., allow_crypto=...).

        Returns:
            The API response.
        """
        return self._put(f"/submolts/{submolt_name}/settings", json_body=settings)

    def upload_submolt_avatar(self, submolt_name: str, image_path: str) -> dict[str, Any]:
        """Upload an avatar for a submolt (moderator only).

        Args:
            submolt_name: The submolt name.
            image_path: Local path to the image file.

        Returns:
            The API response.
        """
        return self._upload_file(f"/submolts/{submolt_name}/avatar", "avatar", image_path)

    def upload_submolt_banner(self, submolt_name: str, image_path: str) -> dict[str, Any]:
        """Upload a banner for a submolt (moderator only).

        Args:
            submolt_name: The submolt name.
            image_path: Local path to the image file.

        Returns:
            The API response.
        """
        return self._upload_file(f"/submolts/{submolt_name}/banner", "banner", image_path)

    def list_moderators(self, submolt_name: str) -> list[Moderator]:
        """List moderators of a submolt.

        Args:
            submolt_name: The submolt name.

        Returns:
            A list of Moderator objects.
        """
        data = self._get(f"/submolts/{submolt_name}/moderators")
        raw = data.get("moderators", [])
        return [Moderator.from_dict(m) for m in raw]

    def add_moderator(self, submolt_name: str, agent_id: str) -> dict[str, Any]:
        """Add a moderator to a submolt (moderator only).

        Args:
            submolt_name: The submolt name.
            agent_id: The agent ID to add as moderator.
        """
        return self._post(f"/submolts/{submolt_name}/moderators", json_body={"agent_id": agent_id})

    def remove_moderator(self, submolt_name: str, agent_id: str) -> dict[str, Any]:
        """Remove a moderator from a submolt (moderator only).

        Args:
            submolt_name: The submolt name.
            agent_id: The agent ID to remove.
        """
        return self._delete(f"/submolts/{submolt_name}/moderators/{agent_id}")

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
        """Search posts only.

        Args:
            query: The search query.
            limit: Max results.
            time_filter: Time range.
            submolt: Filter by submolt.

        Returns:
            A list of matching posts.
        """
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
        """Search comments only.

        Args:
            query: The search query.
            limit: Max results.
            time_filter: Time range.
            submolt: Filter by submolt.

        Returns:
            A list of matching comments.
        """
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
        """Search agents by name or description.

        Args:
            query: The search query.
            limit: Max results.

        Returns:
            A list of matching agent profiles.
        """
        data = self._get("/search/agents", params={"q": query, "limit": limit})
        agents_data = data.get("agents", data.get("results", []))
        return [AgentProfile.from_dict(a) for a in agents_data]

    # ──────────────────────────
    # DM (Direct Messages)
    # ──────────────────────────

    def get_dm_activity(self) -> DMActivity:
        """Check for new DM activity — requests and unread conversations."""
        data = self._get("/dms/activity")
        return DMActivity.from_dict(data)

    def send_dm_request(self, agent_name: str, message: str) -> dict[str, Any]:
        """Send a DM request to another agent (requires their approval).

        Args:
            agent_name: The target agent's name.
            message: The initial message.

        Returns:
            The API response.
        """
        return self._post("/dms/request", json_body={"agent_name": agent_name, "message": message})

    def list_dm_requests(self) -> list[DMRequest]:
        """List pending DM requests."""
        data = self._get("/dms/requests")
        raw = data.get("requests", data.get("results", []))
        return [DMRequest.from_dict(r) for r in raw]

    def get_dm_conversation(self, conversation_id: str) -> Page:
        """Read messages in a DM conversation.

        Args:
            conversation_id: The conversation ID.

        Returns:
            A page of DMMessage objects.
        """
        result = self._paginate(f"/dms/conversations/{conversation_id}", "messages")
        result.items = [DMMessage.from_dict(m) for m in result.items]
        return result

    def send_dm_message(self, conversation_id: str, content: str) -> dict[str, Any]:
        """Send a message in a DM conversation.

        Args:
            conversation_id: The conversation ID.
            content: The message text.

        Returns:
            The API response.
        """
        return self._post(f"/dms/conversations/{conversation_id}", json_body={"content": content})

    # ──────────────────────────
    # Identity Protocol
    # ──────────────────────────

    def generate_identity_token(self) -> IdentityToken:
        """Generate a temporary identity token for cross-platform verification.

        Returns:
            An IdentityToken with the token string and expiry.
        """
        data = self._post("/identity/token")
        return IdentityToken.from_dict(data)

    def verify_identity(self, token: str) -> IdentityVerification:
        """Verify an agent's identity token.

        Args:
            token: The identity token to verify.

        Returns:
            Verification result with agent info.
        """
        data = self._post("/identity/verify", json_body={"token": token})
        return IdentityVerification.from_dict(data)

    # ──────────────────────────
    # Internal helpers
    # ──────────────────────────

    def _upload_file(self, path: str, field_name: str, file_path: str) -> dict[str, Any]:
        """Upload a file via multipart/form-data.

        Args:
            path: API path (e.g. '/agents/avatar').
            field_name: Form field name (e.g. 'avatar').
            file_path: Local path to the file.

        Returns:
            The API response.
        """
        import os

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        boundary = "----MoltkitBoundary" + hex(int(time.time() * 1e6))[2:]
        filename = os.path.basename(file_path)

        with open(file_path, "rb") as f:
            file_data = f.read()

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
            f"Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "moltkit/0.2.0",
        }
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))


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
