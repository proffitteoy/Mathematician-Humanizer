# Which discourse structure is a measurement, and which is an encoding?

## Research conclusion

A useful discourse view should be a **typed, ordered relational object with a declared equivalence**, rather than a vector of native graph counts. There are two different commitments:

1. Native vertex IDs and XML declaration order are serialization choices. Removing their influence needs no rhetorical hypothesis.
2. Treating an unannotated unary span carrier as an identity is an additional, explicit representational-semantic convention. Under that convention a narrow quotient is well defined. It does not license flattening multinuclear structure, forgetting scope, changing segmentation, or replacing typed hierarchy by a bag of yields.

This work supplies that quotient and its invariance argument. On the exposed calibration panel it removes a real source of encoding dependence without eliminating annotation sensitivity. This is progress toward a measurement contract, not evidence of stylistic identifiability, parser accuracy, coherence, quality, or human/AI discrimination.

## 1. The object and its types

Let the source layer be L = (X, E, S, B, Z):

- X is the source character stream under the earlier experiment's fixed all-Unicode-whitespace-removal convention
- E = (e1, ..., en) is an ordered partition into annotated EDU character intervals
- S is the ordered released sentence-interval sequence
- B is the ordered blank-line source-block partition
- Z is the XML tag interval overlay, including tag name, tag nesting/order, and attributes; the root carries metadata separately from document-internal tag roles

Keep E/S/B incidence rather than force all three segmentations to refine one another. A source block may overlap a heading, list, or speaker tag; a tag may cover several blocks. A source tag is not an inferred rhetorical paragraph type. The retained tag types in this panel include section, subsection, subsubsection, list, speaker, and block. If true paragraph functions are needed later, that is a new annotation/prediction layer with its own uncertainty.

The discourse layer T is a rooted, ordered-by-yield attachment tree. Its vertices are typed carriers:

- EDU-anchor carrier: retains the EDU ordinal; it may have dependents
- span-group carrier
- multinuc-group carrier
- any other explicitly represented carrier attributes, retained rather than silently discarded

A carrier's complete yield Y(v) is its anchored EDU, if any, plus the EDUs below it. Yields are ordered sets, not just convex hulls; discontinuities remain represented. Different carriers can have the same complete yield. Neither equal yield nor equal relation label makes two carriers interchangeable.

An attachment v→parent(v) has an exact label r, the source inventory type t(r), and derived incoming role ν:

- span or an inventory-multinuc label: N
- an inventory-rst label: S
- unrecognized label/type: unknown, explicitly flagged
- root: ROOT

N/S here are source-format-derived incoming roles. The tree is not silently converted into binary constituency, and a segment with dependents is not treated as a leaf. In particular, Y(parent(v)) includes v and potentially other dependents; it is **not a claimed nucleus-only target span**. This distinction matters for any relation-scope encoder.

The implementation rejects unsupported RS3 document/header metadata, duplicate inventory names, root incoming-relation attributes, and invalid EDU coordinate partitions rather than silently dropping them. This restriction does not exclude any of the 15 cached graphs. Source XML root metadata is supported; it is distinct from RS3 document metadata. The attachment tree may have discontinuous carrier yields; no projectivity/constituency claim is assumed.

The full scientific record also keeps native source files and provenance. Those support audit/replay. They are not interchangeable with the model-facing quotient, and are not redistributed here.

## 2. Two equivalences, not one vague notion of 'same discourse'

### E0: strict serialization invariance

Consistently rename vertex identifiers; reorder group declarations; change XML attribute ordering or equivalent escaping. EDU order, anchors, hierarchy, labels, types, and all source-layer intervals and tags remain fixed. These transformations preserve the parsed typed object up to anchored isomorphism.

Changing EDU declaration order is not E0: it changes the source coordinate/anchor correspondence. Whitespace normalization is the pre-existing coordinate convention, not a general assertion that whitespace edits preserve meaning. Moving a paragraph boundary or changing a section tag to a list tag is not E0 either.

### E1: a certified identity-bridge convention

A carrier w may contract into its only child c exactly when:

1. w is a group with type span and has no EDU anchor
2. w has exactly one direct child c
3. the edge c→w has label span, hence identity-bridge role N
4. w has no extra semantic attributes beyond its structural kind/type and incoming parent/label

