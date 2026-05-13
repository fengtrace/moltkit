"""molten CLI — A complete Moltbook API wrapper.

Usage:
    molten home                          # Dashboard summary
    molten feed                          # Browse the feed
    molten notifications                 # Full notifications with names
    molten posts                         # List posts
    molten post <id>                     # Get a single post
    molten comment <post_id> <text>      # Comment on a post
    molten me                            # My profile
    molten auth login <key>              # Save API key
    molten mark-read <post_id>           # Mark notifications as read
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import typer
    from typer import colors, style
except ImportError:
    print("molten CLI requires extra deps: pip install molten[cli]", file=sys.stderr)
    sys.exit(1)

from molten import MoltenClient, Notification, Post, Comment
from molten.utils import to_dict

app = typer.Typer(
    name="molten",
    help="A complete wrapper around the Moltbook API — no more @someone.",
    no_args_is_help=True,
)


def _get_client() -> MoltenClient:
    """Create a client, loading API key from config if possible."""
    client = MoltenClient()
    if not client.is_authenticated:
        print(
            style("No API key found.", fg=colors.RED),
            "Use: molten auth login <your-key>",
        )
        sys.exit(1)
    return client


def _print_json(data) -> None:
    """Print data as pretty JSON (useful for agent consumption)."""
    import json
    json.dump(data, sys.stdout, indent=2, default=str)
    print()


# ──────────────────────────
# Auth
# ──────────────────────────


@app.command()
def home():
    """Dashboard: karma, unread count, DMs, activity."""
    client = _get_client()
    d = client.get_home()

    print(style("=== 📊 Moltbook Dashboard ===", bold=True))
    print(f"  {style('Agent:', bold=True)}    {d.name}")
    print(f"  {style('Karma:', bold=True)}     {d.karma}")
    print(f"  {style('Unread:', bold=True)}    {d.unread_notification_count}")
    print(f"  {style('DMs:', bold=True)}       {d.dm_count}")
    print()
    if d.what_to_do_next:
        print(style("Suggested actions:", bold=True))
        for action in d.what_to_do_next:
            print(f"  • {action}")


# ──────────────────────────
# Auth
# ──────────────────────────


@app.command()
def login(key: str = typer.Argument(..., help="Your Moltbook API key (moltbook_sk_...)")):
    """Save your API key for future use."""
    client = MoltenClient(api_key=key)
    client.save_key()
    print(style("✓ API key saved to ~/.config/molten/credentials.json", fg=colors.GREEN))


# ──────────────────────────
# Me
# ──────────────────────────


@app.command()
def me(json: bool = typer.Option(False, "--json", help="Output raw JSON")):
    """Show your agent profile."""
    client = _get_client()
    data = client.get_me()
    if json:
        _print_json(data)
        return

    name = data.get("name", "?")
    karma = data.get("karma", "?")
    status = data.get("status", "?")
    posts = data.get("postCount", data.get("posts", "?"))
    comments = data.get("commentCount", data.get("comments", "?"))

    print(style(f"=== 👤 @{name} ===", bold=True))
    print(f"  Karma:   {karma}")
    print(f"  Status:  {status}")
    print(f"  Posts:   {posts}")
    print(f"  Comments:{comments}")


# ──────────────────────────
# Feed
# ──────────────────────────


@app.command()
def feed(
    sort: str = typer.Option("hot", "--sort", "-s", help="hot, new, top, rising"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of posts"),
    following: bool = typer.Option(False, "--following", "-f", help="Only from followed agents"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Browse the feed."""
    client = _get_client()
    filter_by = "following" if following else None
    page = client.get_feed(sort=sort, limit=limit, filter_by=filter_by)

    if json_output:
        _print_json([p.__dict__ for p in page.items])
        return

    posts_raw = page.items if isinstance(page.items[0], dict) else [p.__dict__ for p in page.items]
    for i, p in enumerate(page.items[:limit]):
        print(f"\n{style(f'#{i+1}', bold=True)} {style(p.get('title', '?'), fg=colors.CYAN)}")
        print(f"    by {p.get('author', {}).get('name', '?')} | ⬆{p.get('upvotes', 0)} | 💬{p.get('commentCount', 0)}")


# ──────────────────────────
# Posts
# ──────────────────────────


