---
name: style-compiler
description: Run the local Style Compiler's character-level writing measurements and propose review-gated paragraph-boundary edits. Use for Chinese-first stylometry research or an explicitly requested structural editing experiment; it does not identify authors, detect AI, or supply a personal voice model.
---

# Style Compiler

This repository is an experimental research core. Read `README.md` and `docs/architecture.md` from its root for current commands, projections and limits. Do not represent implemented arithmetic as construct validation or completed empirical research.

Accept only a local document satisfying `schemas/document.schema.json`. Use `style-compiler extract` (or `PYTHONPATH=src python -m style_compiler extract`) and report raw measures with sentence/paragraph evidence, comparison eligibility and missing reasons. Character counts are not Chinese word tokens. Optional parser, embedding, reference and personal-style capabilities are unavailable.

When the user supplies a paragraph sentence-count constraint, `plan --max-sentences N` can propose one newline insertion. Describe it as experimental, inspect the exact candidate and preserve protected strings. Measured candidate deltas do not predict writing benefit. Only use `apply --semantic-review-approved` after the caller explicitly approves the candidate's meaning and task fit. Preserve the original for rollback.

For a research design, read `docs/research-protocol.md`. Fit only a provenance/rights-reviewed real non-personal corpus with a validated leakage-safe split; the tool abstains when support is absent. Never fabricate fitted distributions, percentiles, probabilities, author profiles or intervention effects. No source detector or detector-evasion objective exists.

Personalization remains disabled. Do not inspect personal writings or `proffitteoy/nothing-new` until explicit final-personalization authorization; that future authorization also requires a separately reviewed implementation. Do not download unverified-license corpora, install models, spend on external generation, or mutate a remote repository as a side effect of invoking this skill.
