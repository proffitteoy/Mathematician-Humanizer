# Bounded Chinese long-form acquisition and source audit

Checked 2026-10-02 UTC. This package adds **measured source samples**, not another list of prospective corpora. No raw source prose is included in these deliverables.

## Result

**13 complete Markdown documents / 133,637 source-text bytes / 13 verified Git blob identities** were acquired from three primary repositories at pinned historical commits. The declared production units are **two repeated blog bylines and three named interview respondents**. They are not five independently verified natural authors of all included words.

Every document meets a transparent long-form diagnostic: at least 1,000 Han characters in prose/list-continuation candidates and at least eight such paragraph-like blocks. The measured range is **1,125–4,789 Han characters**, median **2,437**; block count range **9–32**, median **15**. These are block-scanner measurements, not Chinese word counts, linguistic paragraph gold labels, or clean author-only prose.

This materially improves on NUS SMS (median 11 characters) and CSL abstracts (median 193.5 characters): complete sustained arguments, experiential narratives/advice, and elicited interview answers can now be inspected with original structure. It does **not** establish broad human-language coverage or solve the unrestricted, many-author blog corpus gap.

## Acquired sources

### Yihui Xie / 谢益辉: four blog articles

[Primary repository snapshot](https://github.com/yihui/yihui.org/tree/017635f6514ab5f7ed0cabd1ceab9701c49002a6), maintainer commit timestamp 2021-12-25.

- 职业羞耻感, 2017-02-25: argumentative essay about work and social responsibility
- 袋鼠国归来, 2017-06-03: travel narrative
- 身健在，且加班, 2019-04-05: work-organization argument mixed with first-person experience
- 他乡遇故吃, 2019-12-11: food memoir

The [historical README](https://github.com/yihui/yihui.org/blob/017635f6514ab5f7ed0cabd1ceab9701c49002a6/README.md) explicitly applies CC BY-NC-SA 4.0 to page content. This overrides neither third-party rights nor the noncommercial limitation. The repository's software MIT badge is not used as the text license. Article files lack individual author fields; attribution comes from the site's declared default byline.

Yihui was already a metadata-only noncommercial candidate in the earlier source catalogue. This is newly inspected long-form material relative to the acquired 788+39 blog sets, **not discovery of a previously unknown source**.

### Miao Yu / 于淼: six blog articles

[Primary repository snapshot](https://github.com/yufree/yufree.cn/tree/3de429db3216b9cbc3ac32d41f993b83181eecd3), maintainer commit timestamp recorded in the manifest.

- 旅居杂记, 2019-03-16: reflection on sojourning and belonging
- 博物馆, 2020-12-07: personal museum experience and visitor advice
- 情绪化, 2021-04-22: social commentary
- 科普与精英主义, 2021-07-11: argument about science communication
- 地铁数列, 2021-09-13: an opening puzzle frames an argument about art criticism; it is not fiction
- 观书有感, 2021-10-09: reflection on reading and nonfiction writing

The pinned site uses its author's [theme submodule footer](https://github.com/yufree/hugo-lithium-theme/blob/3a86ef906347706d8c11c92361623706a9f5d4c9/layouts/partials/footer.html), which explicitly links CC BY-NC-SA 4.0. The same notice is visible on a [current article page](https://yufree.cn/cn/2021/07/11/popular-science/). The chain from site commit → .gitmodules → pinned author-maintained theme → footer is preserved locally. Four sampled files explicitly name Miao Yu; two have an empty author field and use site-default attribution. These are different strengths of attribution evidence.

### Liqi project: three elicited interviews

[Primary project snapshot](https://github.com/LiqiVolunteer/fangtan/tree/2e82da59fecc814dd75301b5092faab2c95e210a), 2019-04-30.

- hb: project README groups publication in December 2018; latest file-commit claim is 2018-12-19
- Sofish: grouped in December 2018; latest file-commit claim is 2018-12-25
- ZachSaw: grouped in January 2019; latest file-commit claim is 2019-01-02

The [project README](https://github.com/LiqiVolunteer/fangtan/blob/2e82da59fecc814dd75301b5092faab2c95e210a/README.md) describes participant contributions and CC-BY-NC-SA sharing. **It does not specify a license version.** That omission remains an explicit rights gate for broader downstream use. The original lisan.io URLs are preserved from the README; current pages could not be retrieved. Exact original publication days are not supplied and are not invented from Git commit dates.

Respondents are distinct named contribution units; the interviewer/editor identities and degree of language editing are unresolved. Neither LiqiVolunteer nor lisan.io is treated as the article author. These three documents support between-respondent comparisons under similar questions, but only one interview per respondent is available in this pinned repository.

## Structure and source findings

1. **The argument prose is genuinely long.** It is not padded with source code or expanded abstracts. No fenced-code blocks occur in this selected sample. However, source-level length is still not a human-authorship certificate.
2. **Indentation matters.** Much of 身健在，且加班 is four-space-indented continuation prose under ordered questions. Treating every indented line as code would discard substantive argument. The audit preserves that role separately.
3. **Interview questions are a shared template.** H2 questions in two interviews and bold-paragraph questions in the third are marked as interviewer/project text, not respondent prose. Answer lists remain separate list roles rather than being flattened into paragraphs.
4. **Quotation roles differ.** In 职业羞耻感, one marked block attributes someone else's statement and another quotes the author's earlier social post. Both remain quotation-role evidence; neither is automatically a new independent work. Inline reported speech, book paraphrases and footnotes are still not fully attributed.
5. **Administrative material survives without becoming prose evidence.** 博物馆 ends with an old postcard campaign, registration link and image. The source is preserved intact, but that ending is flagged separately and excluded from the long-form diagnostic. The form was not opened or populated.
6. **No remote images, comments, logs or personal inboxes were acquired.** Images retain source references only. No raw article text is redistributed.
7. Seven audit checks pass: byte-covering span partitions, span hashes, question boundaries without blank lines, indented list prose, frontmatter/quotes, campaign boundary and exclusion of baseline/owner repositories. This is not full CommonMark/rendering validation or independent linguistic annotation.

## What coverage actually increased

The useful additions are three broad forms: argumentative/reflective blog essays, experiential blog narrative/advice, and elicited Q&A. Five provisional routing labels in the manifest are **not five independently balanced genres**.

Two blog bylines both contribute argument, but their sources and periods are different. Other form labels have sparse or single-author cells. Three interview respondents share a format, yet have no repeated documents across topics or periods. The document-weighted inverse-HHI of the five declared units is only **3.073**, even in this small hand-selected set.

The existing acquired blog inventory comprises Harttle, wu-kan, ddadaal and the 39-document Zhengtianbao pilot. Authorized repository metadata confirmed that fourth source. This sample does not draw from them or the excluded owner's blog. No combined “independent author total” is asserted across sources with different authorship evidence.

Selection is purposive and biased toward educated, technically connected web writers and creative-tool users. Adding their nontechnical prose reduces the prior code/tutorial dominance; it does not represent Chinese society, professionally edited essays, fiction, spontaneous conversation or population author variation. Dates are publication claims plus content-addressed maintainer history. Unsigned historical commits are not independent timestamps, and even signed repository history is not proof of unaided human composition. **Verified unaided human documents: 0. Model-admitted documents: 0.**

## Rights and resource boundaries

All three source families impose noncommercial conditions; Liqi's exact license version is unresolved. They are kept as bounded source/structure research observations, with no unrestricted commercial or training-use claim. Any later use must fit the applicable license or obtain the required permission. The [CC BY-NC-SA 4.0 deed](https://creativecommons.org/licenses/by-nc-sa/4.0/) also warns that privacy, publicity, moral and third-party rights may remain.

Raw articles total 133,637 bytes. Recorded HTTP bodies plus connector provenance responses and a 64 KiB preliminary/retry-metadata allowance total **1,284,857 bytes**, well below 20 MiB. This is logical research-payload accounting, not a measurement of encrypted network overhead. Acquisition used sequential bounded reads, no archives, no source-code execution and no downloaded executables. Parsing was capped at 512 MiB address space.

MPWAC's huge archive was not fetched. This task does not imply that a supported, permitted small sample of that release has been established. Other leads with unresolved text licenses or inaccessible source histories were not promoted into the measured corpus.

## Deliverables and stopping condition

- `candidate_manifest.json`: exact public source URLs, immutable commits/blob hashes, declared author/respondent units, date evidence, rights, provisional tasks and measured structures for all 13 documents
- `aggregate_audit.json`: measured results and their interpretation limits
- `acquisition_receipt.json`: bounded transfer accounting
- `sample_verification.txt`: seven passing checks
- `sample_freeze.json`: hashes fixing this 13-document audit before any larger metadata inventory

The immediate sample-audit task is complete. The larger multi-author long-form acquisition goal remains open. The separately generated pinned-frame inventory quantifies the next possible batch without upgrading metadata-only candidates to long prose, clean human text or independent authors.
