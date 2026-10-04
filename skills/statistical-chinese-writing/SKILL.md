---
name: statistical-chinese-writing
description: Write or rewrite Chinese using multiple empirically observed TRAIN HUMAN Baike/Web source-conditioned statistical reference neighbourhoods, while preserving supplied meaning and voice. Use for Chinese prose writing, revision, humanizer-style editing and explicit statistical-style or style-compiler requests; preserve genre and voice, not authorship detection or a universal human style.
---

# Statistical Chinese Writing

Write usable Chinese through a mandatory measure–diagnose–revise–remeasure loop. The supplied parser measures every original and candidate; reference coordinates guide targeted revisions, never a universal human score. This remains a writing prototype: human preference and quality gains are unvalidated.

## Integrated editorial workflow

Read [editorial-layers.md](references/editorial-layers.md) for author/reader calibration, genre routing, paragraph logic, rhythm, word choice, justified omissions, and rollback. Apply architecture before sentence and surface edits. This is not a union of forbidden-word lists: factual accuracy, protected text, user voice and genre override every heuristic.

Run the non-mutating [lint and review workflow](references/lint-and-review.md) on the exact original and candidate. Its soft observations do not measure Chinese statistics, prove semantic fidelity, or score human authorship. Keep protected code/math/quotes/URLs and explicitly locked literals unchanged during style-only edits. Review meaningful warnings rather than trying to reach zero.

Source-specific adoption decisions and license/provenance are in [humanizer-integration.md](references/humanizer-integration.md). Existing measurement assets remain unchanged. The sibling [Tao mathematical exposition skill](../tao-inspired-math-exposition/SKILL.md) is the specialized mathematics reference module. In mathematical prose, theorem hypotheses and proof dependencies outrank rhetorical brevity.

## Read only what is needed

- Read [measurement-loop.md](references/measurement-loop.md) for the executable commands, pinned runtime setup, revision receipts, and semantic gate. Measurement is required; a missing runtime produces NOT_VERIFIED, never acceptance.
- Read [reference-guide.md](references/reference-guide.md) to interpret source conditions, neighbourhoods, and permitted writing moves.
- Use `python scripts/show_reference.py baike lower_single_han_share` or `python scripts/show_reference.py web upper_single_han_share` to inspect a compact, jointly conditioned card. Resolve script paths relative to this skill folder. All exact cards are in [human-joint-reference.json](references/human-joint-reference.json).
- Read [example-measurement-note.md](references/example-measurement-note.md) for actual measured successes and misses; [measured-owned-examples.json](references/measured-owned-examples.json) contains the results.
- Read [owned-examples.json](references/owned-examples.json) only for a same-content demonstration. The example text is explicitly AI-generated fiction, not corpus evidence or proven good writing. Its frozen hashes are in [owned-examples.freeze.json](references/owned-examples.freeze.json).

## Preserve the writing task

1. Extract a short content ledger from the supplied text/brief: entities, quantities and units, times, who does what to whom, scope, qualifications, negation, uncertainty, and attributed views. Distinguish required wording from ideas that may be rephrased. Preserve the supplied speaker, attitude, register, and degree of certainty.
2. Use the user's requested source/tendency if supplied. Otherwise choose a plausible reference based on the task, not a claim about the author's identity. For a broad request to demonstrate variation, provide two versions: a Baike lower-single-Han-share-guided candidate and a Web upper-single-Han-share-guided candidate. For an ordinary single rewrite, choose one appropriate neighbourhood and produce one draft; do not force the user through a questionnaire.
3. Treat one source-plus-band card as a bundle. Its ten coordinates were summarized from the same observed subset. Read its quantiles and covariation together. Do not assemble ten independently selected percentiles, turn its means into ten compulsory targets, or describe its coordinatewise ranges as a joint acceptance region. A middle band is also available; preserve variation within every band.
4. Write or revise using a few content-compatible choices of lexical units and clause packaging. The guide gives concrete moves; these are writing hypotheses informed by observations, not learned causal rules. Keep natural irregularity. Do not create a per-word plan or quotas for verbs, pronouns, short words, or negators.
5. Run `scripts/prose_lint.py` and reconcile the draft with every ledger item. Explicitly review unchanged passages and potential false positives; restore any edit that erases a necessary premise, attribution, actual uncertainty, author voice or meaningful Unicode. Document meaningful decisions in `editorial_review` as described in the lint guide. Specifically check caps versus exact amounts, first dates versus recurring dates, conjunctions/disjunctions, attachment of conditions, and negation scope. Remove unsupported experiences, emotions, examples, benefits, relationships, or causal claims. An author/self-check is not independent semantic or human validation.
6. Freeze the exact original file and first draft as separate UTF-8 files. Run `scripts/measure_text.py` on both using the same source/band and pinned runtime. The script does not strip, normalize, delete formulas, or rewrite line breaks. Compare all ten actual coordinates with q10/q90 and support; inspect any missing values, parser failures, and dimensions that moved against the intended change. Do not substitute visual estimates or a different tokenizer.
7. Diagnose a few content-compatible changes from the measured deviations and writing problems. Revise the text, save a new version, reconcile the content ledger again, and run the same measurement on the new exact bytes with `--previous` pointing to the prior receipt. At least one measured revision/remeasurement is required when the first candidate has an identified fixable writing or targeted-dimensional problem; a retained deviation needs a concrete meaning/voice reason. Do not mechanically repair every outlier.
8. Run `scripts/check_revision.py` on original and final measurements with their exact text files and a hash-bound semantic review. Then run `scripts/check_editorial_revision.py` with the same inputs, explicit locks and the extended editorial review. Only `MEASURED_AND_EDITORIALLY_REVIEWED` completes the integrated workflow; the older `MEASURED_AND_REVIEWED` status covers only its statistical/semantic portion. This status means measurements and an explicit content/voice review exist, not validated quality or statistical acceptance. A self-check must remain labelled a self-check. If measurement or runtime verification fails, a useful draft may still be delivered clearly labelled `NOT_VERIFIED`; do not call it accepted, measured, or complete under this skill.

