# Chinese corpus candidates: provenance before scale

Checked 1 October 2026. Metadata/licensing research was followed by one bounded local WikiConv Chinese-2002 format/provenance pilot (22,364-byte archive); no bulk corpora downloaded, no raw corpus committed and no H_G reference admitted. Personal material, including `proffitteoy/nothing-new`, was not inspected and is excluded until separately authorized.

## 1. Best first conversational candidate: WikiConv Chinese

[Original EMNLP 2018 paper](https://aclanthology.org/D18-1305/), [maintainer’s corpus README](https://github.com/conversationai/wikidetox/tree/main/wikiconv), [Chinese release](https://figshare.com/articles/dataset/WikiConv_-_Chinese/7376012), [ConvoKit documentation](https://convokit.cornell.edu/documentation/wikiconv.html).

Wikipedia talk-page history, from a 2018-07-01 dump. The Chinese release covers 87,005 users and 7,731,744 conversational **actions**, not that many independent messages. Actions include additions, edits, deletion and restoration; revision and reply metadata allow reconstruction. Chinese years available through ConvoKit are 2002–2018. Maintainer terms distinguish CC0 metadata from CC BY-SA 3.0 comment content. Figshare's generic CC BY 4.0 badge conflicts with this more specific statement; follow the content-specific notice and retain provenance. Early timestamps reduce modern-LLM contamination, but bots, templates, quoted passages and automated notices require filtering. It represents collaborative editing discussions, not everyday Weibo, private messaging or personal essays.

Recommended role: short-form dialogue and pragmatic transitions, with account/thread/date-group splits. Reconstruct one declared revision state per comment and deduplicate edits; do not treat restoration copies as independent prose. The maintainer schema's `user_id`/`user_text` identify the actor submitting an edit. A deletion, restoration or modification actor is not automatically the author of the underlying wording. Keep edit actor, initial comment attribution, subsequent contributors and quoted speaker distinct. The [ConvoKit representation](https://convokit.cornell.edu/documentation/wikiconv.html) exposes final utterance states plus modification/deletion/restoration histories; it must not be silently pooled with raw action rows. Do not publish usernames as stylometric identities when only linguistic aggregate analysis is needed.

## 2. Academic candidate: CSL

[Original COLING 2022 paper](https://aclanthology.org/2022.coling-1.344/), [official repository and license statement](https://github.com/ydli-ai/CSL).

396,209 Chinese core-journal metadata records dated 2010–2020, from the National Engineering Research Center for Science and Technology Resources Sharing Service; 13 categories and 67 disciplines. Includes titles, abstracts, keywords and labels, **not full papers**. The paper says authors supplied these metadata and reports only accessing publicly available metadata. Its Ethical Considerations section explicitly reports permission to use some metadata for NLP research: this is positive rights evidence, not an absence of permission. The repository declares Apache 2.0 using software-license language; downstream scope over underlying texts, later instruction-data variants and redistribution still needs verification. The historical publication interval is documented, but the analyzed bytes and released version also need binding to a preservation record; a date range alone does not verify every current record. Peer review and timestamps do not prove single-author, unassisted prose or factual correctness.

Recommended role: disciplinary abstract style and rhetoric, not long-form argument structure. Original article/year identifiers and author/journal mapping need verification before writer- or journal-disjoint experiments; the released task tuple alone does not guarantee those fields.

## 3. Small syntax-validation candidate: UD Chinese GSD

[Official treebank page](https://universaldependencies.org/treebanks/zh_gsd/index.html), [repository](https://github.com/UniversalDependencies/UD_Chinese-GSD).

Traditional Chinese Wikipedia treebank, annotated/converted by Google; official declared treebank license CC BY-SA 4.0. **Annotation and underlying-text rights must remain distinct.** The [official README changelog, entry dated 2019-11-15 for v2.5](https://github.com/UniversalDependencies/UD_Chinese-GSD/blob/e0d85a020182e264d6384be2a59c0f4879a1cc35/README.md#changelog) says removal of the NC restriction applies to UD annotations, while Google claims no ownership or copyright over the underlying content. This README was verified at commit `e0d85a020182e264d6384be2a59c0f4879a1cc35` (r2.17/r2.18 tag target); the pinned [LICENSE.txt](https://github.com/UniversalDependencies/UD_Chinese-GSD/blob/e0d85a020182e264d6384be2a59c0f4879a1cc35/LICENSE.txt) states the treebank license. This is not evidence that the prose is unlicensed; it means source-text license and attribution need their own trace before text reuse/redistribution clearance.

POS/dependency annotations mix manual non-UD annotation and automated conversion; some attributes are automatically assigned with partial manual correction. This supports auditing tokenization, parts of speech and dependency features. It is not an author-profile corpus, a representative conversational sample or intact long documents. Pin text and annotation versions separately: later annotation revisions do not establish a new composition date, while old release dates do not prove current text bytes are unchanged. Source description establishes a Wikipedia collection, not verified single-author or unassisted status for every sentence.

## 4. Broad web pool to postpone: CLUECorpus2020

[Original technical report](https://arxiv.org/abs/2003.01355), [official repository](https://github.com/CLUEbenchmark/CLUECorpus2020), [LICENSE](https://github.com/CLUEbenchmark/CLUECorpus2020/blob/master/LICENSE).

Common-Crawl-derived Chinese web corpus; the original report describes 100 GB raw text and 35 billion characters. Repository also lists news, community text, Wikipedia and reviews in a smaller collection. Root license is MIT and explicitly phrased for software/documentation; a scrape-level license and per-source rights must be audited separately. A pre-2020 release offers useful temporal provenance but not verified human authorship, author identity, representative sampling or source-level consent. Boilerplate and cross-site duplication can dominate distributions. It is an exploratory background pool, not the initial gold reference corpus.

## 5. Blog and long-form essay gap

No off-the-shelf Chinese personal-blog corpus with both verified human authorship and clearly adequate text-reuse rights was established in this bounded audit. Do not fill this gap by treating any public GitHub mirror as licensed. Better candidate construction is a small opt-in or explicitly CC-licensed set of dated posts, with original URLs, author identities or approved pseudonyms, declared translation status and a license snapshot. Verify that the license covers prose, not only a theme/source-code repository.

Later candidate check: [Yihui's official repository README](https://github.com/yihui/yihui.org#readme) explicitly licenses page content under CC BY-NC-SA 4.0 and says the site includes Chinese and English blogs plus project pages. This is a concrete prose-license candidate, distinct from the repository's software MIT notice. It is not a ready human-reference corpus: individual quotations, translations, revision history, historical evidence and the intended noncommercial use still require review. A dated page on the current branch is not an immutable historical text. One author/site also cannot identify population-wide author or source variation. No posts were imported or profiled.

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

A historical timestamp is evidence with a stated scope, not a universal binary label: template generation, translation, ghostwriting and older automation existed. A trustworthy record binding particular bytes to an earlier time can exclude later-origin generation of that preserved version; a current page's old display date cannot. Git hashes fix objects, but author/committer dates are supplied metadata, as the [official Git documentation](https://git-scm.com/docs/git-commit#_commit_information) explains. Conversely, polished or formulaic writing does not establish AI authorship. The compiler should report provenance uncertainty and never manufacture ground truth through its own detector. See the [provenance feasibility decision and bounded pilot results](design/provenance-feasibility-v0.1.zh.md): the local archive audit found 79 headers among 84 top-level records, unresolved version numbering and incomplete context. It supports format/attribution diagnostics, not population fitting; raw texts remain outside this repository.
