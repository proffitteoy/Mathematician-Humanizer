# What is learned and what is not

The input consists of matched HUMAN/CHATGPT document views with explicit TRAIN/DEV split, hard lineage component, domain, instrument identity and numeric feature values. Dataset labels are observational production labels; “HUMAN” is not an independently verified absence of assistance. Raw texts are neither required by contrast.py nor included in its output. Personal and held-out generator material are forbidden.

contrast.py computes all TRAIN feature contrasts: for each complete pair, human value minus AI value; average differences within lineage component, then equally across components. A fixed-seed component bootstrap supplies exploratory 95% percentile intervals. The human median/range describe available TRAIN documents, not a universal writing norm. Features remain correlated and the intervals are not multiplicity-adjusted. Missing observations remain missing; zero is not missing. Pairwise available counts are shown.

An exploratory inspection card needs at least 8 TRAIN components, an interval excluding zero, and the same difference direction with at least 4 components in every TRAIN domain. These are explicitly engineering screening rules, not validated statistical acceptance thresholds. A separate DEV audit checks the frozen direction using at least 4 components overall and 2 per domain. No fit parameter, direction or reference range uses DEV. Subsequent card use is nevertheless development-adapted. All features, including failed ones, stay in the artifact.

The current bridge admits the existing surface-source-units-gap-safe/0.1.0 instrument only. It measures F002/F003 paragraph density/single-sentence share, F013/F014/F015/F016 sentence-length median/IQR/p90/normalized MAD, F024 adjacent length change and F025 lag-1 rank correlation. These are character/segmentation measures. They do not measure reasoning depth, authenticity, coherence or writing quality. Parser/sequence aggregations with other identities cannot be silently attached to these cards.

Candidate comparisons report each coordinate's actual change and change in absolute distance to the corresponding TRAIN human median. There is no aggregate quality objective or automatic numeric ranking. The source may already be better than the reference median; a farther candidate may be better prose. Length, prompt, collection and domain differences remain alternative explanations. Editing effects need matched candidate interventions and independent reader preference evidence that this delivery does not provide.

# Input schema

    {
      "schema_version": "paired-style-observations/0.1",
      "role": "observational_train_dev",
      "measurement_identity": "surface-source-units-gap-safe/0.1.0",
      "measurement_profile": {
        "version":"source-units-gap-safe/0.1.0", "segmenter_version":"punctuation-lines/1.0.0",
        "operational_feature_version":"character-core/1.0.0", "unicode_version":"15.0.0",
        "offset_unit":"unicode_codepoint", "normalization":"none",
        "unit_policy":"segment_full_source_then_select_complete_units",
        "pair_policy":"original_consecutive_sentences_in_one_target_component"
      },
      "measurement_profile_sha256":"6b520a4fe678d9d4336efa3046d6e2174306062eb40cd04791b62944c2b8a270",
      "provenance": {"source": "exact source and frozen split receipt"},
      "rows": [
        {"pair_id":"pair1", "component_id":"lineage1", "split":"TRAIN",
         "domain":"web", "condition":"HUMAN", "features":{"F013":20.0}},
        {"pair_id":"pair1", "component_id":"lineage1", "split":"TRAIN",
         "domain":"web", "condition":"CHATGPT", "features":{"F013":30.0}}
      ]
    }

Run python scripts/contrast.py observations.json --output evidence.json only on an admitted export. The script rejects TEST labels, other generators, cross-split components, incomplete/duplicate pairs, nonfinite numbers and invalid instruments at use time. Hashes bind the TRAIN rows, DEV rows, model/audit and each job; they catch accidental mutation but are not signatures and do not authenticate a dishonest source or reviewer.

The shown profile/hash pair is the actual Python Unicode 15.0.0 profile used in this delivery, not a value to copy onto a different extractor. Candidate analysis checks the complete emitted profile and hash. The prepared evidence_domain is bound separately; changing domain requires another explicit preparation/inspection. Surface cards never consume linguistic keys. Physical lines in source-format corpora may reflect dataset layout rather than writer-chosen paragraphs; F002/F003 are particularly exposed to that confound.

No script proves semantic equivalence. Numeric-token multiset/sign/unit checks, exact protected-string counts and independently recorded scope/ledger review strengthen the preserved baseline, but subject/object swaps, attribution changes, negation and quantifier drift may evade mechanical guards. Retain per-claim evidence and inspect failures. One successful example is not general validation.
