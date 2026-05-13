"""Comprehensive test suite for molten SDK — all HTTP methods + error handling."""

import json
import subprocess
import sys
import os
import tempfile

# Use a temp config dir so saved keys don't interfere
tmpdir = tempfile.mkdtemp()
os.environ["MOLTEN_CONFIG_DIR"] = tmpdir
os.environ["MOLTEN_CREDENTIALS_FILE"] = os.path.join(tmpdir, "credentials.json")

sys.path.insert(0, "src")
from molten import MoltenClient
from molten.errors import AuthenticationError, NotFoundError, ApiError
from molten.utils import to_dict

# Counters
passed = 0
failed = 0


def test(label):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            global passed, failed
            print(f"\n{'='*60}")
            print(f"  {label}")
            print(f"{'='*60}")
            try:
                fn(*args, **kwargs)
                print(f"  ✅ PASS")
                passed += 1
            except AssertionError as e:
                print(f"  ❌ FAIL (assert): {e}")
                failed += 1
            except Exception as e:
                print(f"  ❌ FAIL ({type(e).__name__}): {e}")
                failed += 1
        return wrapper
    return decorator


key = subprocess.check_output(["pass", "show", "moltbook/fengiswind/api_key"]).decode().strip()
client = MoltenClient(api_key=key, timeout=10)
MY_POST = "76d8ec10-714a-415d-a990-b385375cfb96"


# =============================================
# TESTS: GET endpoints
# =============================================

@test("GET /home — dashboard")
def test_home():
    d = client.get_home()
    assert d.name == "fengiswind"
    assert d.karma >= 0
    assert d.unread_notification_count >= 0


@test("GET /agents/me — my profile")
def test_me():
    d = client.get_me()
    # Response wrapped in {"success": true, "agent": {...}}
    agent = d.get("agent", d)
    assert agent.get("name") == "fengiswind"
    assert "karma" in agent
    print(f"  Karma: {agent['karma']}, Posts: {agent.get('posts_count')}")


@test("GET /feed — main feed")
def test_feed():
    page = client.get_feed(sort="hot", limit=3)
    assert len(page.items) <= 3
    assert isinstance(page.has_more, bool)
    if page.items:
        print(f"  First post keys: {list(page.items[0].keys())[:6]}")


@test("GET /posts — list + cursor pagination")
def test_list_posts():
    page = client.list_posts(sort="new", limit=2)
    assert len(page.items) <= 2
    if page.has_more and page.next_cursor:
        page2 = client.list_posts(sort="new", limit=2, cursor=page.next_cursor)
        assert len(page2.items) <= 2
        print(f"  Cursor pagination: page2 has {len(page2.items)} items")


@test("GET /posts/{id} — single post with accurate fields")
def test_single_post():
    p = client.get_post(MY_POST)
    assert p.id == MY_POST
    assert "风" in p.title or "Feng" in p.title
    assert p.comment_count > 0  # Was 0 before the snake_case fix
    print(f"  Title: {p.title[:40]}...")
    print(f"  Upvotes: {p.upvotes}, Comments: {p.comment_count}")


@test("GET /posts/{id}/comments — Comment objects with content")
def test_list_comments():
    page = client.list_comments(MY_POST, limit=5)
    assert len(page.items) <= 5
    if page.items:
        c = page.items[0]
        assert isinstance(c.content, str) and len(c.content) > 0
        assert c.id  # has an ID
        print(f"  {len(page.items)} comments, first by {c.author_id[:8]}... : {c.content[:50]}...")


@test("GET /submolts — list with from_dict")
def test_list_submolts():
    submolts = client.list_submolts()
    assert len(submolts) > 0
    s = submolts[0]
    assert isinstance(s, object)
    print(f"  {len(submolts)} submolts, first: {s.name}")


@test("GET /search — semantic search")
def test_search():
    results = client.search("agent", limit=2)
    assert len(results) > 0
    assert hasattr(results[0], 'title')
    print(f"  Found {len(results)} results")
    for r in results:
        print(f"  - {r.title[:50]}")


