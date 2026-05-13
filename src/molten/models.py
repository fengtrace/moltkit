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


@dataclass
class Post:
    """A post on Moltbook."""

    id: str
    title: str
    content: str
    author: Agent | None = None
    author_id: str = ""
    submolt_id: str = ""
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
            author_id=data.get("authorId", ""),
            submolt_id=data.get("submoltId", ""),
            url=data.get("url"),
            upvotes=data.get("upvotes", 0),
            downvotes=data.get("downvotes", 0),
            comment_count=data.get("commentCount", 0),
            created_at=data.get("createdAt", ""),
            is_deleted=data.get("isDeleted", False),
            is_pinned=data.get("isPinned", False),
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
    created_at: str = ""
    is_deleted: bool = False
    replies: list[Comment] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Comment":
        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            post_id=data.get("postId", ""),
            parent_id=data.get("parentId"),
            author_id=data.get("authorId", ""),
            upvotes=data.get("upvotes", 0),
            created_at=data.get("createdAt", ""),
            is_deleted=data.get("isDeleted", False),
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
            related_post_id=data.get("relatedPostId"),
            related_comment_id=data.get("relatedCommentId"),
            agent_id=data.get("agentId", ""),
            is_read=data.get("isRead", False),
            created_at=data.get("createdAt", ""),
            post=post,
            comment=comment,
        )


@dataclass
class Submolt:
    """A community on Moltbook."""

    id: str
    name: str
    display_name: str = ""
    description: str = ""
    subscriber_count: int = 0
    is_subscribed: bool = False


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
