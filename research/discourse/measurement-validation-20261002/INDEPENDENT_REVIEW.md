# Independent audit: Chinese discourse-view measurement

## Verdict

**The frozen native-representation results reproduce. The interpretation needs an encoding caveat.** The run establishes a faithful view of supplied annotations and descriptively measures differences between two released annotation files. It does not establish predictive discourse recovery, coherence, writing quality, or human/AI discrimination. It also does not isolate semantic annotation disagreement from native RS3 grouping choices.

The reported **7 of 10 rank reversals** is correct for the frozen fraction of native groups whose yields cross blank-line source blocks. It must remain the frozen result. Post-hoc grouping checks below demonstrate dependence on the representation; they are not replacements for that result or validation of a preferred alternative.

## Independent checks

- Reparsed all 15 graphs over 10 documents from the existing local cache; no downloads, models, fitting, remote writes, or edits to original artifacts
- Recomputed and matched 185 feature/agreement fields, all seven paired sensitivity summaries, and all five paired agreement targets to numerical tolerance below 1e-12
- Independently checked the actual view against separately parsed XML attributes, relation definitions, EDU spans, descendant yields, ancestor paths, nuclearity, paragraph membership, vertices, and labelled edges; all 15 graphs passed
- Confirmed 6,351 native vertices and 6,336 parent edges, with 2,237 primary EDUs, 666 primary sentences, and 275 source-format blocks
- Confirmed exact XML/tokenized/EDU character-stream alignment and the released RS3/adjudicated boundary equality
- Verified all 45 cached inputs against both logged SHA-256 and pinned Git blob hashes; frozen code hashes and original artifact hashes remain unchanged
- Re-ran the 12 synthetic tests through their unittest suite without invoking their result-file-writing entry point; all passed

The retention result concerns the declared structural fields, after whitespace normalization. It is not byte-for-byte source preservation, independent annotation accuracy, or recovery from unannotated text. Projection completeness is a software consistency property because the supplied global node/edge table is part of the representation.

## Metric definitions and denominators

### Native graph overlap

An EDU coordinate is a Unicode-code-point offset after removing all Unicode whitespace. A vertex yield contains its own EDU when it is a segment, together with all descendant EDUs. Adjacent character intervals are merged; discontinuities remain separate intervals.

The group-yield score is multiset overlap over native group yields. The edge scores compare each nonroot vertex's yield, its parent's yield, and the **child** kind/group type; richer variants add incoming nuclearity and relation. They are not graph-isomorphism scores, canonical RST constituency scores, or Parseval. Parent kind/type, root attributes, and the relation inventory are not independent features in the overlap score, although the view retains them. Different native node IDs are already ignored.

The fully labelled macro edge F1 is **40.8992%**. Pooling the five documents instead gives 41.0985% from **853 matches / 2,068 reference edges / 2,083 alternate edges**. The reported headline is correctly the unweighted mean of five document F1s, not this pooled value. Group-yield macro F1 is 71.2647%, from pooled counts of 707 matches, 981 primary groups and 996 alternate groups.

The incoming non-span relation histogram counts native attachment edges, including multinuclear links. Satellite fraction divides satellite edges by **all** nonroot native edges, including span/nucleus bridges. Native mean/max depth similarly counts these bridges. These quantities consequently depend on grouping conventions.

### Segmentation

The segmentation metric excludes document start/end and matches exact normalized-character internal boundaries. The released primary and alternate RS3 boundary sets match each other and the adjudicated segmentation files on all five documents. The 100% result therefore establishes common released segmentation; it is not an independent segmenter-accuracy result or evidence that the two annotators originally agreed perfectly.

For the separate adjudicated versus pre-adjudication segmentation files, macro F1 is **91.5854%**. There are **981 matched boundaries / 1,087 reference boundaries / 1,051 alternate boundaries**. Pooled F1 is 91.7680%. Neither statistic can be identified with the paper's differently reported 97.4% agreement without reproducing its exact denominator and method.

### Paragraph crossing and ranking

The frozen observable is crossing native groups / all native groups, including the root and unary span wrappers. Across the five paired files, pooled counts are **131 / 981** primary and **150 / 996** alternate. These pooled ratios are not the document-macro measurement-difference calculation.

The macro absolute difference is **2.6310 percentage points**, with a maximum of 4.8470 points. Comparing every pair among five documents gives **7 reversals, 0 tie changes, and 3 unchanged orders**. Those ten pair comparisons share documents and are not ten independent trials. The run gives no population uncertainty interval, genre effect, general human ceiling, or minimum meaningful style difference. One document per genre also confounds genre and document/source effects.

## Grouping-equivalence diagnostic: keep separate from the frozen result

The paired files contain **925 unary span groups**: 466 in the primary annotations and 459 in the alternate annotations. Every one is type=span with exactly one direct child linked by relation=span. The files also contain 438 duplicated group yields: 210 primary and 228 alternate. Also, 487 group vertices share a yield with a segment-with-dependents; these counts can overlap. These are large representation effects, not just rare corner cases.

