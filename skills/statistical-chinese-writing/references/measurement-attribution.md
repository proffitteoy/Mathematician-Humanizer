# Measurement source and attribution

The small `scripts/vendor` tree is an unchanged minimal subset of the recovered style-compiler project: surface observation/projection, sentence segmentation, feature definitions, Chinese linguistic extraction/contracts, and the local Stanza adapter. `runtime-manifest.json` pins each vendored file by SHA-256. No learned next-unit predictors, raw corpus, user's original/rewrite text, model weights, or third-party Python package implementations are copied into that tree.

The recovered project contains no general project-level license. This owner-authorized publication in the original repository does not add a permissive project license. Further redistribution still requires an applicable grant. This absence is distinct from the included Unicode-derived ranges and external parser/model licenses.

Unicode 15.0.0 ranges are derived from Unicode's official Scripts.txt (source URL/hash in `unicode_scripts.py`); the accompanying `UNICODE-LICENSE.txt` is preserved unchanged with the ranges.

External Stanza code is Apache-2.0, installed separately. Refer to `runtime-manifest.json` for official upstream links and distinct model/data/vector rights: model-card declarations are not a blanket license for UD source data or fastText vectors. Weights are verified locally, not redistributed by this skill.
