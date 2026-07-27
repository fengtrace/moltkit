"""moltkit CLI — A complete Moltbook API wrapper.

Usage:
    moltkit home                          # Dashboard summary
    moltkit profile                       # Structured profile
    moltkit agent <name>                  # View other agent
    moltkit feed                          # Browse the feed
    moltkit notifications                 # Full notifications with names
    moltkit posts                         # List posts
    moltkit post <id>                     # Get a single post
    moltkit create-post <submolt> <title> # Create a new post
    moltkit delete-post <id>              # Delete a post
    moltkit comments <post_id>            # List comments
    moltkit comment <post_id> <text>      # Comment on a post
    moltkit search <query>                # Search posts
    moltkit submolts                      # List communities
    moltkit follow <name>                 # Follow an agent
    moltkit unfollow <name>               # Unfollow an agent
    moltkit upvote <post_id>              # Upvote a post
    moltkit downvote <post_id>            # Downvote a post
    moltkit upvote-comment <id>           # Upvote a comment
    moltkit me                            # Raw profile (legacy)
    moltkit auth login <key>              # Save API key
    moltkit mark-read <post_id>           # Mark notifications as read
    moltkit mark-all-read                 # Mark all read
    moltkit status                        # Full status snapshot
    moltkit check                         # Incremental check
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import typer
    from typer import colors, style
except ImportError:
    print("moltkit CLI requires extra deps: pip install moltkit[cli]", file=sys.stderr)
    sys.exit(1)

from moltkit import MoltenClient, Notification, Post, Comment
from moltkit.utils import to_dict

app = typer.Typer(
    name="moltkit",
    help="A complete wrapper around the Moltbook API — no more @someone.",
    no_args_is_help=True,
)


def _get_client() -> MoltenClient:
    """Create a client, loading API key from config if possible."""
    client = MoltenClient()
    if not client.is_authenticated:
        print(
            style("No API key found.", fg=colors.RED),
            "Use: moltkit auth login <your-key>",
        )
        sys.exit(1)
    return client


def _print_json(data) -> None:
    """Print data as pretty JSON (useful for agent consumption)."""
    import json
    json.dump(data, sys.stdout, indent=2, default=str)
    print()


# ──────────────────────────
# Home / Dashboard
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
# Profile
# ──────────────────────────


@app.command()
def profile(json_output: bool = typer.Option(False, "--json", help="Output raw JSON")):
    """Show your structured agent profile."""
    client = _get_client()
    p = client.get_my_profile()

    if json_output:
        _print_json(to_dict(p))
        return

    print(style(f"=== 👤 @{p.name} ===", bold=True))
    print(f"  Karma:     {p.karma}")
    print(f"  Status:    {p.status or 'active'}")
    print(f"  Followers: {p.follower_count}")
    print(f"  Following: {p.following_count}")
    print(f"  Posts:     {p.posts_count}")
    print(f"  Comments:  {p.comments_count}")
    if p.description:
        print(f"\n  {p.description}")


@app.command()
def agent(
    agent_id: str = typer.Argument(..., help="Agent ID or @name"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """View another agent's profile."""
    client = _get_client()
    a = client.get_agent(agent_id)

    if json_output:
        _print_json(to_dict(a))
        return

    print(style(f"=== 👤 @{a.name} ===", bold=True))
    print(f"  Karma:     {a.karma}")
    print(f"  Status:    {a.status or 'active'}")
    print(f"  Followers: {a.follower_count}")
    print(f"  Following: {a.following_count}")
    print(f"  Posts:     {a.posts_count}")
    print(f"  Comments:  {a.comments_count}")
    if a.description:
        print(f"\n  {a.description}")


# ──────────────────────────
# Auth
# ──────────────────────────


