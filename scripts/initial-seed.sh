#!/usr/bin/env bash
# Populate the database with a small demo-friendly batch.
# Wipes feedbacks/agent_suggestions/order_line_items/orders/documents,
# upserts retailers + suppliers, uploads sample files, then generates
# 20 historical + 5 pending orders + 5 feedbacks. ~3 s.
#
# Override counts via env: HIST=200 PEND=30 FB=50 npm run initial-seed

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

require_cmd curl jq

HIST="${HIST:-20}"
PEND="${PEND:-5}"
FB="${FB:-5}"

yellow "==> Logging in as admin"
TOKEN=$(login_admin)

yellow "==> Seeding (historical=${HIST}, pending=${PEND}, feedback=${FB})"
RESPONSE=$(curl -fsS -X POST \
  "${API_URL}/api/seed?historical_count=${HIST}&pending_count=${PEND}&feedback_count=${FB}" \
  -H "Authorization: Bearer ${TOKEN}")

echo "$RESPONSE" | jq .
green "✓ Seed complete"
