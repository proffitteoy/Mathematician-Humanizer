# Chinese discourse measurement: aggregate-only public derivative

> Publication derivative prepared after independent review. The original frozen report, evaluator and results are preserved unchanged locally. This release omits all per-document numerical records and paragraph vectors; it contains aggregate findings and method code only. Constructing this derivative did not rerun or retune the measurements.

## Decision

**Keep the paragraph/hierarchy representation, but do not promote its summaries to comparative style, coherence, or human/AI claims.** The representation retains the supplied annotation exactly. Differences between two released native annotation files reverse 7 of 10 document-pair orderings for one paragraph-hierarchy summary. These differences combine annotation and RS3 encoding choices; this experiment does not isolate semantic disagreement. No predictive discourse parser was evaluated.

The experiment is complete under its narrow scope. The appropriate outcome is an information-preserving descriptive view plus a documented uncertainty warning, not a trained model or a single writing-quality score.

## Design, freeze and exposure

- Dataset pin: `6846a7e21a3a91f29e1376fe4a0f27c4810f2f51`; five development documents followed by one frozen evaluation of the five double-annotated test documents
- Recorded freeze: 2026-10-02T01:55:29Z; first logged test-body download: 01:55:35Z. SHA-256 hashes cover the protocol, evaluator, retrieval code and synthetic tests, and still match. Prior retained inspection files contain test metadata headers. The chronology and parent messages support development-before-test; the later audit cannot independently exclude unlogged earlier access or reruns
- 2,237 primary EDUs, 666 sentences, and 275 source-format paragraphs across the ten documents. Development: 1,145 EDUs / 127 paragraphs; test: 1,092 EDUs / 148 paragraphs
- All ten documents are now explicitly exposed calibration material. None may be presented as a future held-out validation set
- No owner text, training split, translated EDU layers, Stanza predictions, ML training, paid API, external-model upload, rewriting, or remote write was used

## What the views retain

The ordered layout keeps token, sentence, paragraph and EDU character spans, plus sentence identity/order. Normalization removes Unicode whitespace only. XML metadata is excluded from the body. Blank-line source paragraphs include separately formatted headings and list blocks; these are not independently adjudicated semantic paragraph functions.

The hierarchy keeps native RS3 vertices, parent pointers, relation definitions, nuclearity and complete ancestor paths. A segment with dependent children is preserved correctly. Exact yield sets preserve gaps, rather than flattening them to a bounding interval. Paragraph projections retain intersecting EDU and native-node references, including cross-paragraph structure, using a shared labelled edge table. No binarization or RST-to-dependency conversion occurs.

Entity identity/coreference/bridging, argumentative support/attack/truth, perceived rhythm, coherence quality and human/AI provenance are explicit nulls with `no_gold_layer` reasons. RST labels are rhetorical annotations, not argumentative truth.

## Retention and controls

- Exact XML/sentence/EDU character-stream alignment: 10/10 documents. Both RS3 annotations align on all five test documents
- Native vertex attributes, relation definitions, paragraph/sentence spans and JSON round trip: exact for all 15 annotation graphs (6,351 native vertices; 6,336 labelled parent edges)
- Paragraph projections recover 100% of supplied vertices and labelled edges for all 15 graphs. This is software/representation consistency: annotations were inputs, so it does **not** demonstrate discovery of gold structure from unannotated text
- No discontinuous native yields, unknown nuclearity labels, or paragraph-straddling EDUs/sentences appeared in this panel. Synthetic fixtures separately exercise discontinuity and segment-with-dependents cases
- Twelve invented-fixture tests passed. A balanced and a right-branching tree with identical sentences, sentence bag, relation histogram and nuclearity histogram remain distinguishable by their full hierarchy views. Equal-length sentence reordering demonstrates that a length sequence alone is insufficient
- Sentence-order reversal was detected on all 10 corpus documents while preserving the sentence bag. Moving a paragraph boundary changed the paragraph projection on all 10 while preserving sentence order and the native graph. These are representation sensitivity tests; no claim is made that a perturbation reduces human-perceived quality

## Annotation agreement, not parser accuracy

