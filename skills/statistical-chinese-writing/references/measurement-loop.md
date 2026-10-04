# Executable writing loop

Run from the skill folder, or resolve all script paths relative to it. Input is a UTF-8 file, preserved byte-for-byte. All reports use exclusive creation: choose a new output name for every run. Do not edit prose after its measurement; any edit invalidates that version's receipt.

Validation evidence is in [measurement-validation.json](measurement-validation.json); attribution and redistribution limits are in [measurement-attribution.md](measurement-attribution.md).

## 1. Configure the frozen runtime

Use an existing compatible interpreter and official model directory:

```sh
export STYLE_PYTHON=/your/runtime/bin/python
export STYLE_MODELS=/your/stanza-models
python scripts/measure_text.py original.txt --source web --output original.measurement.json
```

The paths above are explicit user configuration, not a bundled dependency on the author's computer. `--python` and `--models` override those environment variables. Without a matching interpreter, packages, or models, the command writes `NOT_VERIFIED` and exits 2. It never installs or downloads anything, and never substitutes another parser. Interpreter subprocesses use `-I`, offline flags, two CPU threads and a wall timeout (default 300 seconds). Resource-limited/failed sentence parses are not complete verification.

The exact tested identity is Python 3.12.14 / Unicode 15.0.0, Stanza 1.10.1, torch 2.3.1+cpu and numpy 1.26.4. All observed dependency versions, source file hashes, five model sizes/SHA-256 hashes, immutable model URLs and model licensing notes are in `runtime-manifest.json`. This is the restored parity runtime, not the older installation-audit environment. A differing runtime remains NOT_VERIFIED even if its output looks plausible.

For a new Linux CPU environment, the user can install Python 3.12.14 from the official Python distribution, create a virtual environment, then install the pins below from official package indexes. This installation was not rerun by this skill upgrade. Availability and platform support may differ; do not silently relax pins.

```sh
python3.12 -m venv .style-runtime
.style-runtime/bin/python -m pip install torch==2.3.1+cpu --index-url https://download.pytorch.org/whl/cpu
.style-runtime/bin/python -m pip install stanza==1.10.1 numpy==1.26.4 networkx==3.3 tqdm==4.67.1 emoji==2.14.1 protobuf==6.32.1 requests==2.32.5 urllib3==2.5.0 charset-normalizer==3.4.3 idna==3.10 certifi==2025.8.3
```

Download each `models[].url` from the manifest into `MODEL_ROOT/zh-hans/<models[].path>` and `resources_manifest.url` into `MODEL_ROOT/resources.json`. The five weights total 439,803,564 bytes (not included in this small skill archive). Their immutable revision is `82f2856d1cf4f933738a8a84b5ad959d156040a0`. The resources URL contains a moving branch: only the recorded hash is accepted. The measurement command hashes every model before loading it. Never use an arbitrary model mirror or ignore a mismatch. See the model-rights caveats in `runtime-manifest.json`; package/code licensing is not blanket permission for underlying data or vectors.

## 2. Measure the unchanged original and candidate

```sh
python scripts/measure_text.py original.txt --source web --output original.measurement.json
python scripts/measure_text.py draft-v1.txt --source web --output draft-v1.measurement.json
```

Choose `--band reference` (default) or one named band from `show_reference.py`. Use the same condition throughout a comparison. Output includes all 71 actual instrument values with numerators/denominators/opportunities/missing reasons, parser audit/coverage, runtime/profile identity, and ten source-conditioned q10/q90 diagnostic rows with reference-component support. The other measured coordinates have no reference card here. Do not invent reference quantiles for them.

Statuses:
- `MEASURED`: pinned instrument ran and required reference dimensions/parse coverage are available; semantic review is still pending
- `NOT_VERIFIED`: runtime, file identity, model identity, reference, parser coverage or required measurements failed; no acceptance claim
- `BELOW_Q10`, `ABOVE_Q90`, `WITHIN_MARGINAL_Q10_Q90`: per-coordinate descriptions only, never a joint pass/fail or human score

