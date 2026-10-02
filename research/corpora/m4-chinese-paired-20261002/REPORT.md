# Original M4 Chinese paired cohort: prepared and frozen

Prepared 2026-10-02 for private scientific research. This is a data preparation and support audit, not a fitted detector, a human-style claim, or commercial-training clearance.

## Result

- Exactly the two approved original files were acquired at commit `628bf0fcb2e8c6b7ffa71fd1af6be413aced8f7d`: **18,302,396 bytes**, within the new 20 MiB transfer cap. Both approved Git blob IDs matched. No retry, substitute file, paid API, remote write, training, or rewriting occurred.
- **3,000 exactly matched paired answer records**, representing **2,987 source-question families**. Each record has one shared human answer and separate ChatGPT/davinci outputs. The human observation is counted once, not once per generator.
- The full schema differs from the earlier Baike-only prefix: each file has **1,500 Baike and 1,500 Web rows**. Baike IDs are strings; Web IDs are integers. Twelve Web questions have multiple human answers (11 questions have two, one has three). A documented schema amendment preserves these records and groups them as the same question.
- **2,951 connected components** after same-question and exact/near-copy checks. Fixed component allocations are **1,771 train / 590 dev / 590 test**. This corresponds to **1,806 / 590 / 591 question families**, and **1,816 / 591 / 593 paired answer records**.
- The previously inspected 128 question families and one connected-copy family remain train/dev only. **Zero exposed components or graph edges cross into fresh test.**

## Pairing and original bytes

Both files retain their exact original bytes and are verified by byte length, Git blob SHA-1 and SHA-256. Records are joined by source-aware typed question ID plus exact prompt and human answer, never row order. All 3,000 prompt/human/source comparisons agree. Private byte-offset indexes recover the original rows without rewriting them. Decoded original CR, LF, CRLF, and literal backslash sequences remain unchanged.

Shared human answers: 3,000 nonblank. ChatGPT: 3,000 nonblank. Davinci: 2,998 nonblank plus two whitespace-only outputs. There are no null arms. Missing outputs stay in the cohort as missing observations. Ten additional nonblank davinci strings have no alphanumeric sentence-proxy span. The preparation's `lexical` flag means nonblank pre-tokenization availability, not a guarantee that every linguistic channel has a valid denominator; the actual analyzer must preserve channel-specific missingness.

## Copy grouping and its limits

Grouping uses NFKC/casefold/whitespace removal only in a separate grouping view. Edges include identical question IDs, exact normalized prompts, exact whole answers, and exact original blank-line blocks of at least 80 normalized characters. Near-copy checks use exact character-set Jaccard joins at 0.80: question 3-grams for prompts of at least 12 characters, answer 5-grams for answers of at least 50 characters. Thresholds and seed were fixed before full-file inspection; no result-based tuning occurred.

The graph records 13 repeated-question links, 13 exact-prompt links, 65 exact-answer links, and 36 exact-block links, including redundant links within already connected components. There are eight normalized exact-answer duplicate groups. All are within a generator/arm; none duplicates across different arms. Near-copy checks found no additional distinct-text matches at the declared threshold. The exact prefix-filter implementation was independently checked against brute-force all-pairs on 199 synthetic documents with 98 positive pairs; all agreed. This does **not** prove absence of semantic paraphrase, short excerpts, or arbitrary substring containment.

The largest component contains 30 question families. Component size distribution by paired answer records: 2,933 singletons, 15 pairs, one triple, one four-record group, and one 30-record group. Component clustering is used for uncertainty; multiple answers and repeated human arms do not create extra independent questions.

## View support

Counts below are paired answer records, not independent author or question counts. The JSON aggregates also provide unique-question support and equally weighted within-question support fractions.

| Original-view proxy | Human | ChatGPT | Davinci | Joint H–ChatGPT | Joint H–davinci | Joint all three |
|---|---:|---:|---:|---:|---:|---:|
| At least two nonempty original lines | 1,147 | 2,221 | 1,670 | 757 | 583 | 479 |
| At least two original blank-line blocks | 609 | 2,205 | 1,606 | 392 | 312 | 244 |
| At least two sentence-proxy units | 2,732 | 2,979 | 2,598 | 2,716 | 2,376 | 2,370 |

