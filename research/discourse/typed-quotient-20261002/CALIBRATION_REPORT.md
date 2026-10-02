# Exposed-panel calibration of the typed identity-bridge quotient

## Main findings

The narrowly specified quotient is mechanically invariant under its intended encoding transformations. It does **not** make the two supplied annotations of a document agree. All five paired quotient trees remain nonidentical. The correct next modeling object is an ordered, typed source-plus-hierarchy view with explicit measurement uncertainty, not a collection of native graph counts selected for apparent stability.

A particularly informative result is that removing certified identity bridges does not uniformly shrink annotation differences. Mean EDU-depth discrepancy increases from 0.4887 native hops to 0.5314 quotient hops, and boundary-LCA-depth discrepancy increases from 0.3685 to 0.4910. That is compatible with correct canonicalization: invariance and inter-annotation agreement are different requirements.

## Scope and verified preservation

- The same 10 already exposed GCDT documents, containing 2,237 primary EDUs, 666 released sentences and 275 blank-line source blocks
- Five documents have a second released discourse annotation; 15 graphs in all
- Pinned dataset commit: 6846a7e21a3a91f29e1376fe4a0f27c4810f2f51
- 45 existing cached inputs rechecked against both SHA-256 and their recorded Git blob hashes
- No new data/model download, fitting, rewriting, owner-text use, remote write, or publication performed
- Earlier frozen outputs and independent-audit files remained byte-for-byte unchanged

Across all 15 graphs, 1,410 certified unary span identity bridges were removed: 6,351 native vertices became 4,941 quotient vertices. The 10 primary quotient graphs contain 3,312 vertices and 1,075 groups. The five primary/alternate paired graphs contain 1,607/1,629 vertices and 515/537 groups, respectively. There are zero unknown-role edges in the full 15-graph replay.

Every graph passed idempotence, ID/declaration-order invariance, double identity-bridge expansion, anchor/order/source-layer retention, surviving-yield retention, non-span label/role conservation, and invariant feature/signature comparison. Thirteen explicit synthetic tests cover valid invariance and prohibited transformations, including multinuclear flattening, N/S reversal, block-type change, unknown semantic attributes, segment carriers with dependents, and straddled source boundaries. Schema checks reject unmodeled metadata instead of dropping it.

## Residual paired sensitivity

All values below are unweighted means over five document pairs. The ten document-rank comparisons share documents and are not independent trials. Percentage-point differences apply to fractions, not relative percent changes.

| Observable | Mean absolute difference | Maximum absolute difference | Rank reversals / 10 |
|---|---:|---:|---:|
| Quotient mean EDU attachment depth | 0.5314 hops | 1.0143 hops | 2 |
| Quotient mean source-block-boundary LCA depth | 0.4910 hops | 0.8378 hops | 1 |
| Quotient group source-block-crossing fraction | 2.4114 pp | 4.6289 pp | 3 |
| Boundary LCA yield fraction | 3.4185 pp | 8.5784 pp | 2 |
| Non-span labelled-attachment satellite share | 3.0080 pp | 6.8497 pp | 0 |

There were no tie changes for these five observables. The paired set has 143 source-block boundaries, all aligned between distinct EDUs in both releases. The full 10-primary set has 265 boundaries, also all aligned. The implementation explicitly marks a straddled boundary's LCA statistic missing; the synthetic suite tests that case.

The last two observables are already invariant to identity bridges before explicit contraction. The first three require quotient evaluation to achieve that invariance. This distinction follows from their definitions, not from apparent stability in these data.

The earlier frozen result of 7/10 rank reversals for **native** group crossing remains unchanged and correct. Its 3/10 quotient counterpart reproduces the independent audit's narrow-contraction diagnostic. These are different estimands with different denominators. The change is not a causal attribution of four reversals to encoding, not evidence that three is the true semantic instability, and not a reason to overwrite the frozen metric.

## What the exact typed comparison adds

The stronger canonical-tree equality check is false for all five annotation pairs. Pure ID renaming and certified identity bridges therefore do not explain all observed differences under the declared object.

Two lossy signature summaries provide detail:

