# Exact96 calibration duplicate / lineage gate v0.1

## Current state

Source implementation and synthetic tests only. This directory does not authorize a natural execution. No natural exact96 cache/body has been read by its implementation author; no gate matching manifest, execution approval, root GO, marker or natural result was created during implementation. The frozen source-v01/public tree is unchanged.

The proposed gate consumes precisely the 96 private gzip records emitted by the separately authorized source-calibration runner. It never reads compressed source corpora, downloads, owner text, NLP/POS, sensors/features, targets, predictions or fits. It does not create candidate frames. There are no replacements, implicit retries or automatic batch resizing.

## Frozen dependencies and authority

- Source freeze SHA256: 5eb673703d71a6f26d8f2828c99e3e4d857355714b541d38ba15fdc424a142cf
- Source execution contract v02 SHA256: ea88b0398cf3d60178056b4f5ab44b7da9ec8196c7a87a2fa2c07ba20d29d1c2
- Bounded old-projection certificate SHA256: bcd447e5bdcefa3db6d980d100ddc44ce1c49c8a560fd8d84870ddb379685768
- Eight source implementation modules are hard-pinned; seven used modules are executed directly from their hash-checked source bytes with no bytecode-cache loader. The reviewed manifest additionally freezes every source-v01/public Python file, every new gate public Python file, the interpreter, imported runtime/shared-library bindings, source registry/metadata, complete source receipt, marker, exposure/read/progress ledgers, all 96 compressed cache hashes, certificate and all nine certificate artifacts
- Exact96 files are determined solely by the frozen metadata record keys; any extra/missing cache file, differing metadata/raw SHA/length, invalid map, altered risk sidecar or different frozen-projector replay stops the stage
- Original metadata is compared exactly; replay first computes source_risk_gate.gated_metadata(raw, original_metadata), then calls the frozen projector on its gated copy
- SOURCE_IMPLEMENTATION_GO and CALIBRATION_GO do not authorize this matching stage

After source execution completes, preparation hashes only compressed cache bytes and records metadata. It does not decompress any cache:

    PYTHONDONTWRITEBYTECODE=1 python public/calibration_gate.py prepare-manifest

This writes a private proposal. An independent reviewer must bind its externally supplied SHA256 in a review object containing:

    decision = APPROVE_CALIBRATION_COPY_GATE_EXECUTION
    manifest_sha256 = externally verified proposal SHA256
    reviewer = independent reviewer identity
    independent_review = true
    synthetic_tests_passed = true

Root must separately issue a GO object containing:

    actor = root
    action = CALIBRATION_COPY_GATE_GO
    manifest_sha256 = same externally verified SHA256
    review_sha256 = externally verified independent review SHA256
    no_other_stages = true

Then, and only then:

    PYTHONDONTWRITEBYTECODE=1 python public/calibration_gate.py execute --manifest private/calibration-gate.manifest.proposal.private.json --manifest-sha256 EXTERNAL_SHA256 --review REVIEW_PATH --review-sha256 EXTERNAL_REVIEW_SHA256 --go ROOT_GO_PATH

All CLI production roots are fixed; synthetic tests exercise kernels using disposable files beneath this gate's private root. A consumed one-time marker remains after failure or stop; no deletion, second execute, resume, larger cap, split-retry or alternate directory is authorized.

## Resource sharing

The existing shared 90-minute accounting includes metadata, blog increment, old projection exclusion and source-calibration receipts. The gate's elapsed time includes authority verification, cache processing, signatures, matching and graph closure. Signature readback adds the gate receipt's elapsed time to the same shared clock. Kernel seccomp prevents network and child execution; GPU is disabled, numerical threads limited to two, RSS and address space capped at 3 GiB.

All files in the old fingerprint root (at least 566,539,146 bytes), source-v01/private, and this gate/private are charged. This includes SQLite rollback journals, partial outputs, temporary synthetic artifacts while present, manifests, approvals stored within these roots, and terminal receipts. SQLite signatures use the frozen writer, in-place transactions and pre-add conservative reservation; no uncharged plaintext file or alternate temporary directory is created.

The combined total must stay below 1 GiB. There is no new allocation: combined bytes minus the root-provided 843,782,930-byte baseline must remain below the same 80 MiB exact96 reservation. This gate reserves 64 KiB for emergency accounting *inside* that existing 80 MiB; this strengthens the source runner's 4 KiB minimum without adding budget. The control file remains source-v01/private/control.json with exactly {state: run|pause|stop}. Pause consumes wall time and all resource checks continue. Every matcher callback enforces controls and aggregate limits.