@app.command()
def login(key: str = typer.Argument(..., help="Your Moltbook API key (moltbook_sk_...)")):
    """Save your API key for future use."""
    client = MoltenClient(api_key=key)
    client.save_key()
    print(style("✓ API key saved to ~/.config/moltkit/credentials.json", fg=colors.GREEN))


# ──────────────────────────
# Me (raw, legacy)
# ──────────────────────────


@app.command()
def me(json: bool = typer.Option(False, "--json", help="Output raw JSON")):
    """Show your agent profile (raw JSON)."""
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
# Follow / Unfollow
# ──────────────────────────


@app.command()
def follow(
    name: str = typer.Argument(..., help="Agent name to follow"),
):
    """Follow an agent."""
    client = _get_client()
    result = client.follow(name)
    print(style(f"✓ Following @{name}", fg=colors.GREEN))


@app.command()
def unfollow(
    name: str = typer.Argument(..., help="Agent name to unfollow"),
):
    """Unfollow an agent."""
    client = _get_client()
    result = client.unfollow(name)
    print(style(f"✓ Unfollowed @{name}", fg=colors.GREEN))


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
    """Browse the home feed."""
    client = _get_client()
    filter_by = "following" if following else None
    page = client.get_feed(sort=sort, limit=limit, filter_by=filter_by)

    if json_output:
        _print_json([to_dict(p) for p in page.items])
        return

    for i, p in enumerate(page.items[:limit]):
        author_id = p.author_id or p.author.name if p.author else "?"
        print(f"\n{style(f'#{i+1}', bold=True)} {style(p.title, fg=colors.CYAN)}")
        print(f"    by {author_id} | ⬆{p.upvotes} | 💬{p.comment_count}")


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
        _print_json([to_dict(p) for p in page.items])
        return

    for i, p in enumerate(page.items[:limit]):
        author_id = p.author_id or p.author.name if p.author else "?"
        print(f"\n{style(f'#{i+1}', bold=True)} {style(p.title, fg=colors.CYAN)}")
        print(f"    by {author_id} | ⬆{p.upvotes} | 💬{p.comment_count}")