Delete w and transfer w's incoming attachment to c. If w is the root, c becomes root. All other edges, labels, anchors, source intervals and tags remain unchanged.

**Semantic assumption I:** an otherwise unannotated single-nucleus span carrier denotes its child's complete scope without introducing an additional semantic operator. Under I, the c→w span/N edge is an identity wire, not a separate rhetorical relation. Removing that wire deliberately changes the number of native N edges and native parent hops. Every non-span incoming label and its N/S role survives on the replacement attachment.

I is narrower than 'unary nodes never matter.' A unary node with an explicit role, extra annotation, non-span child edge, or multinuc type stays. If a source/editor uses a bare unary span to express a genuine scope distinction, I is inappropriate for that source. Keep E0 only, or encode that distinction so E1 no longer applies. This study has not validated a universal RS3-to-RST converter.

Write Q(T,L) for exhaustive E1 contraction followed by deterministic ID-free rooted serialization, with L and the exact relation inventory included. Identity-provenance is reconstructible from the unchanged native inputs and the in-memory projection q:V(T)→V(Q). Neither raw IDs nor bridge multiplicity should enter the default learner.

## 3. Why the normal form is well defined

### Proposition 1: termination

Each contraction removes exactly one vertex and does not add a vertex. A finite tree therefore terminates after at most |V| contractions.

### Proposition 2: order independence

Consider two eligible vertices.

- If their identity chains are disjoint, the contractions commute. Retargeting one carrier's incoming attachment does not change the other's child count, type, or child's label.
- If they lie on the same identity chain, both contraction orders identify the chain with its deepest noncontracted carrier. All internal chain edges are span/N. The chain's top incoming attachment is the one retained at its endpoint in either order.

No contraction creates a newly eligible formerly ineligible parent: when a child wrapper is replaced, the replacement has that wrapper's original incoming label and the parent's child count is unchanged. Carrier attributes also do not change. Thus maximal removable identity chains are already determined in the input. Contracting each to its endpoint gives a unique typed reduced tree up to native-ID renaming. This also proves the one-pass implementation is equivalent to arbitrary exhaustive contraction.

### Proposition 3: information retained by the quotient

For every original carrier v, Y(v)=Y(q(v)). EDU anchors themselves never contract, so their order and identity remain. Every non-span attachment is retained exactly once with its original label, inventory type and derived incoming role; its endpoints become their quotient representatives. All branching structure and every multinuc carrier survive, although identity wires immediately above/below them disappear. Source layout L is copied unchanged.

The intentionally forgotten information is the number/IDs of certified identity bridges and their span/N wire hops. 'Preserves nuclearity' therefore means preservation of labelled attachment roles, not preservation of the count of all native N edges.

### Proposition 4: complete invariant for this equivalence

Order each node's children by the minimum EDU ordinal in its yield. Child yields are nonempty and disjoint in the accepted anchored tree, so this order is deterministic. Serialize each surviving node by its root-child-index path, full retained attributes, EDU anchor if present, incoming label and role. Include the ordered EDU intervals, character stream, inventory, and source layer.

Equal serialized normal forms imply an anchor- and type-preserving isomorphism of the reduced trees. Each original tree is E1-equivalent to its reduction; hence equality implies E0/E1 equivalence. The converse follows from Propositions 2–3. Thus Q is a complete invariant for the specified equivalence, **not a complete invariant of rhetorical meaning**.

### Corollary: principled feature construction

Any deterministic f(T,L)=g(Q(T,L)) is invariant under E0/E1. This is stronger than observing stability on this panel. Conversely, any deterministic invariant can be regarded as a function on equivalence classes. The scientific choice is which properties of those classes measure a construct, not whether to include another native count.

The full Q is intentionally richer than a measurement panel. A histogram or average may be invariant without retaining enough information for a proposed task. Invariance is necessary for a representation-independent input under this contract; it does not establish usefulness or semantic validity.

## 4. Exact counterexamples prevent over-canonicalization

All examples are synthetic and executable in the supplied tests. Letters are one-EDU anchors.

### 4.1 An identity bridge changes raw depth and denominators

Start with span root R, child A attached by span/N, child B attached by evidence/S. Put A and B in separate source blocks.

