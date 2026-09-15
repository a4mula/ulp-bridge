#!/usr/bin/env bash
#
# ULP Bridge Publisher — ping helper for L (Local agent)
#
# Posts messages to ntfy.sh topic to wake P (Project Lead).
#
# Usage:
#   scripts/ping.sh <type> <ref>
#
# Examples:
#   scripts/ping.sh pr-ready pr:7
#   scripts/ping.sh blocked issue:14
#   scripts/ping.sh status commit:abc123
#

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_DIR="$HOME/.ulp"
TOPIC_FILE="$CONFIG_DIR/bridge-ntfy.topic"
AUDIT_LOG="$REPO_ROOT/docs/audit-log.md"

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <type> <ref>"
    echo "  type: pr-ready, blocked, status, new-task, etc."
    echo "  ref:  pr:7, issue:14, commit:abc123, etc."
    exit 1
fi

TYPE="$1"
REF="$2"

# Read topic
if [[ ! -f "$TOPIC_FILE" ]]; then
    echo "ERROR: Topic file not found at $TOPIC_FILE"
    exit 1
fi

TOPIC="$(cat "$TOPIC_FILE")"
if [[ -z "$TOPIC" ]]; then
    echo "ERROR: Topic file is empty"
    exit 1
fi

# ---------------------------------------------------------------------------
# Construct payload
# ---------------------------------------------------------------------------

TIMESTAMP="$(date -u +%FT%TZ)"
PAYLOAD="{\"v\":1,\"from\":\"local\",\"type\":\"${TYPE}\",\"ref\":\"${REF}\",\"ts\":\"${TIMESTAMP}\"}"

# ---------------------------------------------------------------------------
# POST to ntfy
# ---------------------------------------------------------------------------

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    -d "$PAYLOAD" \
    -H "Content-Type: application/json" \
    "ntfy.sh/${TOPIC}")

if [[ "$HTTP_CODE" -ne 200 && "$HTTP_CODE" -ne 201 && "$HTTP_CODE" -ne 202 && "$HTTP_CODE" -ne 200 ]]; then
    echo "ERROR: ntfy POST failed with HTTP $HTTP_CODE"
    exit 1
fi

echo "Ping sent: type=$TYPE, ref=$REF, topic=$TOPIC"

# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

if [[ -f "$AUDIT_LOG" ]]; then
    echo "" >> "$AUDIT_LOG"
    echo "## ${TIMESTAMP}" >> "$AUDIT_LOG"
    echo "" >> "$AUDIT_LOG"
    echo "${TYPE} → ${REF}" >> "$AUDIT_LOG"
    echo "  \`\`\`" >> "$AUDIT_LOG"
    echo "${PAYLOAD}" >> "$AUDIT_LOG"
    echo "  \`\`\`" >> "$AUDIT_LOG"
else
    echo "# Audit Log" > "$AUDIT_LOG"
    echo "" >> "$AUDIT_LOG"
    echo "## ${TIMESTAMP}" >> "$AUDIT_LOG"
    echo "" >> "$AUDIT_LOG"
    echo "${TYPE} → ${REF}" >> "$AUDIT_LOG"
    echo "  \`\`\`" >> "$AUDIT_LOG"
    echo "${PAYLOAD}" >> "$AUDIT_LOG"
    echo "  \`\`\`" >> "$AUDIT_LOG"
fi
