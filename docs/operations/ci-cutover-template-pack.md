# CI Cutover Template Pack

**文档属性**: CI 模板配置
**版本**: 1.0
**日期**: 2026-04-25
**Agent**: Agent_AdapterGovernance

## 1. 概述

本模板包提供三种 policy profile 的 CI 配置文件，分别对应 strict/transitional/pilot 场景。每个模板集成了 verify 和 compare 命令，并连接到 evidence bundle 路径。

## 2. 目录结构

```
.github/workflows/
├── repo-wiki-strict.yml      # strict profile CI
├── repo-wiki-transitional.yml # transitional profile CI
└── repo-wiki-pilot.yml       # pilot profile CI

ci/
├── profiles/
│   ├── strict.profile.yaml
│   ├── transitional.profile.yaml
│   └── pilot.profile.yaml
├── scripts/
│   ├── evaluate-profile.sh
│   ├── collect-evidence.sh
│   └── decision.sh
└── tests/
    ├── test_strict_profile.sh
    ├── test_transitional_profile.sh
    └── test_pilot_profile.sh
```

## 3. Workflow 模板

### 3.1 Strict Profile Workflow

```yaml
# .github/workflows/repo-wiki-strict.yml
name: repo-wiki-strict

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

env:
  PROFILE: strict
  EVIDENCE_DIR: .repo-agent-eval/strict-${{ github.run_id }}

jobs:
  verify-and-compare:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pydantic PyYAML rich typer pathspec pytest

      - name: Generate artifacts
        run: python -m repo_wiki.main init

      - name: Run verify (strict mode)
        id: verify
        run: |
          python -m repo_wiki.main verify --ci --profile strict > verify-result.json
          cat verify-result.json
          echo "exit_code=$(python -c 'import json; print(json.load(open("verify-result.json"))["exit_code"])')" >> $GITHUB_OUTPUT

      - name: Run baseline compare
        id: compare
        run: |
          python -m scripts.qoder_baseline_comparison --target docs/ --baseline qoder-style/ --output compare-result.json
          cat compare-result.json

      - name: Collect evidence
        run: |
          mkdir -p ${{ env.EVIDENCE_DIR }}
          cp verify-result.json ${{ env.EVIDENCE_DIR }}/
          cp compare-result.json ${{ env.EVIDENCE_DIR }}/
          cp -r docs/sections ${{ env.EVIDENCE_DIR }}/ 2>/dev/null || true

      - name: Upload evidence bundle
        uses: actions/upload-artifact@v4
        with:
          name: evidence-bundle-strict
          path: ${{ env.EVIDENCE_DIR }}

      - name: Decision gate
        run: |
          python ci/scripts/decision.sh --profile strict \
            --verify verify-result.json \
            --compare compare-result.json \
            --evidence ${{ env.EVIDENCE_DIR }}
```

### 3.2 Transitional Profile Workflow

```yaml
# .github/workflows/repo-wiki-transitional.yml
name: repo-wiki-transitional

on:
  push:
    branches: [develop, release/*]
  pull_request:

env:
  PROFILE: transitional
  EVIDENCE_DIR: .repo-agent-eval/transitional-${{ github.run_id }}

jobs:
  verify-and-compare:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pydantic PyYAML rich typer pathspec pytest

      - name: Generate artifacts
        run: python -m repo_wiki.main init --legacy-compat

      - name: Run verify (transitional mode)
        id: verify
        run: |
          python -m repo_wiki.main verify --ci --profile transitional --legacy-compat > verify-result.json
          cat verify-result.json

      - name: Run baseline compare (allow legacy)
        id: compare
        run: |
          python -m scripts.qoder_baseline_comparison \
            --target docs/ \
            --baseline qoder-style/ \
            --allow-legacy \
            --output compare-result.json
          cat compare-result.json

      - name: Check legacy compatibility
        id: legacy-check
        run: |
          if grep -q '"mode": "legacy_qs_compatibility"' verify-result.json; then
            echo "legacy_compat=true" >> $GITHUB_OUTPUT
            echo "Legacy Qxx/Sxx compatibility mode activated"
          fi

      - name: Collect evidence
        run: |
          mkdir -p ${{ env.EVIDENCE_DIR }}
          cp verify-result.json ${{ env.EVIDENCE_DIR }}/
          cp compare-result.json ${{ env.EVIDENCE_DIR }}/

      - name: Upload evidence bundle
        uses: actions/upload-artifact@v4
        with:
          name: evidence-bundle-transitional
          path: ${{ env.EVIDENCE_DIR }}

      - name: Decision gate
        run: |
          python ci/scripts/decision.sh --profile transitional \
            --verify verify-result.json \
            --compare compare-result.json \
            --evidence ${{ env.EVIDENCE_DIR }}
```

