# Using the observed reference neighbourhoods

## What the cards are

`human-joint-reference.json` contains TRAIN records labelled HUMAN in two stored source conditions: `baike` and `web`. These labels are not independently verified unassisted authorship, author identities, genres, or all human styles. They are useful reference conditions, with substantial internal variation.

Ten dimensions describe each source and each of three empirical bands: noun, verb, adjective and adverb token shares; mean token codepoint length; single-Han token share; first-person, second-person and negator-form token shares; and mean dependency span. Arrays follow the file's `features` order. Ratios are fractions, not percentages; a value of 0.28 is 28%. A single-Han token is not the same as a one-character sentence or a share of raw characters. Cue forms are surface measurements, not claims about meaning, perspective, or polarity.

All token proportions use T: parser tokens excluding UPOS=PUNCT and all-punctuation/whitespace tokens. Dependency span uses A: nonroot arcs whose head and dependent remain in T, with distances in ranks after punctuation removal. Exact cue lexicons and formulas are in `features`; no raw-character or dictionary-word count is an equivalent denominator.

Observations are document-global measurements. Within each source, joint-valid HUMAN document vectors are averaged within each component, then each component receives equal weight. Quantiles and covariance are over those component-mean vectors. All ten dimensions must be available for reference inclusion; observed zeros are retained, and null is not zero. The joint-available HUMAN support is 899 Baike documents / 868 components and 903 Web documents / 890 components. This differs from the paired HUMAN–AI contrast sample; do not substitute sample sizes between them.

Within each source, components are grouped using observed single-Han-token-share tertile thresholds. Each band's ten-dimensional mean, quantiles, covariance and correlation come from that same subset. These are conditional moment/quantile summaries, not a full joint density, clusters discovered by an author-style model, or proven categories. Coordinatewise intervals do not define a calibrated multivariate coverage region. Look at the card's exact `band_definition` before assigning a measured input near a tied threshold.

Source-card SHA-256: `e9b5c98fa2655b897c296af985fe1dc32a13c2b92bc6146e26685ea87929fb27`.
Measurement-profile SHA-256: `221323897ea20205d0801383537558b4411cb47eb945c2deac51e24ccb2549a3`.
Upstream paired aggregate SHA-256: `6103981dd75f2e0674644bf48e0135b542eb0eb25fdf08091b90d7fae046ff9c`.
The bundled file retains its numeric-projection provenance. No corpus text, individual rows, row IDs, caches or checkpoints are bundled.

## Choose a neighbourhood, not a universal average

The six bands retain real alternatives. Their single-Han-share and token-length means, shown only to orient selection, are:

| Source / band | Components | Single-Han share | Mean token length |
| --- | ---: | ---: | ---: |
| Baike / lower | 291 | 0.326 | 1.843 |
| Baike / middle | 290 | 0.438 | 1.603 |
| Baike / upper | 287 | 0.539 | 1.475 |
| Web / lower | 298 | 0.397 | 1.754 |
| Web / middle | 295 | 0.492 | 1.542 |
| Web / upper | 297 | 0.582 | 1.438 |

These means are not writing targets. Inspect the complete selected card and its interquartile/outer ranges; do not choose a mean independently for each dimension. Preserve the input's voice and information density. A text need not land inside every marginal interval. Source and band distinctions must not be advertised as “formal people” versus “informal people”.

If the original input is measured with the same parser, its observed single-Han share can help choose a nearby band for a light rewrite; a requested change can motivate a neighbouring band. This is reference selection, not inference of the author's identity. Without the parser, make a qualitative choice and do not claim that the output occupies that band.

## Translate the reference into writing choices

The following are practical hypotheses to try, not causal findings:

- For a lower-single-Han-share tendency, retain useful multi-character terms and name constraints directly when the content supports them: `首次开放日期`, `接收范围`, `数量上限`. Combine closely related facts in a compact sentence when that stays clear. Do not manufacture abstractions, replace ordinary words with jargon, or assume lower share always means shorter prose.
- For a higher-single-Han-share tendency, try familiar short-word constructions and direct clauses: `第一次开放`, `收哪些书`, `最多能带`. Break a dense constraint into readable clauses when its scope remains explicit. A question may introduce an already supplied list; it must not invent an audience relationship or become a repeated template.
- Read the other eight dimensions with the selected band. Check actual covariation before expecting simultaneous changes. Between-source contrasts and within-band correlations can differ; a source mean does not specify the direction of every sentence-level edit.
- Keep verbs that express the required actions and nouns that identify their arguments. Changing lexical packaging may affect several measurements at once. Do not “correct” one coordinate by breaking another part of the sentence.
- Person and negator rates are principally preservation constraints. An impersonal brief can remain impersonal under Web guidance. `不用付费` may preserve `参与免费`, but deleting `只/不/最多` or changing their scope to fit a target does not.
- If meaningful wording and the card conflict, keep the wording. Use another compatible band, a lighter rewrite, or disclose the limited fit. Never invent a statistical result to justify an aesthetic choice.

The owned examples illustrate a compact, entity-and-constraint-led rendering versus a more clause-led explanation of the same fictional facts. They were drafted from the observed source-level contrasts and frozen before measurement, before the joint cards arrived. Do not retrofit a claim that they targeted or were sampled from a particular joint band. They are not demonstrations that all ten coordinates matched a band or that readers prefer either version.

Actual measurement of the two frozen examples is now available in [example-measurement-note.md](example-measurement-note.md). The noun/verb/adverb directions moved as expected, but the shorter-token directions reversed. The listed phrase choices are hypotheses, not reliable one-to-one measurement controls; do not promise those directions without measuring.
