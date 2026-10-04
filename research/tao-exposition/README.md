# Tao-inspired mathematical exposition: public subset

This snapshot contains a reusable writing skill, aggregate development reference distributions, original English/Chinese examples and their measurement receipts. Source: [Terence Tao’s official blog](https://terrytao.wordpress.com/), public snapshot 2026-10-04. The study inventoried 1,234 records and measured 1,114 eligible articles/pages (2,381,354 English lexical tokens). Development uses 1,040 articles; 74 were reserved by year/article for evaluating frozen descriptive rules. See `summary.json` and the skill’s corpus guide for limits.

The public subset excludes original blog text/HTML, API responses, private parse caches, source catalogue, per-article statistics, model weights and private research reports. The statistics are not evidence of authorship, imitation fidelity or mathematical correctness. Chinese has its own instrument and no Tao-specific Chinese reference corpus.

## Checks

From repository root:

- `python skills/tao-inspired-math-exposition/scripts/test_audit.py`
- `python research/tao-exposition/examples/build_reviews.py`

The second command rebuilds four evidence receipts and bounded arithmetic checks. These checks are distinct from actual linguistic measurements. The included linguistic receipts record the completed measurements; rerunning requires the pinned runtime and separately obtained model weights described in the skill. No parser/model installation is performed by these tests.

The initial English example and final example have identical words; three paragraph boundaries were revised after measuring paragraph length. Other statistical deviations remain disclosed. Original example text hashes and reference/model identities are preserved. Publication changed only the example helper’s repository-relative skill lookup.

## Rights and attribution

Original Tao prose is not redistributed. The included Chinese measurement adapter is a minimal subset of the user-authorized style-compiler project; this publication does not invent a license for upstream code. Preserve its attribution and Unicode license. Any repository-level license must respect separate third-party code, models, corpora and vector rights. Model weights and external packages are not bundled.
