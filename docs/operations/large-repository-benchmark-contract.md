# Large Repository Fixture and Benchmark Contract

## Purpose

Stage 0 provides a deterministic fixture generator and a machine-readable measurement envelope. It validates provenance, inventory counts, hashes, environment capture, and benchmark evidence shape. It does not claim that the 10,000 effective-file or 100,000 Git-file production gates have passed.

## Fixture Layout

The fixture is a container with two separate surfaces:

```text
<fixture>/
  fixture-manifest.json
  repository/
    src/...
    vendor/generated/...
```

`repository/` is the benchmark workload. Keeping `fixture-manifest.json` outside that directory prevents control metadata from changing the requested Git-file count.

Generate a small contract fixture:

```bash
python scripts/large_repo_fixture.py \
  --output .repo-agent-eval/fixtures/scale-contract \
  --effective-files 32 \
  --git-files 64 \
  --seed 1
```

The manifest uses `repo_agent.scale_fixture/1.0` and records:

- source, generator, generated timestamp, fixture commit/revision, seed, and `repo_agent.scale_fixture_hash/1`
- requested and observed Git/effective/excluded file counts
- total workload bytes and file-type distributions
- the complete expected effective-file list and its hash
- a framed path-and-content inventory hash
- the recommended generated-file exclusion

The same seed and counts produce the same workload bytes, paths, inventory, and fixture hash at any root. `generated_at` records the invocation and is not part of the workload hash.

Synthetic fixtures default `fixture_commit` to `synthetic-seed:<seed>`; captured repository fixtures must pass their real commit or immutable revision with `--fixture-commit`. Source, generator, fixture commit, and timezone-aware generation time are required non-empty provenance values. Validation also compares requested Git/effective counts with the observed workload and rejects malformed hashes or provenance.

The generated Python, TypeScript, Go, Java, Kotlin, C#, Rust, and Markdown files use language-specific, minimally valid source forms. This makes file-type distribution evidence representative rather than satisfying counts with copied empty files or one language's syntax under unrelated extensions.

## Benchmark Evidence

Run the Stage 0 inventory benchmark:

```bash
python scripts/large_repo_benchmark.py \
  --fixture .repo-agent-eval/fixtures/scale-contract \
  --output .repo-agent-eval/benchmarks/scale-contract.json \
  --cache-policy cold \
  --provider mock/replay \
  --network-condition offline
```

The report uses `repo_agent.scale_benchmark/1.0` and includes:

- fixture provenance and stable hash
- OS, Python, Node, machine, CPU, memory, provider, model, and network condition
- exact command arguments, working directory, cache policy, and measured/warmup state
- elapsed time, peak RSS, exit code, expected/observed counts, bytes, distribution, and hashes
- explicit `contract_status`, `gating_status`, and `non_gating_reasons`

A warmup, invalid manifest, changed file, count mismatch, unavailable peak RSS, or hash mismatch is non-gating. The `stage0-contract` profile proves only that benchmark evidence is complete and internally consistent. `production_scale_gate` remains `not_evaluated` until G004 applies the measured-run counts and thresholds from AC-S01 through AC-S07.

## CI Scope

CI uses fixtures with single-digit file counts. This keeps contract regression fast while exercising the same generator, inventory framing, provenance, and benchmark schema used by later 10k/100k runs. CI must not replace production measured runs with these small samples.
