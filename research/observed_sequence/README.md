# Observed linguistic sequence pilot

This separate research module predicts **instrument-observed next-unit POS composition**. It does not modify `research/learned` synthetic admission gates, certify syntax, identify authors, classify human/AI origin, or complete the full multi-view style architecture.

The fixed sample/protocol is maintained outside this repository in the reviewed `style-learning-pilot` bundle. Raw sources, identities, model outputs, token parses and trained weights belong outside the repository. A source record is not an independently verified author work.

## Implemented interfaces

- `contracts.py`: immutable source/projection-independent record provenance, 68 real `zh:` channel identities, sensor opportunities/missingness, unit statuses and known-component split checks
- `prepare.py`: exact source-unit alignment, whitespace-closed prefix opportunities, a coverage-preserving pair ledger, 14-bin primitive POS composition, and stable train-only record-equal normalization
- `producer.py`: explicit sentence-local production through an existing hash-verified backend, with an exact-input cache and uncached strict-prefix readback. Importing never initializes Stanza or downloads data
- `extract.py`: explicit manifest-only **gate** and **train-dev** stages. The gate checks the fixed hash-ranked first eight training records. Every eligible strict prefix is freshly parsed and compared to cached token forms/spans, POS, heads, relations, primitive target counts and local features. No test extraction or fitting API is provided
- `models.py`: positive smoothed prior/latest-state baselines, mask/length and pooled-raw MLPs, nonlinear DeepSets, GRU and explicit-seed shuffled GRU; conditional record-equal soft-target cross entropy

## Information and target contract

Inputs are actual visible prefixes, supplied as `[T,272]`: 68 channels × (value, presence, log-opportunity, opportunity-known). Three history-derived channels are excluded from both ordered and unordered arms. Two additional values describe only the observed contiguous prefix unit/codepoint length. IDs, speaker/page keys, individual offsets, future length/availability and next-unit opportunities are not model features.

The target is the next genuine source unit's 13 existing lexical UPOS categories plus OTHER, including INTJ/SYM/X where applicable. Normalized composition CE is averaged first within each eligible record and then over records with at least one scoreable target. Zero-eligible records remain in coverage; they do not receive zero loss. Parse failures/excluded spans are barriers. An unconfirmed boundary cancels that prediction opportunity but does not delete a text unit from a later confirmed prefix.

A terminal at prefix EOF alone is insufficient: later punctuation/closers can extend it. The current source opportunity requires observed whitespace after the prior unit and exact source-prefix segmentation agreement. This conditional subset is not an arbitrary-character online generator.

Training-only moments are record-equal and computed with stable centered within/between-record variance. Exactly constant and unsupported channels retain scale zero and encode zero in all partitions, with support counts and presence/known flags retained. No epsilon erases genuine small variance.

## Tests

From the repository root, with the already installed CPU environment:

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONPATH=src:. \
  /path/to/existing/python -m unittest discover -s research/observed_sequence -p 'test_*.py' -v
```

The original synthetic fixtures test deterministic maps, losses, known-group rejection, cache identity, gaps, denominator handling, stable constants/near-constants, prefix isolation, exact parameter counts, order sensitivity and one optimizer mechanics step. These tests are not new natural observations or parser-accuracy evidence.

## Execution gates

The user-approved research purpose and a root-reviewed protocol are prerequisites; hashes validate bytes, not authorization. Natural extraction is a separate opt-in action with no network, two CPU threads, a 90-minute wall budget, 3 GiB observed RSS ceiling and 250 MB private-output budget. Runtime checks are not a claim of kernel-enforced instantaneous memory isolation. The gate receipt must pass before train/development expansion. Its raw cache and fresh-prefix evidence remain private for independent readback.

The test partition stays sealed until source/implementation review, train-only transforms and final model/checkpoint selection are frozen. Actual model fitting needs its separate review/approval. No fitting occurs at import or during extraction. All `comparison_eligible`, human-origin and author-ground-truth promotions remain false.