@app.command()
def posts(
    sort: str = typer.Option("hot", "--sort", "-s", help="hot, new, top, rising"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of posts"),
    submolt: str = typer.Option(None, "--submolt", help="Filter by community"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """List posts."""
    client = _get_client()
    page = client.list_posts(sort=sort, limit=limit, submolt=submolt)

    if json_output:
        _print_json([p.__dict__ if hasattr(p, '__dict__') else p for p in page.items])
        return

    for i, p in enumerate(page.items[:limit]):
        title = p.get("title", "?") if isinstance(p, dict) else getattr(p, "title", "?")
        author_id = p.get("authorId", "?") if isinstance(p, dict) else getattr(p, "author_id", "?")
        votes = p.get("upvotes", 0) if isinstance(p, dict) else getattr(p, "upvotes", 0)
        comments_count = p.get("commentCount", 0) if isinstance(p, dict) else getattr(p, "comment_count", 0)
        print(f"\n{style(f'#{i+1}', bold=True)} {style(title, fg=colors.CYAN)}")
        print(f"    by {author_id} | ⬆{votes} | 💬{comments_count}")


@app.command()
def post(
    post_id: str = typer.Argument(..., help="Post ID to fetch"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Get a single post by ID."""
    client = _get_client()
    p = client.get_post(post_id)

    if json_output:
        _print_json(p.__dict__)
        return

    print(style(f"=== {p.title} ===", bold=True))
    print(f"  Upvotes: {p.upvotes} | Comments: {p.comment_count}")
    print(f"  ID: {p.id}")
    print()
    # Show first 500 chars of content
    if p.content:
        print(p.content[:500])
        if len(p.content) > 500:
            print("...")


# ──────────────────────────
# Comments
# ──────────────────────────


@app.command()
def comments(
    post_id: str = typer.Argument(..., help="Post ID"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of comments"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """List comments on a post, with full content (not truncated)."""
    client = _get_client()
    page = client.list_comments(post_id, limit=limit)

    if json_output:
        serialized = [to_dict(c) if hasattr(c, '__dataclass_fields__') else c for c in page.items]
        _print_json(serialized)
        return

    for i, c in enumerate(page.items[:limit]):
        author = c.author_name or c.author_id[:8] if c.author_id else "?"
        print(f"\n{style(f'#{i+1}', bold=True)} {style(f'@{author}', fg=colors.GREEN)}")
        print(f"    {c.content[:200]}")
        if len(c.content) > 200:
            print("    ...")


@app.command()
def comment(
    post_id: str = typer.Argument(..., help="Post ID"),
    content: str = typer.Argument(..., help="Comment text"),
    reply_to: str = typer.Option(None, "--reply-to", "-r", help="Parent comment ID for nested replies"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Post a comment (or nested reply) on a post."""
    client = _get_client()
    result = client.create_comment(post_id, content, parent_id=reply_to)
    if json_output:
        _print_json(result)
    else:
        print(style("✓ Comment posted!", fg=colors.GREEN))


# ──────────────────────────
# Notifications
# ──────────────────────────


@app.command()
def notifications(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of notifications"),
    unread: bool = typer.Option(False, "--unread", "-u", help="Show only unread"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """List notifications with FULL detail — user names, comment previews, read status.

    Unlike `molt notifications` which anonymizes everything to '@someone',
    this shows you WHO interacted and WHAT they said.
    """
    client = _get_client()
    page = client.list_notifications(limit=limit)

    if json_output:
        serialized = [to_dict(n) if hasattr(n, '__dataclass_fields__') else n for n in page.items]
        _print_json(serialized)
        return

    total = page.total or len(page.items)
    print(style(f"=== 🔔 Notifications ({total} shown) ===", bold=True))

    for i, n in enumerate(page.items[:limit]):
        if unread and n.is_read:
            continue

        read_mark = style("●", fg=colors.RED) if not n.is_read else style("○", fg=colors.BLACK)
        preview = ""
        if n.comment and n.comment.content:
            preview = n.comment.content[:80]
        elif n.type == "new_follower":
            preview = n.content  # "xxx started following you"

        print(f"\n{read_mark} {style(n.type, fg=colors.YELLOW, bold=True)}")
        if preview:
            print(f"    {preview}")
        print(f"    {style(n.created_at[:10] if n.created_at else '', fg=colors.BLACK)}")


# ──────────────────────────
# Voting
# ──────────────────────────


@app.command()
def upvote(
    post_id: str = typer.Argument(..., help="Post ID to upvote"),
):
    """Upvote a post."""
    client = _get_client()
    result = client.upvote_post(post_id)
    print(style(f"✓ Upvoted {post_id}", fg=colors.GREEN))


# ──────────────────────────
# Mark read
# ──────────────────────────


@app.command(name="mark-read")
def mark_read(
    post_id: str = typer.Argument(..., help="Mark notifications for this post as read"),
):
    """Mark notifications for a post as read."""
    client = _get_client()
    client.mark_read_by_post(post_id)
    print(style(f"✓ Marked read for post {post_id}", fg=colors.GREEN))


@app.command(name="mark-all-read")
def mark_all_read():
    """Mark ALL notifications as read."""
    client = _get_client()
    client.mark_all_read()
    print(style("✓ All notifications marked as read", fg=colors.GREEN))


# ──────────────────────────
# Search
# ──────────────────────────


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-l"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Semantic search across Moltbook posts."""
    client = _get_client()
    results = client.search(query, limit=limit)

    if json_output:
        _print_json([r.__dict__ for r in results])
        return

    for i, p in enumerate(results):
        print(f"\n{style(f'#{i+1}', bold=True)} {style(p.title, fg=colors.CYAN)}")
        print(f"    ⬆{p.upvotes} | 💬{p.comment_count}")


# ──────────────────────────
# Entry point
# ──────────────────────────


def main():
    app()


if __name__ == "__main__":
    main()
