# AI-only Chinese writing pilot: design and collection summary

This completed collection contains 24 model-generated Chinese documents. It is a small AI-only pilot, not a human-writing comparison, a detector evaluation, or evidence of improved writing quality. No stylistic feature or detector score has been computed for this collection.

## Content design

Six everyday topics are crossed with two genres, essay and explanatory prose, and two request conditions. Each content request asks for 600–900 Chinese characters. The default condition gives the topic and genre. The natural-expression condition adds exactly “语言自然、贴近日常表达。”

[CONTENT_PROMPTS.json](CONTENT_PROMPTS.json) contains the six topics, the two generic genre templates and the exact condition modifier. Their Cartesian product reproduces all 24 content requests. These are content-level prompts; they do not purport to reproduce the full platform context or unavailable generation settings.

The design allocated whole topics before generation using split seed 4817: four topics, or 16 documents, to pilot development; one topic, or four documents, to pilot validation; and one topic, or four documents, to a topic reserve. All genre/request combinations for a topic remain in the same split. These labels do not mean that a model has been fitted or evaluated. The topic reserve remains unscored.

Each item was generated in a separate context under one nominal generation configuration, without the other pilot documents or measurement criteria in its content request. The requests call for original writing without consulting existing articles. The first completed texts were retained without best-of selection or editorial rewriting. Separate contexts do not constitute cross-model replication.

## Model provenance and limitations

The exact model identifier, revision, temperature, top-p and generation sampling seed were not exposed and remain unknown. This collection therefore cannot support an exact-model attribution or a reproducible API-model comparison. Platform-level context was not experimentally controlled; the published content prompts are not a clean-room API specification.

## Aggregate collection checks

All 24 planned content cells are present, nonempty and UTF-8 readable. No pair is byte-identical. The collection contains 17,893 Han characters in total, with 701–802 Han characters per document; all 24 fall within the requested range under this counting convention. Han characters are not word tokens, and the count excludes punctuation and non-Han characters.

The [aggregate data](COLLECTION_AGGREGATE.json) records design counts, topic-split integrity, duplicate count, descriptive length and the unknown model fields. These checks establish collection completeness and basic properties only. They do not establish independent authorship, semantic quality or stylistic differences. No source text or per-document identifier, hash or length record is included here.

## Interpretation

The default versus natural-expression contrast can support a small prompt-condition comparison once an analysis plan is fixed. It cannot identify human authorship. A future human comparison would need defensible provenance and matching evidence for task, genre, topic and length; a shared topic label alone is insufficient to make a pair.

This collection is separate from the existing natural-sequence study and its frozen evaluation data. No pilot text has been added to that study or used to select its models. Any later measurement must preserve that separation and report uncertainty appropriate to the small topic count.
