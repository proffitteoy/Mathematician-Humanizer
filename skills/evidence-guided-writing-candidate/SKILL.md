---
name: evidence-guided-writing-candidate
description: Produce and evaluate source-faithful Chinese rewrite candidates using TRAIN-fitted observational human/AI contrast cards. Use for this project's generic de-AI writing experiments; reader benefit is unvalidated and personal-voice imitation is not enabled.
---

# Evidence-guided writing candidate v0.1

This candidate connects measured corpus differences to explicit inspection and actual rewrites. It extends the preserved host-LLM workflow in ../style-writing-prototype. The learned object is a paired observational contrast and reference summary, not a generator, causal editing policy, human-quality score, or accepted final skill. Read references/evidence-contract.md before interpreting cards. The repository's docs/ACCEPTANCE.zh.md remains the owner-judged acceptance contract.

## Use it

From this skill directory, with a supplied local evidence bundle. The included fitted artifact uses Python 3.12 / Unicode 15.0.0; a different Unicode measurement profile is rejected rather than silently treated as equivalent:

    python scripts/bridge.py prepare input.txt --evidence references/paired-surface-evidence.json --domain web --genre general --output work/job.json

Use the actual corpus domain only when it fits. An unsupported domain, instrument mismatch, missing measurement, or unreplicated contrast yields no usable card. Do not relabel the input to force support. Commands use local files and standard Python; no model download, API call, corpus scan or background fit occurs.

Here web/baike name source collections. A new user's article or a synthetic example is not automatically in-domain because it is an essay or explanation. The candidate records this application as an unvalidated transport hypothesis and makes no in-domain quality claim. Unknown domain and mismatched profiles stop the grounded path; missing or unreplicated coordinates cannot justify an edit.

Read the input and the emitted diagnosis. Before changing prose, fill the existing job contract in ../style-writing-prototype/references/job-contract.md:

- Record each factual/logical commitment with exact source evidence, including hypotheses, quantifier dependencies, uncertainty, temporal order, attribution, causal strength, obligations and exceptions. Protect exact formulas, names, quotations and critical technical relations
- Inspect only available evidence cards. For each proposed evidence-guided edit, cite its feature_id in evidence_card_ids and an exact source_problem_evidence span. Describe the actual reading problem and why this particular change addresses it. A corpus mean difference by itself is no defect and no reason to edit
- Generate a minimal candidate and retain the original. A structural alternative is useful only when it tests a different supported hypothesis. State which decisions came from a card and which are ordinary editorial judgment. Preserve failed versions. Never inject errors, anecdotes, details, random sentence variation or a copied author's voice to look human
- Give the original, ledger and candidate to a separate reviewer without the corpus direction or feature results. Obtain an actual per-claim judgment, added-claim review and completeness check. Add ledger_completeness: checked_no_omissions and relations_and_scope: checked_preserved only if that reviewer explicitly found them. Record honest fail/uncertain judgments instead when appropriate. The runner verifies declarations and excerpts, not semantic truth or reviewer independence
- After that review, bind its exact texts with workflow.binding(job,candidate). Select only among faithful candidates using concrete reading/task reasons, never the contrast score. A changed distance to a training median is descriptive and cannot repair a semantic failure. When none improves the input, keep the original

Run:

    python scripts/bridge.py evaluate work/job.json --evidence references/paired-surface-evidence.json --domain web --output work/result.json

The .txt output is the selected candidate or the unchanged original on abstention. Exit 2 means abstention. The JSON separates fidelity gates, observed style deltas, reference-distance changes, evidence provenance and editorial selection. It retains rollback text. A real rewrite depends on the invoking host language model; Python does not generate new paragraphs.

## Deliver and learn

Lead with the complete rewrite, then state any meaningful limitation. A normal user need not see the entire metric record. For this research project retain complete before/after examples, rejected candidates, reviewer evidence, exact instrument/model bindings, and user judgments.

On synthetic or development examples, report the observed changed coordinates and review result, not a success rate for human writing. The first real validation target is blinded reader comparison against the existing baseline and unchanged input with separate semantic review. Until that exists, say “evidence-guided research candidate,” not “validated de-AI model.” A source-label contrast is observational, not proof that human readers prefer an edit. No detector evasion or origin probability is promised.

The original 13+ numeric sequence checkpoints may be useful research instruments but are not imported here and do not generate this prose. Do not imply otherwise. Personal writings remain excluded: this candidate does not meet the acceptance condition for personal-stage work.
