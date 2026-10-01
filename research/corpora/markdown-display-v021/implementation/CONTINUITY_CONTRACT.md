# Markdown display-text continuity profile v0.2.1

## Revision and authorship

The submitted v0.2 package and its hash inventory remain unchanged. Revision v0.2.1 changes only the profile/schema version and table-scope container equality: it uses the complete path of unique AST opener indices, not just the sequence of token types. A heading in a sibling item, separate list or separate blockquote cannot reset a table scope in a different container. The same actual container can still reset scope at a heading or thematic break. `container-identity.diff` preserves the exact code change. This fix is self-authored by the reviewing agent under explicit root authorization and awaits independent root inspection. No natural runner or natural execution is included.

## Scope and status

This is separately authorized code and synthetic-test work only. There is no natural-input runner, source-reading manifest, calibration permission, diagnostic GO, acquisition, model fit, split, remote write or source-admission permission in this package. No v0.2 natural text has been processed. The v0.1 smoke remains frozen, consumed and non-repeatable; its independent decision was instrument-integrity PASS with role admission BLOCKED after a table annotation was emitted as a list candidate.

The purpose is a measurement correction: distinguish proven non-content Markdown syntax from removed or unknown visible content. It is not a yield target, a general Markdown renderer, or a semantic-equivalence claim.

## Frozen implementation substrate

`continuity_projection.py` loads and verifies the exact v0.1 projector source SHA256 `06da4976dfd55f48f55a23600f32561dd2325fcc1c7d3abb94b73752a9680f2a` before executing its trusted implementation code. Source Markdown is never executed. The underlying grammar remains markdown-it-py 4.2.0 / mdurl 0.1.2 under their MIT licenses. The v0.1 source-map and conservative role machinery is reused, while its output profile and single-span contract are not relabeled.

A v0.1 unresolved record stays quarantined. Additional unresolved content discovered while recursively inspecting visible link labels also quarantines the complete v0.2 record. This version does not bypass malformed delimiters to recover more text.

## Supported visible-text continuity

The distinct profile is `historical-blog-markdown-display-continuity/0.2.1` with schema `markdown-display-continuity/2.1` and source frame `historical_blog_markdown`.

Only two kinds of removed source are classified as proved syntax-only:

1. Emphasis delimiters actually consumed and resolved by the pinned CommonMark inline grammar, with no unresolved marker text left by the conservative substrate
2. A validated Markdown link's opening/closing wrapper plus non-visible destination/title/reference-key syntax. The exact visible label boundaries come from the same parser's `parseLinkLabel`; labels are recursively analyzed for emphasis, hard content barriers and unsupported constructs

Each retained character is the original source character, in original order, with `[raw_lo, raw_hi, "identity", 0]` provenance. There is no normalization, inserted space, decoded entity, substitution, hidden-title emission or invented text. A raw newline inside a visible label remains a hard boundary under this profile. An invisible newline inside validated link destination/title syntax may be syntax-only, but unaccounted source indentation remains a boundary.

Examples in the synthetic tests establish that `前**重点**后` becomes the visible text `前重点后`, and `前[标签](https://example.test)后` becomes `前标签后`, with discontinuous source spans and explicit elision edges. A removed inline code/quote/math/entity/escape/autolink/image/unknown-content scope never licenses such a join. Recursion into a link label cannot turn its code or quoted contents into ordinary body text.

The representation preserves visible-text adjacency for the supported syntax subset. It does not establish general semantic equivalence, originality, unaided human composition, per-item rights, or role truth for otherwise unmarked prose. Hyperlink identity is retained as structural evidence, not interpreted as author attribution.

## Output and proof invariants

