# Offline WikiConv structural audit

`wikiconv_zip_audit.py` reproduces the **mechanical portion** of the [bounded provenance pilot](../../docs/design/provenance-feasibility-v0.1.zh.md#8-有界执行结果与实际准入决定). It reads one local ConvoKit WikiConv ZIP and writes aggregate JSON to standard output. Python 3.11+ and its standard library suffice. It has no downloader, extraction step, corpus-code execution, model dependency or fitting function. Input archives remain outside this repository.

## Run

From the repository root, replace the placeholder with your authorized local archive path:

```sh
python research/audits/wikiconv_zip_audit.py /path/to/local/full.corpus.zip \
  --expected-sha256 8c6b3f21adaad7b1d55eef3122593b418264c61b7bab9cd30c2f07cfbfce41ab
```

The hash pin is optional for other separately admitted artifacts. Do not remove it when reproducing this pilot. The script does not silently acquire a file if the path is missing. Exit status is 0 on success or 2 on a rejected/unreadable/unsupported input; errors use fixed codes without source strings or local paths. Standard output contains the archive hash and aggregate counts, not record/account identifiers, source text or paths. It writes no files; redirect output only to a destination appropriate for the data.

### Exact artifact used in the pilot

- Official [Chinese 2002 ZIP](https://zissou.infosci.cornell.edu/convokit/datasets/wikiconv-corpus/corpus-zipped/chinese/wikiconv-2002/full.corpus.zip), retrieved 2026-10-01 10:02:25 UTC
- Compressed bytes: 22,364; uncompressed bytes: 110,239; members: 5
- SHA-256: `8c6b3f21adaad7b1d55eef3122593b418264c61b7bab9cd30c2f07cfbfce41ab`
- Server Last-Modified: 2026-02-26 02:54:47 GMT. Historical record timestamps do **not** establish an independently preserved pre-LLM byte snapshot
- Actual `index.version`: 1. The [official download configuration](https://github.com/CornellNLP/ConvoKit/blob/master/download_config.json) inspected for the pilot reported 3. This discrepancy remains unresolved. The script reads only the local index and makes no claim to fetch or validate a current upstream configuration
- [WikiConv source and content notice](https://github.com/conversationai/wikidetox/tree/main/wikiconv): metadata CC0; comment content CC BY-SA 3.0. See the [source/use review](../../docs/corpus-provenance.md) for derivative-version and attribution qualifications. A successful audit does not grant new data-sharing permission

Expected observations for those exact bytes:

| Output | Expected |
|---|---:|
| `top_level_records` | 84 |
| `section_headers_true / false / unknown` | 79 / 5 / 0 |
| `conversation_metadata_records / speaker_metadata_records` | 81 / 19 |
| `serialized_views / distinct_event_ids` | 90 / 89 |
| Original / modification / deletion / restoration views | 5 / 1 / 0 / 0 |
| Missing top-level reply targets, including nested views | 1 of 2 non-null references |
| Missing nested reply targets | 2 of 5 non-null references |
| Top/original speaker-key differences among nonheaders; same text among these | 3; 3 |

The original source flags determine the 79/5 header split; it is not a linguistic judgment. Metadata speaker records are not verified natural persons. Different recorded keys, including equal wording under different keys, leave aliases, renaming, conversion and actual wording authorship unresolved.

## Measurement and selection contract

- Counts include every top-level record. Missing/null header flags have a separate unknown count; they are not silently treated as nonheaders. Unknown speaker keys are distinct from missing speaker metadata
- Count views and distinct event IDs separately. A final view duplicated in a modification list is not a second independent work. Duplicate top-level IDs fail; duplicate IDs across historical views are retained and reported through view/ID totals
- Normalize top-level `reply-to` and historical `reply_to`, `conversation_id` and `root`, `meta` and `meta_dict`. Object-valued speaker fields use `speaker.id`, not `speaker_id`. This follows the [official loader/serializer](https://github.com/CornellNLP/ConvoKit/blob/master/convokit/model/corpus_helpers.py), rather than declaring intentional serialization differences to be defects. Conflicting aliases fail closed
- Inspect at most one nested history level. Absent history container fields are counted separately; an empty or absent list cannot prove no historical event occurred. Explicit action-type absence does not become an inferred `ADDITION` event
- Reply/parent checks test target-ID existence, whether a target occurs only in another conversation, and whether its ID appears in multiple conversations. They do not validate temporal order, detect graph cycles, reconstruct merge/split events, or prove complete history. Roots are checked against the view IDs without inventing absent records
- For lineage summaries, sort nonheaders by numeric timestamp and then ID as an internal, non-emitted tie-break. In order, select the first not-yet-selected conversation with: (L1) a modification-list view; (L2) known but unequal top/original speaker keys; (L3) a non-null reply target absent from the top-level view. Missing or overlapping candidates produce a status, not a forced replacement sample. These are diagnostic criteria, not probability sampling
- Group views by their recorded conversation key. Report historical views whose conversation differs from their enclosing record; do not silently rewrite them. If a selected conversation has more than 50 views, report the bound and omit detailed lineage counts without substituting another conversation. Other whole-archive mechanical totals remain available
- Page-type output uses a fixed whitelist and an `other_or_unknown` bucket. Field-form output also uses fixed labels, never arbitrary source keys/values

The script cannot reproduce the pilot's prose screening or its **0 eligible / 82 excluded / 2 unresolved** use-specific disposition. Those conclusions combine source flags and explicitly documented assistant review; they are not machine-produced or independent human gold. No language, originality, translation, unaided-human, quality, authorship or H_G label is produced. The result is a structural diagnostic, not a representative corpus estimate or a validated linguistic annotation.

## Safety limits and tests

Limits are fixed in source, not overrideable CLI flags: at most 64 KiB compressed, 2 MiB total uncompressed, 16 entries and a 200:1 per-member compression ratio. Only the five exact flat JSON/JSONL filenames in the pilot schema are accepted. ZIP path/type checks, duplicate-member rejection, encryption/compression checks, bounded reads, actual STORED/DEFLATE expansion, exact stream termination, byte lengths and CRC validation precede parsing. Raw compressed streams are checked directly: the declared ZIP output length alone is not trusted. JSON duplicate keys, unsupported record shapes and conflicting aliases fail closed. No archive member is extracted or executed.

```sh
python -m unittest discover -s research/audits -p 'test_*.py' -v
```

Tests use self-authored **synthetic fixtures only**, including explicit privacy canaries and malformed ZIP/JSON cases. They test deterministic selection, field mappings, missingness, repeated IDs, graph-reference counts, bounds and sanitized error output. They are not empirical language evidence. Reproducing the real counts additionally requires the separately acquired hash-pinned archive; tests never download it.

Aggregate-only output is not a formal anonymization or differential-privacy guarantee. Small cells, source fingerprints and externally available information can still make a corpus recognizable. Review publication scope before sharing an audit of another dataset. This tool supports a narrowly bounded format; rejection of a different artifact does not establish that the artifact is corrupt.
