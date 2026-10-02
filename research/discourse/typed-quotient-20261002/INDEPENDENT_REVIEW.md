# Independent review of the typed identity-bridge quotient

## Finding

No material defect was found in the narrow unary-span quotient or its use in the current calibration replay. The result is conditional on the declared convention that an unannotated unary span carrier with a span-labelled sole child introduces no additional semantic scope. This is not evidence that all representation differences are semantically immaterial.

The implemented contraction preserves ordered EDU anchors, complete yields, retained node types and semantic attributes, retained direct-child arities, and the exact labels, inventory types and derived roles of every non-span attachment under the vertex projection. It does not establish independently adjudicated rhetorical meaning, constituency structure, coherence, quality, or human/AI discrimination.

## Reproducible synthetic verification

Run `python independent_randomized_review.py`. The script imports the sibling `typed_quotient.py`, reads no corpus or private cache, and writes only `independent_randomized_review_results.json`. That result records the exact reviewed module SHA-256, seed, aggregate checks, resource limits and observed resource use.

With seed 9127, all 2,000 generated trees passed. They contained 1,096 eligible vertices in total; 1,327 cases had discontinuous carrier yields, 563 had extra semantic node attributes, and 1,485 had segment anchors with dependents. Every case passed:

- A separately implemented eligibility rule versus the implementation's candidate set
- Random-order elementary contraction versus the implementation's one-pass reduction
- Idempotence, repeated-wrapper invariance, and ID/declaration-order invariance
- Retained anchors, yields, child arities and semantic attributes
- Non-span labels, derived roles and projected edge endpoints
- Unchanged EDU order, coordinate intervals, normalized text and relation inventory

The reviewed module's 13 synthetic tests also passed. The run used one standard-library process with enforced 512 MiB address-space and 600 CPU-second limits, consuming approximately 2.03 CPU seconds and 17,520 KiB peak RSS in the recorded run. There were no models, downloads, network calls, corpus rows, source annotations, or per-case output files.

This finite synthetic suite verifies implementation behavior over generated cases. It is not an empirical sample of discourse and supplies no held-out evidence or generalization estimate. Structural validation and canonical comparison reuse the reviewed module; the sequential eligibility and rewrite logic are separately implemented. The test generation is deterministic and was not used to tune features or rank sensitivity.

## Why the normal form is unique

Each elementary contraction removes exactly one vertex. A contraction preserves every remaining vertex's child count and the incoming label of the branch presented to its parent. The eligibility of any other remaining vertex therefore stays unchanged. Adjacent removable carriers are connected by span edges; contracting them in either order has the same surviving endpoint and transfers the same outer incoming label. Disjoint contractions commute. Consequently reduction terminates in the same retained labelled tree, up to the permitted native-ID/declaration differences. EDU-minimum child ordering and root-path identifiers then give a deterministic serialization.

Feature invariance follows only when a feature is evaluated on this normal form. The low-level `features` and `counters` functions accept raw graphs too; the replay explicitly supplies quotient graphs. Boundary-LCA yield fraction and non-span satellite share also remain invariant before contraction, whereas raw attachment depths and raw group-crossing fraction need not.

## Clarifications and limits checked during review

- The protocol now explicitly excludes span edges from relation-scope signatures and identifies the unchanged input plus in-memory projection as provenance
- The labelled-attachment denominator retains `same-unit`; it is not exclusively a count of substantive rhetorical relations
- Source XML root metadata is retained by the layout view. Unsupported RS3 document/header metadata, incoming labels on the tree root, duplicate relation inventory names, and invalid EDU coordinate partitions now fail closed rather than being silently discarded
- Discontinuous carrier yields remain allowed. The object is an EDU-anchored attachment hierarchy; projective constituency is not an assumption of the implementation
- Typed-carrier and relation-scope multiset overlaps are lossy. Shared anchors can contribute many carrier matches, repeated yield/type descriptors can obscure connectivity, and span edges are absent from relation-scope overlap. Full canonical equality is the stronger comparison
- Source blocks and tags remain layout annotations, not independently validated semantic paragraphs or rhetorical roles
- The ten exposed documents and five paired annotations remain retrospective calibration. Residual differences include annotation differences and representation choices outside this deliberately narrow equivalence

No original outputs, calibration report, protocol, or quotient implementation were modified by this review. Its only added artifacts are this note, the synthetic test script, and its aggregate result.