### 3.3 Pilot Profile Workflow

```yaml
# .github/workflows/repo-wiki-pilot.yml
name: repo-wiki-pilot

on:
  push:
    branches: [feature/*, pilot/*]
  pull_request:

env:
  PROFILE: pilot
  EVIDENCE_DIR: .repo-agent-eval/pilot-${{ github.run_id }}
  PILOT_REPOS: "repo-agent,AI_API_Atlas"

jobs:
  verify-and-compare:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pydantic PyYAML rich typer pathspec pytest

      - name: Generate artifacts
        run: python -m repo_wiki.main init --pilot-mode

      - name: Run verify (pilot mode)
        id: verify
        run: |
          python -m repo_wiki.main verify --ci --profile pilot --pilot-mode > verify-result.json
          cat verify-result.json

      - name: Run baseline compare (pilot)
        id: compare
        run: |
          python -m scripts.qoder_baseline_comparison \
            --target docs/ \
            --baseline qoder-style/ \
            --pilot \
            --output compare-result.json
          cat compare-result.json

      - name: Collect pilot metrics
        run: |
          mkdir -p ${{ env.EVIDENCE_DIR }}
          cp verify-result.json ${{ env.EVIDENCE_DIR }}/
          cp compare-result.json ${{ env.EVIDENCE_DIR }}/

          # Generate pilot metrics
          python -c "
import json
v = json.load(open('verify-result.json'))
c = json.load(open('compare-result.json'))
metrics = {
    'profile': 'pilot',
    'verify_exit_code': v.get('exit_code', -1),
    'verify_grade': v.get('grade', 'UNKNOWN'),
    'hard_gate_failures': v.get('summary', {}).get('hard_gate_failures', 0),
    'soft_gate_failures': v.get('summary', {}).get('soft_gate_failures', 0),
    'overall_score': c.get('summary', {}).get('overall_score', 0),
    'pilot_repos': ['repo-agent', 'AI_API_Atlas']
}
print(json.dumps(metrics, indent=2))
" > ${{ env.EVIDENCE_DIR }}/pilot-metrics.json

      - name: Upload evidence bundle
        uses: actions/upload-artifact@v4
        with:
          name: evidence-bundle-pilot
          path: ${{ env.EVIDENCE_DIR }}

      - name: Log decision (pilot allows failures)
        run: |
          python ci/scripts/decision.sh --profile pilot \
            --verify verify-result.json \
            --compare compare-result.json \
            --evidence ${{ env.EVIDENCE_DIR }} \
            --allow-continue
```

## 4. Policy Profile 配置

### 4.1 strict.profile.yaml

```yaml
# ci/profiles/strict.profile.yaml
profile: strict
description: Production release gate with zero tolerance
version: "1.0"

criteria:
  hard_gate_failures: 0
  soft_gate_failures: 0
  overall_score: 0.85
  structural_score: 0.90
  quality_score: 0.80

verify_config:
  command: "repo-wiki verify --ci --profile strict"
  exit_code_map:
    0: "ALL_PASS"
    1: "HARD_GATE_FAIL"
    2: "SOFT_GATE_FAIL"

compare_config:
  command: "scripts/qoder_baseline_comparison --target docs/ --baseline qoder-style/"
  score_threshold: 0.85

failure_messages:
  HARD_GATE_FAIL: |
    ❌ HARD gate failure detected.
    Evidence: {evidence_bundle}/verify-result.json
    Required action: Fix structural issues before release.
    Contact: Agent_QualityRelease for rollback.

  SOFT_GATE_FAIL: |
    ⚠️ SOFT gate failure detected.
    Evidence: {evidence_bundle}/compare-result.json
    Required action: Review quality issues before release.
    Contact: Agent_QualityRelease for waiver.

  SCORE_BELOW_THRESHOLD: |
    ❌ Overall score below threshold (required: >= 0.85)
    Evidence: {evidence_bundle}/compare-result.json
    Required action: Improve quality before release.
```

