# New named-author Chinese essay and reporting stratum

Checked 2026-10-02 UTC. Baseline source reports: `proffitteoy/style-compiler` at `f6e2e43dbc0927bd881858bd5d84246b388b1ccf`.

## Result

**47 acquired articles, 12 new repeated named-author trajectories, two original publishing institutions.** This expands beyond the previously concentrated technical-blog author pool. It is a bounded source-research addition, not a feature extraction or fitted-model result.

- **芭樂人類學 / Guava Anthropology:** 41 articles, comprising four sole-byline pieces for each of ten identified contributors plus one separately labeled coauthored article
- **環境資訊中心 / Environmental Information Center:** three bylined articles each from two reporters, six articles total
- **Current pages claim publication between 2009-11-02 and 2021-12-29**
- **Verified immutable pre-2022 byte snapshots: zero**. The acquired bytes are current 2026 pages, not historically pinned Git blobs or recovered pre-2022 archives
- 182,610 body-text Unicode codepoints, including 147,793 Han codepoints and 1,136 nonempty source structural blocks. These include quotations, captions and references; they are not counts of clean sole-author prose
- 4,337,862 bytes of selected article HTML; 6,816,210 accounted direct response-body bytes including discovery/rights evidence and an initial probe allowance, below the 20 MiB limit
- Seventeen preservation/provenance checks pass. No source prose is in this public package

The usable contribution is **published, author-attributed Chinese writing with explicit uncertainty**. The absence of proof of unaided composition is not used to discard all real writing. Conversely, the named bylines and old publication dates are not converted into a claim that every word is original, unaided, unchanged since publication, or absent from language-model pretraining.

## Author trajectories and actual breadth

