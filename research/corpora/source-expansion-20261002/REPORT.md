# Stratified human-source expansion: findings and acquisition gates

Checked 2026-10-02 UTC. Chinese-primary; no raw corpus redistribution. Downloaded payloads total **3,766,105 bytes**, below the 20 MiB ceiling. Only two corpus payloads were inspected: official NUS Chinese SMS ZIP and one CSL benchmark split. Other downloads were primary metadata, terms or papers. Source hashes and measured aggregate audits accompany this report.

## Main result

The available expansion is real, but it must be stratified. The best immediately auditable additions are academic abstracts and personal microtext. Large Chinese forum/review/web corpora exist, yet author/date/genre metadata and data-specific rights differ substantially. No newly identified source simultaneously supplies broad genres, verified individual authorship, long documents, cross-topic coverage, clear unrestricted rights and discourse gold labels.

The 15-source ranked manifest distinguishes measured counts from publisher claims, original corpus from task views, source-text rights from code licenses, and three research roles. The strongest next steps are:

1. **Academic group comparisons:** pilot CSL by discipline and length, then acquire article-licensed pre-2022 full papers for long-document tests
2. **Informal-language coverage:** use privacy-screened adult NUS SMS as a short-message stratum; investigate Chiphell/LSICC terms and speaker metadata before further transfer
3. **Author modeling:** CCTAA supplies the right held-out-topic design but needs licensed Gigaword; LSICC Douban is the large candidate to investigate, not an already admitted corpus
4. **Genre validation:** resolve ToRCH2014 or LCMC access rights; use the separate gold-annotation investigation for discourse validation

## Verified samples

### NUS Chinese SMS, official 2015-03-09 snapshot

Measured **31,465 messages / 594 contributor pseudonyms / 28,421 exact unique texts**. The corpus has 3,044 duplicate excess rows; the ten largest contributors account for 35.9% of messages. Inverse-HHI effective author count is only **56.953** under raw message weighting, illustrating why nominal author count is insufficient.

A conservative age screen leaves 27,628 messages from 478 contributors known to be older than 18. Within-author exact deduplication leaves 25,921 messages; **366 contributors have at least 20 distinct messages**. This does not imply 366 suitable long-form authors: median message length is **11 characters**, and only 64 original messages reach 100 characters. Contributor IDs are not verified real-world identities, and topic labels are absent.

