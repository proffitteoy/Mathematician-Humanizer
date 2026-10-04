# Humanizer integration research, 2026-10-04

This is the source-by-source adoption and adaptation catalog for this integrated skill. Repository detector results do not generalize by default. Upstream texts and scripts were read, not executed or installed. New implementation should be original. Preserve upstream license notices when incorporating substantial expressive content/code. No user text was uploaded to external detectors.

## Pinned sources and scope

- B = blader/humanizer @ 225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8, SKILL v3.1.0. MIT, Copyright 2025 Siqi Chen. https://github.com/blader/humanizer/blob/225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8/SKILL.md
- H = hannsxpeter/humanizer @ 978116a9ac2b094b7a6bb5f6a482b0eee41f3084, v1.2.1. MIT, Copyright 2026 aihxp. https://github.com/hannsxpeter/humanizer/blob/978116a9ac2b094b7a6bb5f6a482b0eee41f3084/SKILL.md
- K = keez97/humanizer @ 2d9a116fa9caee2c3466a7c7d419cbe02b35a470, v2.9.0. LICENSE contains MIT plus descent acknowledgment, Copyright 2025 Siqi Chen and 2026 Karim Atari. GitHub NOASSERTION is not absence of license. https://github.com/keez97/humanizer/blob/2d9a116fa9caee2c3466a7c7d419cbe02b35a470/SKILL.md
- R = harshaneel/humanize @ 9c3dec34dc8e0ed9d26de14a869900a714da8f9e. MIT. https://github.com/harshaneel/humanize/blob/9c3dec34dc8e0ed9d26de14a869900a714da8f9e/plugins/humanize/skills/humanize/SKILL.md
- A = Aparnabuilds/humanizer @ fd9728f1a66a5338dff533c712dd44509900e065, v3.0.0. MIT. https://github.com/Aparnabuilds/humanizer/blob/fd9728f1a66a5338dff533c712dd44509900e065/SKILL.md
- AB = Aboudjem/humanizer-skill @ a58df065367550b6ce40ff3f648335018d8e0589. MIT, Copyright 2026 Adam Boudjemaa. https://github.com/Aboudjem/humanizer-skill/blob/a58df065367550b6ce40ff3f648335018d8e0589/skills/humanizer/SKILL.md


Read scope: B full SKILL and package validation; H full SKILL + all five references + eval fixtures; K full SKILL + all four references + score.py, perplexity.py, binoculars.py; R full humanize and ai-check SKILLs, research reference, benchmark scripts/baseline, 14 scenario tests; A full SKILL and README. Bibliographies were inspected; their cited research papers were not all independently replicated or verified. Source heuristics therefore do not become scientific universal laws.

Repository counts do not represent independent methods. K explicitly descends from B; A credits B, Aboudjem and brandonwise. Much of B/H/K/A/AB derives from the same Wikipedia signs catalog. Distinct increments are voice/restraint/unicode (H), architecture plus numeric lint (K), statistical/rhetorical + benchmark (R), integrity/brand constraints (A), explanatory CLI/token-preservation (AB).

## Operational precedence

1. Current user requirements and document purpose.
2. Meaning, facts, exact spans, epistemic force, attribution, authorization, and relevant safety constraints.
3. Demonstrated author voice appropriate to this audience and channel.
4. Genre/locale conventions.
5. Evidence-backed editorial diagnosis.
6. Optional cosmetic defaults.

A pattern hit is a question to review, not proof of machine authorship. Never label a person, generation model, or AI-edited percentage from style alone. Never manufacture randomness, factual error, faulty calculation, memory, or opinion to satisfy a style rule.

## Comprehensive implementation catalog

Use each item as a rule with: id; phenomenon; source; applicability; exception; proposed action; meaning-risk; validation example. ADOPT = useful guard/practice; ADAPT = conditional diagnostic; REJECT = unsupported/destructive objective. Evidence labels: S=verified source instruction; M=mechanical behavior read in code; E=author's reported experiment; J=our editorial judgment. S does not imply proven efficacy.