A short text may lack windowed measures while the ten reference coordinates remain available. Report missing values, never replace them with zero or pad the text.

## 3. Diagnose, revise, remeasure

Use actual measured discrepancies to identify a few feasible changes. For example, inspect unnecessary nominal packaging when noun share is elevated; check sentence attachment/embedding for dependency span; prefer content-compatible lexical alternatives for single-Han share. These are writing hypotheses, not causal guarantees. Never invent a speaker, remove a qualification, or add negation solely to shift a coordinate. If an initial candidate has a fixable issue, produce a revised version and measure it:

```sh
python scripts/measure_text.py draft-v2.txt --source web --previous draft-v1.measurement.json --output draft-v2.measurement.json
```

Record the intended change and inspect the actual direction after parsing. A missed direction remains a miss. The old text and measurement stay frozen. A revision is a new candidate, not independent replication.

## 4. Semantic and voice gate

The model/author explicitly reconciles every content-ledger item and the user's requested voice against the original; the CLI does not understand meaning or perform independent semantic proof. Save a review bound to the exact original and final SHA-256 values:

```json
{
  "schema": "statistical-writing-semantic-review/1",
  "original_sha256": "<64 lowercase hex from original measurement>",
  "candidate_sha256": "<64 lowercase hex from final measurement>",
  "reviewer_kind": "author_self_check",
  "meaning_preserved": true,
  "voice_preserved": true,
  "unsupported_additions": false,
  "unresolved_items": [],
  "ledger": [
    {"id": "C1", "original_claim": "One explicit content obligation", "candidate_evidence": "Where and how the candidate preserves it", "verdict": "preserved"}
  ],
  "dimensional_review": [
    {"feature_id": "zh:cue.pronoun_first", "decision": "retain_for_meaning_or_voice", "reason": "Example only: the source has no first-person speaker; do not add one"}
  ]
}
```

This is a schema example, not a completed review. Use the real ledger and provide a specific retain reason for each final out-of-range dimension. Include quantities/units, dates, actors, logical connectives, negation scope, qualifications and attribution. Mark independent human review only when one actually occurred.

```sh
python scripts/check_revision.py original.measurement.json draft-v2.measurement.json --original-text original.txt --candidate-text draft-v2.txt --review draft-v2.semantic-review.json --output draft-v2.check.json
```

`MEASURED_AND_REVIEWED` means this workflow is documented. It does not mean a validated human-like/quality score, proven semantic equivalence, or all coordinates passing. Missing content review yields `NEEDS_SEMANTIC_REVIEW`; unresolved review or dimensional issues yield `NEEDS_REVISION_OR_REVIEW`. Keep revising for identified meaningful problems; do not chase all means or all marginal intervals. Deliver the exact checked bytes.

## Reuse an already frozen trusted measurement

Do not repeatedly parse unchanged originals just to redisplay statistics. `reuse_measurement.py` checks a known receipt hash, exact source bytes, profile/reference identity and full parse coverage. It labels output `MEASURED_REUSED` and explicitly records that the runtime was not reexecuted. It requires the original trusted receipt, not remembered numbers:

```sh
python scripts/reuse_measurement.py original.txt --receipt TEXT_MEASUREMENT.json --receipt-sha256 <previously-recorded-receipt-hash> --id original --source web --output original.reused.json
```

Public regression tests use synthetic text and generated receipts only. Private task inputs, revisions, and their historical receipts are excluded from this publication. Receipt reuse checks integrity and compatibility, not independent authenticity or parser correctness.

## Integrated upgrade final gate

MEASURED_AND_REVIEWED completes only this base measurement/semantic layer. For the integrated editorial workflow, continue with check_editorial_revision.py and the extended review in [lint-and-review.md](lint-and-review.md). Only MEASURED_AND_EDITORIALLY_REVIEWED completes both layers. A pass remains documented self-review, not semantic proof.
