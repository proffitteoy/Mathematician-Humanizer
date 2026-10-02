# Secondary tool-session cache backup

This is a secondary recovery copy with no durability guarantee. The ordinary per-record disk cache and append-only ledger remain authoritative during normal execution. The tool-session store is local to the extraction worker; the root agent cannot read its keys directly and may make its separately verified mirror from the on-disk archive. Neither copy is a GitHub or Library upload.

## Payload and size

The archive includes exact decompressed JSON bytes for every committed private arm cache in the snapshot, a complete committed execution-ledger prefix, and per-record original gzip SHA256, exact JSON SHA256, byte lengths and compression metadata. It contains all original fields, including parser annotations, typed71-channel values, denominators, opportunities, flags and source-structure audit data. It contains no raw corpus file. No measurement is transformed, rounded, omitted or re-fit.

The archive is TAR compressed with XZ/LZMA2, preset6 and16MiB dictionary. Its cap is32MiB for a complete secondary archive. Crossing the cap records a failure; the original caches and previous verified secondary generation are unchanged. The extractor does not drop features or claim the oversized generation was backed up.

Scientific payload identity is the exact original JSON byte sequence and its SHA256. A future Python/Zlib version may emit different gzip container bytes. Restoration then preserves all JSON bytes, creates a new gzip SHA256, retains the exact original ledger separately and writes an explicit private old-gzip/new-gzip/JSON hash mapping. The active ledger updates only the physical container identity/size and labels that regeneration. It never claims that the original gzip hash survived when it did not. Source, projection, parser, annotation and sequence identities remain unchanged.

## Snapshot and promotion

1. Approximately every500 newly committed caches, select the ledger prefix ending at the last complete cache_committed event. Ignore any incomplete trailing write or uncommitted cache
2. Verify every selected current gzip SHA against the selected ledger, decompress losslessly, and build the private archive plus per-record manifest
3. Reject an archive above32MiB without altering source caches or the prior verified backup
4. Divide the archive into bounded64KiB binary chunks. Read each as base64 through a tool result captured inside functions.exec; never print the encoded payload
5. Store candidate chunks and their index under a new generation in the extraction worker's functions.store
6. Read each stored chunk back, decode to local scratch and verify its SHA. Reassemble the archive, verify the entire archive SHA and inspect all original JSON payload hashes and the committed count
7. Promote the active generation only after all checks pass. Only then release the older tool-store payload. Record exact last_backed_up_count, archive SHA and the secondary-only durability limitation

The supervisor launches both extraction and archive compression as children of the same existing two-core/process-tree resource watchdog. Backup CLI helpers restrict themselves to the same first two available cores. The unchanged extractor is not edited. The aggregate120-minute rerun wall budget subtracts the fresh pilot and preliminary checks. Tool-store transfer and readback have bounded chunks and never log payloads.

## Keys and recovery

Production active key: zh_extraction_secondary_v1:active

Generation prefix: zh_extraction_secondary_v1:generation:<generation>

Each active entry retains the archive SHA, compressed byte count, exact committed count, chunk index and chunk keys. Synthetic test entries use a separate zh_secondary_synthetic_v1 prefix. Root's mirror, if present, has its own keys and verification receipt.

secondary_store_restore.js reconstructs an archive solely from the active worker-local store and the public helper code; it does not require the original archive/index files or raw corpus. It verifies chunk and archive hashes, then restores cache payloads and records any new gzip/ledger identities. A filesystem reset does not prove that this secondary store survived: check the active key and validate readback first. Never describe unavailable data as recovered before the restoration checks pass.

If the worker's store is unavailable, the root may attempt its independently verified mirror. If neither is available, report the actual recoverable count and preserve the distinction from historical progress.

## Synthetic validation completed before real secondary use

Ten synthetic unit tests cover exact JSON/gzip/ledger roundtrip, deliberately different gzip headers with identical JSON and explicit old/new mappings, partial ledger tails, uncommitted files, budget failure preserving the prior archive and sources, corrupt cache rejection, out-of-scope test-split rejection, chunk/readback corruption, and path traversal rejection.

A32-record synthetic archive was additionally transferred through actual functions.store and read back with an identical whole-archive SHA. A deliberately failed candidate left the prior verified generation active. The source archive/index directory was then made unavailable, and the32 records were restored solely from the tool-store chunks with all original JSON bytes and all32 original gzip hashes verified. These checks establish the implemented recovery path, not platform durability.
