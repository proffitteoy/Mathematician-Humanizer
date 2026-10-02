# Discourse corpora for validating style measurements

Research date: 2026-10-02 UTC. This is a bounded metadata and primary-source inspection, not a corpus ingestion or model experiment. No owner texts, paid datasets, bulk corpus downloads, fitting, or remote writes were used.

## Recommendation

**Smallest justified first experiment:** ten GCDT documents only: five development documents for decisions and the five fixed, double-annotated test documents for final checking. Keep the 20-essay PSE and English GUM components optional additions for features the first experiment cannot validate. Exact GCDT IDs and available fields are recorded in `minimal_gcdt_manifest.json`; this file contains metadata, not source prose.

Use a small Chinese-first validation battery, with three separately reported components:

1. **GCDT** for sentence/paragraph/EDU alignment and full-document rhetorical hierarchy, conditional on a document-level rights manifest. Start with its five development documents and five double-annotated test documents. It is the closest fit for the structural problem.
2. **Paibi Student Essays (PSE and PSE-I)** for Chinese rhetorical parallelism. Use the original corrected representation for cross-paragraph parallelism and the augmented representation for local branch-span evaluation. Start with 20 essays, selected by document and annotation coverage, not by whether a proposed metric succeeds.
3. **GUM**, explicitly English-only methodological comparison, for testing implementations of cohesion/coreference and eRST graph measurements. Start with 10 documents in overlapping genres, subject to source-specific licenses. Do not combine its language distributions with Chinese results.

For true argumentative support/attack relations, **CN-F in XLD-ARI** is a promising *conditional* additional pair-level test: explicit CC-BY-NC-SA 4.0, subject to noncommercial-use suitability and source/provenance review. It does not solve full-document argumentative hierarchy. CEDAR is useful oral-debate evidence but requires a more careful source-rights and schema check; neither is a replacement for written-Chinese argument trees.

These data can establish whether a proposed measurement recovers annotated structure. They cannot establish that a structure distinguishes human writing from AI writing. RST nuclearity is not an argument-quality score; discourse relations are not the same as claim-support-attack edges; paragraph links are not a validated coherence rating; sentence lengths are not perceptual rhythm gold labels.

## Version pins

Exact commit IDs were obtained from the original repositories using read-only GitHub metadata or Git reference listings. Pins are preferable to moving `main` branches or an unqualified dataset name.

| Resource | Exact pin | Observed release information |
| --- | --- | --- |
| GCDT | `6846a7e21a3a91f29e1376fe4a0f27c4810f2f51` | Last commit 2022-11-30 |
| GUM | `22fdf87f9c71c96bcc771461d06e689b1f90020d` | V12.1.0, commit 2026-05-02 |
| PSE / PSE-I | `71b5226143d6b03019f4708437b1f981328b7034` | README calls current data v1.0; use the SHA, since no v1.0 tag was returned |
| CN-F / XLD-ARI | `3c0711dcaa9635482db16d44ee301c6c9d4d7a8f` | LREC-COLING 2024 repository |
| TED-CDB | `1684a0a01028a94ef7e962bb98ea6a68c9f03b03` | Last commit 2021-10-11 |
| CEDAR | `cb46d01672c9f1fd203eca6ee57bca4f4bc9fbb7` | Last commit 2026-04-10 |
| Chinese Essay Organization | `a8c337bd978778ed87bc600c6bc00b7b58f18b69` | Last commit 2021-10-09 |
| ConFiguRe | `c5ba931a76c7d664fb10de304b4eb56dea486060` | COLING 2022 repository |
| UnifiedDep | `27b4e30cbbb691f9fdd56289dda3bc7f6be95000` | Last commit 2021-05-26 |
| CCTRS | `31246a54f264085f76b52f74366d62e34232c865` | Current HEAD, exact date not inspected |

For historical benchmark reproduction only, GUM V8.0.0 resolves to `ed1d2e92d613eabc7461139e15b5f39caab2c1d7`. Do not apply V8 results to V12.1.0 without re-evaluation.

The companion metadata JSON files record repository paths, object hashes, and reported licenses for the six repositories inspected before the unauthenticated API quota was reached. Further SHA pins came from `git ls-remote`, without cloning data.

## GCDT is the best Chinese rhetorical-tree starting point