- `regions` is a total, ordered, nonoverlapping partition of the raw source into `content`, `syntax_only`, or `barrier`. Raw codepoint coordinates are never normalized offsets
- A segment may have several monotonically ordered `source_spans`. Its `text` is exactly the concatenation of those raw spans. Every output character has a one-codepoint identity map. No raw content character is reordered, duplicated or selected twice
- Raw-adjacent output characters need no synthetic edge. Every discontinuous adjacency has an explicit `proved_syntax_only_elision` edge with left/right output indices, exact source gap and proof IDs covering every removed codepoint in that gap
- `syntax_proofs` identifies the parser-recognized emphasis or validated-link-wrapper source spans, paragraph context and AST types. A proof never authorizes a cross-paragraph or removed-content join
- `barriers` and `syntax_elisions` are exact views of the total partition. `content_boundaries` records separate emitted segments, their raw gap and non-continuity reasons
- Whitespace-only islands are classified as discarded visible whitespace rather than emitted as prose
- `validate_projection` defaults to deterministic replay of this frozen profile from the already supplied bytes, then independently checks character provenance, total partition, coverage, proof-span coverage, edge identities, counts and fixed non-admission claims. This performs no additional source-file read, but is real additional computation that a future bounded executor must budget. The projector's internal validation omits redundant replay because the result was just derived
- A rehashed forged syntax certificate cannot legitimize deleting arbitrary visible content: public validation must exactly reproduce the frozen profile, and content/hard-gap checks must still pass. Such consistency is not semantic adjudication

This is intentionally incompatible with the v0.1 single-contiguous-span/no-gap interface. A consumer must explicitly opt in to v0.2. It must not pass these multi-span segments through the old single-span validator or drop the continuity evidence.

## Table-annotation and caption scope

The v0.1 role error is preserved, not retroactively fixed. V0.2 adds conservative hard barriers:

- A paragraph immediately preceding a table, or an immediately preceding containing list, is ambiguous as a caption and excluded
- After a table, following notes, plain paragraphs, numbered/bulleted lists, lazy/indented continuations, additional tables and their annotations remain in unresolved annotation scope until an explicit heading or thematic break in the same container
- A heading inside a nested quote/list does not clear a surrounding table's annotation scope. Nested-table ambiguity may conservatively extend to end of document
- The explicit boundary is a structural stopping rule, not semantic evidence that the next paragraph is original body prose. Substantial omissions are possible and declared

The existing image-containing, image-adjacent, standalone-emphasis-heading/caption and known-caption safeguards remain. Syntax cannot locate every unmarked annotation or caption in arbitrary documents.

## Copy, lineage and exposure compatibility

Always retain the exact raw Markdown view and every original source binding, including quarantined and zero-segment records. A future gate must also retain v0.2 projected text, every mapped raw fragment and the complete source-cover/elision evidence, with explicit profile IDs. Canonical work IDs remain separate from commit identity.

The prior wiki-profile bounded exclusion certificate does not cover the new Markdown profile automatically. Syntax-only continuity changes character n-gram adjacency and denominators even while every retained character is source-exact. The future consumer must refuse a claim of complete comparison coverage until a separately reviewed, bounded compatibility extension or equivalent evidence covers these views. No fingerprint database or old source body is read or changed here.

The existing three diagnostics, earlier 96 calibration works and their full exposed graph closure remain permanent exclusions. No future revised diagnostic run is authorized by this code package.

## Verification and next gate

Current corrected-revision evidence: the original 61 synthetic test methods plus 10 new container-identity regressions pass, including the existing 200 deterministic malformed/Unicode fuzz inputs. Another 33 source-free adversarial methods pass. The reviewer authored this narrow correction at root instruction; an independent root review is still required before any natural execution contract.

Run synthetic tests only:

    PYTHONDONTWRITEBYTECODE=1 /workspace/shared/style-ml-env/bin/python -m unittest -v test_continuity_projection.py

Next: independent source-only review and additional synthetic adversaries against these exact hashes. Only after that review may root consider a new, separate versioned diagnostic manifest with new explicit byte/time/memory/thread limits, pre-read exposure ledgers and a one-time marker. The current package has no natural runner, no resource approval for such execution and no permission to reuse v0.1's consumed marker or budget. No automatic expansion to the 788 acquired candidates or the proposed 12-item calibration is allowed.