### 01. Task, document, and edit-scope calibration (ADOPT; H step0, K modes, B file/embedded modes, A contexts)
- Determine rewrite/audit-only/proofread/voice-match and lightweight/standard/structural intensity.
- Determine audience, channel, genre, intended length and whether text is a reply with shared context.
- Isolate quoted speech, citations, code, URLs, commands, identifiers, frontmatter, tables and exact-data spans; prose edits cannot mutate them accidentally.
- Prefer small targeted edits when few concrete problems exist; unchanged is a valid outcome.
- Rebuild only when architecture is substantively defective, not because an arbitrary tell count was crossed.
- No unrequested in-place writes or publication; a file-write request governs output behavior rather than an upstream mandatory confirmation template.
- Detect-only never mutates input.

### 02. Meaning and claim ledger (ADOPT; H Meaning check; K principle8; A integrity)
- Inventory names, entities, numeric values, units, ranges, dates, versions, URLs, quotations, rankings, temporal sequence, attribution and causal claims.
- Compare source to output in both directions: detect additions and omissions, not merely whether old number strings remain.
- Preserve negation, obligation, possibility, approximation, comparison direction, scope, confidence, claimed intent, and who acted.
- Adding because/therefore/most/first/only/always is a semantic edit even without a new number.
- Opinion vs fact distinction: preserve existing opinions; do not invent user endorsement, stance, memories or relationships. Explicitly requested creative voice may adjust attitude to stated material but cannot invent world claims.
- If detail absent, simplify, keep supported abstraction, or ask; never pad with invented specifics.
- Correctness issue in source: flag it separately or ask permission to resolve substantive ambiguity; don't preserve/introduce demonstrably false mathematics as a style feature.
- Preserve truthful uncertainty and necessary risk/disclaimer text even when it sounds less punchy.

### 03. Writer-profile discovery and calibration (ADOPT/ADAPT; H voice-matching; K VOICE-CALIBRATION; R step0)
- Use supplied sample first, user-approved profile second; infer cautiously from input when neither exists.
- Observe sentence-length distribution, diction/register, paragraph openings, punctuation, recurring constructions, stance, humor, reader address, transitions and deliberate absences.
- Note sample confidence and domain mismatch; short samples cannot justify broad stable conclusions.
- Match distribution, not distinctive sentences, topic facts, opinions or personal experiences from sample.
- Author's demonstrated punctuation and lexical habits override generic style warning lists.
- Avoid caricature (not every sentence becomes a fragment because one sample did).
- Voice discovery should be task-scoped; no unnecessary scanning unrelated user folders.

### 04. Reader knowledge and reasoning omission (ADOPT; B26, K B9, R levers4/9)
- Retain implicit steps an intended reader can infer from shared context.
- Remove re-teaching of known background, duplicate diagnoses and proof irrelevant to the actual decision.
- Do not automatically add explanatory conclusions after examples.
- Keep incomplete thought, qualified intuition, genuine aside or unresolved emotional tension when it belongs to author and doesn't make a material claim misleading.
- Distinguish unstated reasoning from invalid inference; critical missing premise affecting truth/decision must be surfaced, not hidden.
- Tests: before/after should not acquire unrequested because/therefore chains or mini-lessons.

### 05. Content selection and paragraph weighting (ADAPT; K A2/A6, R lever4, A F4/F5)
- Unequal treatment may reflect actual importance; do not force one paragraph per idea or equal space per alternative.
- Merge redundant paragraphs, let a thought extend naturally, retain a meaningful digression.
- Paragraph-order swap can diagnose disconnected exposition but is not a universal failure: lists, reference material and modular reports can be reorderable.
- Opening need not announce an outline; useful navigation remains in long technical work.
- Preserve necessary dependencies without adding artificial transition words.
- Never add a fourth irrelevant element just to break a three-part structure.

### 06. Openings, conclusions, and staged importance (ADAPT; B1-5,13,24-26; K A5/B9; R SignalI; A E15)
- Cut broad world-changing openers where specific substance can begin immediately.
- Cut repetition of heading in first sentence and non-informative standalone setup.
- Remove fake candor, dramatic teaser questions, lesson closers and aphorisms when they merely restate.
- End on last useful detail, unresolved question or concrete action when appropriate; do not force a summary or optimistic uplift.
- Keep actual narrative suspense, literary refrain and useful synthesis when genre/author calls for them.
- A short sentence or attractive closing is not intrinsically artificial.