The [Guava author directory](https://guavanthropology.tw/index.php/article/6338) supplies contributor profiles and stable author pages. Its [about page](https://guavanthropology.tw/index.php/article/6337) identifies a collective blog founded in 2009, written largely by university and research-institute anthropologists. This is **public humanities/social-science writing by scholars**, not a corpus of peer-reviewed academic papers.

| Named author | Pre-2022 entries observed in author index | Date range of those indexed claims | Sole-byline articles acquired |
|---|---:|---|---:|
| 邱韻芳 | 36 | 2010-06-07–2021-10-04 | 4 |
| 趙恩潔 | 25 | 2012-11-02–2021-12-20 | 4 |
| 郭佩宜 | 25 | 2009-11-16–2021-11-29 | 4 |
| 趙綺芳 | 24 | 2009-11-30–2019-10-28 | 4 |
| 林秀幸 | 24 | 2009-11-09–2019-05-30 | 4 |
| 潘美玲 | 22 | 2011-01-10–2021-08-30 | 4 |
| 徐雨村 | 17 | 2010-08-30–2021-05-10 | 4 |
| 容邵武 | 14 | 2009-12-21–2020-03-23 | 4 |
| 彭仁郁 | 12 | 2013-06-03–2021-02-23 | 4 |
| 莊雅仲 | 14 | 2009-11-02–2021-12-29 | 4 |

The index observation totals 213 candidate entries, **not 213 downloaded articles**. The pilot selected four approximately date-spread entries per author, then added one replacement candidate after discovering a coauthor mismatch. The mismatched article was retained as coauthored, so nothing was silently overwritten or relabeled. Selection is a transparent convenience sample, not random or population representative.

Two additional trajectories are [陳文姿](https://e-info.org.tw/author/200003) (selected articles dated 2018, 2019 and 2020) and [賴品瑀](https://e-info.org.tw/author/200154) (2015, 2017 and 2018). Article metadata identifies them specifically as reporters, with separate fields for translators, reviewers, writers, outside sources and other bylines. Those roles must not be collapsed into one author field.

### Genres

Provisional article-level classifications, based on content and paratext review:

- Public/social commentary: 15
- Ethnographic field/travel essays: 12
- Film/book/performance criticism: 8
- Personal/research reflections: 6
- Reported environmental news: 6

At least two substantial nontechnical prose genres are now concretely present: field/travel essays and cultural criticism. The reporting stratum adds a second institutional editing context, but is shorter than many humanities pieces: its body Han count is 1,098 / 1,381 / 1,946 minimum / median / maximum, versus 1,581 / 2,814 / 7,571 for Guava. It should not be advertised as six giant investigative features.

Within-author variation is visible, but uneven. 邱韻芳 spans cultural travel, policy commentary and documentary criticism; 趙綺芳 spans performance criticism and embodied research reflection; 郭佩宜 spans social analysis, film discussion, a translator's afterword and Solomon Islands events. 潘美玲's four pieces remain one Tibet/India fieldwork series despite spanning different places and a decade. Ten contributors from one scholarly community are a real author expansion, **not ten independent platform or demographic strata**.

All these sources predominantly use Taiwan traditional-character Chinese. This materially broadens genre and byline coverage, while also introducing regional/script, institutional and topic differences from the prior technical bloggers. None of those differences can automatically be interpreted as author style.

## Rights and acquisition gates

### Guava Anthropology

Every one of the 41 selected article pages contains its own CC BY-NC-ND 3.0 Taiwan notice, with author attribution and article link. The site footer states the same default with exceptions. [Example article notice](https://guavanthropology.tw/article/6557), [license](https://creativecommons.org/licenses/by-nc-nd/3.0/tw/), [robots](https://guavanthropology.tw/robots.txt).

Article and author routes are not disallowed by the observed robots file. Acquisition preserves the complete original HTML, licenses, structural content and attribution privately. Images and linked works were not downloaded. The license's noncommercial and no-derivatives restrictions remain relevant, along with third-party quotations and privacy rights. This does not authorize commercial model training or publication of transformed source prose.

### Environmental Information Center

The [site license](https://e-info.org.tw/copyright) states CC BY-NC-ND 4.0 for eligible content, with exceptions for third-party material, separately marked works and project-specific content. The [foundation FAQ](https://tnf.org.tw/faq) expressly describes noncommercial academic research among permitted purposes. The observed [robots file](https://e-info.org.tw/robots.txt) permits routes generally. The six selected articles have source reporter fields and are catalogued as original reporting under the site default, with exception review preserved as a limitation.

The [editorial guidelines](https://e-info.org.tw/editorial-guidelines) separate authorship, reporting and editorial responsibility. Its current AI policy permits auxiliary uses such as translation, language correction and research assistance; this is a useful warning that missing AI labels do not prove no assistance. It is **not evidence that the selected 2015–2020 articles were AI-assisted**, nor a retroactive guarantee that they were not.

### Excluded: The Reporter / 報導者

Its article [CC license notice](https://www.twreporter.org/a/lience-footer) initially looked promising. However, the current [robots/usage notice](https://www.twreporter.org/robots.txt) explicitly prohibits automated scraping, text/data mining and AI/software evaluation without written permission. Therefore only rights/robots evidence was acquired; **no Reporter article corpus was acquired**. No alternate route or mirror was used to bypass that restriction.

## Preservation and attribution findings

1. **Index bylines can hide coauthorship.** [Guava 6907](https://guavanthropology.tw/index.php/article/6907) appears under 莊雅仲's index but credits 蔡侑霖、傅偉哲、鄧家洋、莊雅仲 on the article. It is kept as a four-person byline unit, not sole 莊雅仲 evidence and not three newly established trajectories. [Guava 6857](https://guavanthropology.tw/index.php/article/6857) provides the fourth sole-byline candidate instead.
2. **Some pieces explicitly disclose another publication venue.** [3512](https://guavanthropology.tw/index.php/article/3512) names 放映週報; [6906](https://guavanthropology.tw/index.php/article/6906) names 聯合副刊, 2021-12-09; [6805](https://guavanthropology.tw/article/6805) names 人類學視界 26:40–44. These are attributed republications/cross-publications, with deduplication-group notes. First-publication exclusivity and all external versions were not verified.
3. **A translator's afterword is not a translated-book corpus.** [6605](https://guavanthropology.tw/index.php/article/6605) explicitly describes a blog-specific afterword. Its speaker role is the named essayist/translator; the book author must not replace that byline.
4. **HTML structure matters.** [6886](https://guavanthropology.tw/index.php/article/6886) stores most prose in div elements. Initial p-only inspection produced just ten characters; full-body structural inspection recovers 4,558 Han characters. [6857](https://guavanthropology.tw/index.php/article/6857) has six long blocks and should not be artificially fragmented merely to pass an eight-paragraph threshold.
5. **Bylined articles contain other people's language.** [5111](https://guavanthropology.tw/article/5111) explicitly opens with a tourism-brochure excerpt. Other essays contain dialogue, quotations, references and captions. Structural roles are retained privately, but inline-source attribution is not gold annotated. Publicly discussed minors/trauma appear in at least one essay and require privacy-aware handling before broader use.

The source inspection view excludes comments and site navigation. Guava original HTML and body HTML remain intact; environmental-report DraftJS blocks and entity metadata remain intact. Character counts and structural checks are acquisition/completeness diagnostics only. No tokenization, syntactic parsing, style features or model fitting was performed.

## Historical certainty and modeling protocol

The source article dates and author-index dates agree for every Guava selection. Environmental metadata supplies earlier publication timestamps and separate 2026 updated-at timestamps. The latter may reflect migration or revision; this pass cannot determine which. Archive/CDX attempts did not return a usable historical capture. **Never mix these current-fetch/date-claimed pages into the pinned pre-2022 Git stratum without retaining that distinction.**

Recommended research use:

1. Keep source family, platform, genre, topic, script/region, publication-date claim, retrieval time, revision certainty, author unit and contribution role as separate variables
2. Treat the 46 sole-byline documents as repeated-author candidates and the one coauthored document as a separate unit; do not turn every contributor or quoted speaker into a new author
3. Preserve connected article/series, republication and same-event groups before any split. Check cross-source near-duplicates against the existing corpus in a later authorized analysis; no such comparison is claimed here
4. Use author-balanced sampling and matched topic/length/genre comparisons. The pilot is insufficient for a fully crossed author-by-genre design, especially for the Tibet/India series and two environment reporters
5. Perform span-level quotation, reference, caption, translation and privacy review before attributing all residual prose to individual authors. Keep paragraph order and do not concatenate across removed spans
6. Use ordinary human-publication evidence with an explicit assistance-unknown label. Do not require an impossible unaided-human certificate, and do not train a human/AI detector using date as a disguised label
7. Do not alter the currently frozen TRAIN/DEV/TEST experiment with this exploratory source pool. This task assigned no new split roles and did not touch its feature caches

No classics were substituted for modern writers. No owner blog was acquired. No new peer-reviewed academic-paper stratum was established here; that remains distinct from scholars' public essays.

## Receipts, limits and reproduction

70 requests are in the direct-download ledger; one article request timed out with zero response bytes and the same URL succeeded on one retry. An earlier successful 81,156-byte access probe preceded the ledger, so that amount is explicitly included as an allowance rather than silently omitted. One earlier CDX probe returned no body. Web search/open tool transport bytes are unavailable; the byte accounting applies to the bounded direct acquisition, not encrypted network traffic or search-engine infrastructure.

Lightweight acquisition and inspection are single-threaded; article downloads were sequential. Initial evidence/discovery work briefly overlapped network requests, so the initial manifest's concurrency-one intent should not be read as an observed whole-task network guarantee. No parallel model computation, GPU work or unbounded crawling occurred. All acquisition completed within the 30-minute first-pass window and well below 200 selected records.

`VERIFICATION.json` verifies response sizes and SHA-256 hashes, exact selection completion, dates, CC notices, byline roles, source-block handling and budget. `ARTICLE_CATALOG.jsonl` and `EINFO_ARTICLE_CATALOG.jsonl` contain public titles, links, dates, identities, roles, rights and limitations. The public package contains only these metadata, aggregate receipts and our own scripts. The local `private/` tree is excluded from publication.

Reproduction requires permitted access to the sources; current web bytes may change, and these checksums identify this fetch rather than guarantee later restoration. The private source cache is local and is not a durable published backup.

The final acquisition helper also refuses an existing receipt whose private cache is missing or altered, and hard-blocks Reporter URLs except the two rights-evidence paths. These post-acquisition safeguards do not rewrite any prior request result. Run scripts from their preserved public/ directory beside an authorized private/ cache; do not assume publishing this metadata also publishes or restores that cache.