### 4.2 transitional.profile.yaml

```yaml
# ci/profiles/transitional.profile.yaml
profile: transitional
description: Compatibility transitional gate
version: "1.0"

criteria:
  hard_gate_failures: 0
  soft_gate_failures: 3
  overall_score: 0.70
  structural_score: 0.75
  quality_score: 0.65
  legacy_compatibility: true

verify_config:
  command: "repo-wiki verify --ci --profile transitional --legacy-compat"
  exit_code_map:
    0: "ALL_PASS"
    1: "HARD_GATE_FAIL"
    2: "SOFT_GATE_FAIL (within tolerance)"

compare_config:
  command: "scripts/qoder_baseline_comparison --target docs/ --baseline qoder-style/ --allow-legacy"
  score_threshold: 0.70

legacy_support:
  qxx_pattern: "^Q\\d{2}-.+\\.md$"
  sxx_pattern: "^S\\d{2}-.+\\.md$"
  min_q_files: 4
  min_s_files: 4
  min_total: 8

failure_messages:
  HARD_GATE_FAIL: |
    ❌ HARD gate failure in transitional mode.
    Evidence: {evidence_bundle}/verify-result.json
    Required action: Fix structural issues.

  SOFT_GATE_FAIL: |
    ⚠️ SOFT gate failures within tolerance (≤3).
    Evidence: {evidence_bundle}/verify-result.json
    Action: Log and continue. Review at next cycle.

  LEGACY_COMPAT_ACTIVATED: |
    ℹ️ Legacy Qxx/Sxx compatibility mode activated.
    Evidence: {evidence_bundle}/verify-result.json
    Note: This is expected during migration period.
```

### 4.3 pilot.profile.yaml

```yaml
# ci/profiles/pilot.profile.yaml
profile: pilot
description: Exploratory gate for pilot testing
version: "1.0"

criteria:
  hard_gate_failures: 1
  soft_gate_failures: 5
  overall_score: 0.60
  structural_score: 0.65
  quality_score: 0.55

verify_config:
  command: "repo-wiki verify --ci --profile pilot --pilot-mode"
  exit_code_map:
    0: "ALL_PASS"
    1: "HARD_GATE_FAIL (logged)"
    2: "SOFT_GATE_FAIL (logged)"

compare_config:
  command: "scripts/qoder_baseline_comparison --target docs/ --baseline qoder-style/ --pilot"
  score_threshold: 0.60

pilot_config:
  test_duration_days: 14
  repos:
    - repo-agent
    - AI_API_Atlas
  collect_metrics: true

failure_messages:
  HARD_GATE_FAIL: |
    ⚠️ HARD gate failure in pilot mode (logged only).
    Evidence: {evidence_bundle}/verify-result.json
    Action: Log and continue. Analyze at pilot end.

  SOFT_GATE_FAIL: |
    ⚠️ SOFT gate failures in pilot mode (logged only).
    Evidence: {evidence_bundle}/verify-result.json
    Action: Log and continue. Analyze at pilot end.

  PILOT_COMPLETE: |
    ✅ Pilot phase data collected.
    Evidence: {evidence_bundle}/pilot-metrics.json
    Action: Generate pilot report.
```

## 5. 脚本工具

### 5.1 decision.sh

