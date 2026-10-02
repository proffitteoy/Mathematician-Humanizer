# Schema amendment 1: identity structure, before any split or outcome fitting

The full files each contain 3,000 rows: 1,500 labelled `baike` and 1,500 labelled `web`. Baike IDs are strings and Web IDs are integers. There are 2,987 distinct typed `(source, source_ID)` question identities. Twelve Web question identities occur more than once (11 twice, one three times), with the same prompt and different human answers. All 3,000 `(source, typed source_ID, exact prompt, exact human answer)` composites are unique within each file.

The original strict unique-string-ID check correctly stopped preparation before grouping or splitting. The following schema handling supersedes that unsupported schema assumption, without changing copy thresholds, seed, or observed-outcome definitions:

1. Preserve original ID type and source. Use `(source, ID type, source_ID)` as question-family identity.
2. Join paired answer records by that question identity plus exact original prompt and human answer; require a unique cross-file one-to-one composite match. Never use row order.
3. Preserve all 3,000 human answer observations once logically, including multiple answers within a question. Preserve both machine outputs for each matched answer record. Count 2,987 questions, not 3,000 independent questions.
4. Explicitly connect every record with the same question identity before exact/near-copy grouping; all such answer variants share one component and split.
5. Stratify the fixed component hash allocation by observed source profile (`baike`, `web`, or a mixed connected component) and maximum human length bucket. This adds an observed source factor before allocation, without semantic topic inference. Report each source cell separately. Both remain Chinese QA; source labels alone do not establish broad held-out-domain generalization.
6. Neither source has verified per-row authors or dates. Unknown authorship remains recorded uncertainty, not an admission ban. No source, answer, or component is dropped for lack of paragraph support.

This amendment responds only to new schema evidence. No model fit, metric-result comparison, seed search, threshold tuning, or split had occurred.
