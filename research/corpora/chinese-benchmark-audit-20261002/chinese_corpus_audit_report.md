# Chinese paired human/AI corpus audit

Audit date: 2026-10-02. Scope: small public-data schema, provenance, format and overlap audit; no model training, no detector demo, no raw redistribution. All numbers below marked “sample” describe a fixed source-order prefix, not an estimated population prevalence.

## Decision

**Use the original M4 Chinese QA release as the first limited-population paired multi-view pilot, with original HC3-Chinese as a domain-stratified complementary collection.** The actual M4 payload preserves shared questions, human answers and formatting, and supports some genuinely multi-paragraph paired examples. Its two early generators and one broad QA domain are limitations to state, not grounds to discard valid paired observations. Do not claim universal human style or identified author voice.

Add C-ReD as a broader generator/domain, sentence-level and topic/prompt-confound stress test. Add CUDRT as an explicitly **human-prefix-conditioned continuation** condition. Neither is a substitute for original paragraph structure: C-ReD deliberately flattens documents; the audited CUDRT human payloads are also flattened. MULTITuDE is not a usable anonymous paired-data source in the audited release; HC3Plus loses the alignment/context metadata needed for paired analysis.

## What was actually obtained

33 sample files, 30,392 source records, **8,012,506 bytes (7.64 MiB)** total. Most records are short HC3Plus heldout texts; record count is not effective sample size or evidence of style identification.

Selection was fixed before text/quality inspection:
- Original HC3-Chinese: first 64 complete rows in each of seven source-domain files, preserving every human/ChatGPT answer, including nulls and empty outputs
- Original M4: first 128 complete rows in each of the two Chinese generator files
- HC3Plus: entire small Chinese validation-QA, validation-SI and test-SI files
- C-ReD: first 32 CSV data records in each of five domains for human, GPT-4o and Qwen2.5 (480 records)
- CUDRT: first 32 records in each of News/Thesis original, GPT4 and Qwen ratio25 files (192 records)

All source fields/labels retained. JSONL and CSV bytes are unchanged. Two original CUDRT JSON arrays were bounded by complete objects and closed with a synthetic final array bracket; object content and strings are unchanged. Temporary partial retrieval fragments were kept separately and never treated as rows. No quality-based replacement, sample expansion or training occurred. Raw samples remain local and must not be published.

Reproducibility: `combined_manifest.json` records exact URLs, pinned Git/Hugging Face revisions, file IDs, sample rules, sizes and SHA-256 hashes. CUDRT Drive files are not immutable versions; hashes anchor the observed snapshot.

## Corpus comparison

### Original M4 / M4GT