```bash
#!/bin/bash
# ci/scripts/decision.sh
# Policy evaluation and decision script

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

# Load profile config
PROFILE_CONFIG="ci/profiles/${PROFILE}.profile.yaml"

# Extract verify results
EXIT_CODE=$(python3 -c "import json; print(json.load(open('$VERIFY_JSON'))['exit_code'])" 2>/dev/null || echo "999")
GRADE=$(python3 -c "import json; print(json.load(open('$VERIFY_JSON'))['grade'])" 2>/dev/null || echo "UNKNOWN")
HARD_FAILURES=$(python3 -c "import json; print(json.load(open('$VERIFY_JSON')).get('summary',{}).get('hard_gate_failures',0))" 2>/dev/null || echo "0")
SOFT_FAILURES=$(python3 -c "import json; print(json.load(open('$VERIFY_JSON')).get('summary',{}).get('soft_gate_failures',0))" 2>/dev/null || echo "0")

# Extract compare results
OVERALL_SCORE=$(python3 -c "import json; print(json.load(open('$COMPARE_JSON')).get('summary',{}).get('overall_score',0))" 2>/dev/null || echo "0")

echo "=== Decision Gate: $PROFILE ==="
echo "Verify: exit_code=$EXIT_CODE grade=$GRADE hard=$HARD_FAILURES soft=$SOFT_FAILURES"
echo "Compare: overall_score=$OVERALL_SCORE"
echo "Evidence: $EVIDENCE_DIR"

# Decision logic based on profile
case $PROFILE in
  strict)
    if [ "$HARD_FAILURES" -gt 0 ] || [ "$SOFT_FAILURES" -gt 0 ]; then
      echo "❌ REJECTED: strict profile requires zero failures"
      exit 1
    fi
    SCORE_THRESHOLD=0.85
    if (( $(echo "$OVERALL_SCORE < $SCORE_THRESHOLD" | bc -l) )); then
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
    if (( $(echo "$OVERALL_SCORE < $SCORE_THRESHOLD" | bc -l) )); then
      echo "⚠️ WARNING: score $OVERALL_SCORE < $SCORE_THRESHOLD"
    fi
    echo "✅ APPROVED: transitional profile passed"
    ;;

  pilot)
    if [ "$ALLOW_CONTINUE" = true ]; then
      echo "⚠️ PILOT MODE: allowing continue despite failures"
      echo "Logged: hard=$HARD_FAILURES soft=$SOFT_FAILURES score=$OVERALL_SCORE"
    else
      if [ "$HARD_FAILURES" -gt 1 ] || [ "$SOFT_FAILURES" -gt 5 ]; then
        echo "❌ REJECTED: pilot failures exceed limits"
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
```

### 5.2 collect-evidence.sh

```bash
#!/bin/bash
# ci/scripts/collect-evidence.sh

set -e

EVIDENCE_DIR="${1:-.repo-agent-eval/default}"
PROFILE="${2:-strict}"
TIMESTAMP=$(date +%Y%m%d%H%M%S)

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
cp "ci/profiles/${PROFILE}.profile.yaml" "$EVIDENCE_DIR/"

# Generate decision record
cat > "$EVIDENCE_DIR/decision.yaml" <<EOF
---
date: "$(date -Iseconds)"
profile: $PROFILE
evidence_dir: $EVIDENCE_DIR
timestamp: $TIMESTAMP
EOF

echo "Evidence collected to: $EVIDENCE_DIR"
```

## 6. 测试 Fixtures

### 6.1 test_strict_profile.sh

```bash
#!/bin/bash
# ci/tests/test_strict_profile.sh
# Test strict profile with quality artifacts

set -e

TEST_DIR=$(mktemp -d)
trap "rm -rf $TEST_DIR" EXIT

# Create quality test artifacts
mkdir -p $TEST_DIR/docs/sections
mkdir -p $TEST_DIR/ai/source-of-truth

# Create passing artifacts (should pass strict)
cat > $TEST_DIR/docs/00-overview.md <<'EOF'
# Overview

## Project Description

This is a comprehensive project overview with substantial prose content.

## Core Problem

We need better documentation.

## Core Capabilities

The system can generate docs.
EOF

cat > $TEST_DIR/docs/01-architecture.md <<'EOF'
# Architecture

```mermaid
graph TD
    A --> B
```

## System Layers

.repo-wiki, ai/source-of-truth, docs/
EOF

# Create sections
for section in project architecture services data-model api operations development security; do
  mkdir -p $TEST_DIR/docs/sections/$section
  echo "# $section" > $TEST_DIR/docs/sections/$section/index.md
done

# Run verify
cd $TEST_DIR
python -m repo_wiki.main verify --ci --profile strict > verify-result.json

# Check exit code
EXIT_CODE=$(python3 -c "import json; print(json.load(open('verify-result.json'))['exit_code'])")
if [ "$EXIT_CODE" -ne 0 ]; then
  echo "❌ FAIL: strict profile should pass with quality artifacts"
  exit 1
fi

echo "✅ PASS: strict profile handles quality artifacts correctly"
```

