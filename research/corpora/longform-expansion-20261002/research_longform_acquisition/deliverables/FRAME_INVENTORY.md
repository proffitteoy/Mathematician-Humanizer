# Pinned historical frame inventory and next batch

This is metadata inventory after the 13-document audit was frozen. No additional article bodies were downloaded for this step; all three complete Git trees had already been obtained. Dates below are path or README claims, not independently certified dates of composition.

## Full available source frames

| Primary frame | Matching source files | Source bytes | After index/child-section exclusions | Path-level work families | Declared production units |
|---|---:|---:|---:|---:|---|
| Yihui Chinese Markdown/RMarkdown | 1,274 | 3,602,536 | 1,269 files / 3,506,146 bytes | 1,266 | one default blog byline |
| Yufree Chinese Markdown/RMarkdown | 305 | 3,118,583 | 304 files / 3,118,543 bytes | 304 | one default blog byline |
| Liqi repository interviews | 3 | 19,676 | 3 files / 19,676 bytes | 3 | three named respondents; editor roles unresolved |

Combined matching frame: **1,582 source files / 6,740,795 bytes**. After excluding two blog section indexes and four child-section paths: **1,576 article-candidate source files / 6,644,365 bytes**, representing **1,573 path-level work families**. These are ceilings before actual language, prose, originality, privacy and source-role review, not admitted documents.

- Yihui's path years span 2001 and 2005–2021. Three `.Rmd`/`.md` pairs share paths and are alternative views of three works. Four `content/cn/kids/` paths, including that section's index, were quarantined without downloading their bodies
- Yufree's source paths span 2012–2021. There are 48 `.Rmd` files with 48 corresponding rendered HTML views, which are not added as new works. Two further HTML-only article candidates are inventoried separately: 9,456 bytes for `2020-04-07-covid-19-community.html` and 386,207 bytes for `2021-03-07-demo-ml-metabolomics/index.html`. Their prose length, embedded material and role suitability are unverified, and neither was downloaded
- Liqi's entire available Markdown article frame is the three already sampled interviews. Its README links **34 distinct interview URLs**, covering July 2018–April 2019, but **31 have no body in this repository**. That list is a catalogue of leads, not 34 acquired documents or 34 verified authors. Exact days are generally absent. Current retrieval of the tested original lisan.io article URLs failed

Full paths, bytes, blobs, source URLs, exclusions and path-year counts are in `pinned_frame_inventory.json`. No source body text is included.

## Exact proposed next batch

A smaller next step is a **221-file / 2,790,922-byte** long-form-enriched Markdown reconnaissance batch:

- Yihui: **49 files / 761,628 bytes**
- Yufree: **172 files / 2,029,294 bytes**
- Maximum individual file: **98,496 bytes**
- Additional declared blog bylines: **0**
- Additional interview respondents: **0**

Deterministic selection: remaining `.md` article candidates dated in their paths from 2015 through 2021, at least 6,000 source bytes, excluding already sampled files, section indexes, all `kids/` paths and RMarkdown. The exact file/URL/blob manifest is `next_batch_proposal.json`. Source-byte size is only a length-enrichment heuristic; it does not establish the amount of Chinese prose. **The batch has not been acquired.**

Current conservatively accounted primary payload is 1,284,857 bytes. This proposed batch would bring it to **4,075,779 bytes**, below the same 20 MiB cap. Even all remaining non-quarantined Markdown/RMarkdown candidate bytes, **6,510,728**, would fit the byte budget, for a total of **7,795,585 bytes**. That larger option is not recommended before role-quality review, and the two HTML-only candidates are outside that calculation.

## Extraction and admission approach

1. Fetch sequentially from the pinned raw URLs with response and aggregate limits; verify Git blob SHA-1, SHA-256 and exact bytes before parsing. Do not execute source, RMarkdown, JavaScript or notebook cells
2. Preserve the complete original source and a byte-covering role map. Distinguish frontmatter, headings, ordered/list continuations, code, explicit quotation, image/reference/caption material and administrative tails. Do not stitch text across removed spans
3. Inspect inline and indirect quotation, translations, copied tutorials, book notes, self-reuse and multi-part series. Group translations, rendered versions and related source/quotation families for leakage control
4. Screen personal/minor-related material and unusual rights notices before retaining prose for a model dataset. Excluding a children-named directory is only an initial precaution, not a completed privacy audit
5. Count actual long-form candidates and provisional tasks only after inspection; keep unknown authorship, editing and assistance status. Noncommercial fit and source rights remain required. Metadata volume does not resolve these gates
6. To close the many-author gap, acquire different, appropriately licensed author communities with repeated works under overlapping tasks and topics. More documents from these two blogs increase within-source evidence, not author–source separation. The 31 missing Liqi bodies need an accessible primary release or authorized source copies, and the project needs an exact license-version clarification

No training, model fitting, raw redistribution or new author-count claim is authorized or performed by this inventory.