Published Chinese coverage is 3,000 human answers plus 3,000 ChatGPT and 3,000 davinci-003 responses from Baike/Web QA. Chinese has one unique prompt template and default generation settings, unlike the broader English prompt variety. The Chinese-specific appendix uses a >100-Chinese-character human-answer selection threshold; this differs from generic longer-text wording. M4GT reuses this Chinese data for multilingual binary detection, not a full Chinese version of all three tasks. [M4 paper](https://aclanthology.org/2024.eacl-long.83.pdf), [M4GT paper](https://aclanthology.org/2024.acl-long.218.pdf)

The actual sample has fields `prompt, human_text, machine_text, model, source, source_ID`; all 128 IDs align between the two files, with identical prompts and identical human answers. This is question-paired, not author-paired or factual-evidence-matched. `source=baike` occurs in both; source_ID is a qid-like string, but no per-row author, source URL, publication date or generation timestamp exists. Do not count the repeated human arm twice. [Original release and schema](https://github.com/mbzuai-nlp/M4/tree/main/data)

Source tables report MIT for Chinese source data. That is the dataset authors’ attribution, not a verified rights chain for individual web answers. No root-level release license was observed in the pinned M4 tree. Preserve attribution and resolve intended training/publication rights separately; public availability alone is not a redistribution license.

Original split caution: the M4 paper describes standard train/dev/test counts but does not establish family grouping. M4GT’s official All-mode code uses label-stratified row-level `train_test_split` and generates IDs afterward; it does not group prompts or source_IDs. Retain the old split as provenance if recovered, but do not assume it is question-disjoint. [Official split code](https://github.com/mbzuai-nlp/M4GT-Bench/blob/main/src/transformer_detector.py#L15-L35)

### Original HC3-Chinese

Published scope: 12,853 questions, 22,259 human answers and 17,522 ChatGPT answers across open_qa, baike, nlpcc_dbqa, medicine, finance, psychology and law. Human material is pre-existing QA/wiki content rather than newly commissioned answers. ChatGPT was queried through the early preview website, refreshing conversation per question, sometimes adding domain-specific instructions. One question can have multiple answers in either arm. This is question-paired, not aligned author voice. [Primary paper](https://arxiv.org/abs/2301.07597)

Actual original rows preserve `question, human_answers, chatgpt_answers`, but no author/time/URL or stable row ID. The raw Hugging Face loader exposes source configurations under a train split, which is not the paper’s detector split. The authors separately provide raw/filtered and full/sentence variants; do not use those derived variants as if they were unmodified prose. [Official HC3 release instructions](https://github.com/Hello-SimpleAI/chatgpt-comparison-detection/blob/main/HC3/README.md)

Rights are explicitly source-dependent: the card says CC-BY-SA 4.0 unless stricter upstream terms apply. The source table reports open_qa MIT, medicine CC-BY-NC 4.0, finance CC-BY 4.0, psychology CC0, but Baidu Baike none and NLPCC/law unknown. The loader’s Apache header is a **code** license and its dataset-license variable is blank; it is not blanket data clearance. [Dataset card](https://huggingface.co/datasets/Hello-SimpleAI/HC3-Chinese), [Source-rights table](https://github.com/Hello-SimpleAI/chatgpt-comparison-detection#dataset-copyright)

### MULTITuDE

Original v1 Chinese is Mandarin news, 2,683 retained rows, entirely test-only, around 300 headline families, with eight generators: davinci-003, GPT-3.5-turbo, GPT-4, Alpaca-LoRA-30B, Vicuna-13B, LLaMA-65B, OPT-66B and OPT-IML-Max-1.3B. Generation is headline-conditioned, so shared headline does not supply shared factual reporting. [Paper](https://aclanthology.org/2023.emnlp-main.616.pdf)

Official v1 files are request-gated, institutional/research-only, with no onward sharing outside the approved request and caveats about human labels/third-party rights. No request or download was made. The documented release schema has text, label, multi_label, split, language, length and source, **without title, URL, prompt/pair ID, author or timestamp**. Therefore treat released rows as unpaired unless the mapping is obtained. v2 adds obfuscations to the same base; v3 changes coverage and has Chinese train/test rows, so “Chinese test-only” applies only to v1/v2 base. [v1](https://zenodo.org/records/10013755), [v2](https://zenodo.org/records/13846588), [v3](https://zenodo.org/records/15519413)

Creation code drops date/summary and later URL/title; it removes incomplete final sentences, adjusts lengths in both arms, and deduplicates. Initial whitespace-token filters are questionable for Chinese, even though later lengths use Polyglot. Original family-aware construction cannot recover omitted IDs, and deduplication prevents safe row-order matching. GPL in the code repo is not the data license. [Creation notebook](https://github.com/kinit-sk/mgt-detection-benchmark/blob/main/01_dataset_creation.ipynb)

### HC3Plus / HC3-SI

Adds Chinese summarization (LCSTS/news2016), English-to-Chinese translation and HC3-question paraphrasing, generated with GPT-3.5-Turbo-0301. These are useful semantic-control task ideas, but they do not provide multiple generators. [Primary paper](https://arxiv.org/abs/2309.02731)

Actual sampled release rows have only `text, label`, with no input, pair ID or task/domain tag. Do not recover pairs from row position. Chinese SI test has 22,490 rows, equal class counts, with median text lengths 22/27 characters for labels 0/1; it is mainly unsuitable for paragraph/discourse analysis. Validation-QA has no newline in any of 1,780 texts. A separate data license was not found in the pinned repository; inherited source rights still matter. [Official data release](https://github.com/suu990901/chatgpt-comparison-detection-HC3-Plus/tree/main/data/zh)

### C-ReD

Broader Chinese coverage: five core domains (plus a Traditional-Chinese news extension) and nine generators; human sources include THUCNews/Sina, Zhihu-KOL, Douban reviews, Gaokao model essays and ChinaXiv papers. News has an upstream 2005–2011 collection window; some actual essay/paper rows retain a year, while news/review/QA samples do not. No author IDs or source URLs occur in the audited rows. Human QA provenance is not equivalent to a verified pre-LLM publication date. [Primary paper](https://arxiv.org/html/2604.11796v1)

Release filenames identify GPT-3.5-turbo, GPT-4o, Claude-3.5-Haiku, Gemini-2.5-Flash, Doubao-1.5-Pro, Qwen2.5, Qwen3, DeepSeek-V3 and DeepSeek-R1; per-row generation dates/snapshot versions are absent in our sample. Actual machine rows retain `original_id` and `prompt`; all 320 sampled machine rows join the corresponding 160 human IDs. But only **40 of 160** cross-generator families use identical prompts: templates/constraints differ across generators. Call this source/topic-matched, not a clean fixed-prompt generator intervention. Labels are reversed from HC3Plus: **1=human, 0=machine**. Preserve original label plus an explicit canonical mapping. [Official release](https://github.com/HeraldofLight/C-ReD)

All 480 sampled texts are single-line, matching documented deliberate single-paragraph normalization, metadata removal, punctuation repair, and Markdown/list/heading stripping. The primary paper also describes length and quality filtering. Thus original paragraph/layout/hierarchy are **missing by construction**, not observed zeros. Lexical and sentence experiments remain eligible if they explicitly target this edited release; this is view-specific ineligibility, not corpus-wide rejection. The public tree has no root license or split manifest, and `evaluation/README.md` is empty; the paper’s fixed train/test claim cannot establish family-disjoint splits from these artifacts. Broad generator/domain counts are useful stress coverage, not identification of “human style.”

### CUDRT

Chinese generators reported include Baichuan2-13B, ChatGLM3-6B-32K, GPT-3.5-turbo, GPT-4-1106 and Qwen1.5-32B. Tasks span creation/QA, continuation, polish/expand, summary/refine, rewrite and translation. The paper claims 2016-or-earlier human inputs, with Chinese news from Sina/Guangming and academic text via Baidu Academic; academic segments are cleaned/excerpted. Per-row proof of author/date/rights is not present in our sample. [Primary paper](https://arxiv.org/html/2406.09056v3)

The official Google Drive links are anonymously readable; they were reached from the primary repository, with no login. Actual ratio25 records have `ID, Type, Complete_Ratio, Human_Content` and the generator-specific combined text. Original records additionally contain `Human_Abstract, Human_Splitcontent_0.75`. GPT4/Qwen prefixes share 21 News and 19 Thesis IDs; all matched human text agrees, but order differs. Never join by row order. [Original data entrypoint](https://github.com/TaoZhen1110/CUDRT/blob/LLMs/Origin_data/README.md), [Parallel-data entrypoint](https://github.com/TaoZhen1110/CUDRT/blob/LLMs/DatasetAll/README.md)

The combined outputs start with the supplied human prefix in every joinable audited case (32+21 News; 32+19 Thesis). The generator code explicitly concatenates that prefix with a generated suffix. Hence these are **hybrid continuations**, not all-machine prose. All 128 sampled Human_Content values are single-line; 126/128 combined outputs have multiple nonempty lines. A naive paragraph contrast would largely encode the preprocessing pipeline. Original News/Thesis median lengths are 1,326/1,472 characters, useful for sentence-order and continuation discourse tests after source/boundary validation. [Qwen generation code](https://github.com/TaoZhen1110/CUDRT/blob/LLMs/DataPreprocess/Qwen/Chinese/Create/Complete/process1_ratio25.py)

No root dataset license was found; a detector subdirectory license does not license the upstream corpus. Original heldout family grouping was not established by this bounded audit. These are limitations requiring provenance work, not proof that the corpus is unusable for every research question.

### Watchlist only

C-HAT-Bench describes shared source IDs, five Chinese domains and six generators across collaboration modes, potentially closer to a crossed design. Its paper’s release link resolves only to the generic anonymous hosting domain, so a usable specific release/schema/license was not verified here. Do not count paper claims as audited data. [Primary paper](https://arxiv.org/html/2609.32770v1)

## Original-format support and observed defects

Counts use decoded original strings, without rewriting. “Multiline” means at least two nonempty CR/LF-separated lines; “multi-block” means at least two nonempty blank-line-separated blocks after ignoring leading/trailing whitespace. CR, LF and CRLF are interpreted equivalently in this measurement view; raw strings remain unchanged. A line or blank block is a structural proxy, not a gold rhetorical paragraph. This distinction matters: davinci often begins with empty lines.

| Original M4 sample arm | Texts | Multiline | Multi-block | ≥500 Unicode characters | Median characters |
|---|---:|---:|---:|---:|---:|
| Human (unique shared arm) | 128 | 99 | 62 | 27 | 246 |
| ChatGPT | 128 | 80 | 77 | 6 | 247 |
| davinci | 128 | 65 | 60 | 0 | 135 |

Joint human–ChatGPT support: 60 multiline, 33 multi-block, 4 pairs with both ≥500 characters. Joint human–davinci: 51 multiline, 27 multi-block, zero both ≥500. Across all three arms: 40 multiline, 20 multi-block. Keep all families; a paragraph-eligible stratum is a conditional population, not a replacement sample.

HC3 original preserves useful but domain-dependent format. Among the first 64 families/domain, baike has 11 jointly multiline families and open_qa 20; other domains have none using literal line breaks. Human psychology has 84/285 multiline answers but its 64 ChatGPT answers have none. No sampled HC3 family has both arms containing two nonempty blank-line blocks; that is a bounded-sample result, not a full-corpus impossibility. One psychology family has both arms ≥500 characters.

Required schema/format flags:
- HC3 finance: two null **human** answer entries; retain them as missing, never stringify to “None”
- HC3 nlpcc_dbqa: one empty ChatGPT answer; M4 davinci: one whitespace-only output
- All 64 HC3 medicine ChatGPT answers and 104/192 nlpcc ChatGPT answers contain literal backslash-n sequences, unlike actual newlines. Preserve originals; any decoding view must be separate, reversible and explicitly tagged
- Domain, role and prompt wording are entangled with refusal, list, length and formatting patterns; these are observations to control/stratify, not automatic exclusions

## Duplicate/overlap findings and limits

- The 128 M4 human duplicates across generator files are intended shared arms. Family-level inference must not count them as independent humans
- HC3 finance human answers contain five exact duplicate excess entries; law ChatGPT answers eight; psychology human answers one. No answer-level deletion was performed
- Original HC3 sample and HC3Plus validation-QA share 38 distinct exact texts, or 73 after NFKC plus whitespace removal. These are derivatives, not independent external replications
- Entire HC3Plus SI validation/test files share two exact human texts (11 and 21 characters). Short strings can legitimately recur; this does not prove broad split leakage. SI test itself has 49/5 within-class exact duplicate excess entries
- No exact or whitespace-normalized question overlap was found between our fixed HC3 and M4 prefixes. This does not exclude full-corpus overlap: upstream BaikeQA/WebTextQA is shared
- The only normalized M4–HC3 answer match in these prefixes is empty/whitespace content, not meaningful provenance overlap
- Full-corpus near-duplicate, translated duplicate, author and temporal leakage remain unaudited. No split is certified clean by this small audit

## Proposed crossed train/dev/test design

1. **Freeze provenance before features.** Keep untouched source text, original label and source split; add canonical role, corpus/version, domain, task, generator/snapshot-known-or-unknown, exact prompt and prompt-template ID, source-family ID, human identity if available, date precision, preprocessing lineage, rights status, and character-offset views. Retain null/empty/failed generations with eligibility flags. Do not collapse lines, strip list markers, normalize punctuation or truncate the only copy.

2. **Use connected source families as the unit.** Group identical source IDs only within a verified corpus namespace, exact/normalized question+human hashes, upstream URLs when available, duplicate/near-duplicate components, all answers, generators, tasks, sentences and paragraphs. C-ReD film titles, essay prompts and paper IDs need broader topic groups beyond row IDs. CUDRT all ratios/operations share a source family. Freeze duplicate thresholds before label-based analyses and report ambiguous joins.

3. **Preserve original heldouts, but do not inherit unsafe row splits.** Save original split labels. If an original test family overlaps training, quarantine the whole connected component from fitting rather than silently relabeling rows. For a new study, assign families by a documented seeded hash to 60/20/20 train/dev/test, stratified on available domain/topic/length metadata and with minimum support checks. This audit’s inspected source rows are development/audit material; a later confirmatory test must be newly frozen without result-guided selection.

4. **Cross the factors that actually exist.** M4 permits within-question human/ChatGPT/davinci contrasts in QA; HC3 permits domain contrasts for early ChatGPT. Their union is an incomplete domain×generator×epoch design, not a full crossing. Do not fill nonexistent cells or estimate a generic generator effect from them. C-ReD enables broader domain×generator stress cells, with prompt-template strata/holdouts. CUDRT enables News×Thesis × generator × operation/ratio cells, explicitly keeping generation mode separate from pure-answer writing. No training is authorized/performed by this audit.

5. **Freeze separate test panels.** (a) unseen family, seen domain+generator; (b) unseen topics within domain; (c) unseen generator on unseen families; (d) unseen domain with shared generators; (e) both domain and generator held out where the corpus supports it; (f) task/epoch transfer. For original M4, label unsupported panels as unavailable rather than claiming universal generalization. Do not use C-ReD flattened paragraphs as a paragraph holdout.

6. **Make three views traceable to the same document.** Sentence boundaries retain punctuation and offsets; estimates are document/family-clustered, not inflated by sentence count. Paragraph view retains original breaks and distinguishes line breaks, blank lines, list items and possible serialization artifacts. Discourse view uses ordered rhetorical-move/entity/transition annotations with blinded, independently checked labels; short or flattened records retain a “view unavailable” flag. Do not synthetically reconstruct author paragraphs.

7. **Test the confounds explicitly.** Report within-question paired differences and domain/generator-specific distributions, family-clustered intervals and effect sizes. Compare against length-only, topic/content-only and formatting-only controls; stratify common length support; mask content entities only in a separate diagnostic view. Test paragraph/sentence-order shuffles and prompt-template holdouts without changing the raw observation. Report refusal/prompt-echo/serialization sensitivity separately. Multiple human answers allow within-question human variability estimates, but unknown authors cannot support an author-voice model.

Mandatory validity fixes are label mapping, source-family grouping, null/empty handling, hybrid boundaries and excluding destroyed paragraph structure from that estimand. Limited generator age, QA scope, imperfect factual equivalence, unknown author/date and small paragraph support are stated/stratified limitations, not reasons to reject every paired group comparison. Dataset count or detector accuracy alone cannot identify human style.

## Concrete next bounded acquisition, proposed only

No further download or training was performed. The present 10 MiB cap remains respected. The smallest complete two-generator M4 Chinese acquisition is the two pinned original files: `qazh_chatgpt.jsonl` 7,025,906 bytes and `qazh_davinci.jsonl` 11,276,490 bytes, totaling **18,302,396 bytes (17.45 MiB)**. It requires a separately authorized **20 MiB raw-data acquisition cap**; compression is not a reason to disguise the uncompressed size. A complete two-generator population cannot fit the current 10 MiB bound.

After that approval, retrieve exactly those two files at the pinned commit and no English data or detector-derived splits. Validate all row IDs, human/prompt equality, null/empty arms, complete file hashes and CR/LF-preserved text. Build question-family/near-duplicate connected components before any split. Store the human arm once logically while retaining original files. Use a fixed recorded seed/hash to allocate approximately 60/20/20 of eligible family components, with length/topic strata, aiming at about 1,800/600/600 families only if the full audit confirms 3,000 distinct families. Publish actual component counts and allocation imbalance rather than forcing the nominal counts.

Fit paired group summaries on train, choose measurement definitions on dev, then lock an unseen-family test. Keep a second disjoint test panel with davinci withheld from fitting; ChatGPT/davinci comparisons on the same test families must share the same human arm and prompt. Paragraph-eligible support is reported separately; all unavailable views remain missing, never zero. M4 alone has no held-out-domain claim. HC3 domain-transfer acquisition is a later separate, declared budgeted stage; do not quietly combine it with M4 to manufacture a fully crossed generator×domain design.

If a new cap is not authorized, continue only the current schema/annotation feasibility work, or propose a complete **single-generator** M4 ChatGPT cohort (7,025,906 bytes) as a new bounded acquisition; label the missing second-generator population explicitly. No additional acquisition is implied by this report.
