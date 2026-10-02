# Acquired pinned long-form stratum: 221-file structural/source audit

Checked 2026-10-02 UTC. This report concerns private noncommercial source research. It publishes no source prose, document-level numeric measurements, or private role spans.

## Result

**221 of 221 scheduled Markdown files were acquired and verified, totaling 2,790,922 original bytes.** Every file matches both the exact Git-tree byte count and pinned Git blob SHA-1; its SHA-256 is retained privately. All original bytes, line boundaries, quotations, lists, code, HTML comments and source metadata remain intact.

- Yihui: **49 files / 761,628 bytes**
- Yufree: **172 files / 2,029,294 bytes**
- Additional default blog bylines: **0**; the frame still uses the same two site bylines
- Verified unaided-human documents: **0**; model-admitted documents: **0**

The acquisition fulfilled the exact predetermined selection: remaining `.md` article candidates with path-date claims in 2015–2021 and at least 6,000 source bytes, excluding previously acquired sample paths, section indexes, child-section paths and RMarkdown. This is a **convenience stratum enriched for source length**, not representative human writing, a random sample, or 221 new authors.

## Characters, paragraphs and long-form screen

Across all 221 files:

- Complete source: **1,064,318 Unicode codepoints**, including **795,206 Han codepoints**
- Prose/list-continuation candidates: **782,707 codepoints**, including **661,981 Han codepoints**, in **4,104 paragraph-like blocks**
- Candidate Han count per file: **0 / 2,567 / 27,359** minimum / median / maximum
- Paragraph-like blocks per file: **0 / 12 / 215** minimum / median / maximum

**191/221 pass the operational screen** of at least 1,000 Han codepoints and eight prose/list-continuation blocks: **44/49 Yihui and 147/172 Yufree**. The other **30** remain acquired source observations, not missing downloads. Screen-positive files contain **624,634 candidate-prose Han codepoints** in **3,954 blocks**; their Han-count minimum / median / maximum is **1,047 / 2,789 / 27,359**.

“Paragraph-like block” means contiguous source lines in the same role, delimited by blanks or role changes. It is not a linguistic gold paragraph. Han counting covers U+3400–4DBF and U+4E00–9FFF; these are character counts, not Chinese words. Inline quotation, link text, Markdown syntax and unresolved borrowing can remain inside a prose candidate. Passing the screen does not grant authorship, rights, privacy or model-dataset clearance.

## Measured role mixture

The byte-covering scanner assigns every original source byte to a role. Principal aggregate roles are:

| Role | Source bytes | Blocks | Files containing role |
|---|---:|---:|---:|
| Prose candidates | 2,184,752 | 4,019 | 219 |
| List-continuation prose | 32,840 | 85 | 6 |
| List items | 251,794 | 1,316 | 64 |
| Marked quotation | 165,100 | 654 | 46 |
| Bibliographic/contributor labels | 51,147 | 985 | 7 |
| Fenced code | 27,491 | 90 | 11 |
| HTML/comment blocks | 25,193 | 16 | 7 |
| Frontmatter | 21,587 | 221 | 221 |
| Image references | 11,109 | 140 | 35 |

Headings, blanks, display mathematics, tables, standalone links, thematic breaks and ambiguous indentation are counted separately in `aggregate_audit.json`. Prose plus list continuations occupy approximately **79.46% of source bytes**. No source code was run, and no referenced images, forms, pages or datasets were fetched.

The scanner was extended conservatively from the earlier sample: correct-length fenced-code termination, multiline HTML comments/blocks, display mathematics, references and bibliographic/contributor labels are kept out of prose candidates. The original scanner and this version produce **the same 191 screen-positive decisions** on this batch. The prior 13-file sample reproduces under its unchanged original scanner, and all its frozen deliverables remain unchanged. This agreement is not full CommonMark validation.

## Language evidence

All 221 files contain at least 1,350 Han characters somewhere in the original source. A transparent script proxy, Han divided by Han plus ASCII Latin letters, marks **212 whole sources as Han-dominant** and **9 as mixed/Latin-heavier**. These latter results can reflect code, references and English paper titles, not a non-Chinese article.

Inside the narrower prose roles, after bibliographic/contributor labels are separated, **219 are Han-dominant**, **one is mixed**, and **one has no eligible prose letters** because it is entirely list-form content. This is a script diagnostic, not validated language identification or proof of human composition.

## Bounded source audit: why the roles matter

A targeted review of code-heavy, quotation-heavy, HTML-heavy, list-heavy, low-prose and script-outlier cases found material risks hidden by byte length:

1. **Book notes contain extensive third-party quotations.** Yihui's [Principles notes](https://github.com/yihui/yihui.org/blob/017635f6514ab5f7ed0cabd1ceab9701c49002a6/content/cn/2020-07-19-principles-notes.md) and [Poor Charlie's Almanack notes](https://github.com/yihui/yihui.org/blob/017635f6514ab5f7ed0cabd1ceab9701c49002a6/content/cn/2018-08-24-poor-charlies-almanack.md) alternate commentary with book excerpts. Their site's license is not evidence that every embedded quotation can be reused under that license.
2. **Markdown source includes text not rendered as normal article prose.** [The essay about Feng Zikai](https://github.com/yihui/yihui.org/blob/017635f6514ab5f7ed0cabd1ceab9701c49002a6/content/cn/2020-03-21-tk.md) retains literary excerpts inside HTML comments. The original bytes survive, but those spans are excluded from the prose diagnostic.
3. **Some large files are contributor compilations.** Seven Yufree research digests have repeated named-recommender labels and explicit community-contribution framing; [one pinned example](https://github.com/yufree/yufree.cn/blob/3de429db3216b9cbc3ac32d41f993b83181eecd3/content/cn/2021-07-01-2021-research-paper-one/index.md). Bibliographic titles, links, named recommendations, and list summaries are not all the default blogger's author prose. All seven fail the conservative prose screen. Named recommenders are not promoted to independently verified authors or extra author counts.
4. **Long lists can be meaningful writing without satisfying this screen.** Dictionary-style pieces and numbered reflections keep their list role. Excluding them from this narrow paragraph diagnostic does not mean their text is worthless or short.
5. **Technical prose and code remain mixed.** Some tutorials contain sustained argument as well as code; a source file's byte size alone cannot distinguish them.

Frontmatter attribution is also uneven: all 49 Yihui files lack a per-file author field. Among 172 Yufree files, 33 name Miao Yu, 108 have an empty author field, and 31 lack it. Site-default bylines are useful provenance but do not override embedded contribution, quote or editorial roles.

Automated review flags found inline quotation marks in 145 files, reprint/translation/rights terms in 32, family/minor-related terms in 95, email-like strings in two, and administrative-call terms in 59. These are deliberately broad lexical prompts for review, **not validated claims** that a file contains a child's private data, unauthorized reproduction, or an actual active solicitation. No full privacy, indirect-quotation or rights clearance is claimed.

## Duplication and repeated material

The comparison scope is the 221 new files plus the prior 13 local sample files, **234 total**. No other corpus or web source was searched.

- Exact full-source duplicate groups: **0**
- Normalized non-frontmatter full-body duplicate groups: **0**
- Exact normalized long prose-block repeats across documents: **0** under the stated minimum lengths
- Prose-shingle comparisons involving a new file: **27,183 pairs**
- High-overlap flags: **13 pairs among six digest documents**, all within Yufree, none involving the prior sample

Review of those flags identifies **shared short digest introductions**. Their main research summaries remain in list roles, so a small repeated introduction dominates the residual prose-shingle representation. These are not thirteen pairs of duplicate complete articles, and no files were removed. The finding is evidence to preserve a shared-template/series grouping, not evidence of plagiarism or clean independence elsewhere.

Full-body normalization is NFKC, whitespace removal and casefold. Long-paragraph matching requires at least 100 original codepoints and 40 Han characters. Near-overlap uses exact sets of normalized five-codepoint shingles within each prose span, never across removed role boundaries; flags require Jaccard ≥0.8, or smaller-set containment ≥0.8 with at least 200 shared shingles. These checks do not rule out paraphrase, shared book sources, translated reuse or quotation duplication outside the prose roles.

## Requests, resource limits and rights

First pass: **221 attempts, 217 verified, four network timeouts with zero response-body bytes**. Its state and receipt are preserved unchanged. A separately authorized, explicitly recorded single retry of the **same four pinned identities** succeeded. Final result: **225 HTTP requests, 221 verified files, no replacements, no redirects followed and no unrecorded retries**.

All downloads finished **400.113 seconds from the original acquisition start**, inside the original 590-second window. The acquisition used one bounded process at a time, with at most four concurrent requests, a 512 MiB address-space limit and exact-size-plus-one read caps. The structural/duplication audit also stayed below 512 MiB and completed in seconds; measured peak RSS is recorded in the receipts. Derived artifacts remain below 50 MiB.

Conservative cumulative accounting is **4,209,416 bytes against a 20,971,520-byte cap**: 1,284,857 previously accounted bytes, 2,790,922 new source bytes, plus a **133,637-byte reserve** for the earlier reproduction cache because its creation lacks a receipt establishing whether it was copied locally or downloaded again. Excluding that uncertainty reserve gives the original projected 4,075,779 bytes. These are logical response-body measurements and allowances, not encrypted wire traffic.

Both source families carry CC BY-NC-SA 4.0 notices: [Yihui's pinned README](https://github.com/yihui/yihui.org/blob/017635f6514ab5f7ed0cabd1ceab9701c49002a6/README.md) and [Yufree's pinned theme footer](https://github.com/yufree/hugo-lithium-theme/blob/3a86ef906347706d8c11c92361623706a9f5d4c9/layouts/partials/footer.html), linked from the site's pinned submodule. The noncommercial limitation and possible third-party, privacy, moral and publicity rights remain. Nothing here authorizes commercial training, raw redistribution, or an inference that all content is human-written or AI-free.

## Deliverables and reproduction

Publish only files listed in `PUBLICATION_ALLOWLIST.txt`: this report, aggregate audit, first/final receipts, source URL/blob provenance, own acquisition/audit/test code, verification results and checksum manifest. No remote writes were performed by this acquisition task.

The scripts record this exact bounded method and operate beside the earlier `research_longform_acquisition` package. Reproduction needs that package's pinned tree metadata, proposal and original 13-file sample plus an independently rights-appropriate private raw cache. `acquire_pinned.py` refuses an existing acquisition state; it does not silently repeat downloads. `retry_timeouts.py` preserves the first pass and is specific to the recorded four-timeout state and original wall cap, not a generic retry loop. `audit_pinned.py` and `verify_pinned.py` are offline once private inputs exist. Ten invariant/regression tests pass.

The private identity manifest, request-by-request history, document measurements, byte-span maps, source bodies and review extracts are deliberately excluded from the publication allowlist. **Acquisition and bounded audit are complete; author-level, privacy, rights and dataset-admission review remain open.**