A narrow audit contraction removes a type=span group only when it has exactly one span-linked child, transferring the wrapper's parent and incoming relation to that child. This removes only a span/nucleus bridge, preserves EDU order and descendant yield, and keeps every non-span rhetorical relation label. The wrapper's incoming relation and its derived nuclearity are retained at the replacement attachment. The removed span edge's N label and parent-hop depth are intentionally not retained as separate events.

**Equivalence scope:** this contraction is semantics-preserving for the experiment's declared labelled descendant-yield graph interpretation, where a node denotes its complete yield and an unlabeled single-nucleus span wrapper adds no rhetorical relation. It is not a blanket claim about every RS3 editor or RS3-to-RST converter. No converter-normalized gold tree, standard RST nuclearity assignment, or Parseval equivalence was validated. Arbitrary multinuclear flattening, removal of branching span groups, or deletion of relation-bearing edges is not justified by this check and was not done.

Exploratory results on the same already-exposed files:

| Observable definition | Macro absolute paired difference | Rank reversals / 10 |
| --- | ---: | ---: |
| Frozen native group fraction | 2.6310 percentage points | 7 |
| Unique native group yields, duplicates removed | 2.1747 percentage points | 6 |
| Unique nontrivial yields across both groups and segments | 2.0551 percentage points | 6 |
| Groups remaining after the narrow unary-span contraction | 2.4114 percentage points | 3 |

The final row has a different group denominator, and the middle rows are alternative summaries, not asserted canonical rhetorical structures. No correction factor or percentage of disagreement attributable to encoding follows from these comparisons. They demonstrate that the exact rank-instability count changes under defensible representation transformations. Native annotation files remain nonidentical after the narrow contraction, so merely renaming node IDs or removing unary wrappers does not account for every difference. Further semantic-versus-encoding attribution remains unresolved.

The appropriate conclusion is **native annotation-plus-encoding sensitivity**, not rejection of discourse hierarchy or all discourse-derived features. Before model fitting, specify the intended invariances, validate a canonical conversion if one is needed, and compare observables that satisfy those invariances. New definitions would need fresh confirmatory documents rather than retroactive optimization on this panel.

## Paragraphs and headings

The evaluator concatenates XML text nodes, excluding attributes, and splits at blank lines. It does not use XML section/subsection/list/speaker tags to infer rhetorical paragraphs or paragraph functions. Source-format blocks can include separately formatted headings or list items; the boundary-crossing feature inherits these choices. The original report substantially discloses this limitation. Neither lossless block projection nor boundary-LCA depth validates semantic paragraph interpretation.

The synthetic sentence-order check reverses sentence identities; the corpus check likewise compares reversed identity sequences. This is a sensitivity check on the ordered representation, not a raw-text perturbation experiment measuring parser response or human-perceived deterioration. The paragraph-boundary check actually recomputes projections while holding the supplied graph fixed, which is appropriate for its stated software-control purpose.

## Freeze and exposure evidence

All four frozen hashes match current files. Recorded chronology is internally consistent:

- Clock-tool freeze: 2026-10-02 01:55:15 UTC
- Recorded executor freeze: 2026-10-02 01:55:29 UTC
- First logged test-body download: 2026-10-02 01:55:35 UTC
- Recorded test evaluation: 2026-10-02 01:58:15 UTC

Retained earlier test inspection files contain metadata headers rather than bodies. The parent also received a development-pass/freeze-intent message before the completion message; it cannot certify exhaustive absence of earlier access or reruns. The evaluator requires matching frozen hashes and refuses its ordinary test entry point when a test-results file already exists. This supports the recorded development-then-test history. A later file audit cannot independently attest that no earlier unlogged body access, deleted-result rerun, or alternate script execution occurred. Strong wording should remain proportional to the available audit trail. All ten documents are correctly marked exposed and ineligible for future held-out claims; the present replay does not restore held-out status.

## Delivery and scope

This audit exports only an aggregate review, aggregate checks, and the replay code. It contains no per-document score table, source prose, sentence hashes, reconstructed graphs, full annotations, or paragraph vectors. The original file named aggregate_summary.json still contains document-level numerical records; dev_results.json and test_results.json additionally contain paragraph vectors. They are not part of this aggregate-only deliverable.

Rights/provenance assertions were not independently re-adjudicated. This audit verifies local input hashes against the pinned metadata and preserves the original distinction among repository licensing, paper licensing, and upstream source terms; it does not grant redistribution clearance.

## Files

- INDEPENDENT_REVIEW.md: this aggregate-only review
- aggregate_checks.json: machine-readable aggregate verification and exploratory diagnostics
- recompute_audit.py: read-only replay using existing local inputs; writes only a new aggregate output

Primary dataset reference: [pinned GCDT repository](https://github.com/logan-siyao-peng/GCDT/tree/6846a7e21a3a91f29e1376fe4a0f27c4810f2f51). This audit used only the already retained local files.
