# Chinese train/dev extraction: interrupted run and public-source recovery

## Current state

The extraction did not finish. An executor replacement interrupted the active run on2026-10-02 around03:39UTC. The tool reported an executor-key change during session recovery. Fresh checks found no extraction directory, frozen M4 cohort, restored runtime/models or parser process. Searches of the expected workspace paths and shallow /workspace and /tmp locations found no surviving copy.

The last observed progress was4,338 committed arm caches:3,632 TRAIN and706 DEV, approximately115.0MiB. These are historical checkpoint counts from the replaced executor. The recoverable private-cache count is0. All-TRAIN processing had been observed, but there is no presently available TRAIN dataset from this interrupted run. Neither a full completion receipt nor the full hash/coverage verification receipt was reached. Downstream natural-data fitting and throughput gates remain closed.

No test bodies or davinci answer bodies were read by this extraction. No private sample was uploaded. No source text, identity list, cache body or token data appears in this recovery package. No download, dependency installation or extraction restart occurred after replacement.

## What has been recovered

- extract.py is reconstructed byte-for-byte from the exact previously emitted source. Its SHA256 is617c3b1ebc88f623e7de9930aad873d00a48a06ee41e4e7c5e9eabd6ffd4aec1, exactly matching the original pilot receipt
- extraction_protocol.json has the original canonical-JSON digest6e2c5562dfd51b3735486475376662acf09d1fe218a95e5005fb4eeb6ac719a9. The deterministic20-family selection, original71-channel order, split/arm restrictions, byte-offset reader, null/denominator handling and cost rule are unchanged
- bounded.py and run_tests.py were reconstructed from their emitted source. Their prior file hashes were not captured, so byte identity is not independently certified
- cache_schema_reconstructed.json recovers the exact ordered71 IDs, family mapping and cache/ledger field contract. It is explicitly not presented as a byte-exact copy of the lost complete channel_schema.json. The authoritative measurement definitions remain the pinned original instrument source
- Files ending.reconstructed.json contain prior emitted aggregate facts only. They are not fresh test or execution receipts. Their names intentionally do not satisfy the wrapper's normal current-run receipt gates
- input_pins.json preserves frozen corpus, code, model and compatibility-runtime identities. It does not contain raw data or private record locators

The wrapper's private caches, execution ledger, private pilot identity plan, full parser-profile object, complete original channel schema export and final full-corpus aggregates were not recovered. The hash of the prior private pilot plan survives in the public predeclaration receipt; its identities must be rederived deterministically from the verified original cohort.

## Evidence observed before interruption

Model-free checks ran before any corpus bodies were opened:164 tests ran,163 passed, one pre-existing optional Unicode-table check skipped, zero failures/errors. This comprised156 restored-instrument tests and8 wrapper tests. Those tests have not been rerun in the replacement executor because the dependencies are absent.

The deterministic40-arm TRAIN pilot took20.70s wall, peaked at991,932,416bytes sampled process-tree RSS, and wrote973,802bytes of compressed private caches. It produced320 instrument operational units.39/40 arms had no parse failure; one alignment-failed unit was retained. The conservative cost projection was2,839.64s (47.3min) and190,468,123bytes (181.6MiB) derived disk, within the approved limits. The original40 caches were reused during the interrupted full pass; none now survive locally.

The latest emitted source/arm reliability snapshot covered2,025 arms and20,127 operational units. It was a partial progress snapshot, not the final cohort:

- Web HUMAN:498 arms, no parse failures;35/2,575 local units had a defined100-token-window value
- Web CHATGPT:498 arms, no parse failures;0/5,264 local units had a defined100-token-window value
- Baike HUMAN:515 arms;8 arms contained37 alignment-failed units and1 resource-limited unit;46/7,530 local units had a defined100-token-window value
- Baike CHATGPT:514 arms, no parse failures;0/4,758 local units had a defined100-token-window value

There were no whole-source failures at that snapshot. Most local100-token-window values were unavailable because their unchanged operational sentences were shorter than100 lexical tokens. Those zero-denominator cases were retained as typed missing values, not zeros. These are implementation-availability observations, not a linguistic-validity or human-style result.

## Exact rerun conditions

The intended population remains4,814 arm measurements from1,816 TRAIN and591 DEV paired answer records, HUMAN+CHATGPT only. The wrapper verifies the frozen cohort digest, uses only the exact approved CHATGPT JSONL byte offsets, checks source/question/answer hashes, and never decodes the whole raw corpus file or opens davinci. Family weights, failures and original unit denominators are retained. No8-unit whole-corpus gate, truncation, sentence substitution or result-driven record replacement is introduced.

The original instrument remains candidate_unvalidated. The3 history-dependent channels are audit-only for the core model. Whole-source and cumulative guards require separate resource-failure/mask controls. These are supplied complete-unit annotation sequences, not a certified live-prefix producer. UD remains syntax; discourse graph is null. Original-writer Web paragraphs remain unknown while lexical/sentence observations are retained.

A rerun needs a supported persistent execution/storage plan and the verified original input, runtime and model bytes. This package does not authorize new downloads or another expensive run. Once those prerequisites are separately resolved, recreate a private/cache directory, rerun model-free checks, reproduce the frozen pilot selection and retain fresh per-record hash/commit evidence. A local per-record cache supports process recovery only while its filesystem survives; it did not protect this run against executor replacement.

Do not reopen downstream cache gates until a complete new full receipt and a complete independent cache/hash/coverage verification both exist. The historical aggregate receipts here cannot substitute for available per-record data.
