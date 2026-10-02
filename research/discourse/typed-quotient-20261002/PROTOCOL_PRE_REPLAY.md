# Typed discourse quotient: retrospective development protocol

Status: exploratory development on the same 10 exposed GCDT documents (15 released annotation graphs, five paired), not fresh validation. No choice here is tuned to minimize rank reversals. A small set of observables is selected for a specified invariance and interpretation; unfavorable sensitivity is retained. Definitions below are written before the new aggregate replay.

## Inputs and constraints

Use only the existing private GCDT cache, pinned manifest, download hashes, and unchanged earlier outputs. No new corpus/model downloads, fitting, owner-text use, rewriting, or remote writes. One standard-library process, at most 512 MiB and 600 CPU seconds. Public files contain only theory, protocol, code, synthetic examples, provenance hashes, and aggregates; no per-document rows, sentence hashes, raw text, annotation graphs, or paragraph vectors.

## Declared object

The input is an ordered EDU-anchored rooted attachment tree, not an independently validated canonical RST constituency parse. Segment vertices may have dependents. The source view retains the normalized character stream, ordered EDU and sentence intervals, blank-line source-block intervals, and typed XML element interval overlays with original attributes. Root metadata is kept separate. Tags remain source tags; no heading/list/speaker role is inferred beyond the source annotation. The existing all-Unicode-whitespace removal is an explicit coordinate convention, not a claim that whitespace edits are generally meaning-preserving.

Each attachment carries its exact relation label and its source inventory type. Derived incoming role is N for span or multinuc relations, S for rst relations, and unknown otherwise. The inventory is preserved. These are RS3-derived incoming roles, not a claim of independently adjudicated nuclearity or rhetorical truth.

## Equivalence and canonicalization

E0: consistently rename vertex IDs and reorder the XML declarations of group vertices, without changing EDU order, labels, types, anchors, or layout. XML attribute order and equivalent XML escaping do not matter after parsing. Reordering EDU declarations is not allowed.

E1: insert or remove a group w only when it has type span, no extra semantic attributes, no EDU anchor, and exactly one direct child c whose incoming relation is span (derived role N). Transfer w's parent and incoming label to c; preserve all other attachments. This is a certified identity bridge under the explicit assumption that an unannotated unary span carrier adds no semantic scope. It is a semantic representation convention in addition to pure serialization invariance. It is not asserted for every RS3 editor or converter. If the source assigns an extra scope/role to such a carrier, E1 must be disabled or the role retained.

The quotient contracts all and only E1 nodes, retains segment anchors, branching span groups, every multinuc group and arity, every non-span relation and role, all source-layout data, and all remaining typed hierarchy. The canonical serialization replaces native IDs by deterministic root-path IDs, with children ordered by their minimum EDU ordinal. Removed identity-bridge provenance remains an audit sidecar and is not a learning feature.

No reassociation, multinuclear flattening, head reassignment, duplicate-yield merging, relation coarsening, N/S reversal, boundary movement, EDU splitting, or semantic paragraph inference belongs to this equivalence.

## Small measurement panel, fixed before replay

1. Quotient mean EDU attachment depth and quotient mean source-block-boundary LCA depth: counts of retained attachment hops, not intrinsic rhetorical depth or quality.
2. Quotient group source-block-crossing fraction: groups whose complete yields overlap >1 source block, divided by surviving groups, root included. Conditional on the declared quotient and source-block convention.
3. Boundary LCA yield fraction: for each source-block boundary aligned between two EDUs, size of their LCA's complete EDU yield / total EDUs, then mean. Straddling boundaries are missing for this statistic, counted separately. This estimates the annotation's merge scope at a visible boundary, not paragraph coherence.
4. Rhetorical satellite share: S edges / all non-span rhetorical edges (rst or multinuc). Unknown labels are flagged, not silently absorbed. Relation histogram counts the same edge events with exact labels; multinuclear edges remain separate events.
5. Relation-scope exact overlap: multiset of (child yield, parent yield, child kind/type/anchor, parent kind/type/anchor, relation label, source relation type, derived incoming role) after quotient. This is a declared attachment signature, not graph-isomorphism, Parseval, or standard RST relation accuracy.
6. Quotient typed-carrier overlap: multiset of (yield, kind, group type, EDU anchor). Root and anchors retained. Exact full canonical-tree equality is checked separately; overlap does not certify isomorphism.

Source sentence/block/EDU incidence and typed tag overlays are retained as structured inputs. On the five released paired annotations, segmentation is shared; agreement of this source layer is therefore by construction, not a segmenter benchmark.

## Verification and uncertainty

Prove termination and uniqueness of the quotient, and feature invariance as factorization through it. Verify idempotence, declaration/ID invariance, arbitrary repeated wrapper insertion, yield/anchor/layout retention, and non-span attachment-label conservation on all 15 graphs. Synthetic cases must reject flattening, N/S reversal, and source block-type changes. Replay the fixed panel across all 10 primary documents, with paired sensitivity only for the five double-annotated documents. Publish document-macro differences and rank changes plus aggregate denominators; no document-level records.

Report residual paired differences as annotation-plus-unremoved-representation sensitivity, never pure semantic disagreement, a population reliability estimate, a human ceiling, a human/AI effect, or a coherence/quality result. Five paired documents and ten dependent rank comparisons cannot establish downstream generalization. All exposed documents stay calibration-only.
