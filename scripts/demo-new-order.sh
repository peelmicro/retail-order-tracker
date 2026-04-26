#!/usr/bin/env bash
# Trigger n8n workflow 01 (New Order — Analyst Agent Trigger) for an order.
# The workflow logs in as admin internally and calls
# POST /api/agents/analyst/run/by-order/{order_id}, persisting a fresh
# AgentSuggestion row.
#
# Usage: demo-new-order.sh [orderId]
#   - With no arg: picks the most recent pending order without a suggestion.
#
# Prereq: workflow 01 must be Active in the n8n UI
# (http://localhost:5678 — login admin/admin).

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

require_cmd curl jq

ORDER_ID="${1:-}"

if [[ -z "$ORDER_ID" ]]; then
  yellow "==> No orderId given — picking the most recent pending order without a suggestion"
  TOKEN=$(login_admin)
  ORDER_ID=$(curl -fsS "${API_URL}/api/orders?status=pending_review&page=1&page_size=50" \
    -H "Authorization: Bearer ${TOKEN}" \
    | jq -r '[.items[] | select(.hasSuggestion == false)] | .[0].id // empty')
  if [[ -z "$ORDER_ID" ]]; then
    red "No pending order without a suggestion found. Pass an orderId explicitly: $0 <orderId>"
    exit 1
  fi
  echo "  picked: ${ORDER_ID}"
fi

yellow "==> Calling n8n webhook /webhook/new-order"
RESPONSE=$(n8n_webhook_post "new-order" \
  "$(jq -nc --arg id "$ORDER_ID" '{orderId: $id}')")

echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
green "✓ n8n workflow 01 invoked for order ${ORDER_ID}"