The creators describe voluntary personally sent messages, public release and an open-license/public-domain approach. They explicitly note that personal names were not removed. The repository has no formal SPDX license file, so this audit does not rebrand it as CC0. No messages, pseudonyms, telephone-derived tokens or individual demographic records appear in these deliverables. [Official release](https://github.com/WING-NUS/nus-sms-corpus), [creator paper](https://arxiv.org/abs/1112.2468)

### CSL discipline-classification development split

Measured **1,000 rows, 1,000 unique abstracts, 67 discipline labels**. Its headerless TSV has three fields: task prompt, abstract, discipline. It does not supply authors or per-record dates. Median abstract length is 193.5 characters; paragraph layout is unavailable. The full published corpus contains 396,209 records from 2010–2020; those are abstracts/metadata, not full papers. Four benchmark task views reuse the same 10,000 documents.

The repository declares Apache-2.0 using software wording; the paper separately states permission for metadata NLP research. This is support for a bounded research pilot, not a finding that all commercial/redistribution uses of the underlying papers are cleared. [Primary repository](https://github.com/ydli-ai/CSL), [paper](https://aclanthology.org/2022.coling-1.344/)

## High-impact source cautions

- **LSICC Douban:** 37M reviews, approximately 1M users and 18k books are publisher claims, not this audit's measured counts. User/date/book-tag fields make it promising for cross-book tests. The same README claims CC BY-NC-SA and bans redistribution; resolve the conflict and original-source rights before admitting it. [Release](https://github.com/JaniceZhao/Douban-Dushu-Dataset)
- **LCCC-large:** 12M conversations mix social posts with subtitles and chatbot-related sources. Its filters remove emojis, symbols and ungrammatical writing. It is unsuitable as clean human gold, and its MIT code file does not override the dataset's research-only notice. [Release](https://github.com/thu-coai/CDial-GPT)
- **ToRCH2014:** 657 files across 15 genres are useful coverage; the 45 named collectors are not 45 text authors. The release page has no explicit reuse license. [University release](https://corpus.bfsu.edu.cn/info/1070/1387.htm)
- **MPWAC:** 10M 2019 web articles and an explicit CC BY 4.0 dataset tag are worth cataloguing. URL/text records do not establish author identity, genre or every source's rights. Its compressed payload is **26,211,046,534 bytes**; no corpus bytes were fetched. [Deposit](https://zenodo.org/records/3242512)
- **Blog-1K:** English, not Chinese; the derivative's ISC claim needs reconciliation with the original noncommercial-research terms. The original includes adolescent writers. It does not solve Chinese multi-author blog coverage. [Derivative](https://zenodo.org/records/7455623), [original](https://u.cs.biu.ac.il/~koppel/BlogCorpus.htm)
- **NaturalConv:** human-elicited dialogue is distinct from spontaneous discussion. Its terms restrict download sources to Tencent; the primary endpoint failed in this pass. Convenient mirrors are not an authorized substitute. [Terms](https://huggingface.co/datasets/xywang1/NaturalConv/blob/main/LICENSE)
- **SegmentFault:** current terms restrict scraping/AI research without written permission despite the CC text banner. No content acquisition was attempted. [Terms](https://segmentfault.com/tos)

## Bounded next acquisition proposals

- CSL: additional train/test discipline files total **5,285,250 bytes**. Utility: verify balanced discipline sampling and duplicates. Do not acquire the 1.83 GB reformatted pretraining derivative merely for scale
- Chiphell: first published ZIP is **15,665,368 bytes**; all four ZIPs total **152,657,594 bytes**. Utility: inspect actual thread/speaker/date schema and subject coverage after rights/research-use clarification. No ZIP downloaded
- Hans: enumerate up to 20 pre-2022 articles across fields, check each PDF's CC BY versus CC BY-NC notice, and exclude the GCDT academic documents. Exact transfer bytes must be measured after the article list exists; no mass crawl or inferred author counts

## Admission and evaluation protocol

1. Preserve document ID, source URL, source/publication snapshot, original-text hash, exact terms/rights evidence, author-identity unit, genre, topic, language variety, length regime and preprocessing history
2. Treat genres, topics, platforms and author identities as separate variables. A million book reviews remains one register; hundreds of disciplines are not hundreds of genres
3. Deduplicate exact/near copies and syndicated text before splitting. Split by underlying document and thread; preserve speaker boundaries. Use author-held-topic tests only when real repeated-author metadata supports them
4. Balance or cap contributors and report effective authors as well as nominal authors. Report platform and genre weights, not just raw totals
5. Match human/AI comparisons on topic, task, length, register and source period. Pre-2022 is provenance evidence, not proof of human-only production or protection against training-set contamination
6. Keep microtext, abstracts and long documents separate. Gold discourse labels validate measurements; unannotated volume cannot replace that validation
7. Publish only aggregate measurements and justified derived artifacts. Retain privacy screening, source-attribution records and relevant no-redistribution restrictions

## Deliverable inventory

- `ranked_source_manifest.json`: 15 candidates, role rankings, rights/access status and transfer plans
- `nus_aggregate_audit.json`: measured aggregate statistics, no individual identifiers
- `csl_sample_stats.json`: measured shape, discipline counts and lengths
- `source_hashes.json`: acquisition provenance and SHA-256 hashes; no corpus content

The multi-author Chinese blog/essay gap remains open. This report does not substitute existing three-account blogs, unclassified crawls, or unrelated English corpora for that missing stratum.
