# Testable generic writing prototype v0.1

A usable host-LLM writing skill plus executable local diagnosis/checking workflow, four original Chinese demonstrations, every full candidate (including failures), and actual local analyzer outputs. It is not the final learned multi-view Style Compiler, a human/AI detector, or evidence that stage one has passed.

## Quick test

Ask a capable coding assistant to use SKILL.md on your own input, or run the preparation command yourself:

```sh
cd path/to/style-writing-prototype
python scripts/workflow.py prepare input.txt --genre technical_commentary --output work/job.json
```

The host assistant fills source-grounded commitments, proposes full rewrites, records independent semantic review, then runs finalize. This separation is deliberate: the Python code does not pretend to contain a trained generator. Running prepare alone gives a diagnosis and job shell, not a rewritten article. The complete worked jobs are immediately runnable:

```sh
python scripts/workflow.py finalize examples/mathematical-explanation.json \
  --measurements measurements-compact --output reports/math-replay.json
python -m unittest discover -s tests -v
```

For fresh full linguistic measurements, set STYLE_PYTHON to your existing Stanza-enabled Python executable and STYLE_STANZA_MODELS to your existing verified model directory. No automatic installation or download occurs:

```sh
"$STYLE_PYTHON" scripts/analyze.py input.txt \
  --models "$STYLE_STANZA_MODELS" \
  --output work/analysis.json
```

The pinned local parser is Stanza 1.10.1 / zh-hans GSDSimp nocharlm resources 1.10.0. When installed under a repository (for example skills/style-writing-prototype), the runner discovers the containing checkout via research/linguistic/adapter.py and src/style_compiler. A standalone copy falls back to ../style-compiler. Use --research /path/to/style-compiler to override. The standard Python interpreter can replay cached measurements and perform new surface-only analysis. Missing models/dependencies are disclosed rather than downloaded. No installation is required for the standard-library path.

## What to inspect

- SKILL.md: the actionable workflow
- EXAMPLES.zh.md: originals, selected complete outputs, semantic commitments, changes and measurements
- FAILURE_ANALYSIS.zh.md: retained failures and candid limitations
- examples/*.json: full light/structural/repaired candidates and exact review records
- reports/*.final.txt: the four selected full texts. Full execution records can be recreated with finalize; local *.result.json files are not necessary for publication
- measurements-compact/*.json: exact-text-bound global 71-channel values with opportunities/missingness, separate eight-metric surface summaries, selected sentence diagnostics, parser identity and SHA-256 of the full local bundle. Raw token graphs and full 71-channel sentence vectors are deliberately omitted
- Full measurements/*.json remain in the original local delivery directory and are excluded from the publication package; compact files are summaries, not full analyzer bundles
- examples/*.json embeds the independent model review records, not human judgments; raw reviewer reports remain in the local delivery directory

All demonstration inputs were newly authored for this task. They are not human reference texts, empirical controlled-test inputs, held-out evaluation data, or personal writings. The initial candidate pass was drafted before analyzer results; final repaired candidates and explicit intervention plans were produced after inspecting measurements and independent failure reports. This is a transparent demonstration of the workflow, not a randomized measurement-driven intervention study.

## Still missing

A trained joint style model, fitted sequence/discourse dynamics, learned rewrite policy, empirical causal effects of interventions, calibrated semantic validation, and human indistinguishability evidence. The learned 12-descriptor condition classifier is neither imported nor called. Current choices are declared editorial hypotheses implemented by the host language model. No files in the research checkout are changed and no remote writes occur.

## Failure behavior

Changed protected formulas/numbers, review failures, stale bindings, missing per-claim evidence, and all-candidate rejection stop final selection. An unchanged original remains available. Passing only establishes that these checks and the recorded review passed, not that the prose is factually correct or human-like. Owner testing is still required.
