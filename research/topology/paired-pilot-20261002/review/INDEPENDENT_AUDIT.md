# Independent audit: paired PHD pilot

Audit date: 2026-10-02. Scope: 32 frozen prompt-pairs, 16 Wikipedia and 16 Reddit QA, from the released historical text-davinci-003 benchmark.

## Verdict

The saved numerical results are internally reproducible. Selection, pairing, tokenizer inputs, and the practical notebook estimator conventions were checked. The headline must distinguish the safeguarded 29-pair variant from the original estimator's mean-slope algebra on all 32 pairs.

The all-pair, length-matched mean-gap interval crosses zero. This is an inconclusive small pilot for a robust length-controlled marginal mean difference, not evidence that topology is useless. Measurement instability, nuisance confounding, and conditional incremental value in a future joint model are separate questions. This experiment measures the first two incompletely and does not test the third. It does not validate a universal human/style axis, a writing-quality objective, a deployable detector, or integration into a learned style model.

## 1. Reproduced results and denominators

All differences below are human minus AI. All intervals are the originally specified 10,000-replicate, domain-stratified prompt-pair percentile bootstrap, replayed without a new seed.

| Original estimator seed | Complete pairs / selected | Human mean | AI mean | Mean gap | Gap 95% interval | Human-positive AUROC |
|---|---:|---:|---:|---:|---|---:|
| Original window, safeguarded | 29/32 | 9.498 | 7.412 | 2.087 | [1.269, 2.988] | .822 |
| Original window, upstream algebra | 32/32 | 10.360 | 8.119 | 2.242 | [.400, 4.392] | .776 |
| Matched length, safeguarded | 29/32 | 9.367 | 7.665 | 1.702 | [.551, 2.893] | .717 |
| Matched length, upstream algebra | 32/32 | 10.235 | 8.302 | 1.934 | [-.113, 4.340] | .687 |

The safeguard excludes three pairs: two because the generated text fails and one because the human text fails. Coverage is 29/32 pairs (90.625%): 14/16 Wikipedia and 15/16 Reddit. At the individual-text level it retains 61/64 estimates (95.313%), with human availability 31/32 and AI availability 30/32. The paired complete-case statistics correctly discard both members of an affected pair. Reporting simply “three failed estimates” without the pair denominator would hide that the three usable partner scores also leave the paired comparison.

Those same three texts occur in both window conditions, so the saved file has six unavailable estimator reports, not six distinct failed texts. All 320 saved estimator reports were replayed from their numerical energies. The other seed and original-window paper-prose sensitivity retain all 32 pairs.

The unguarded matched-length AUROC interval is [.550, .812], although the mean-gap interval crosses zero. These are different estimands with different sensitivity to extreme values; their intervals are not contradictory. Neither is classification accuracy. No threshold, probability, or classifier was fitted.

## 2. Safeguard policy materially changes the estimand

The recovered estimator rejects a text when any individual rerun slope falls outside [0, .999), even when the mean slope is valid. The released implementation transforms the mean of three slopes without that per-rerun rule. The three rejected texts have finite mean-slope dimensions 15.917, 20.264, and 37.655. Treating these as unavailable is an explicit engineering variant, not an exact implementation of the source's output rule.

Diagnostic arithmetic on the already saved slopes shows:

- Any-rerun margins from 0 through .02 all retain the same 29 pairs
- A mean-only guard retains all 32 pairs throughout that same margin range
- A stricter .05 margin retains 28 pairs with an any-rerun guard and 30 with a mean-only guard

Thus the exact .001 epsilon is not a knife-edge in this sample. The consequential arbitrary choice is checking each rerun versus transforming the average. These diagnostics are post hoc transparency checks, not a basis for choosing a favorable guard. The predeclared guard reduces the matched-length interval's width from 4.453 to 2.342 while changing both membership and the target population. It does not uniformly increase the estimated mean gap: the all-pair mean gap is actually larger. Presenting both prevents a misleading “successful replication” based only on the cleaner conditional sample.

## 3. Seed instability is larger than the initial maximum implied

The reported 9.298-point maximum only includes estimates passing the safeguard under both seeds. It is correct for that conditional subset but is not the full-cohort maximum.

- Across every text's finite mean-slope algebra, the largest change is **24.595**: a 63-token human cloud moves from **37.655 to 13.060**
- A 55-token generated cloud moves from 20.264 to 9.770, a 10.495-point change
- Among texts passing both seeds, a 66-token human cloud moves from 17.561 to 8.263, a 9.298-point change
- All three primary abstentions are short clouds: 55, 56, and 63 content tokens
- Restricting both seeds to the same 29 passing pairs gives original-window gaps 2.087 versus 1.865, and matched-length gaps 1.702 versus 1.683. Four of these 29 within-pair gap signs change in each condition

The smallest failed clouds fit over subset sizes 40, 42, 44, 46, 48, 50, 52. This narrow size range helps explain why an apparently good log-linear fit need not produce a stable dimension. The transformation 1/(1 − slope) sharply magnifies slope error near one.

The two seed labels do not imply independent Monte Carlo noise across documents. The runner resets the estimator seed per text: same-length clouds receive identical subset-index schedules, including each matched-length pair. This is a common-random-number design that differs from the upstream global threaded RNG. Its error covariance has not been measured. Two seeds and three reruns per estimate cannot establish calibrated Monte Carlo uncertainty.

