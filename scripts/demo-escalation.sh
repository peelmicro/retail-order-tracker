#!/usr/bin/env bash
# Trigger n8n workflow 03 (Escalation — Notify Supervisor) for an order.
# The workflow constructs a "ticket" payload and POSTs it to httpbin.org
# (mock); production would point at PagerDuty/Slack/etc.
#
# Usage: demo-escalation.sh [orderCode] [reason]
#   - With no orderCode: picks the most recent escalated order.
#   - reason defaults to "Operator-confirmed escalation".
#
# Prereq: workflow 03 must be Active in the n8n UI.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

require_cmd curl jq

ORDER_CODE="${1:-}"
REASON="${2:-Operator-confirmed escalation}"

TOKEN=$(login_admin)

if [[ -z "$ORDER_CODE" ]]; then
  yellow "==> No orderCode given — picking the most recent escalated order"
  PICK=$(curl -fsS "${API_URL}/api/orders?status=escalated&page=1&page_size=1" \
    -H "Authorization: Bearer ${TOKEN}" \
    | jq -r '.items[0] // empty')
  if [[ -z "$PICK" || "$PICK" == "null" ]]; then
    red "No escalated orders found. Submit feedback with action=escalate first,"
    red "or pass an explicit orderCode: $0 <orderCode> [reason]"
    exit 1
  fi
  ORDER_ID=$(echo "$PICK" | jq -r '.id')
  ORDER_CODE=$(echo "$PICK" | jq -r '.code')
  echo "  picked: ${ORDER_CODE}"
else
  ORDER_ID=$(curl -fsS "${API_URL}/api/orders?page=1&page_size=200" \
    -H "Authorization: Bearer ${TOKEN}" \
    | jq -r --arg code "$ORDER_CODE" '[.items[] | select(.code == $code)] | .[0].id // empty')
  if [[ -z "$ORDER_ID" ]]; then
    red "Order with code ${ORDER_CODE} not found in the first 200 results."
    exit 1
  fi
fi

yellow "==> Firing escalation webhook for ${ORDER_CODE}"
RESPONSE=$(n8n_webhook_post "escalation" \
  "$(jq -nc --arg id "$ORDER_ID" --arg code "$ORDER_CODE" --arg reason "$REASON" \
    '{orderId: $id, orderCode: $code, reason: $reason}')")

echo "$RESPONSE" | jq . 2>/dev/null || echo "$RESPONSE"
green "✓ Mock supervisor ticket created for ${ORDER_CODE}"