All 1,500 released Web human strings are single-line, with no original blank-line separation. Original writer paragraph/layout availability is therefore **unsupported/unknown for that stratum**. This observation alone proves neither that writers used one paragraph nor that stripping definitely occurred. Web remains usable for supported lexical/sentence work: 1,417 H–ChatGPT and 1,297 H–davinci Web answer pairs have at least two sentence-proxy units in both arms.

All 392 H–ChatGPT and 312 H–davinci jointly multi-block records are Baike. That paragraph-supported subset is a conditional population with selection bias, not a representative estimate of the entire cohort or universal writer structure. Sentence and block boundaries are structural proxies, not gold rhetorical annotations. Two-unit ordered-prose inspection is allowed; no arbitrary eight-unit gate or online-forecast support requirement is imposed. Actual discourse labels remain unmeasured.

## Fixed split and generator holdout

The fixed seed is `m4-zh-paired-v1-2026-10-02-before-full-audit`. Components are stratified by observed source profile and maximum original human-answer length (<200, 200–499, or ≥500 Unicode characters). Within each stratum, SHA-256 order determines rounded 60/20/20 component counts, with exposed components excluded from test. The same seed and thresholds were retained through schema repair and verification.

Test is further split into disjoint question-component panels:

- Seen-generator panel: **296 components, 296 question families, 297 answer records**
- Generator-transfer panel: **294 components, 295 question families, 296 answer records**

Primary fitting/tuning, if later authorized, is restricted to human+ChatGPT in train/dev. Davinci is withheld from all model and measurement fitting/tuning. Generator transfer is evaluated on unseen question components; the same shared human and ChatGPT arms are available there for matched comparisons. Merely auditing schema and view support has not fitted any outcome. Test bodies must not be used for choosing features, thresholds, seeds, or model settings.

Joint multi-block test support is modest: 35 H–ChatGPT pairs in the seen-generator panel; 25 H–davinci pairs and 17 three-arm pairs in the generator-transfer panel. Report this limited conditional support rather than manufacturing paragraphs or overselling power.

Within a question, average over available paired answer variants first, then weight each source-question family equally. The private manifest carries 1/(answer count) base weights, a single logical human arm, and copy-component inference clusters. For a view-specific estimate, recompute the within-family mean using only available paired answers and report missingness denominators. Source-specific raw and equal-family support are in the aggregates.

## Scope, provenance and rights

The operational population is the original M4 benchmark-labelled human/machine QA release. Unknown author identity, dates, assistance, and individual rights are uncertainties to disclose, not automatic exclusions. Baike and Web are observed source strata within Chinese QA; this is not a broad cross-domain or modern-model population. Per-row author/date, validated topic labels, exact generator snapshots, and individual provenance evidence are unavailable. No held-out-topic, chronology, author, broad-domain, or domain×generator panel is claimed.

Attribution: the [original M4 data release](https://github.com/mbzuai-nlp/M4/tree/628bf0fcb2e8c6b7ffa71fd1af6be413aced8f7d/data) and the M4 authors' [EACL paper](https://aclanthology.org/2024.eacl-long.83/). The paper's source table attributes Chinese source data to MIT; this is an authors' source attribution, not a verified per-answer rights chain. No root-level release license was present in the audited pinned tree. Retain original source/model attribution and unknown upstream author/date/rights. Raw data and individual identity/measurement manifests must not be redistributed; no blanket commercial-training permission is asserted.

## Verification, resources and deliverables

Verification passes: complete byte-offset recovery of all 3,000 pairs; exact cross-generator prompt/human agreement; all 2,987 question weights sum to one; question/component split isolation; exposed-family exclusion; davinci fitting exclusion; frozen file/code hashes; CR/LF/CRLF and literal-escape cases; and synthetic exact-prefix-join versus brute-force agreement.

One process was used, with a 1 GiB address-space ceiling and bounded CPU. The final preparation pass used approximately 6 CPU seconds and 468 MiB peak RSS. Preparation/verification reruns remained far below the 15-minute compute cap. Derived local files total approximately 9.1 MiB, below 150 MiB; source raw bytes total 17.45 MiB. The initial unsupported unique-string-ID schema check failed safely before splitting, then the documented source-aware amendment was applied. Later reruns validated code/support reporting without changing the seed, thresholds, or resulting allocation.

The public package contains only original code, protocol/amendments, this aggregate report, aggregate JSON, verification receipts, and whole-file integrity hashes. It contains no raw texts, examples, individual IDs, text hashes, per-sample values, split identities, or private numeric uploads. All raw/cohort/split/edge manifests remain local. No remote writes were made.
