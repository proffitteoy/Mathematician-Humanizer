---
name: style-compiler
description: Measure Chinese writing with the local Style Compiler research modules and inspect constrained editing candidates. Use for stylometry research, sentence/paragraph diagnostics, or testing this project's writing skill; no validated human/AI detector or personal voice model is currently supplied.
---

# Style Compiler

Read the repository's `README.md` for current implementation status and `docs/ACCEPTANCE.zh.md` for the two-stage, owner-judged acceptance target. Distinguish executable measurements, empirical measurement checks, trained models and demonstrated writing benefit; none substitutes for another.

## Choose the implemented path

- For the standard-library core, accept the local document contract in `schemas/document.schema.json`; run `style-compiler extract` or `PYTHONPATH=src python -m style_compiler extract`. Return measures, opportunities, evidence, missing reasons and comparison eligibility. Character counts are not Chinese word tokens.
- For POS, dependency and lexical measurements, read `research/linguistic/README.zh.md`. The separate71-channel module and pinned local Stanza path exist; no download or installation is implicit. Exact source spans, discontinuities, parser/profile identity and per-channel opportunities are mandatory. Do not promote parser-derived counts to validated style constructs. Read `research/parser_error/PUBLICATION_STATUS.zh.md` when interpreting their reliability.
- For topology, read `research/topology/README.md`. Use the existing pinned local encoder and stated numerical profile only when available. Short-text abstention, duplicate points, truncation and sampling are part of the result. PHD is neither a writing-quality target nor evidence of human origin. Full-text contextual embeddings are not valid prefix observations.
- The learned multi-view prototype in `research/learned/README.md` remains synthetic-only unless a separately reviewed real-data protocol and release explicitly changes that status. Do not feed real observations by relabeling them as synthetic fixtures or advertise unfitted weights as a learned style distribution.

## Editing experiments

The implemented core planner can propose a single newline insertion when a paragraph sentence-count constraint is supplied: `plan --max-sentences N`. Inspect its exact candidate, protect the document's invariant strings and preserve rollback. Use `apply --semantic-review-approved` only after the caller's explicit approval of that candidate's meaning and task fit. A measured delta does not predict better prose.

For an ordinary rewrite or generation request beyond that operation, disclose that the current compiled rewrite policy is not yet empirically learned. An independently generated baseline draft can be useful for testing, but label it accordingly; do not claim an unavailable compiler/ranker produced it. Never invent fitted percentiles, human probabilities, author profiles, reference bands or a successful meaning check.

## Research and personal stage

Use `docs/research-protocol.md` and the current learned-model design for real-data admission, lawful source use, work/lineage splits and held-out evaluation. Do not silently tune on a published diagnostic slice. No external generation spend, model download, raw-text upload or remote repository mutation occurs as a side effect of invoking this skill.

The project owner has conditionally authorized personal-stage work once the generic stage is defensibly ready for acceptance; the exact current condition is in `docs/ACCEPTANCE.zh.md`. This does not itself assert that the condition has been met or that a personal implementation exists. Before reading the owner's writings, check the recorded stage decision and a reviewed personal-data implementation. Preserve unknowns and content, including mathematical hypotheses and logical scope. Final acceptance remains the owner's decision.


## Integrated writing skills

For Chinese drafting or revision, use [statistical-chinese-writing](../../../skills/statistical-chinese-writing/SKILL.md): source-conditioned aggregate references, pinned measurement and explicit semantic/editorial review. For mathematical exposition and learning notes, use [tao-inspired-math-exposition](../../../skills/tao-inspired-math-exposition/SKILL.md), preserving its language and corpus limitations. Neither skill is a trained rewriting policy, quality validator, authorship detector, or personal voice model. See [publication scope and checks](../../../docs/writing-skills-publication-20261004.md).