All figures below are document-macro F1 over five paired documents. The native tree metric matches exact character-yield sets and, for edges, both child and parent yields plus the child node kind/group type; progressively richer variants add incoming nuclearity and relation. It is a deliberately strict native anchored multiset metric, **not Parseval** and not comparable numerically to the paper’s binary benchmark.

| Agreement target | Macro F1 | Document range |
| --- | ---: | ---: |
| EDU boundaries in the two released RS3 files | 100.00% | 100.00–100.00% |
| Separate adjudicated vs pre-adjudication EDU files | 91.59% | 89.77–93.02% |
| Native group yields | 71.26% | 64.79–80.00% |
| Native edge spans/type | 52.29% | 45.62–62.68% |
| Native edge spans/type + nuclearity | 49.34% | 42.17–59.68% |
| Native edge spans/type + nuclearity + relation | 40.90% | 33.65–51.45% |

The released double-RS3 trees share the adjudicated EDU segmentation. Their 100% boundary match is therefore not independent segmentation agreement. The separate pre-adjudication segmentation files provide the nontrivial 91.59% boundary F1. The adjudicated segmentation files also match primary RS3 boundaries exactly on all five documents. This experiment does not reproduce the paper’s 97.4% segmentation-agreement figure: the stated boundary-F1 calculation and denominator here must be kept distinct from the paper’s statistic.

## Sensitivity of the small summary panel

Differences below substitute the alternate native annotation file while keeping the underlying document fixed. Native annotation and grouping/encoding effects are mixed. A rank flip means a pair of documents reverses order between annotations; there are only ten possible document pairs. These are diagnostic descriptive counts, not independent trials or population estimates.

| Observable | Mean absolute difference | Maximum difference | Pair-order flips / 10 |
| --- | ---: | ---: | ---: |
| Mean native EDU depth | 0.4887 | 1.3286 | 2 |
| Maximum native EDU depth | 0.8000 | 2.0000 | 0 |
| Max depth / (EDUs − 1) | 0.0034 | 0.0096 | 1 |
| Groups with >2 direct children, percentage points | 1.7434 | 2.6060 | 3 |
| Groups crossing paragraphs, percentage points | 2.6310 | 4.8470 | 7 |
| Satellite incoming edges, percentage points | 1.4384 | 3.1260 | 0 |
| Mean paragraph-boundary LCA depth | 0.3685 | 0.6667 | 1 |

**Main failure:** the crossing-paragraph group fraction changes by only 2.63 percentage points on average, but the between-document differences are small enough that 7/10 pair rankings reverse. It is not justified as a stable comparative ranking signal in this small native-representation panel. This failure concerns one native-representation summary on five documents; it is not evidence that discourse hierarchy itself is intrinsically unusable. Zero flips for a different feature in five documents is not validation of general stability. Native depth values are also tied to RS3 encoding and should not be called universal rhetorical complexity.

## Independent audit qualification

The independent audit reproduced all frozen headline results, matched 185 stored feature/agreement fields, verified all seven sensitivity summaries and all 15 retained graph views, and checked all 45 input hashes. It also identified substantial native grouping effects: the paired files contain 925 unary span groups (466 primary, 459 alternate) and 438 duplicated group yields (210 primary, 228 alternate).

The frozen crossing observable counts crossing native groups divided by all native groups, including the root and unary span wrappers. Incoming satellite fraction and native depth likewise include span/nucleus bridges. Thus their denominators and values depend on encoding conventions. The full-edge agreement score ignores node IDs but includes child kind/group type; parent kind/type, root attributes and the relation inventory are not independently scored by that overlap metric, although the view retains them.

Post-hoc checks on these already-exposed files gave:

| Observable definition | Macro absolute paired difference | Pair-rank reversals / 10 |
| --- | ---: | ---: |
| Frozen native group fraction | 2.6310 percentage points | 7 |
| Unique native group yields, duplicates removed | 2.1747 percentage points | 6 |
| Unique nontrivial yields across groups and segments | 2.0551 percentage points | 6 |
| Groups remaining after narrow unary-span contraction | 2.4114 percentage points | 3 |

