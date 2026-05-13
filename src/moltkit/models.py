"""Data models for Moltbook API responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Agent:
    """An agent on Moltbook."""

    id: str
    name: str
    karma: int = 0
    description: str = ""
    is_following: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Agent":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            karma=data.get("karma", 0),
            description=data.get("description", ""),
            is_following=data.get("is_following", False) or data.get("isFollowing", False),
        )


@dataclass
class AgentProfile:
    """Full agent profile from /agents/:id or /agents/me."""

    id: str = ""
    name: str = ""
    description: str = ""
    karma: int = 0
    follower_count: int = 0
    following_count: int = 0
    posts_count: int = 0
    comments_count: int = 0
    status: str = ""
    created_at: str = ""
    is_following: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentProfile":
        agent = data.get("agent", data)
        return cls(
            id=agent.get("id", ""),
            name=agent.get("name", ""),
            description=agent.get("description", ""),
            karma=agent.get("karma", 0),
            follower_count=agent.get("follower_count", 0) or agent.get("followerCount", 0),
            following_count=agent.get("following_count", 0) or agent.get("followingCount", 0),
            posts_count=agent.get("posts_count", 0) or agent.get("postCount", 0) or agent.get("posts", 0),
            comments_count=agent.get("comments_count", 0) or agent.get("commentCount", 0) or agent.get("comments", 0),
            status=agent.get("status", ""),
            created_at=agent.get("created_at", "") or agent.get("createdAt", ""),
            is_following=agent.get("is_following", False) or agent.get("isFollowing", False),
        )


@dataclass
class Submolt:
    """A community on Moltbook."""

    id: str = ""
    name: str = ""
    display_name: str = ""
    description: str = ""
    subscriber_count: int = 0
    is_subscribed: bool = False
    created_at: str = ""
    avatar_url: str = ""
    banner_url: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Submolt":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            display_name=data.get("display_name", "") or data.get("displayName", ""),
            description=data.get("description", ""),
            subscriber_count=data.get("subscriber_count", 0) or data.get("subscriberCount", 0),
            is_subscribed=data.get("is_subscribed", False) or data.get("isSubscribed", False),
            created_at=data.get("created_at", "") or data.get("createdAt", ""),
            avatar_url=data.get("avatar_url", "") or data.get("avatarUrl", ""),
            banner_url=data.get("banner_url", "") or data.get("bannerUrl", ""),
        )


@dataclass
class Post:
    """A post on Moltbook."""

    id: str
    title: str
    content: str
    author: Agent | None = None
    author_id: str = ""
    submolt_id: str = ""
    submolt_name: str = ""
    url: str | None = None
    upvotes: int = 0
    downvotes: int = 0
    comment_count: int = 0
    created_at: str = ""
    is_deleted: bool = False
    is_pinned: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Post":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            author_id=data.get("author_id", ""),
            submolt_id=data.get("submolt_id", ""),
            submolt_name=data.get("submolt_name", "") or data.get("submoltName", ""),
            url=data.get("url"),
            upvotes=data.get("upvotes", 0),
            downvotes=data.get("downvotes", 0),
            comment_count=data.get("comment_count", 0) or data.get("commentCount", 0),
            created_at=data.get("created_at", "") or data.get("createdAt", ""),
            is_deleted=data.get("is_deleted", False) or data.get("isDeleted", False),
            is_pinned=data.get("is_pinned", False) or data.get("isPinned", False),
        )


@dataclass
class Comment:
    """A comment on a post."""

    id: str
    content: str
    post_id: str = ""
    parent_id: str | None = None
    author_id: str = ""
    author_name: str = ""
    upvotes: int = 0
    downvotes: int = 0
    created_at: str = ""
    is_deleted: bool = False
    replies: list[Comment] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Comment":
        replies_data = data.get("replies", [])
        replies = [Comment.from_dict(r) for r in replies_data] if replies_data else []

        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            post_id=data.get("post_id", "") or data.get("postId", ""),
            parent_id=data.get("parent_id") or data.get("parentId"),
            author_id=data.get("author_id", "") or data.get("authorId", ""),
            author_name=data.get("author_name", "") or data.get("authorName", ""),
            upvotes=data.get("upvotes", 0),
            downvotes=data.get("downvotes", 0),
            created_at=data.get("created_at", "") or data.get("createdAt", ""),
            is_deleted=data.get("is_deleted", False) or data.get("isDeleted", False),
            replies=replies,
        )


@dataclass
class Notification:
    """A notification on Moltbook."""

    id: str
    type: str  # post_comment, new_follower, mention, comment_reply, dm_request
    content: str
    related_post_id: str | None = None
    related_comment_id: str | None = None
    agent_id: str = ""
    agent_name: str = ""
    is_read: bool = False
    created_at: str = ""
    post: Post | None = None
    comment: Comment | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Notification":
        post_data = data.get("post")
        post = Post.from_dict(post_data) if post_data else None

        comment_data = data.get("comment")
        comment = Comment.from_dict(comment_data) if comment_data else None

        return cls(
            id=data.get("id", ""),
            type=data.get("type", ""),
            content=data.get("content", ""),
            related_post_id=data.get("relatedPostId") or data.get("related_post_id"),
            related_comment_id=data.get("relatedCommentId") or data.get("related_comment_id"),
            agent_id=data.get("agentId", "") or data.get("agent_id", ""),
            agent_name=data.get("agentName", "") or data.get("agent_name", ""),
            is_read=data.get("isRead", False) or data.get("is_read", False),
            created_at=data.get("createdAt", "") or data.get("created_at", ""),
            post=post,
            comment=comment,
        )


@dataclass
class HomeDashboard:
    """The /home endpoint response."""

    karma: int = 0
    name: str = ""
    unread_notification_count: int = 0
    activity: list[dict] = field(default_factory=list)
    dm_count: int = 0
    what_to_do_next: list[str] = field(default_factory=list)


@dataclass
class Page:
    """A paginated response."""

    items: list
    has_more: bool = False
    next_cursor: str | None = None
    total: int | None = None
