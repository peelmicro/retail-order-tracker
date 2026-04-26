#!/usr/bin/env bash
# Shared helpers sourced by initial-seed.sh and demo-*.sh.
# Exposes API_URL / N8N_URL / credentials, color helpers, login_admin.

set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
N8N_URL="${N8N_URL:-http://localhost:5678}"
N8N_USER="${N8N_USER:-admin}"
N8N_PASSWORD="${N8N_PASSWORD:-admin}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123}"

if [[ -t 1 ]]; then
  green()  { printf "\033[32m%s\033[0m\n" "$*"; }
  red()    { printf "\033[31m%s\033[0m\n" "$*" >&2; }
  yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
else
  green()  { printf "%s\n" "$*"; }
  red()    { printf "%s\n" "$*" >&2; }
  yellow() { printf "%s\n" "$*"; }
fi

require_cmd() {
  for cmd in "$@"; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
      red "Missing required command: $cmd"
      exit 1
    fi
  done
}

# Hit an n8n webhook with basic auth, surface a friendly error if the
# workflow isn't Active (n8n returns 404 for inactive webhook paths).
n8n_webhook_post() {
  local path="$1"
  local body="$2"
  local response http_code
  response=$(curl -sS -w '\n%{http_code}' -X POST "${N8N_URL}/webhook/${path}" \
    -u "${N8N_USER}:${N8N_PASSWORD}" \
    -H 'Content-Type: application/json' \
    -d "$body")
  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | sed '$d')
  if [[ "$http_code" -ge 400 ]]; then
    red "n8n responded ${http_code} for /webhook/${path}"
    if [[ "$http_code" == "404" ]]; then
      red "  → the workflow is probably not Active. Open ${N8N_URL}, find the"
      red "    workflow, and toggle 'Active' on the canvas."
    fi
    if [[ -n "$body" ]]; then
      red "  body: $body"
    fi
    exit 1
  fi
  printf '%s' "$body"
}

login_admin() {
  local token
  token=$(curl -fsS -X POST "${API_URL}/auth/login" \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    -d "username=${ADMIN_USER}&password=${ADMIN_PASSWORD}" \
    | jq -r '.accessToken')
  if [[ -z "$token" || "$token" == "null" ]]; then
    red "Failed to obtain admin token from ${API_URL}/auth/login"
    exit 1
  fi
  printf '%s' "$token"
}
