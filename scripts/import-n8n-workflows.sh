#!/bin/sh
# One-shot script run by the rot-n8n-init container.
#
# Waits for n8n to finish its initial bootstrap (tables, encryption key),
# then imports every JSON workflow under /workflows/ via the n8n CLI.
# Errors are swallowed so re-runs are idempotent.

set -e

echo "n8n-init: waiting 30s for n8n to finish bootstrap..."
sleep 30

imported=0
for f in /workflows/*.json; do
  if [ ! -f "$f" ]; then
    continue
  fi
  name=$(basename "$f")
  echo "n8n-init: importing $name"
  if n8n import:workflow --input="$f"; then
    imported=$((imported + 1))
  else
    echo "n8n-init: failed to import $name (may already exist, continuing)"
  fi
done

echo "n8n-init: done — $imported workflow(s) processed"