### 07. Stance, concessions, and false balance (ADAPT; K B13/Soul; R lever9; A E17; H stance-mode)
- Do not manufacture objection then refute it; keep real competing interpretations and options.
- Preserve asymmetry in evidence and author commitment; don't automatically split benefits/costs into matched halves.
- Preserve real ambiguity and mixed feelings rather than resolve to a tidy middle position.
- Do not turn neutral rewrite into a new recommendation without authorization/source support.
- Do not force first person, invented uncertainty or disagreement to satisfy a quota.

### 08. Sentence syntax and rhythm (ADAPT; B6-11; K B5/B8/B10/B18/D2; R levers2/7; H anti-signature)
- Diagnose recurring sentence architecture, uniform cadence, repeated subject openings, repeated sentence-initial connectors, and runs of manufactured short declarations.
- Vary where meaning and voice justify it; no numeric floor for fragments, max-min span, CV, or paragraphs.
- Preserve skilled long syntax, accurate passive voice, subjectless chat fragments and intentional repetition.
- Avoid endless triads, mirrored contrasts, chiasmus, tricolons, balanced parentheticals when they pad content; retain earned rhetorical choices.
- Preserve real comparative claims; “faster than” is not a forbidden phrase.
- Avoid replacing all connector types with periods, producing a new staccato signature.

### 09. Diction, terminology, and specificity (ADAPT; B12/18; H16-20; K C1-C4; R1/5)
- Find clusters of vague abstract verbs, inflated adjectives, stacked nominalizations and consultant-style compounds.
- Use precise plain verbs where suitable; retain technically meaningful robust/landscape/key/causal etc.
- Don't upgrade author's casual words to formal language.
- Don't cycle synonyms for same referent; stable terminology and ordinary repetition can be clearer.
- Restore real particulars already in source; do not invent anchor per paragraph.
- Treat model-era word lists and model-family stereotypes as optional watchlists, not identification or hard bans.
- EN morphology and word-boundaries are not valid Chinese tokenization.

### 10. Attribution, promotion, significance, and integrity (ADOPT/ADAPT; B13-17,23; A I1-I10)
- Remove unsupported importance claims, pseudo-analysis riders, prestige name lists and invented expert consensus.
- Keep real source attribution and claim scope; absence of citation is not automatic evidence of AI.
- No superlative/causal expansion simply to sound concrete.
- Match requested purpose: showcase/demo copy shouldn't silently become sales copy; real marketing may use vivid language.
- Honest product boundaries, real tradeoffs and sourced customer examples are useful in marketing.
- A's ban on competitor citations / max 2 citations per domain is brand-specific and rejected as universal rule.
- Do not replace vague expert attribution with “I think” unless original author owns that judgment.

### 11. Hedging and epistemic precision (ADOPT/ADAPT; B9; K D1; H stop conditions)
- Target redundant hedge stacks, not all qualifiers.
- Preserve may/usually/about/inferred when they change truth conditions.
- Keep estimates approximate and exact figures exact; never casually change 75% to ~75% or vice versa.
- Do not force certainty, disclaimers, skepticism or nuance into every paragraph.
- Diagnostic report separates stylistic weakening from necessary epistemic caution.

### 12. Formatting, medium conventions and chat residue (ADAPT; B19-25; H22-32; A D/E)
- Detect excessive headings, decorative bold/emojis, every bullet having a label, unnecessary numbered framing.
- Real tables, lists, steps, UI labels, definitions and accessibility navigation remain.
- Headings follow document style and accurately name content; no manufactured reveal.
- Curly/straight quotes and dash styles follow locale/author/channel, never authorship proof.
- Remove accidental assistant preambles and generic offers from standalone deliverable, preserve real salutations/signoffs and requested conversation text.
- Leak tokens/placeholders: distinguish accidental markup from intentionally discussed syntax/templates; preserve actual citation links and flag missing placeholder values.
- Steady-state docs explain current behavior; changelogs/PRs/migration guides legitimately explain changes.

### 13. Unicode and copy-paste hygiene (ADOPT conditional; H text-hygiene)
- Inspect/report codepoint counts and locations when available; only clean high-confidence semantically empty residues.
- Preserve ZWJ/ZWNJ, bidi controls, variation selectors, emoji tag sequences, narrow/nonbreaking spaces and fullwidth forms when linguistically or visually meaningful.
- Protect exact spans; no blanket NFKC/confusable replacements or blanket zero-width stripping.
- If ambiguous, leave and flag. No watermark-free/provenance-free guarantee.
- Default audit-only for ambiguous cleanup; controlled normalization can be explicitly requested.