The narrow contraction removes only a type=span group with exactly one span-linked child, transferring the wrapper's parent and incoming relation to that child. It preserves EDU order, descendant yield and every non-span rhetorical relation, while intentionally removing the redundant N/span bridge and its parent hop. Its equivalence claim is limited to the declared labelled descendant-yield interpretation. Canonical RST conversion, standard Parseval equivalence and arbitrary group flattening were not validated.

These exploratory rows have different group/yield denominators. They are not replacements for the frozen 7/10 result, a selected improved metric, or evidence for any percentage of disagreement attributable to encoding. Native files remain nonidentical after contraction; semantic-versus-encoding attribution remains unresolved. The correct conclusion is **native annotation-plus-encoding sensitivity for one representation summary on five documents**, not that discourse hierarchy is intrinsically unusable. New definitions would require fresh confirmatory documents. See `INDEPENDENT_REVIEW.md` for the complete aggregate-only audit and `aggregate_checks.json` for its aggregate checks.

## Limits and stopping gate

- Retention passes; raw-text recovery, predictive-parser performance, Chinese entity/coreference accuracy, support/attack extraction, argument truth, human/AI discrimination and perceptual-quality validity remain untested or unavailable
- The five paired documents span five genres but do not identify a population distribution, a universal human ceiling, or a minimum meaningful style difference. Sources and genres are confounded; author independence is not established
- The original frozen evaluation and definitions remain unchanged. No threshold or replacement metric was selected from the test outcomes. An independent post-hoc replay verified the results and explored grouping sensitivity; it is not another held-out evaluation or a retuning of the original result
- Keep the views and uncertain summaries descriptive/manual-only. Any future parser or style study needs separately authorized fresh documents, provenance/matching, independent annotation and an error budget; this run does not authorize or initiate it

## Bounds and provenance

- Downloaded 835,362 bytes (0.797 MiB), 45 files, with all 45 pinned Git blob hashes verified; below the 10 MiB cap
- Development evaluator: 0.071 CPU seconds, 0.071 wall seconds. Test evaluator: 0.156 CPU seconds, 0.155 wall seconds. Maximum evaluator RSS: 18.0 MiB. Each run is one single-threaded process, hard-capped at 512 MiB address space and 600 CPU seconds
- Private source bytes and all document-level numeric outputs remain outside this release. No raw text, native annotated source, full reconstructed graph, per-document numeric records, paragraph vectors or sentence identity hashes are included. `PUBLIC_AGGREGATES.json` contains only aggregate results
- Repository Apache-2.0, paper CC-BY (unspecified version), and source-specific terms remain distinct and unresolved for redistribution. Document-level provenance remains in the private local record and is not bundled in this aggregate-only release; this experiment does not claim blanket legal clearance or unique-author counts

## Files in this release

- `PUBLIC_REPORT.md`: this clearly marked public derivative; the original report remains unchanged
- `PUBLIC_AGGREGATES.json`: aggregate-only results and audit checks; no document-level record array
- `PROTOCOL.md`, `evaluate.py`, `test_synthetic.py`, `fetch_phase.py`, `freeze.json`: unchanged frozen method artifacts
- `synthetic_results.json`: aggregate outcome of the twelve invented-fixture checks
- `INDEPENDENT_REVIEW.md`, `aggregate_checks.json`, `recompute_audit.py`: aggregate-only independent review, checks and replay code
- `PUBLIC_RELEASE_MANIFEST.json`: exact file allowlist, byte counts and SHA-256 hashes
- `README.md`: release scope and reproduction limits

The frozen protocol and evaluator describe local per-document computations, but none of their per-document outputs are published in this bundle. The code does not grant authorization to upload any outputs it could generate.

## Primary sources

- [Pinned GCDT repository](https://github.com/logan-siyao-peng/GCDT/tree/6846a7e21a3a91f29e1376fe4a0f27c4810f2f51)
- [Pinned data-format documentation](https://github.com/logan-siyao-peng/GCDT/blob/6846a7e21a3a91f29e1376fe4a0f27c4810f2f51/data/README.md)
- [Original GCDT paper](https://aclanthology.org/2022.aacl-short.47/)
- [Pinned repository license](https://github.com/logan-siyao-peng/GCDT/blob/6846a7e21a3a91f29e1376fe4a0f27c4810f2f51/LICENSE)