| Declared signature | Macro F1 | Pooled F1 | Matches / primary / alternate |
|---|---:|---:|---:|
| Typed carrier: yield, type/attributes, anchor | 75.2448% | 75.5253% | 1,222 / 1,607 / 1,629 |
| Non-span attachment scope: both typed endpoints, label/type/role | 34.4060% | 34.6314% | 498 / 1,436 / 1,440 |

These are exact multiset overlaps, not graph-isomorphism scores, Parseval, parser accuracy, independently validated rhetorical relation accuracy, or human agreement ceilings. Typed-carrier overlap benefits from shared EDU anchors; it does not recover connectivity. Non-span attachment signatures exclude span edges and can still coincide for distinct equal-yield/type carriers. Full canonical-tree equality retains connectivity and is the stronger diagnostic.

The 34.4060% figure cannot be compared as an 'improvement' or 'decline' against the earlier native fully labelled-edge macro F1 of 40.8992%. The new signature has different typed endpoint fields, edge inclusion rules, and denominator.

The exact non-span label distributions have document-macro total-variation distance 0.2713 (maximum 0.3411). Thus a satellite-share ranking that does not reverse can coexist with substantial label-composition differences. A single seemingly stable role proportion is not a substitute for the typed relation view.

Across the 10 primary graphs, there are 2,913 non-span labelled events, including 509 whose label is same-unit. They are preserved. This is a reason to call the denominator labelled attachments rather than assuming every event is a substantive rhetorical move. Unknown labels, when present in future data, must remain explicit.

## Interpretation and the learning decision

1. Use the source sequence and typed XML roles as their own view; do not call blank-line blocks validated semantic paragraphs
2. Use the quotient as a structured attachment-hierarchy view, preserving EDU anchors, ordered yields, exact labels/N/S roles, multinuclear arity and genuine nesting
3. Keep boundary merge-scope profiles and exact attachment scopes as interpretable projections of that object; carry their definitions and annotation uncertainty with them
4. Exclude native IDs, wrapper multiplicity, and raw graph size/depth/group fractions from the default predictive path when they purport to measure discourse structure
5. Retain frozen native metrics as labeled diagnostics of native annotation-plus-encoding behavior

No observed difference is a population uncertainty bound or minimum meaningful style effect. There is only one paired document per genre in this small panel, so genre is confounded with document/source. Released paired EDU boundaries are identical; source-layer agreement is shared input, not perfect segmenter accuracy. Residual quotient disagreement can include genuine alternative analyses, annotation errors, and unremoved encoding/conversion choices. This study cannot separate them.

## Reproducibility and computation

Run `python typed_quotient.py --synthetic-only` for synthetic checks. Run `python typed_quotient.py --output aggregate_results.json` from this directory with the unchanged private cache and sibling evidence directories available for the aggregate replay. The latter writes only its requested aggregate result file.

The replay uses one Python standard-library process, approximately 1.1 CPU seconds and 30 MiB peak resident memory, with 512 MiB address-space and 600 CPU-second limits. An independently implemented random-order reducer matched the one-pass quotient on 2,000 seeded synthetic cases, including 1,327 discontinuous-yield cases, 563 with extra semantic attributes, and 1,485 with anchored internal vertices. Its 2.03 CPU-second run used only synthetic trees and no source corpus; details and the exact reviewed module hash are in `INDEPENDENT_REVIEW.md` and `independent_randomized_review_results.json`. No source or annotation bytes are redistributed.

Definitions were written before the first new replay. Post-replay review tightened terminology, documented the non-span signature restriction, and added fail-closed schema validation; these changes did not alter feature definitions or numerical calibration values. `PROTOCOL_PRE_REPLAY.md` preserves the initial wording, and `PROTOCOL.md` records the clarification log. This transparent sequence is not a held-out freeze, and all ten documents remain exposed calibration material.

## Related evidence

- [Pinned earlier measurement and independent audit](https://github.com/proffitteoy/style-compiler/tree/2c3eeb0bcf3020fcba36f13b2bc6bab490b3f1ae/research/discourse/measurement-validation-20261002)
- [Pinned GCDT repository](https://github.com/logan-siyao-peng/GCDT/tree/6846a7e21a3a91f29e1376fe4a0f27c4810f2f51)

The present analysis used the already retained local evidence only. These links identify provenance; they do not grant upstream source/annotation redistribution rights.