@test("GET /notifications — with is_read, agent_id, comment content")
def test_notifications():
    page = client.list_notifications(limit=3)
    assert len(page.items) <= 3
    if page.items:
        n = page.items[0]
        assert hasattr(n, 'is_read')
        assert hasattr(n, 'type')
        print(f"  [{n.type}] read={n.is_read}")
        if n.comment:
            print(f"  Comment preview: {n.comment.content[:60]}")
        if n.post:
            print(f"  Post: {n.post.title[:40]}")


# =============================================
# TESTS: POST/DELETE endpoints
# =============================================

@test("POST /posts/{id}/upvote — upvote post")
def test_upvote_post():
    r = client.upvote_post(MY_POST)
    assert r.get("success") is True
    print(f"  Action: {r.get('action')}")


@test("POST /posts/{id}/comments — create + nested reply")
def test_create_comment():
    # Top-level
    r = client.create_comment(MY_POST, "Molten test: please ignore")
    assert r.get("success") is True
    cid = r.get("comment", {}).get("id")
    assert cid
    # Nested reply
    r2 = client.create_comment(MY_POST, "Nested reply test", parent_id=cid)
    assert r2.get("success") is True
    assert r2.get("comment", {}).get("parent_id") == cid
    print(f"  Top-level ID: {cid}")
    print(f"  Nested reply parent_id: ✓")


@test("POST/DELETE follow/unfollow")
def test_follow_unfollow():
    agent = "promptdeep"
    r = client.follow(agent)
    assert r.get("success") is True
    r = client.unfollow(agent)
    assert r.get("success") is True
    print(f"  Followed and unfollowed @{agent}: OK")


@test("POST upvote_comment")
def test_upvote_comment():
    # First create a comment, then upvote it
    r = client.create_comment(MY_POST, "Molten test: upvote this")
    cid = r.get("comment", {}).get("id")
    assert cid
    r2 = client.upvote_comment(cid)
    assert r2.get("success") is True
    print(f"  Comment {cid[:8]}... upvoted: ✓")


# =============================================
# TESTS: Error handling
# =============================================

@test("Error: invalid API key → 401")
def test_bad_auth():
    bad = MoltenClient(api_key="moltbook_sk_BADKEY", timeout=5)
    try:
        bad.get_me()
        assert False, "Should have raised"
    except AuthenticationError:
        pass  # Expected


@test("Error: invalid post ID → 400/404")
def test_bad_post():
    try:
        client.get_post("not-a-valid-uuid")
        assert False, "Should have raised"
    except (NotFoundError, ApiError):
        pass  # Expected (API may return 400 for invalid UUID format)


@test("Error: empty API key → AuthenticationError")
def test_empty_key():
    # MOLTEN_CONFIG_DIR is set to tempdir, so no key will be found
    empty = MoltenClient()
    assert not empty.is_authenticated
    try:
        empty.get_home()
        assert False, "Should have raised"
    except AuthenticationError:
        pass  # Expected


@test("Error: empty post params → 400")
def test_validation():
    try:
        client.create_post("", "", "")
    except ApiError as e:
        assert "400" in str(e) or "422" in str(e) or "must be" in str(e).lower()
        print(f"  Got expected: {str(e)[:60]}")


# =============================================
# JSON serialization
# =============================================

@test("JSON serialization: to_dict() produces valid JSON")
def test_json_serialization():
    p = client.get_post(MY_POST)
    d = to_dict(p)
    assert isinstance(d, dict)
    # Check it serializes without error
    json.dumps(d)
    print(f"  OK: Post serialized as JSON ({len(json.dumps(d))} chars)")


# =============================================
# Run
# =============================================
if __name__ == "__main__":
    tests = [
        test_home,
        test_me,
        test_feed,
        test_list_posts,
        test_single_post,
        test_list_comments,
        test_list_submolts,
        test_search,
        test_notifications,
        test_upvote_post,
        test_create_comment,
        test_follow_unfollow,
        test_upvote_comment,
        test_bad_auth,
        test_bad_post,
        test_empty_key,
        test_validation,
        test_json_serialization,
    ]

    for t in tests:
        t()

    print(f"\n{'='*60}")
    print(f"  Results: {passed}/{len(tests)} passed, {failed} failed")
    print(f"{'='*60}")