## Priorities and stopping

Meaning, user voice, readability, and the requested format outrank a reference statistic. Zero first-person markers is acceptable in any source when the input has no first-person speaker. Never add `我/我们/你`, change `不/仅/最多`, replace an exact number, or insert fillers to meet a distribution.

Stop when the exact delivered version is measured, its meaningful diagnostic issues are revised or explicitly retained, and the semantic/voice gate is reconciled. If a revision worsens meaning or readability, discard that version and retain the better measured candidate with an explanation. Do not iterate only to move every coordinate inside a marginal interval, homogenize every paragraph, or normalize future articles to one vector. If blocked by a missing runtime or an unresolved semantic choice, report that blocker and keep the draft NOT_VERIFIED or pending review. When the available corpus conditions do not suit the requested voice, say the reference is limited and retain that voice.

## Required measurement, without overclaiming

- Parser/version/profile identity and feature denominators must match the reference measurement. A different tokenizer or guessed count is not comparable. This skill bundles the unchanged minimal measurement adapter and reference summaries. The official Stanza package and model checkpoints are external, pinned by [runtime-manifest.json](references/runtime-manifest.json). It bundles no raw corpus or 72 next-unit predictors; those predictors are not rewriters.
- Freeze example or evaluation prose before measurement. `scripts/freeze_examples.py` writes a new lock file, refusing to overwrite it. It checks exact literals and stated ledger IDs only. Do not present that as semantic equivalence testing. For another task use its own fact ledger and file; do not overwrite the demonstration.
- Report actual changes in individual relevant dimensions and any unexpected direction. Missing/undefined measurements stay missing; short texts can lack windowed measures. Small texts yield coarse, unstable proportions. Do not pad them to make a metric available.
- A covariance matrix describes observed co-movement; it is not a generation model, causal equation, or probability of human authorship. Do not output human-likeness, detector-evasion, quality, or authenticity scores, and do not assign a text to an author/genre class from these cards.
- If measured writing misses a hoped-for direction, say so. Preserve the original frozen result. Any revised version gets a new ID and hash, and remains a new candidate rather than an independent replication.

## Deliver the requested writing

Normally lead with the draft, not the research process. When variants are useful, label them by their concrete reference condition, such as “Baike 来源统计参考 · 低单字词占比倾向” and “Web 来源统计参考 · 高单字词占比倾向”. Do not call either “the human version” or imply that real people have only these styles.

Keep a content ledger with the work. Show it when the user asks for an audit or comparison, when a material ambiguity remains, or when producing a demonstration. Lead with the writing and add a compact measurement summary with actual values or a link to the receipt, the source/band used, material misses, and the semantic-review status. If runtime is unavailable, say “NOT_VERIFIED：尚未完成固定解析器测量”，rather than implying acceptance. A measured result can say: “已按固定口径测量并自查语义；不是作者鉴定，也未验证质量提升。” Do not bury the requested text in caveats.
