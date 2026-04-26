#!/usr/bin/env bash
# Trigger n8n workflow 04 (Retraining — Export Phoenix Dataset).
# The workflow logs in as admin then GETs /api/datasets/export?limit=...
# and returns the Phoenix-shaped JSON. In production this would push
# directly to a Phoenix dataset.
#
# Usage: demo-export-dataset.sh [limit]   (limit defaults to 100)
#
# Prereq: workflow 04 must be Active in the n8n UI.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

require_cmd curl jq

LIMIT="${1:-100}"

yellow "==> Triggering Phoenix dataset export (limit=${LIMIT})"
RESPONSE=$(n8n_webhook_post "retraining" \
  "$(jq -nc --argjson limit "$LIMIT" '{limit: $limit}')")

EXAMPLE_COUNT=$(echo "$RESPONSE" | jq -r '.examples | length' 2>/dev/null || echo "?")

# Show summary without dumping the full examples array
echo "$RESPONSE" | jq 'del(.examples) | .exampleCount = ('"$EXAMPLE_COUNT"')' 2>/dev/null || echo "$RESPONSE"
green "✓ Dataset export complete (${EXAMPLE_COUNT} examples)"
