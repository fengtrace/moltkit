#!/usr/bin/env bash
# ──────────────────────────────────────────────────
# moltkit test data cleanup
#
# Removes Moltbook posts created during integration testing.
# Convention: test posts MUST have "[TEST]" at the start of their title.
#
# Usage:
#   MOLTKIT_API_KEY="moltbook_sk_..." ./scripts/cleanup-test-data.sh
#   ./scripts/cleanup-test-data.sh --dry-run   # Preview only, no deletion
# ──────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "${MOLTKIT_API_KEY:-}" ]; then
    echo "❌ MOLTKIT_API_KEY not set."
    echo "   Usage: MOLTKIT_API_KEY=\"moltbook_sk_...\" $0"
    exit 1
fi

DRY_RUN=false
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=true
    echo "🔍 Dry-run mode — no posts will be deleted"
fi

API="https://www.moltbook.com/api/v1"
AUTH="Authorization: Bearer $MOLTKIT_API_KEY"

echo "🧹 Searching for test posts..."

# Search for posts with "[TEST]" prefix
# Using the search API
SEARCH_RESULTS=$(curl -s -H "$AUTH" "${API}/search?q=%5BTEST%5D&limit=50" 2>/dev/null)
POST_IDS=$(echo "$SEARCH_RESULTS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    posts = data.get('posts', data.get('results', []))
    test_posts = [p for p in posts if p.get('title','').startswith('[TEST]') or p.get('title','').startswith('[test]')]
    for p in test_posts:
        print(f\"{p['id']}|{p['title'][:60]}\")
except: pass
")

if [ -z "$POST_IDS" ]; then
    echo "✅ No test posts found. (Search: ${API}/search?q=%5BTEST%5D)"
    echo "   Note: Moltbook search is semantic — posts with '[TEST]' prefix"
    echo "   may not appear immediately. Try again in a few seconds."
    exit 0
fi

echo ""
echo "Found test posts:"
echo "$POST_IDS" | while IFS='|' read -r id title; do
    echo "  • $id — $title"
done

echo ""
if [ "$DRY_RUN" = true ]; then
    echo "🏁 Dry-run complete. $POST_COUNT posts would be deleted."
    exit 0
fi

echo "Deleting..."
echo "$POST_IDS" | while IFS='|' read -r id title; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE -H "$AUTH" "${API}/posts/${id}")
    if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "204" ]; then
        echo "  ✓ Deleted: $title"
    else
        echo "  ✗ Failed to delete $id (HTTP $HTTP_CODE)"
    fi
done

echo ""
echo "✅ Cleanup complete."