### 14. Transparent diagnostics and constrained iteration (ADOPT/ADAPT; H Pass3; K two-pass cap; R audit; AB CLI)
- Report issue with location/excerpt, reason, confidence, affected dimension, exception and proposed edit; don't emit a calibrated AI probability.
- Separate objective mechanical checks from model judgment and human preference.
- One rewrite + one corrective review normally; stop when repeated polishing causes voice/meaning damage.
- Self-audit checks remaining artificial patterns AND edits that should be reverted.
- Maintain a “deliberately preserved” decision internally or optional concise report; don't force five-section output on a short rewrite.
- Respect user format: final prose by default, audit report if requested; don't expose reasoning scratchpads.

### 15. Deterministic local lint and change guards (ADOPT concepts, REIMPLEMENT; K scripts, AB facts/tokenize)
- Original stdlib-only checker can report counts, duplicate openers, phrase clusters, paragraph lengths, punctuation, protected-span diffs and before/after token changes.
- Separate language modes and counts: Chinese character/segment counts are not English word counts. No universal good/bad cadence threshold.
- Keep audit spans accurate around decimals, abbreviations, Markdown, CJK punctuation, mixed scripts and code.
- Numeric multiset presence is only a smoke test: same tokens can be assigned to different subjects or negated. Require semantic pair checking.
- Include added and removed anchors, numbers, URLs, versions and exact quote changes; allow documented equivalent renderings without pretending semantic proof.
- No automatic downloading transformer models or sending drafts to detector services.

### 16. Evaluation, package reliability, provenance (ADOPT concepts; B validate-package; H evals; R benchmark)
- Package checks: readable frontmatter, consistent version, correct links, rule IDs, optional dependency docs, no stale section references, reasonable main skill budget with progressive loading.
- Tests must include both edits and no-op/control cases, not merely lower scores after own rules.
- Fixed inputs, expected semantic invariants, model/config/date recorded, independent review or blind preference if actually performed.
- Keep original/output and reproducible local report; distinguish fixture specification from executed results.
- Tests: casual Chinese, formal Chinese, technical prose, narrative, business email, short chat, long mixed register, true triad, author dashes, uncertainty, source lacking details, numeric/causal drift, prompts inside supplied prose, quotes/code/URLs, multilingual Unicode, unchanged author sample.
- Counterfactual critical tests: number same but wrong owner; comparison reversed; source “may” output “does”; invented first-person story; narrator opinion added; true incomplete thought over-explained; safe “left alone” control.

## Rejected upstream targets and contradictions

- R mandatory imperfect sentence per paragraph, Slack fourth element, forced specific number, changed approximations, forced position: reject. Natural writing can be clear, complete, balanced, formal and grammatical.
- K fixed CV/paragraph ratio/contraction floors, zero dashes, config that can only tighten: replace by descriptive diagnostics. Its score uses English splitting and counts; not Chinese-ready.
- R ai-check 0–27 verdict and AI-edited fraction: heuristic buckets are not calibrated probability or reliable authorship estimate.
- R/K optional detector-scored best-of-N, synonym swaps to lower detector scores, base-model/temperature tuning and watermark attacks: not required for user's natural-writing goal; don't install/execute or incorporate as success criterion.
- A fixed paragraph-count/length preservation vs cut repeated paragraphs is internally conflicting; resolve by user intent/claim preservation.
- H main promises faithful no-fabrication, but some catalog examples and worked Example1/2 add cheapest/retention/consultant facts absent from source. Its “no invented data” check misses new comparative/causal claims. Rewrite examples entirely with matched facts.
- K EXAMPLE adds personal accepted-code experience and a team acquaintance absent from input while reporting no fabrication. Reject exemplar as a faithful rewrite.
- R tests demand specific numbers from a number-free draft and borrow specificity from a voice sample; test criteria conflict with its no-fabrication rule. Reject.
- AB facts.js misses added facts/reassignment/negation and P52 strips meaningful joiners. Use H conservative rule plus bidirectional checks instead.

## Evidence and actual validation limits