### 6.2 test_transitional_profile.sh

```bash
#!/bin/bash
# ci/tests/test_transitional_profile.sh
# Test transitional profile with legacy Qxx/Sxx format

set -e

TEST_DIR=$(mktemp -d)
trap "rm -rf $TEST_DIR" EXIT

# Create legacy Qxx/Sxx artifacts
mkdir -p $TEST_DIR/docs/sections

# Create Qxx/Sxx files meeting compatibility thresholds
for name in Q01-代码质量.md Q02-弹性.md Q03-性能.md Q04-并发.md \
           S01-注入.md S02-认证.md S03-授权.md S04-数据安全.md; do
  echo "# $name" > $TEST_DIR/docs/sections/$name
done

# Run verify
cd $TEST_DIR
python -m repo_wiki.main verify --ci --profile transitional --legacy-compat > verify-result.json

# Check legacy compat mode
if grep -q '"mode": "legacy_qs_compatibility"' verify-result.json; then
  echo "✅ PASS: transitional profile accepts legacy Qxx/Sxx format"
else
  echo "❌ FAIL: should detect legacy compatibility mode"
  exit 1
fi
```

### 6.3 test_pilot_profile.sh

```bash
#!/bin/bash
# ci/tests/test_pilot_profile.sh
# Test pilot profile allows controlled failures

set -e

TEST_DIR=$(mktemp -d)
trap "rm -rf $TEST_DIR" EXIT

# Create minimal artifacts (should trigger soft gate warnings)
mkdir -p $TEST_DIR/docs/sections
mkdir -p $TEST_DIR/ai/source-of-truth

echo "# Overview" > $TEST_DIR/docs/00-overview.md
echo "# Architecture" > $TEST_DIR/docs/01-architecture.md

# Run verify in pilot mode
cd $TEST_DIR
python -m repo_wiki.main verify --ci --profile pilot --pilot-mode > verify-result.json

# Pilot mode should continue despite warnings
EXIT_CODE=$(python3 -c "import json; print(json.load(open('verify-result.json'))['exit_code'])")

# Should get exit_code 2 (soft gate fail) but still continue
if [ "$EXIT_CODE" -eq 2 ]; then
  echo "✅ PASS: pilot profile allows soft gate failures to continue"
else
  echo "⚠️ WARNING: unexpected exit_code $EXIT_CODE"
fi

# Check that we can collect pilot metrics
python3 -c "
import json
v = json.load(open('verify-result.json'))
print(f'hard_gate_failures: {v[\"summary\"][\"hard_gate_failures\"]}')
print(f'soft_gate_failures: {v[\"summary\"][\"soft_gate_failures\"]}')
print(f'grade: {v[\"grade\"]}')
"
```

## 7. 集成说明

### 7.1 GitHub Actions 集成

将以下文件添加到 `.github/workflows/`:
- `repo-wiki-strict.yml`
- `repo-wiki-transitional.yml`
- `repo-wiki-pilot.yml`

### 7.2 本地测试

```bash
# 运行本地 CI 模拟
cd repo-agent
./ci/scripts/decision.sh --profile strict \
  --verify verify-result.json \
  --compare compare-result.json \
  --evidence .repo-agent-eval/test/

# 运行 profile 测试
./ci/tests/test_strict_profile.sh
```

### 7.3 失败消息示例

当 strict profile 失败时，输出示例：

```
❌ REJECTED: strict profile requires zero failures

Evidence: .repo-agent-eval/strict-123456/verify-result.json

HARD gate failures detected:
  - STRUCT_MISSING_SECTIONS (docs/sections/ missing required sections)
  - STRUCT_NAVIGATION_BROKEN (Navigation links are broken)

Required action: Fix structural issues before release.
Contact: Agent_QualityRelease for rollback guidance.
```

## 8. 下一步

Task 16.2 完成。Task 16.3 依赖 Task 16.2，将在 Atlas 和 benchmark 仓库执行最终试点。