## 4. Bootstrap unit is correct; interval scope is limited

The replay confirms that each resampled unit is a complete human/AI prompt-pair and pooled draws preserve available domain counts. Tokens, MST subsamples, and reruns are not incorrectly treated as independent documents. AUROC is recomputed from each resampled set of pairs.

The intervals nevertheless condition on observed numerical scores, model/runtime, sampling profile, fixed domain composition, and the availability policy. They do not rerun the stochastic estimator, account for uncertainty about excluded values, or incorporate checkpoint, language, generator, or domain shift. The 29-pair pooled mixture is 14:15 rather than the selected 16:16 mixture. Cross-domain comparisons also contribute to pooled AUROC; domain-stratified sampling does not make it a within-domain-only statistic.

With only 16 selected pairs per domain and heavy-tailed transformed scores, nominal percentile-bootstrap coverage is not established. Unique prompts do not demonstrate independent authors, articles, or topics; those higher-level clusters were not audited. Small-sample sampling uncertainty and estimator Monte Carlo instability should therefore be reported separately. The intervals alone are not an adequate account of total uncertainty, and the two seed results should not be averaged opportunistically.

## 5. Length control is useful but incomplete

The equal-length condition correctly builds each text's first L = min(256, human tokens, AI tokens) and independently re-encodes it. It does not slice a full-context embedding cloud. L ranges from 55 to 256, so this is not a fixed-256-token experiment.

Original Wikipedia mean token counts are 475.4 human versus 130.1 AI; Reddit counts are 220.1 versus 284.1. Two human texts are truncated at 510 content tokens; no generated texts are. Length matching weakens rank separation but also changes contextual content and the estimator's available scales. It does not control semantic equivalence, lexical composition, repetition, author effects, or topic drift. It cannot by itself isolate a causal “human style” property.

## 6. Provenance, extraction, and source alignment

Independent checks established:

- Both local archives match their Git blob identities at the pinned [GPTID release](https://github.com/ArGintum/GPTID/tree/8c8759ef94c8769e2f40f3e507f270e4c948a562/data)
- The frozen hash-order selection reproduces all 32 train prompt-pairs, with distinct prompt, human-text, and generated-text hashes
- Result pair identities, source/cleaned hashes, token counts, matched lengths, and truncation metadata match the selected source records
- All 64 encoded input-ID sequences match the [released notebook's](https://github.com/ArGintum/GPTID/blob/8c8759ef94c8769e2f40f3e507f270e4c948a562/example.ipynb) tokenizer, cleaning, and truncation convention; no internal special tokens are present
- All seven pinned model assets match the local manifest, including weights and tokenizer files
- All 320 energy-to-median-to-slope calculations, availability decisions, finite dimensions, and every published mean-gap/AUROC interval replay correctly

The [source estimator](https://github.com/ArGintum/GPTID/blob/8c8759ef94c8769e2f40f3e507f270e4c948a562/IntrinsicDim.py) and notebook confirm the 9/3 draws, notebook grid, three reruns, mean-slope transformation, and absence of the added per-rerun guard. The [paper](https://proceedings.neurips.cc/paper_files/paper/2023/file/7baa48bc166aa2013d78cbdc15010530-Paper-Conference.pdf), Appendix B, describes seven draws and inconsistent endpoint notation. The endpoint-inclusive paper-prose profile is an explicit interpretation, not a claim about the exact historical implementation. The paper also acknowledges stochastic/short-text limitations and mentions extra outlier-correction restarts without a reproducible rule. This pilot appropriately invents no correction rule.

Exact historical checkpoint bytes, RNG schedules, runtime, and the full paper's detector evaluation are not reproduced. Local input equivalence is not historical hidden-state equality. The auditor did not rerun model inference or recompute MSTs from embedding arrays; the numerical replay starts at saved MST energies. Current hashes match the stated frozen commitments, but this audit cannot independently retroactively timestamp preregistration. The old controlled TEST was not consulted.

## 7. Public-release and reproducibility boundary

This audit report, the aggregate JSON, and the numeric replay script contain no corpus text, token IDs, embeddings, weights, archive payloads, source-row indices, or per-text hashes. The script takes explicit file arguments and never overwrites its supplied inputs. It needs NumPy only; the checked run used NumPy 1.26.4.

The original selection/results manifest does contain source indices and unsalted text/prompt hashes. Those are provenance links, not anonymization: a reader with the public archive can recover the associated records, and a fully published deterministic selection recipe also permits linkage. This is not evidence of a newly discovered private-data leak, and no unnecessary content inspection was undertaken. For publication, prefer the aggregate artifacts unless row-level provenance has been separately reviewed. Keep the original frozen evidence unchanged; generate a distinct public derivative rather than editing history. Do not redistribute corpus archives merely because the code is MIT licensed.

Example numerical replay:

    python replay_paired_numeric_audit.py paired-pilot-results.json \
      --summary paired-pilot-summary.json \
      --unguarded unguarded-method-audit.json \
      --output aggregate_numeric_audit.json

The aggregate JSON preserves full-precision comparisons, all existing bootstrap intervals, and clearly labeled post-hoc guard diagnostics. No new inference, estimator sampling, replacement pair, fitted model, or remote write was performed during this audit.
