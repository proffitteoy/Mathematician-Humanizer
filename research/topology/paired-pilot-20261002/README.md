# Original-benchmark paired PHD pilot

Read [PAIRED_PILOT_REPORT.md](PAIRED_PILOT_REPORT.md) first. It distinguishes a 29-pair safeguarded variant from the all-32-pair upstream-algebra audit, and explains why this is not feature admission or detector integration.

## Reproduction artifacts

- `PILOT_PROTOCOL.md`: frozen pre-inference design, budgets and deviations
- `selection-manifest.json`: deterministic original-train prompt-pair selection with source hashes; no text
- `model-manifest.json`: pinned official model/config/tokenizer sources and integrity hashes
- `run_paired_pilot.py`: independent local-only encoder and estimator driver
- `recovered/phd.py`: own reviewed numerical estimator restored from style-compiler
- `analyze_paired_pilot.py`: predeclared paired/domain-stratified summary calculation
- `audit_unguarded.py`: explicitly post-hoc reconstruction of upstream algebra from saved slopes
- `paired-pilot-summary.json`, `unguarded-method-audit.json`: numerical summaries including failure denominators
- `verification.json`, `execution-manifest.json`: measured checks and provenance

The complete per-window diagnostics are retained locally as `paired-pilot-results.json`. They contain numeric energies/slopes and source hashes, no text or embeddings, but are not included in the minimal publication set. Analysis scripts require that file, either from a fresh authorized run or a reviewed numerical-results release.

## Running

This directory does not download dependencies, data or models automatically. Obtain the named original archive files and official safetensors assets under appropriate rights and permitted resource bounds. Verify them against the manifests before execution. Use the Python/package versions recorded in the execution manifest and pilot report.

With prepared local inputs:

```sh
timeout 1800s runtime/bin/python run_paired_pilot.py
OPENBLAS_NUM_THREADS=2 runtime/bin/python analyze_paired_pilot.py
OPENBLAS_NUM_THREADS=2 runtime/bin/python audit_unguarded.py
```

Do not publish `private-inputs/`, `runtime/`, `roberta-base/`, `local-hf-cache/`, or raw benchmark text/embeddings. Upstream source snapshots were inspected as text for the method audit and were not executed. The model and inference runtime are not a production dependency of style-compiler.

The next experiment is not launched automatically. First settle a fixed finite-sample/Monte Carlo stability design and the length/domain interaction question; any downstream feature-admission study needs separate held-out evidence.
