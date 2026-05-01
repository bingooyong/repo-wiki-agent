#!/bin/bash
# ci/scripts/decision.sh
# Policy evaluation and decision script for repo-wiki CI

set -e

PROFILE=""
VERIFY_JSON=""
COMPARE_JSON=""
EVIDENCE_DIR=""
ALLOW_CONTINUE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --profile) PROFILE="$2"; shift 2 ;;
    --verify) VERIFY_JSON="$2"; shift 2 ;;
    --compare) COMPARE_JSON="$2"; shift 2 ;;
    --evidence) EVIDENCE_DIR="$2"; shift 2 ;;
    --allow-continue) ALLOW_CONTINUE=true; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# Default values if files don't exist
EXIT_CODE=0
GRADE="PASS"
HARD_FAILURES=0
SOFT_FAILURES=0
OVERALL_SCORE=1.0

# Extract verify results if file exists
if [ -f "$VERIFY_JSON" ]; then
  EXIT_CODE=$(python3 -c "import json; print(json.load(open('$VERIFY_JSON'))['exit_code'])" 2>/dev/null || echo "0")
  GRADE=$(python3 -c "import json; print(json.load(open('$VERIFY_JSON'))['grade'])" 2>/dev/null || echo "UNKNOWN")
  HARD_FAILURES=$(python3 -c "import json; print(json.load(open('$VERIFY_JSON')).get('summary',{}).get('hard_gate_failures',0))" 2>/dev/null || echo "0")
  SOFT_FAILURES=$(python3 -c "import json; print(json.load(open('$VERIFY_JSON')).get('summary',{}).get('soft_gate_failures',0))" 2>/dev/null || echo "0")
fi

# Extract compare results if file exists
if [ -f "$COMPARE_JSON" ]; then
  OVERALL_SCORE=$(python3 -c "import json; print(json.load(open('$COMPARE_JSON')).get('summary',{}).get('overall_score',0))" 2>/dev/null || echo "0")
fi

echo "=== Decision Gate: $PROFILE ==="
echo "Verify: exit_code=$EXIT_CODE grade=$GRADE hard=$HARD_FAILURES soft=$SOFT_FAILURES"
echo "Compare: overall_score=$OVERALL_SCORE"
echo "Evidence: $EVIDENCE_DIR"

# Decision logic based on profile
case $PROFILE in
  strict)
    if [ "$HARD_FAILURES" -gt 0 ] || [ "$SOFT_FAILURES" -gt 0 ]; then
      echo "❌ REJECTED: strict profile requires zero failures"
      echo "   hard_gate_failures: $HARD_FAILURES"
      echo "   soft_gate_failures: $SOFT_FAILURES"
      exit 1
    fi
    SCORE_THRESHOLD=0.85
    SCORE_COMPARE=$(echo "$OVERALL_SCORE < $SCORE_THRESHOLD" | bc -l 2>/dev/null || echo "0")
    if [ "$SCORE_COMPARE" = "1" ]; then
      echo "❌ REJECTED: score $OVERALL_SCORE < $SCORE_THRESHOLD"
      exit 1
    fi
    echo "✅ APPROVED: strict profile passed"
    ;;

  transitional)
    if [ "$HARD_FAILURES" -gt 0 ]; then
      echo "❌ REJECTED: hard gate failures detected"
      exit 1
    fi
    if [ "$SOFT_FAILURES" -gt 3 ]; then
      echo "❌ REJECTED: soft gate failures $SOFT_FAILURES > 3"
      exit 1
    fi
    SCORE_THRESHOLD=0.70
    SCORE_COMPARE=$(echo "$OVERALL_SCORE < $SCORE_THRESHOLD" | bc -l 2>/dev/null || echo "0")
    if [ "$SCORE_COMPARE" = "1" ]; then
      echo "⚠️ WARNING: score $OVERALL_SCORE < $SCORE_THRESHOLD"
    fi
    echo "✅ APPROVED: transitional profile passed"
    ;;

  pilot)
    if [ "$ALLOW_CONTINUE" = true ]; then
      echo "⚠️ PILOT MODE: allowing continue despite failures"
      echo "   Logged: hard=$HARD_FAILURES soft=$SOFT_FAILURES score=$OVERALL_SCORE"
    else
      if [ "$HARD_FAILURES" -gt 1 ] || [ "$SOFT_FAILURES" -gt 5 ]; then
        echo "❌ REJECTED: pilot failures exceed limits (hard>1 or soft>5)"
        exit 1
      fi
    fi
    echo "✅ CONTINUED: pilot profile"
    ;;

  *)
    echo "❌ Unknown profile: $PROFILE"
    exit 1
    ;;
esac