# Chinese corpus candidates: provenance before scale

Checked 1 October 2026. Metadata and licensing research only; no bulk corpora downloaded. Personal material, including `proffitteoy/nothing-new`, was not inspected and is excluded until separately authorized.

## 1. Best first conversational candidate: WikiConv Chinese

[Original EMNLP 2018 paper](https://aclanthology.org/D18-1305/), [maintainer’s corpus README](https://github.com/conversationai/wikidetox/tree/main/wikiconv), [Chinese release](https://figshare.com/articles/dataset/WikiConv_-_Chinese/7376012), [ConvoKit documentation](https://convokit.cornell.edu/documentation/wikiconv.html).

Wikipedia talk-page history, from a 2018-07-01 dump. The Chinese release covers 87,005 users and 7,731,744 conversational **actions**, not that many independent messages. Actions include additions, edits, deletion and restoration; revision and reply metadata allow reconstruction. Chinese years available through ConvoKit are 2002–2018. Maintainer terms distinguish CC0 metadata from CC BY-SA 3.0 comment content. Figshare's generic CC BY 4.0 badge conflicts with this more specific statement; follow the content-specific notice and retain provenance. Early timestamps reduce modern-LLM contamination, but bots, templates, quoted passages and automated notices require filtering. It represents collaborative editing discussions, not everyday Weibo, private messaging or personal essays.

Recommended role: short-form dialogue and pragmatic transitions, with account/thread/date-group splits. Reconstruct one declared revision state per comment and deduplicate edits; do not treat restoration copies as independent prose. Do not publish usernames as stylometric identities when only linguistic aggregate analysis is needed.

## 2. Academic candidate: CSL

[Original COLING 2022 paper](https://aclanthology.org/2022.coling-1.344/), [official repository and license statement](https://github.com/ydli-ai/CSL).

396,209 Chinese core-journal metadata records dated 2010–2020, from the National Engineering Research Center for Science and Technology Resources Sharing Service; 13 categories and 67 disciplines. Includes titles, abstracts, keywords and labels, **not full papers**. The paper says authors supplied these metadata and reports only accessing publicly available metadata. The repository declares Apache 2.0 using software-license language; do not silently assume this resolves every underlying publisher/author text right. This is a feasible research candidate with explicit repository terms and strong pre-ChatGPT provenance, subject to checking dataset-license scope before redistribution or model release. Peer review and timestamps do not prove single-author, unassisted prose or factual correctness.

Recommended role: disciplinary abstract style and rhetoric, not long-form argument structure. Original article/year identifiers and author/journal mapping need verification before writer- or journal-disjoint experiments; the released task tuple alone does not guarantee those fields.

## 3. Small syntax-validation candidate: UD Chinese GSD

[Official treebank page](https://universaldependencies.org/treebanks/zh_gsd/index.html), [repository](https://github.com/UniversalDependencies/UD_Chinese-GSD).

Traditional Chinese Wikipedia treebank, annotated/converted by Google; official declared license CC BY-SA 4.0. POS/dependency annotations mix manual non-UD annotation and automated conversion; some attributes are automatically assigned with partial manual correction. This supports auditing tokenization, parts of speech and dependency features. It is not an author-profile corpus, a representative conversational sample or intact long documents. Pin a release and verify sentence totals there rather than repeating an unversioned number. Source content is human-origin Wikipedia with collaborative editing, not verified single-author prose.

## 4. Broad web pool to postpone: CLUECorpus2020

[Original technical report](https://arxiv.org/abs/2003.01355), [official repository](https://github.com/CLUEbenchmark/CLUECorpus2020), [LICENSE](https://github.com/CLUEbenchmark/CLUECorpus2020/blob/master/LICENSE).

Common-Crawl-derived Chinese web corpus; the original report describes 100 GB raw text and 35 billion characters. Repository also lists news, community text, Wikipedia and reviews in a smaller collection. Root license is MIT and explicitly phrased for software/documentation; a scrape-level license and per-source rights must be audited separately. A pre-2020 release offers useful temporal provenance but not verified human authorship, author identity, representative sampling or source-level consent. Boilerplate and cross-site duplication can dominate distributions. It is an exploratory background pool, not the initial gold reference corpus.

## 5. Blog and long-form essay gap

No off-the-shelf Chinese personal-blog corpus with both verified human authorship and clearly adequate text-reuse rights was established in this bounded audit. Do not fill this gap by treating any public GitHub mirror as licensed. Better candidate construction is a small opt-in or explicitly CC-licensed set of dated posts, with original URLs, author identities or approved pseudonyms, declared translation status and a license snapshot. Verify that the license covers prose, not only a theme/source-code repository.

Historic public-domain literary works can test long-form measurements, but their period/register is a different population. Use work-specific rights notices and reliable editions; avoid assuming every Wikisource page or modern transcription/translation is public domain. Current Wikipedia text has explicit Wikimedia reuse terms, but collaborative authorship and possible contemporary machine assistance remain confounds.

## 6. Proposed provenance schema and admission gates

For each future sample retain: source URL; collection and earliest verifiable publication timestamps; document/revision ID; content hash; license identifier and exact notice URL; source/platform; declared author or approved pseudonymous ID; genre; language/script; editorial/translation/automation status; consent/rights notes; quote and template spans; segmentation version; split-group IDs.

Admission gates:

1. **Rights:** text scope and permitted use known; quarantine unresolved cases
2. **Origin:** original publisher or maintainer verified; mirrors alone are insufficient
3. **Authorship confidence:** record evidence and uncertainty rather than a hard human label
4. **Unit integrity:** distinguish comments from revision actions, abstracts from papers, chapters from books, pairs from documents
5. **Leakage:** deduplicate near-matches before author/source/topic-group splits
6. **Representativeness:** allocate by research question and register, not available bytes
7. **Privacy:** retain only needed identifiers, remove sensitive disclosures, and honor source removal processes

A pre-2022 timestamp is a useful prior, not proof: template generation, translation, ghostwriting and older automation existed. Conversely, polished or formulaic writing does not establish AI authorship. The compiler should report provenance uncertainty and never manufacture ground truth through its own detector.
