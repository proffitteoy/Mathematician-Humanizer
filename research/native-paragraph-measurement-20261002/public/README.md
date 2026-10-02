# Native paragraph measurement validation

A separate, model-free research adapter for the 47 admitted human-publication articles. Operational descriptive measurements are available; no population comparison or feature-stability finding is implied.

Read `MEASUREMENT_CONTRACT.md` first. It defines source roles, typed layout hierarchy, the exact paragraph projection, versioned punctuation boundaries, formula reuse and limitations. Source markup, ordinary paragraph text and quotation attribution are different evidence types.

## Run

Requires Python 3.12 and the already available lxml 6.1.1 (libxml2 2.14.6 in the recorded run). No network or NLP model is required.

```sh
python -m unittest -v test_native_adapter
python validate_corpus.py \
  --admission-public /authorized/human-admission/public \
  --source-root /authorized/author-expansion \
  --public-output ./public-results \
  --private-output /authorized/private/native-measurements
python verify_lineage.py \
  --instrument-repo /authorized/local-instrument-snapshot \
  --workspace /authorized/workspace \
  --frozen-manifest /authorized/preserved-frozen-manifest.json \
  --output ./public-results/LINEAGE_AND_FROZEN_CHECK.json
```

The admission cache is not distributed. Do not download articles merely to replay this package without the appropriate authorization. `validate_corpus.py` writes all real per-document views/measurements only to the private destination; the outputs of `adapt_html`, `adapt_draftjs` and `measure` must also remain private on real inputs.

## Results

- 47/47 exact body reconstructions; all 182,610 admitted codepoints covered once
- 896 content-bearing explicit paragraph nodes in the declared projection; 146,149 of 161,233 body Unicode-L/N codepoints selected
- 41/41 HTML outer-wrapper invariance checks
- 29 explicit heading nodes; no observed list items, so list validation is synthetic-only
- 15 out-of-body rich-caption blocks and 2 description-only entity entries preserved separately
- One work has under 50% of its body L/N codepoints in the paragraph projection; low coverage is view-specific metadata, not corpus exclusion
- 100 matching-operand synthetic cases reproduce all eight legacy formula values; boundary profiles are intentionally not globally equivalent
- Seven protected M4 artifacts match their prior checksums

`AGGREGATE_VALIDATION.json`, `HANDCHECK_AGGREGATE.json`, `LINEAGE_AND_FROZEN_CHECK.json` and `INDEPENDENT_AUDIT.json` record validation scope. All 47 works retain assistance-unknown operational-human admission. No fit, rewrite, source acquisition or model-based parser execution occurred.
