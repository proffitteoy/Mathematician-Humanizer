# Native-source paragraph measurement, version 1

## Scope and admission

This standalone research adapter measures preserved publication structure. It does not change the M4 experiment, source bytes, existing feature IDs, feature caches, splits, reference populations, or any fitted model. All 47 works remain admitted H_G under operational human-publication admission, including assistance-unknown works and the coauthored work in its existing general-human role. There is no date or historical-snapshot gate.

A supported observation is available for descriptive analysis. Population-comparison eligibility is **not assessed**, rather than a blanket exclusion: contrasts need a specified population, projection, and design. Sparse paragraph markup restricts that paragraph projection, not unrelated lexical or layout evidence. Fitting is neither run nor authorized by this package.

## Representations and exact coordinates

`native-source-paragraphs/1.0.0` consumes the exact admitted Unicode body plus saved HTML or DraftJS. File hashes are checked by the admitted-corpus loader before adaptation. The body is not cleaned, normalized, augmented, or concatenated around excluded passages.

- Offsets are half-open Python Unicode-codepoint intervals into that body
- HTML text and tails are traversed once in source order; there is no substring search, so repeated identical strings cannot relocate a block
- The ordered text-atom partition is disjoint, gap-free, and reconstructs every body codepoint exactly once
- Node ranges describe containment and may overlap; they are not additive text measurements. Only the disjoint atom partition is summed for body coverage
- All source element nodes, empty paragraph elements, and zero-width `br`/`wbr` markers remain visible in the private view
- DraftJS retains block keys, types, original order, declared depth, and entity/style ranges. Its source ranges use UTF-16 code units; they are checked and converted to body codepoint intervals, rejecting split-surrogate or out-of-bounds ranges
- The canonical native-view digest is rechecked at measurement time, rejecting changed views or bodies. This is integrity checking, not an authentication or security boundary

The corpus's 1,136 previously inventoried nonempty native leaf blocks are not rebranded as 1,136 linguistic paragraphs. The richer inventory additionally contains source containers, inline nodes, and empty boundaries.

## Roles and typed source hierarchy

An explicit HTML `p` or DraftJS `unstyled` block supplies **source paragraph** evidence. A generic `div`, a physical line, a bold span, a quotation container, or an atomic image placeholder does not.

HTML retains both full source parent IDs and nearest typed parent IDs. The typed containment relation is wrapper-insensitive after matching/remapping typed nodes by their source identity and ranges; literal preorder IDs can shift when generic wrappers are inserted and are not themselves invariant. Typed nodes include headings, paragraphs, lists/items, quotation containers, figures/captions and code/tables. Heading levels are the observed h1–h6 rank; list nesting is the count of enclosing ul/ol elements; quotation containment records the enclosing blockquote IDs. These are observable layout relations, not style measurements derived from arbitrary DOM depth.

DraftJS retains explicit header levels and declared list depth. The flat serialization does not identify parent blocks, so parent identity is typed missing rather than guessed from depth. Non-list depth remains source metadata, not discourse depth. This release contains no HTML or DraftJS list items; list handling is validated on synthetic fixtures only.

The atom roles are paragraph-mixed-attribution, heading, marked quotation, list item, caption, code/table, atomic entity, unclassified figure text, unknown DraftJS block, inline gap, and whitespace separator. For overlapping contexts, caption then code/table then blockquote then list then heading then figure context take precedence; original node types/ancestors remain available so this primary role does not erase structure. Inline q/cite/link/emphasis markers remain annotations, not new paragraph boundaries or speaker labels.

Generic/inline node `role` describes that node's literal classification; it is not a text-counting field. Its text atoms inherit the nearest explicit boundary owner's effective role. Denominators use eligible paragraph nodes and the disjoint units, never counts of arbitrary node roles.

All substantive text lacking an explicit supported boundary stays in visible inline-gap atoms. Generic divisions are retained in the raw node tree but do not become paragraphs. Markup can be semantically misleading: a p may contain a heading-like label, and h2 may mark related-article links. This adapter does not infer a visual or rhetorical reclassification.

## Primary projection

Select complete content-bearing paragraph nodes whose primary role is paragraph-mixed-attribution and whose body text is owned entirely by that node. Exclude block quotation, list, caption, code/table and figure context; unknown/generic blocks; and source paragraphs containing nested foreign structural content. Empty or Unicode-L/N-free paragraph nodes stay inventoried but do not enter the numerator or denominator.

This is a **source-paragraph mixed-attribution projection**, not clean author prose, the entire article, or gold semantic paragraphs. Ordinary punctuation quotes, footnotes, source notices, editorial notes and heading-like p elements may remain. Their source-markup status is measurable, but their authorial or rhetorical role is not inferred. Every measurement reports the complete-body and selected L/N counts, exposing coverage loss.

## Punctuation profile and formula reuse

`native-boundary-punctuation/1.0.0` segments each selected paragraph independently. It is an operational punctuation unit, not a validated linguistic sentence.

