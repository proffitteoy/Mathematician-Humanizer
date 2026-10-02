# Natural text learning pilot design

This package specifies the next bounded natural-text learning experiment for style-compiler. It contains a research note, prospective protocol, exact71-channel/model contract, and independent design review. It contains no extracted corpus features, model weights, source texts, private identifiers, or empirical results.

Read:

1. `RESEARCH_NOTE_ZH.md` — scientific question, available evidence, identifiability limits, and decision
2. `PROTOCOL.md` — exact objectives, inputs, information-parity baselines, masks, weights, estimands, split firewall, ablations, metrics, falsifiers, budgets, and minimum implementation contract
3. `training_contract.json` — machine-readable catalog and fixed settings
4. `REVIEW.md` — independent design critique and resolution
5. `DESIGN_CHECKS.json` — static consistency checks only

The principal experiment predicts natural next-unit measurements from supplied annotation prefixes. Version1.1 compares matched first moments, explicit observed-pair covariance, learned set information beyond those moments, last-unit effects and ordered state, using production labels only for sampling/evaluation. It is not a human/AI classifier or an online-causal text predictor.

A separate retrospective likelihood experiment conditions every model on the identical entire local sentence multiset, uses common full-packet target classes, and evaluates proper order probabilities. No original indices, frozen history features or unequal future access are allowed.

Actual M4 discourse/argument graphs, stable author identity and a complete global/sequence/discourse style model remain unavailable. Original blank-line block analyses are limited to supported Baike observations. Unknown Web writer layout is not repaired or interpreted as zero.

Execution requires coordinator approval. Any separately approved measurement work has its own execution receipt; this design package itself performed none. Public release, if separately authorized, may include this package but must exclude all raw/private corpus records and per-sample outputs.

Prospective amendment1 adds explicit covariance attribution before empirical fitting/test access. It replaces the optional fitted block-order extension, retains all order/mask controls, and stays within100 fits: core72, core+permutation96, or core+sparse81. Three primary contrasts use98.333333% intervals. See `AMENDMENT_1_COVARIANCE.md`.