@app.command(name="create-post")
def create_post(
    submolt_name: str = typer.Argument(..., help="Community to post in (e.g. newbots)"),
    title: str = typer.Argument(..., help="Post title"),
    content: str = typer.Option("", "--content", "-c", help="Post body text"),
    url: str = typer.Option(None, "--url", "-u", help="Link URL for link posts"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Create a new post in a community."""
    client = _get_client()
    result = client.create_post(submolt_name=submolt_name, title=title, content=content, url=url)
    if json_output:
        _print_json(result)
    else:
        print(style(f"✓ Post created in m/{submolt_name}", fg=colors.GREEN))


@app.command(name="delete-post")
def delete_post(
    post_id: str = typer.Argument(..., help="Post ID to delete"),
):
    """Delete a post."""
    client = _get_client()
    client.delete_post(post_id)
    print(style(f"✓ Post {post_id} deleted", fg=colors.GREEN))


@app.command()
def post(
    post_id: str = typer.Argument(..., help="Post ID to fetch"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Get a single post by ID."""
    client = _get_client()
    p = client.get_post(post_id)

    if json_output:
        _print_json(to_dict(p))
        return

    print(style(f"=== {p.title} ===", bold=True))
    print(f"  Upvotes: {p.upvotes} | Comments: {p.comment_count}")
    print(f"  ID: {p.id}")
    print()
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
    truncate_len: int = typer.Option(80, "--truncate-len", "-n", help="Limit to first N characters"),
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
        if c.author_name:
            author = c.author_name
        elif c.author_id:
            author = c.author_id[:8]
        else:
            author = "?"
            
        content = c.content
        if truncate_len > 0:
            content = content[:truncate_len] + "\n    ..."
            
        print(f"\n{style(f'#{i+1}', bold=True)} {style(f'@{author}', fg=colors.GREEN)}")
        print(f"    {content}")


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
# Voting
# ──────────────────────────


@app.command()
def upvote(
    post_id: str = typer.Argument(..., help="Post ID to upvote"),
):
    """Upvote a post."""
    client = _get_client()
    client.upvote_post(post_id)
    print(style(f"✓ Upvoted {post_id}", fg=colors.GREEN))


@app.command()
def downvote(
    post_id: str = typer.Argument(..., help="Post ID to downvote"),
):
    """Downvote a post."""
    client = _get_client()
    client.downvote_post(post_id)
    print(style(f"✓ Downvoted {post_id}", fg=colors.GREEN))


@app.command(name="upvote-comment")
def upvote_comment(
    comment_id: str = typer.Argument(..., help="Comment ID to upvote"),
):
    """Upvote a comment."""
    client = _get_client()
    client.upvote_comment(comment_id)
    print(style(f"✓ Upvoted comment {comment_id}", fg=colors.GREEN))


# ──────────────────────────
# Notifications
# ──────────────────────────


@app.command()
def notifications(
    limit: int = typer.Option(20, "--limit", "-l", help="Number of notifications"),
    unread: bool = typer.Option(False, "--unread", "-u", help="Show only unread"),
    truncate_len: int = typer.Option(80, "--truncate-len", "-n", help="Limit to first N characters for comments"),
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
            preview = n.comment.content
        elif n.type == "new_follower":
            preview = n.content

        if truncate_len > 0:
            preview = preview[:truncate_len] + "\n    ..."

        print(f"\n{read_mark} {style(n.type, fg=colors.YELLOW, bold=True)}")
        if preview:
            print(f"    {preview}")
        print(f"    {style(n.created_at[:10] if n.created_at else '', fg=colors.BLACK)}")


# ──────────────────────────
# Search
# ──────────────────────────


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    scope: str = typer.Option("all", "--scope", help="all, posts, comments, or agents"),
    limit: int = typer.Option(10, "--limit", "-l"),
    truncate_len: int = typer.Option(200, "--truncate-len", "-n", help="Limit to first N characters"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Semantic search across Moltbook."""
    client = _get_client()

    if scope == "posts":
        results = client.search_posts(query, limit=limit)
    elif scope == "comments":
        results = client.search_comments(query, limit=limit)
    elif scope == "agents":
        results = client.search_agents(query, limit=limit)
    else:
        results = client.search(query, limit=limit)

    if json_output:
        _print_json([to_dict(r) if hasattr(r, '__dataclass_fields__') else r for r in results])
        return

    if not results:
        print(style("No results found.", fg=colors.YELLOW))
        return

    for i, r in enumerate(results):
        if isinstance(r, Comment):
            if r.author_name:
                author = r.author_name
            elif r.author_id:
                author = r.author_id[:8]
            else:
                author = "?"
                
            content = r.content
            if truncate_len > 0:
                content = content[:truncate_len] + "\n    ..."
                
            print(f"\n{style(f'#{i+1}', bold=True)} {style(f'@{author}', fg=colors.GREEN)}")
            print(f"    {content}")
        else:
            title = getattr(r, "title", getattr(r, "name", "?"))
            votes = getattr(r, "upvotes", 0) or getattr(r, "karma", 0)
            print(f"\n{style(f'#{i+1}', bold=True)} {style(str(title), fg=colors.CYAN)}")
            print(f"    ⬆{votes}")


# ──────────────────────────
# Submolts
# ──────────────────────────


@app.command(name="submolts")
def list_submolts(
    sort: str = typer.Option("hot", "--sort", "-s", help="hot, new, subscribers"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of communities"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """List available communities (submolts)."""
    client = _get_client()
    page = client.list_submolts(sort=sort, limit=limit)

    if json_output:
        _print_json([to_dict(s) for s in page.items])
        return

    print(style(f"=== Communities ({len(page.items)}) ===", bold=True))
    for i, s in enumerate(page.items[:limit]):
        subscribed = "✓" if s.is_subscribed else " "
        print(f"  [{subscribed}] {style(f'm/{s.name}', fg=colors.CYAN)}")
        print(f"      {s.display_name} — {s.subscriber_count} subscribers")


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
# Verification
# ──────────────────────────


@app.command()
def verify(
    verification_id: str = typer.Argument(..., help="Verification challenge ID"),
    answer: str = typer.Argument(..., help="Answer to the challenge (e.g. math captcha result)"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Submit a verification challenge answer (e.g. math captcha).

    After creating a post that triggers a verification challenge, use this
    to submit your answer. The verification_id and challenge details are
    included in the create_post response when verification is required.
    """
    client = _get_client()
    result = client.verify(verification_id, answer)
    if json_output:
        _print_json(result)
    else:
        print(style("✓ Verification submitted!", fg=colors.GREEN))


# ──────────────────────────
# Layer 2: Aggregated operations
# ──────────────────────────


@app.command()
def status(
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Full snapshot: karma, unread count, DMs, followers, activity."""
    from moltkit.aggregate import status as _status

    client = _get_client()
    s = _status(client)

    if json_output:
        from moltkit.utils import to_dict
        _print_json(to_dict(s))
        return

    print(style("=== 📊 Moltbook Status ===", bold=True))
    print(f"  {style('Agent:', bold=True)}     {s.name}")
    print(f"  {style('Karma:', bold=True)}      {s.karma}")
    print(f"  {style('Unread:', bold=True)}     {s.unread_notifications}")
    print(f"  {style('DMs:', bold=True)}        {s.dm_count}")
    print(f"  {style('Followers:', bold=True)}  {s.follower_count}")
    print(f"  {style('Following:', bold=True)}  {s.following_count}")
    print(f"  {style('Posts:', bold=True)}      {s.posts_count}")
    print(f"  {style('Comments:', bold=True)}   {s.comments_count}")
    if s.what_to_do:
        print()
        print(style("Suggested:", bold=True))
        for action in s.what_to_do[:3]:
            print(f"  • {action}")


@app.command()
def check(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show details of new items"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of notifications"),
    truncate_len: int = typer.Option(60, "--truncate-len", "-n", help="Limit to first N characters"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON"),
):
    """Incremental check — only new activity since your last check."""
    from moltkit.aggregate import check as _check

    client = _get_client()
    result = _check(client)

    if json_output:
        from moltkit.utils import to_dict
        _print_json(to_dict(result))
        return

    if result.has_new:
        print(style(f"=== 🔔 {result.summary} ===", bold=True))
        print(f"  Karma: {result.current_karma}")

        if verbose and result.new_notifications:
            print()
            print(style("New notifications:", bold=True))
            for n in result.new_notifications[:limit]:
                read_mark = style("●", fg=colors.RED) if not n.is_read else "○"
                preview = n.comment.content if n.comment else n.content
                if truncate_len > 0:
                    preview = preview[:truncate_len] + "\n    ..."
                print(f"  {read_mark} [{n.type}] {preview}")

        if verbose and result.new_followers:
            print()
            print(style(f"New followers ({len(result.new_followers)}):", bold=True))
            for name in result.new_followers:
                print(f"  • {name}")

        print()
        print(f"  Last checked: {result.last_checked}")
    else:
        print(style("✓ Nothing new since last check.", fg=colors.GREEN))
        print(f"  Karma: {result.current_karma}")


@app.command()
def reset_check():
    """Reset the check timestamp to now.

    After this, the next ``moltkit check`` will show everything as new.
    """
    from moltkit.aggregate import reset_check_timestamp
    ts = reset_check_timestamp()
    print(style(f"✓ Check timestamp reset to now ({ts:.0f})", fg=colors.GREEN))


# ──────────────────────────
# Entry point
# ──────────────────────────


def main():
    app()


if __name__ == "__main__":
    main()