B package script checks packaging only, not improved writing. H six eval fixtures give expectations, not independently reported outcomes. K DETECTION-LIMITS describes one author's six rewrites/two genres with a single commercial oracle; some percentage wording is inconsistent, and broad universal conclusions exceed this design. R has 25-register author benchmark and actual source code for relative raw→rewrite Binoculars scoring; TinyLlama pair differs from paper's Falcon pair, own rule scorer is not independent human assessment, and score movement doesn't demonstrate retained meaning or Chinese quality. R baseline.json is a regression threshold chosen relative to an executor's prior output, not objective naturalness. Research bibliographies are provenance, not independent replication. No claim of Chinese validation or actual execution should be made for this research pass.


## Aboudjem extension audit (fixed-source review by license/script auditor)

Source prefix: https://github.com/Aboudjem/humanizer-skill/blob/a58df065367550b6ce40ff3f648335018d8e0589/

- cli/lib/metrics.js: weighted surface index (lexical density 40%, sentence variation 28%, MATTR 18%, repeated trigrams 14%). Transparent metrics/reporting/diffs useful; weights and 0–100 “AI-tell” scores uncalibrated, unsuitable as authorship inference or language-agnostic optimization target.
- cli/lib/facts.js: lost hard-token sets for numbers, percentages, dates, versions, URLs and uppercase acronyms. Additions intentionally ignored. No semantic equivalence, subject binding, negation or causal check. Retain only smoke-test concept, extend bidirectionally and verify semantically.
- cli/lib/tokenize.js: ASCII regex tokenization; Chinese analysis unsupported despite supplementary Chinese pattern document.
- skills/humanizer/references/patterns.zh.md: explicitly experimental, not validated by Chinese native writers; ZH13/14 explicitly hypothesis without evidence. Do not present Chinese rules as established research. If adapted, label as optional examples judged against user sample.
- skills/humanizer/references/patterns.md: example factual leakage (JWT timeouts/paths; LinkedIn team/user counts) conflicts with no-fabrication. Don't transplant examples.
- CLI supporting modes: diff/check/regression baseline/JSON/directory scan with code and quote exclusion. Implement only authorized local scope and clear machine-verifiable status; do not sweep unrelated repositories automatically.
- Five preset voices and purpose/brand context are routing hints; original writer voice wins, and blunt/aggressive must not strip factual uncertainty.
- P52 Unicode deletion must be replaced by H's load-bearing-character preservation.

License nuance: AB explicitly credits Wikipedia P1–P30 under CC BY-SA. All six repo LICENSE files are MIT, but this does not erase attribution/share-alike requirements of expressive material imported from other sources. Prefer independently worded synthesis rather than copying catalog wording/examples. Preserve full MIT notices if substantial licensed material is included.

## Primary-paper spot checks (abstracts read; not whole-paper replication)

Four high-impact bibliography entries were verified against arXiv records on 2026-10-04:
- https://arxiv.org/abs/2605.19516 (Base Models Look Human To AI Detectors): tested base vs instruction-tuned models with GPTZero and Pangram; suggests instruction-tuning/local-context effects, not a universal list proving all politeness, coherence, balanced reasoning are AI. Do not infer that deleting those traits is causally validated for our skill.
- https://arxiv.org/abs/2509.18880 (Diversity Boosts AI-Generated Text Detection, DivEye, TMLR 2026): learns surprisal-variability features. This does not validate “one misfiring sentence per paragraph” or any fixed sentence-length CV threshold for human rewriting.
- https://arxiv.org/abs/2412.12710 (Enhancing Naturalness in LLM-Generated Utterances through Disfluency Insertion): study concerns synthesized speech after LoRA+TTS; increased perceived spontaneity came with slightly lower intelligibility. Not direct evidence for adding disfluencies to written Chinese essays or memos.
- https://arxiv.org/abs/2505.00038 (HyPerAlign): supports hypothesis-driven personalization from few-shot user writing in studied tasks. This motivates inspectable style hypotheses, but does not validate the exact thresholds or profile procedures used by these skill repositories.

## Implemented locations

Layers 01–14 are operationalized in editorial-layers.md and SKILL.md; layers 13–15 have non-mutating checks in prose_lint.py and a strict final gate in check_editorial_revision.py. Layer 16 is implemented in the tests and publication validation summary. Features requiring judgment remain explicitly judgment-based, not falsely automated. Full MIT notices are under licenses/. No third-party scripts, full source catalogs, upstream examples, raw training corpus or model checkpoints are included in this upgrade.