Matching has a cumulative 300,000,000 comparison-increment cap, 12 predetermined batches of eight records, and frozen per-batch signature/hit/binding caps. Exceeding any cap stops without retry or adapting the batch. Failure artifacts remain private and quarantined.

## Signatures, aliases and graph closure

1. Each record's exact raw source, every emitted projected segment and every mapped contiguous raw span receives the frozen normalized/full/block/5-gram signature. SQLite deduplicates text and gram dictionaries while preserving all record/view/member/locator bindings
2. The three certificate-pinned old packages and the full exact96 signature package are compared in every batch. Package-local integer IDs are translated by complete SHA256 digests; near-copy denominators retain every distinct gram, including unmapped grams
3. Every matching direct old member and every coverage-ledger alias of projected or reused old-normalized signatures becomes a private edge. Matching exact96 against its entire package covers all calibration-to-calibration pairs, including cross-source pairs. Same-member self edges are omitted; no aliases are dropped
4. The DSU begins with every metadata member and complete old ancestor components, verifies canonical namespace/member/component identities, validates all stored lineage rows, and preserves every old exclusion flag. It never compares stale old component names against new names to decide contamination
5. Before adding calibration exclusion, calculate final component counts per source and any old-exclusion collision. Any old hit, fewer than32 final components for a source, or cross-source shared component emits exactly calibration_underfilled. No replacement is sampled
6. All calibration members are then permanently exposed in the exported final graph even when underfilled. This contamination step must not change component membership/IDs. Nothing invokes candidate freezing

Zero-segment / role-quarantined records still contribute raw signatures and collisions; no role failure suppresses exposure matching. These records remain quarantined and cannot be admitted. The bounded certificate validates comparisons of declared retained views; it does not certify omitted regions as prose, universal clean-prose coverage, semantic-copy absence, unknown external lineage absence, human authorship, rights or G2 admission.

## Private evidence and independent reconstruction

- calibration.signatures.private.sqlite: deduplicated raw/projected/span signatures, full gram sets, long blocks, every identity/locator/view binding
- record-identities.private.json: frozen record/member/source/projection/cache identities and bounded-view/role support status
- comparison-batch-00..11.private.json.gz: all hits, full denominators, exact reasons, complete referenced bindings and every expanded alias edge
- final-components.private.json.gz: full namespaced member-to-canonical-component map, old contamination before calibration exclusion, final contamination and evidence/package hashes
- calibration-gate.receipt.private.json: terminal status, counts/resources, every output hash and private failure identity
- public/execution.aggregate.json: aggregate status/counts/resources and hashes only; no record or member identifiers, per-record hashes, titles, locators or text

The gzip graph can be privately decompressed by an authorized reviewer to satisfy the existing registry's JSON import interface; this gate does not itself invoke that downstream API or create its candidate frame. Decompression storage must remain charged to the same reservation.

The signature-only readback uses separate varint decoding, full package scans and full-denominator matching, direct/coverage alias reconstruction, and a separate DSU implementation. It reads no raw objects or calibration body caches. It verifies every positive edge *and* absence of omitted declared-signature matches. It does not prove the underlying source's projection correctness; that remains anchored to the reviewed execution plus independent per-record source reviews.

After execution, an authorized reviewer can run:

    PYTHONDONTWRITEBYTECODE=1 python public/verify_gate.py --manifest-sha256 EXTERNAL_MANIFEST_SHA256 --receipt-sha256 EXTERNAL_TERMINAL_RECEIPT_SHA256

Readback has its own one-time marker and private terminal receipt. Running an author's checker is not itself an independent review or G2 admission. Its runtime and artifacts remain part of the shared limits; insufficient remaining resources stop without implicit retries.

## Synthetic validation

    cd public
    PYTHONDONTWRITEBYTECODE=1 python -m unittest test_calibration_gate -v

Synthetic cases include complete96 clean and underfilled flows across all12 batches; frozen raw/map/metadata/projection mismatches; zero-segment raw-only retention; deduplicated text with all aliases; package-local gram-ID differences and unseen-gram denominators; old-to-new canonical-component changes; calibration-calibration and calibration-old collisions; projected-to-all-raw-member alias expansion; missing/incomplete packages; comparison/disk/wall caps; run/pause/stop; one-time markers; and no candidate-frame API.