**Coverage and status.** The repository reports 50 documents, 10 each in academic writing, biography, interview, news, and how-to, with 62,905 tokens and 9,717 EDUs. Each genre has an 8/1/1 train/dev/test split. Sources are Hans Publishers, Chinese Wikipedia, Chinese Wikinews, and Chinese wikiHow. Five test documents have a second annotation. Gold layers include XML/metadata, paragraph/sentence segmentation, and tokenization; syntax is predicted with Stanza. ([Repository](https://github.com/logan-siyao-peng/GCDT))

**What is actually available.** `data/xml` supplies text and metadata; `tokenized` has a sentence per line; `rs3` is the native RST constituency annotation; `others` includes the second annotator's pre-adjudication EDU boundaries. `rsd`, `dis`, extracted EDU text, and translated variants are conversions. Preserve native RS3 for tree shape and nuclearity. Do not treat translated English EDUs as independent English originals or predicted dependency parses as gold syntax. ([Data format documentation](https://github.com/logan-siyao-peng/GCDT/blob/6846a7e21a3a91f29e1376fe4a0f27c4810f2f51/data/README.md))

**Agreement and parser evidence.** The original paper uses 15 coarse and 32 fine relation classes. On five test documents, segmentation agreement is 97.4%, κ=.89; original-Parseval Span/Nuclearity/Relation F1 is 84.27/66.15/57.77. The best reported relation result is 55.28±.23 from GCDT+GUM-12 joint training followed by Chinese fine-tuning; monolingual Chinese RoBERTa gives 51.76±.97. These are historical benchmark results, not a current parser guarantee or a whole-pipeline accuracy claim. The paper's Table 1 has 9,710 EDUs, versus 9,717 in the repository: recount the pinned native files before an experiment. ([Original paper](https://aclanthology.org/2022.aacl-short.47.pdf))

**License is not a single clean blanket.** The repository's LICENSE is Apache-2.0, whereas the paper describes texts, annotations, and guidelines as CC-BY without a version. Underlying texts also come from distinct licensors. That discrepancy remains unresolved, so do not redistribute the whole collection under Apache or assume the paper overrides source terms. The checked academic test article's own PDF identifies CC-BY 4.0; Hans Publishers now also offers CC-BY-NC, making article-level checking important. ([Repository license](https://github.com/logan-siyao-peng/GCDT/blob/main/LICENSE), [checked source article](https://www.hanspub.org/journal/PaperInformation.aspx?paperID=44511), [publisher rights explanation](https://www.hanspub.org/aboutus/))

**Private measurement versus release.** The proposed activity is local measurement on a bounded research subset, with no redistribution of source text, no external-model upload, and no derived corpus release. Record the intended-use basis separately from redistribution permission. Attribution/share-alike/source provenance still matter if derived material is later shared, and noncommercial restrictions cannot be dismissed merely because work is private. Audit the selected ten items, not all fifty, before the execution phase. This report recommends a research route; it does not supply a blanket legal clearance or initiate a rights inquiry.

**Author/date evidence.** Only the five test XML headers were inspected. The academic example has three named authors, created 2021-08-12; the interview example has three speakers but a collective Wikinews author, created 2008-05-01. The news example is dated 2006-03-23. Biography/how-to creation dates can be unknown. Wiki authors are collective labels, not resolved people. Thus neither unique-author count nor full source-date range is established, and 50 documents cannot be advertised as 50 authors. Headers preserve source URLs and sometimes Wikipedia revision IDs. ([Pinned test metadata](https://github.com/logan-siyao-peng/GCDT/tree/6846a7e21a3a91f29e1376fe4a0f27c4810f2f51/data/xml/test))

**Study limitation.** Four source families are confounded with five genres, and one annotator annotated the whole corpus. This is useful measurement gold, not a sufficiently crossed population sample for general Chinese style effects. Its small doubled subset should be used to quantify annotation sensitivity, not to claim a universal human ceiling.

## PSE provides Chinese parallelism labels with a clear dataset license

The released PSE resource contains 409 narrative/argumentative high-school mock-exam essays from an original 544. Its README explicitly licenses the dataset CC-BY-SA 4.0. It preserves paragraphs and sentence text, with sentence/token/POS/dependency preprocessing from LTP; those preprocessing layers are not independently established gold. Original annotations distinguish within-sentence, within-paragraph, and cross-paragraph parallelism. Original agreement was κ=.71 on 30 doubly annotated essays. The repository includes preserved/corrected versions and identifies unresolved annotation issues such as files `12.xml` and `367.xml`. Unique authors and writing dates are not supplied in the described schema. Treat student-writing provenance and potential personal content carefully; do not reidentify authors or send passages to external model services by default. ([Original maintained dataset](https://github.com/Mythologos/Paibi-Student-Essays))

PSE-I contains 3,855 paragraphs, 786 local parallelisms, and 2,153 branches in those same 409 documents. It adds within-sentence branch spans but removes inter-paragraph parallelism and is flat rather than nested. Its strongest published baseline reaches .43 F1 under exact parallelism matching; this is not directly comparable with the older sentence-pair/chunk task. Use exact-span and relaxed branch metrics together, and evaluate original PSE cross-paragraph labels separately. The 2023 paper obtained the data from its original authors. ([2023 primary paper](https://aclanthology.org/2023.emnlp-main.305.pdf), [2016 primary paper](https://aclanthology.org/C16-1076/))

This validates a specific structural component of written rhythm and repetition. It has no RST trees or support/attack graph, and no auditory/prosodic rhythm ratings. Its exam genre cannot stand in for adult blog, news, or professional prose.

## GUM is a valuable English method comparison

The current published inventory is 275 GUM documents in 16 main genres plus 26 GENTLE out-of-domain documents in eight genres: 301 documents and 291,056 tokens overall. It has sentence and paragraph structure, syntax, entities/coreference/bridging, discourse, and summaries. This is unusually useful for checking entity-continuity and structure implementations. Document counts are not author counts, and author/date completeness was not audited corpus-wide. ([Corpus overview](https://gucorpling.org/gum/), [release history](https://github.com/amir-zeldes/gum/releases))

Annotations are CC-BY 4.0; underlying text licenses differ. Academic and court text are listed as CC-BY 4.0; biographies/travel as CC-BY-SA 3.0; news/interviews as CC-BY 2.5; fiction/how-to and several other genres have NC-SA restrictions. Reddit text is not shipped as ordinary plaintext and reconstruction has separate constraints. Exclude Reddit from the first pass and do not assume every GENTLE/new-genre document is covered by one top-level license. ([Pinned license](https://github.com/amir-zeldes/gum/blob/22fdf87f9c71c96bcc771461d06e689b1f90020d/LICENSE.md), [repository warning](https://github.com/amir-zeldes/gum))

Use native `rst/rstweb/*.rs4`: it preserves n-ary trees, nuclearity, secondary graph edges, and signals. Binary Lisp and dependencies are conversions. GDTB supplies PDTB-style relations as a different layer, not an interchangeable encoding of every RST fact. ([RST formats](https://github.com/amir-zeldes/gum/blob/22fdf87f9c71c96bcc771461d06e689b1f90020d/rst/README.md))

**Important gold-status caveat.** eRST non-connective signals include automatic induction from gold syntax/coreference and selectively checked annotations. The 2025 study reports DM identification/association human F1 of 92.3/90 on 36 GUM documents; all-signal anchored agreement is .805 on four documents. Its GUM V9 DMRST condition has primary S/N/R/Full=.620/.545/.492/.482 and secondary Full=.030 with gold EDU/token boundaries. These figures demonstrate error propagation and cannot be silently applied to V12.1 or raw Chinese text. ([eRST primary paper](https://aclanthology.org/2025.cl-1.3.pdf))

**Text-loader trap.** The inspected V12.1 `GUM_academic_art.xml` header contains five summaries labeled human, Claude, GPT-4o post-edited, Llama, and Qwen, although the underlying article is dated 2017. Extract the document body only, never concatenate all XML attributes. Keep corpus source text, new human summaries, generated summaries, and annotations as distinct provenance layers. ([Pinned inspected XML](https://github.com/amir-zeldes/gum/blob/22fdf87f9c71c96bcc771461d06e689b1f90020d/xml/GUM_academic_art.xml))

## Argument relations need their own benchmark

**CN-F / XLD-ARI: conditional pair-level choice.** The original 2024 study introduces 8,187 Chinese financial-forum pairs from Mobile01: 4,623 support, 2,710 attack, 854 unrelated. One financial expert annotated all pairs; a second checked 1,000, yielding κ=.6221. XLM-R single-task macro F1 is 65.0; multilingual training reaches 72.3. These are relation classification results with given pairs, not extraction or document-graph reconstruction. Unique users, full-post count, source dates, and original paragraph boundaries are not established. The paper/repository license is CC-BY-NC-SA 4.0 and academic use is specified. Hold if the intended project use is commercial or uncertain. The repository is available, but the subdirectory listing was blocked by the research fetcher; raw-text schema was not independently opened. ([Paper](https://aclanthology.org/2024.lrec-main.898.pdf), [repository](https://github.com/raruidol/RobustArgumentMining-LREC-COLING-2024), [license](https://github.com/raruidol/RobustArgumentMining-LREC-COLING-2024/blob/main/LICENSE.txt))

**CEDAR: oral-debate extension, not first-pass prose data.** The repository lists 600 debates/318 topics and Apache-2.0, with full transcripts and claim, stance, evidence, rhetoric, speaker-role/time and outcome labels. Data is one archive, not inspected in this metadata-only pass. ([Repository](https://github.com/VelikayaScarlet/CEDAR)) The paper gives 251,726 sentences, 3,631 argument pairs, debate sources spanning 1993–2024, and κ=.66 between annotator groups. ASR output was manually corrected, including disfluencies/grammar/punctuation; therefore transcript rhythm is partly editorial. Unique speakers, per-item dates and rights to organizer videos/transcripts remain unverified. Reported tasks are mostly sentence classification, not RST parsing. A repo software license does not by itself settle upstream video/transcript rights. ([Primary paper](https://aclanthology.org/2026.acl-long.238.pdf))

## Resources to hold or exclude

| Resource | Relevant evidence | Decision |
| --- | --- | --- |
| TED-CDB | 72 talks, 268,099 words and 15,540 PDTB-style relations in the paper; explicit/implicit/nonadjacent relations; no whole-document nuclearity tree. κ=.94 relation type, .92/.83/.81 sense levels. Four-way baseline F1 under 60%. Paper's 26 translated + 56 original counts sum to 82 despite total 72, requiring reconciliation. README notes post-publication corrections. | No LICENSE found in pinned tree. Translation/native-Chinese provenance, author/date metadata, and source reuse terms must be clarified. [Paper](https://aclanthology.org/2020.emnlp-main.223.pdf), [repository](https://github.com/wanqiulong0923/TED-CDB) |
| Chinese Essay Organization | 1,220 high-school essays; sentence and paragraph functions plus three organization grades. Teacher-label agreement: sentence accuracy .80/macro-F1 .77; grade κ=.73. Sentence/paragraph indices are documented, not full argument edges or RST trees. | No LICENSE in pinned repository. Dates and unique authors unknown. Do not ingest solely because JSON is public. [Paper](https://www.ijcai.org/Proceedings/2020/0536.pdf), [repository](https://github.com/cnunlp/Chinese-Essay-Dataset-For-Organization-Evaluation) |
| MCDTB | Macro paragraphs-as-leaves with nuclearity; original LREC paper describes 147 Xinhua documents, later work 720. Figshare landing page displays CC-BY 4.0 but labels item privately shared. | Not preferred without resolving exact version/content and Chinese Treebank/Xinhua upstream terms. No archive fetched. [Original paper](https://aclanthology.org/L18-1302.pdf), [later paper](https://aclanthology.org/C18-1045/), [landing page](https://figshare.com/s/250474dba44e4161b040) |
| SU-CDTB / HIT-CDTB / Sci-CDTB | Different schemes; paragraph-level SU-CDTB and dependency-level abstracts do not supply the same document tree semantics. UnifiedDep says Soochow authorized SU release, HIT requires original authorization. Its current repo only has README and archive metadata entry, no ordinary license. | Do not treat as interchangeable open GCDT replacements. [UnifiedDep](https://github.com/PKU-TANGENT/UnifiedDep), [original comparison](https://aclanthology.org/2022.aacl-short.47.pdf) |
| PDTB-style Chinese Discourse Treebank 0.5 | LDC-distributed resource, distinct from other corpora called CDTB | Exclude paid/permissioned acquisition in this task. [Official catalog](https://catalog.ldc.upenn.edu/LDC2014T21) |
| CCTRS | 500 selected run-on sentences from ten fiction works, topic chains and discourse labels; explicitly omits nucleus/satellite distinction. | No visible LICENSE; selected fragments rather than representative whole documents. Useful annotation ideas, not current eligible ingestion. [Repository](https://github.com/fivehills/CCTRS-corpus-) |
| ConFiguRe | 4,192 literary fragments, 9,010 labeled figurative units in 12 categories; repo MIT license | Figurative-unit labels are not rhetorical hierarchy. Verify underlying literary text rights and author/document split before using; no data loaded. [Repository](https://github.com/PKU-TANGENT/ConFiguRe) |
| NLPCC 2024 Task 5 / CEAMC | The shared task explicitly restricts minor-student data to that task and asks researchers to contact organizers; the inspected CEAMC repo contains only README | Exclude from immediate public-data battery; no outreach initiated. [Task restrictions](https://github.com/cubenlp/NLPCC-2024-Shared-Task5/blob/main/README.md), [CEAMC](https://github.com/cubenlp/CEAMC) |

## Proposed small measurement study

This is a proposed protocol, not work already run.

### Freeze the estimands first

Define each feature in terms of structure and its failure conditions, before human/AI comparison:

- **Written rhythm proxies:** character-length sequence across sentences and EDUs, local long/short alternation, dispersion and serial dependence, plus parallel branch configuration. Keep segmentation accuracy separate from whether readers perceive rhythm. PSE establishes parallelism validity; it does not validate a universal rhythm score.
- **Paragraph cohesion:** entity persistence/reintroduction, cross-sentence and cross-paragraph links, and relation transitions. Separate referential cohesion from rhetorical attachment. Chinese GCDT alone lacks the needed gold coreference layer, so English GUM can test mechanics but cannot validate Chinese coreference performance.
- **Rhetorical hierarchy:** tree depth normalized by EDU count, nuclearity-path profiles, branching, cross-paragraph attachment distance, and placement of elaboration/evidence/concession. Report native n-ary and explicitly chosen binarized views; conversion choices can change depth/branching.
- **Argument relations:** source/target spans, support/attack/none, chains and convergence, and whether evidence connects to the intended claim. RST explanation/evidence labels may motivate candidates but are not a substitute gold for argument mining.

### First battery and stopping gate

1. Make a manifest of the exact 10 GCDT dev/test documents, licensing provenance, source revision/date, collective/unknown author status, gold/predicted layer flags, and parser training exposure. Do not silently substitute documents that fail rights checks. For each test document retain both human annotations.
2. Select 20 PSE essays with a declared stratification across narrative/argumentative type where metadata supports it, local/cross-paragraph parallelism, and annotation-free comparison regions. Keep overlapping PSE/PSE-I versions as two representations of the same documents, never independent observations. Ensure a held-out portion is untouched during feature design.
3. Select 10 GUM documents in the five shared genres only where use rights are clear. Keep this a separate English panel. For a commercial-compatible panel, omit NC data and document the resulting missing how-to cell instead of pretending the genres still match.
4. If eligible, add approximately 150 held-out CN-F pairs balanced for diagnostic class coverage, while also reporting a prevalence-preserving evaluation. This small test is for failure discovery, not a precise population performance claim. Confirm file schema and source grouping before any selection; otherwise defer this component.
5. Run each structural feature on gold labels, each available alternate human annotation, predicted structures given gold boundaries, and fully predicted structures. Compare document-level absolute error, rank agreement, and error direction by genre/length. Score boundaries with precision/recall/F1; trees with a named Parseval variant and native-structure checks; argument edges with span-aware precision/recall/F1 and per-class macro scores.
6. Determine tolerances from the intended use and the human-annotation variation before inspecting group effects. If prediction error or alternate-annotation sensitivity can reverse a feature's ordering, keep it descriptive/manual-only. Inspect failures, freeze a revised definition on development material, and evaluate once on held-out documents. Do not proceed to human/AI inference merely because parser F1 looks respectable.

Use document/source clusters as the resampling unit, not thousands of EDUs as independent samples. A five-document double-annotation panel supports a diagnostic interval and examples, not tight generalization claims. Do not bootstrap an unknown author count as if each document had a unique person behind it.

## Connecting this to future human and AI samples

The validation battery answers whether features measure what they claim. A later, separately authorized matched study answers whether those features vary by production process.

- Collect provenance labels distinguishing original human composition, translation, editing, human–AI collaboration, and AI generation. Historical timestamps alone do not prove purely human authorship; a post-2022 annotation or generated summary does not change the authorship of a verified older body text.
- Match Chinese samples on genre, task/content, intended audience, length band and source setting; cross authors with topics/sources where feasible. Keep naturalistic human writing and prompted model writing from becoming synonymous with different platforms or genres.
- Generate AI samples from the same content constraints and record model/version, generation date, prompt, decoding, revision rounds and interventions. Avoid passing the human reference prose in ways that make the task paraphrase detection unless paraphrase is the actual estimand.
- Hold out authors, source families, topics and prompt families as appropriate. Deduplicate documents and derivatives, including Chinese/English counterpart material and multiple formats of the same annotation.
- On a small balanced Chinese subset, obtain blind independent human annotations of boundaries, discourse structure, cohesion or argument edges as needed. Estimate annotation and parser errors separately for human and AI text; gold-corpus accuracy does not prove equal error on the new domain.
- Report feature distributions and uncertainty within matched strata. Do not turn descriptive differences into an authorship detector, a human-quality score, or rewriting rules without separate validation.

## Outstanding checks before execution

GCDT source-specific licenses and its Apache/CC-BY discrepancy; full document-level author/date manifest; source/genre confounds; PSE privacy-safe extraction and documented preprocessing; current GUM gold-status fields and body-only extraction; model checkpoint/split exposure; CN-F schema and noncommercial suitability. These are explicit gates, not claims already resolved.

No corpus was downloaded in bulk and no measurement or human/AI result is claimed by this report.