- Native groups: one, crossing fraction 1/1 = 1
- Insert span group W between B and R; B→W is span/N, W→R is evidence/S
- Native groups: two, crossing fraction 1/2 = 0.5
- Q is identical in the two cases

Inserting a bridge above every vertex including the root changes both EDU native depths from 1 to 3, again with identical Q. Dividing raw depth by n−1 cannot repair this: n is unchanged.

Therefore raw group fraction, raw vertex/edge counts, native hop depth, and satellite edges divided by all native edges are not valid default features for an E1-invariant learner.

### 4.2 Repeated multinuclear labels do not prove associativity

Compare flat joint(A,B,C) with joint(joint(A,B),C), preserving A,B,C order and labelling every child edge joint/N.

- Flat: three labelled child edges; LCA(A,B) yields {A,B,C}
- Nested: four labelled child edges; LCA(A,B) yields {A,B}

The nested subtree is a real scope distinction in the declared object. Flattening destroys it and changes merge scale 3/3 to 2/3. Algebraic associativity of some natural-language connective, if established for a task, would be an additional semantic quotient requiring its own validation. It is not an XML cleanup.

### 4.3 Yield sets and relation histograms lose direction

In the binary evidence example, swap A's span/N and B's evidence/S incoming attachments. The complete yield set is still {{A},{B},{A,B}}, the label histogram is unchanged, and the topology/counts/depths are unchanged. But which content is satellite versus nucleus reverses. Q and its non-span attachment scopes distinguish the cases.

Deduplicated yield counts and label histograms cannot stand in for the typed discourse object, even when their summary statistics are invariant.

### 4.4 Text-identical layouts can have different source roles

XML section(A), then blank-line B, versus XML list(A), then blank-line B, have the same text and block intervals. Their typed source layers differ. A paragraph encoder that retains only a block boundary vector silently erases source role information; Q(T,L) retains it without pretending that a source tag is a rhetorical function.

## 5. A small family of model-facing observables

### Source sequence and incidence

Retain ordered sentences and source blocks, their exact typed XML overlays, EDU-to-sentence/block incidence, and explicit boundary straddling/missingness. Encode source roles as their supplied categories, with 'untyped/unknown' where appropriate. This view can capture sequencing/formatting structure; it says nothing alone about coherent argumentation. Sentence segmentation, blank-line block conventions, and XML layout extraction each require separate validity checks.

### Typed attachment scopes

Retain Q as the structural object. A local non-span signature is:

(child complete yield, parent complete yield, child type/anchor/remaining attributes, parent type/anchor/remaining attributes, exact relation, inventory type, incoming N/S/unknown).

This is deliberately a scope record, not a claim that its parent yield is the nucleus argument of a binary rhetorical relation. Preserve span edges and all node roles in Q even though the tested non-span signature panel excludes span edges. Exact signature overlap is a diagnostic, not a standard accuracy target.

Labels such as same-unit remain separate exact categories. Across the 10 primary graphs this label accounts for 509 of 2,913 non-span labelled events. Calling all non-span edges substantive rhetorical moves would overinterpret the inventory. Do not silently drop such labels, merge them with span wires, or give their event counts a coherence interpretation.

### Boundary merge scope

For a source-block boundary aligned between different EDUs i and j, let m(i,j) be the quotient LCA. Define merge scope h=|Y(m)|/n. Keep the ordered boundary profile, annotated with local source types, rather than relying solely on its mean.

h describes how large a supplied discourse scope joins content on the two sides of a visible boundary. It is invariant even before explicit E1 contraction: an unanchored unary carrier cannot be the LCA of two distinct anchored vertices. If one EDU crosses the boundary, h is missing there, and the straddling indicator is retained. Treating it as a self-LCA would conflate segmentation mismatch with strong local cohesion.

The denominator n makes the scale explicit; it does not remove effects of document length, EDU granularity, or section organization. Character-, sentence-, or block-weighted alternatives would be different observables, not harmless normalizations.

### Quotient hop depth and crossing fraction

These are legitimate functions of Q, with narrower names and interpretation:

- attachment depth: retained hops from the root to an EDU carrier
- boundary LCA depth: retained hops to its merge carrier
- group crossing fraction: fraction of surviving group carriers whose complete yields touch multiple source blocks, including the root in the denominator

