# Integrated writing skills: public release, 2026-10-04

## Start here

- [Statistical Chinese writing](../skills/statistical-chinese-writing/SKILL.md): source-conditioned aggregate statistical reference cards, pinned measurement/re-measurement, semantic ledger, editorial layers, immutable-span protection, non-mutating prose lint and a strict review gate.
- [Tao-inspired mathematical exposition](../skills/tao-inspired-math-exposition/SKILL.md): genre-aware mathematical organization, condition/quantifier checks, explanatory examples, English article-level reference profiles and a separate Chinese instrument. This is an original exposition workflow, not author impersonation.

The existing compiler/research modules and older candidate skills are retained. These additions do not declare the learned rewriting policy, personal style model, human quality validation or project acceptance complete.

## Humanizer adaptation

The [source-by-source catalog](../skills/statistical-chinese-writing/references/humanizer-integration.md) covers task calibration, meaning and claim ledgers, voice/reader calibration, content selection, openings and endings, stance, rhythm, terminology, attribution, typography, multilingual caveats, protected spans, diagnosis, review and regression testing. Each adoption remains conditional on meaning, voice and genre. The implementation rejects detector-evasion scores and forced randomness, errors or invented personal experiences.

Sources are pinned with their applicable notices. No upstream repository was installed or executed as part of this release; the new checking code is independently implemented. The original repository's absence of a general software-license grant remains unchanged; third-party notices do not license the entire project.

## Publication boundary

This release includes skill instructions, executable source, license notices, aggregate reference statistics, original fictional/synthetic examples and public-safe tests. It excludes private task inputs, their rewrites and historical receipts, private blog caches, raw source corpus and Tao article bodies, parser caches, credentials and model weights. The optional private-input regression was replaced with a generated synthetic receipt reuse test. No private examples are needed for public unit tests.

## Checks and interpretation

Run from the repository root:

```sh
python -m unittest discover -s skills/statistical-chinese-writing/tests -v
python skills/tao-inspired-math-exposition/scripts/test_audit.py
python research/tao-exposition/examples/build_reviews.py
```

The public Chinese subset passes 41 tests with no skips, including fail-closed instrumentation/profile checks, malformed/partial receipts, protected spans, editorial review and synthetic receipt reuse. Tests use synthetic fixtures and do not establish writing quality or rerun full-corpus parsing. Existing aggregate cards retain their original provenance. Live statistical measurement still needs the external pinned runtime and model files; missing dependencies must produce an explicit unavailable result rather than a fabricated score.

The Tao evidence-contract script passes 6 positive/negative cases. Four original-example audit receipts and bounded mathematical checks were rebuilt successfully in the public layout. Linguistic receipts are preserved historical measurements; they were not relabeled as newly executed NLP results.
