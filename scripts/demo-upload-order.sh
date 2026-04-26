#!/usr/bin/env bash
# Upload a deliberately-anomalous JSON order via POST /api/orders.
# Used during demos to deterministically produce an `escalate` candidate
# (extreme quantity + unit price + category mismatch). The Analyst Agent
# is NOT auto-invoked — click "Run analysis" in the Review Queue.
#
# Prints the new orderId/orderCode so you can chain follow-up scripts.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

require_cmd curl jq

TMP=$(mktemp --suffix=.json)
trap 'rm -f "$TMP"' EXIT

cat > "$TMP" <<EOF
{
  "orderId": "DEMO-ESCALATE-$(date +%s)",
  "orderDate": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "deliveryDate": "$(date -u -d '+7 days' +%Y-%m-%dT%H:%M:%SZ)",
  "buyer":  { "code": "CARREFOUR-ES",  "name": "Carrefour España SA" },
  "seller": { "code": "IBERIAN-FOODS", "name": "Iberian Foods SL" },
  "currency": "EUR",
  "lines": [
    {
      "no": 1,
      "sku": "LEATHER-BAG-PREMIUM",
      "description": "Premium leather handbag with gold trim",
      "qty": 50000,
      "unitPriceMinor": 9999900,
      "lineTotalMinor": 499995000000
    }
  ],
  "totalMinor": 499995000000
}
EOF

yellow "==> Logging in as admin"
TOKEN=$(login_admin)

yellow "==> Uploading anomalous order (50,000 × €99,999 leather handbags from a foods supplier)"
RESPONSE=$(curl -fsS -X POST "${API_URL}/api/orders" \
  -H "Authorization: Bearer ${TOKEN}" \
  -F "file=@${TMP}")

ORDER_ID=$(echo "$RESPONSE" | jq -r '.orderId')
ORDER_CODE=$(echo "$RESPONSE" | jq -r '.orderCode')

green "✓ Created ${ORDER_CODE}"
echo "  orderId:   ${ORDER_ID}"
echo "  Next step: open http://localhost:5173/orders and click 'Run analysis' on the new row,"
echo "             or run: npm run demo:rerun ${ORDER_ID}"