The decision stream omits whitespace, retaining a map to the original body offsets. Every output span still indexes the unchanged source. Terminal inventory is the existing `。！？!?．` plus ASCII period; closers use the existing inventory. ASCII period is protected only between logical digits. Runs of terminals/closers attach to the previous unit; any content-bearing terminal-free remainder is one unit. Units containing no Unicode letter/number codepoints do not count.

This intentionally differs from the legacy physical-line segmenter and its whitespace/initial guards. It makes internal whitespace insertion/removal/reflow invariant, including offsets shifting under reflow. Abbreviations and initials can over-segment; because whitespace is omitted, a source string such as `3 . 14` is treated like `3.14`, which can differ from the legacy source-adjacency guard. The whitespace-insensitive rule is transparent and versioned, not claimed to improve linguistic sentence accuracy. Full source paragraphs and their L/N density remain usable independently of this punctuation choice.

The eight original formulas are reused under new NP IDs with new operands and profile identity. Legacy F IDs and baseline caches remain untouched. Let P be selected paragraph count, C their total Unicode-L/N codepoints, L the sequence of punctuation-unit L/N lengths, M=median(L), and Q the list of **within-paragraph consecutive** pairs. No pair crosses paragraph boundaries, excluded roles, or gaps.

| ID | Operational definition | Missingness |
|---|---|---|
| NP002 | 1000 P / C | C=0 |
| NP003 | selected paragraphs containing exactly one punctuation unit / P | P=0 |
| NP013 | median(L) | no units |
| NP014 | q75(L) − q25(L), linear interpolation h=(n−1)q | no units |
| NP015 | q90(L), same interpolation | no units |
| NP016 | median(abs(L−M)) / M | no units |
| NP024 | mean over Q of abs(right−left) / M | no within-paragraph pairs |
| NP025 | Spearman correlation of Q's left/right lengths with average tied ranks | fewer than 3 pairs or constant rank vector |

NP024/NP025 pool only explicit within-paragraph pairs; they are not equivalent to the old document-global adjacency estimand. Formula verification compares 100 synthetic one-paragraph cases with matching operands against all eight existing formulas. The pinned locally available instrument files are from revision 2c3eeb0bcf3020fcba36f13b2bc6bab490b3f1ae, with content hashes recorded. The requested integration base is 9539f5da7ed7546d9888bc596fef39d2662f32ad; no new remote-code download or claim of unverified newer-code equivalence is made.

Support count is selected native paragraphs for NP002/NP003, selected punctuation units for NP013–NP016, and within-paragraph pairs for NP024/NP025; the explicit support_unit field distinguishes these. NP002's denominator is selected L/N, not its support count. Every feature exposes status, support count, numerator/denominator when relevant, descriptive availability, and comparison status `not_assessed`. Zero is only an observed zero; unsupported meanings and absent opportunities return null with a typed reason.

## Captions outside the admitted body

DraftJS entity text is kept separately. CaptionRichText blocks are caption evidence; a desc-only string is an unclassified entity description. In this corpus there are 15 rich-text caption blocks and 2 description-only entries outside the admitted body. They carry exact entity pointers and referring block IDs but null body offsets. A description identical to its rich caption is not duplicated; a distinct description remains a separate metadata entry. None is appended to the 182,610-codepoint admitted body or its paragraph denominator.

## Unsupported meanings

Semantic-paragraph annotation, quotation speaker/borrowed-span attribution, clean-author spans, rhetorical hierarchy, and argument structure are typed missing. Explicit blockquote containment and heading/list metadata remain observed. HTML nesting is not discourse syntax; markup does not establish who uttered quoted words, whether unmarked language was borrowed, or whether the bylined author composed every span.

## Validation and bounds

- 19 synthetic tests, including 50 deterministic randomized wrapper/reflow fixtures and every-position line-wrap insertion in a mixed-script fixture
- Exact disjoint body reconstruction and denominator conservation across all 47 admitted works
- Generic outer-wrapper invariance on all 41 saved HTML bodies, plus arbitrary inner wrapper fixtures
- Deterministic nine-document source×genre and structural challenge inspection against saved source markup, including inline gaps, divisions, captions, headings, quoted multilingual blocks and the coauthored work
- Source-markup/offset inspection only: no rendered-browser visual audit, no human gold discourse/paragraph annotation, and no accuracy confidence interval
- Seven protected M4 raw/protocol/freeze/cohort/split artifacts remain byte-identical to the preserved pre-task manifest

These checks validate the operational implementation and source preservation. They do not establish stable human features, author identity, naturalness, rewrite utility, robust domain-transfer accuracy, or a population contrast. No parser model is loaded, no new source is acquired, and no model is fitted.

## Publication boundary

Public: implementation, synthetic tests, source metadata/checksums, deterministic review selection metadata, and aggregate validation. Private: raw/per-sample text, native views, offsets, per-document measurements, source review packets and specific inspection notes. No raw source prose, fitted state, private export, or rewrite is published.
