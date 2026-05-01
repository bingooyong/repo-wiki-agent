#!/bin/bash
# ci/scripts/collect-evidence.sh

set -e

EVIDENCE_DIR="${1:-.repo-agent-eval/default}"
PROFILE="${2:-strict}"

mkdir -p "$EVIDENCE_DIR"/logs

# Collect verify output
if [ -f "verify-result.json" ]; then
  cp verify-result.json "$EVIDENCE_DIR/"
  echo "[$(date)] verify completed" >> "$EVIDENCE_DIR/logs/verify.log"
fi

# Collect compare output
if [ -f "compare-result.json" ]; then
  cp compare-result.json "$EVIDENCE_DIR/"
  echo "[$(date)] compare completed" >> "$EVIDENCE_DIR/logs/compare.log"
fi

# Collect profile config
if [ -f "ci/profiles/${PROFILE}.profile.yaml" ]; then
  cp "ci/profiles/${PROFILE}.profile.yaml" "$EVIDENCE_DIR/"
fi

echo "Evidence collected to: $EVIDENCE_DIR"