They measure the chosen typed attachment representation. They are not universal rhetorical complexity, organization quality, or semantic depth. Their remaining dependence on unquotiented encoding conventions is measurement uncertainty.

### Non-span labelled-attachment proportions

The exact label histogram and S/(rst-or-multinuc labelled attachments) are E1-invariant. Their unit is a labelled attachment event. A multinuclear group of arity k contributes k child attachments; a chain and a flat group can differ. This is intentional preservation of hierarchy, not a bug to erase by arbitrary division. Keep label categories and arity/type context available to the model. An invariant aggregate need not identify label-local or directional changes.

## 6. A multi-view learning contract, before any fitting

The proposed input is structured, not a request to append dozens of scalar counts:

1. **Source view:** ordered sentence/block sequence, exact source types, and EDU incidence
2. **Discourse view:** Q's typed hierarchy, anchored scopes, exact relations and roles, plus cross-boundary profiles
3. **Content/task control view:** semantic content, topic/genre/prompt or other relevant controls when legitimately available; this is separate from declaring structure to be style

Sentence/block representations can pool anchored EDU information and read incident labelled scope records, while retaining cross-block attachments. Keeping the global quotient prevents independent paragraph pooling from cutting long-distance structure. The source view and discourse view share EDU coordinates, not fabricated per-paragraph discourse trees.

A deterministic encoder of Q is E0/E1-invariant by construction. Randomized implementations should couple randomness to canonical anchors or require distributional invariance; native IDs, insertion order, and identity-bridge multiplicity must not leak through positional features. Raw provenance remains available for auditing outside the predictive path.

An annotation channel can be written schematically as T_a = Enc_a(D; conventions_a), where D is an unknown discourse analysis and a indexes annotation/conversion choices. Q removes only the equivalence declared above. It does not identify D, nor isolate style from topic, author, length, genre, source, task or prompt. Paired views of one document should therefore be treated as alternative measurements of one object, not as independent training documents or automatic positive examples of a content-free style signal.

Future model development should test robustness over declared equivalent serializations exactly, and over available non-equivalent annotations as a sensitivity analysis. Consistency across alternate annotations is a hypothesis-dependent regularizer, not permission to force genuine analysis differences to disappear. Do not select feature definitions because they minimize disagreement on this exposed panel.

Useful uncertainty records include the observed alternate-annotation range, unknown/missing roles, segmentation disagreements, source-type missingness, and the canonicalization version. A two-annotation range is an observed sensitivity envelope, not a confidence interval or a calibrated posterior. No variance decomposition or subtraction of native-versus-quotient error is identified here.

## 7. What leaves the default learner, and what remains

**Exclude as representation-sensitive default inputs:** native IDs, XML declaration order, unary wrapper multiplicity, native vertex/edge counts used as discourse complexity, native depth or its n−1 normalization, all-edge-denominator satellite fraction, and native group fraction interpreted as paragraph organization.

**Relabel and retain conditionally:** quotient attachment depth, quotient group crossing, exact labelled-attachment event counts, boundary LCA merge scope, and source-format block statistics. Each must carry its coordinate, denominator, type convention, segmentation provenance, and quotient version.

**Keep only as native-format diagnostic endpoints:** the original frozen metrics and 7/10 rank reversals. They remain correct for their original estimand; later quotient definitions do not overwrite them.

**Do not invent:** semantic paragraph function, argument truth/support quality, entity tracking/coreference, perceived coherence, author intent, or human/AI provenance from the supplied RST annotations. These need their own definitions and evidence.

## 8. Evidence needed before stronger interpretation

The next confirmatory study should preregister source/annotation semantics, the equivalence, the model-facing object, and its task before acquiring genuinely unexposed examples. It should include multiple documents per source/genre and relevant length/topic controls, independent alternative annotations and converter stress tests, and explicit checks for cases where unary carriers encode genuine information. Segmenter/parser error must be evaluated separately if predicted structures will replace supplied gold layers.

A useful test of discourse contribution is then a controlled, uncertainty-aware comparison between source-only, discourse-only and joined views on an independently specified task. This work establishes neither that such a task is learnable nor that discourse features will help. It establishes what the proposed input means, what transformations leave it unchanged, and which unresolved uncertainties must follow it into that experiment.
