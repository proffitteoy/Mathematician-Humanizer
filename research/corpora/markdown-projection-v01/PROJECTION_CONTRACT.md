# Historical-blog Markdown prose projection, version 0.1

## Authority and current scope

This package is an independent Markdown instrument, not the frozen wikitext projector and not a new source-admission controller. Exactly 788 acquired article candidates exist, including three already exposed diagnostic works. No new candidate body may be read or projected by this package without a separately reviewed execution manifest and root GO. The three diagnostics remain permanently excluded; their source membership does not become eligible because projection succeeds. All 96 earlier calibration members and their exposed graph closure also remain excluded by the downstream admission controller.

Current authorization covers implementation, synthetic tests, limited parser-design inspection of only the existing three diagnostics, and one separately authorized three-diagnostic instrument smoke. It does not authorize new calibration, corpus projection, NLP, features, fitting, splits, raw publication, owner/personal materials, downloads or remote writes. The three-site acquisition and its independent review establish acquisition identity/census only. There is no broad-author or human-origin inference.

## Parser and source grammar

- `markdown-it-py==4.2.0` and `mdurl==0.1.2`, already installed, both MIT. The pinned dependency source inventory is private; safe digests and full license notices are bundled. No package installation was needed.
- The configured CommonMark block and inline parser provides a structural token AST, with GFM tables explicitly enabled. Rendering, syntax highlighting, JavaScript, templates, YAML construction, URL fetching and link validation by network are never invoked.
- Source newlines are normalized only inside the grammar engine, with a lossless raw-codepoint map. Output text remains exact raw UTF-8 source text. No NFKC, whitespace normalization, entity expansion, case folding, language detection, tokenizer or linguistic parser is performed here.
- Root paragraphs and mapped list paragraphs are candidate prose. ATX/setext headings, standalone emphasized heading/caption candidates, frontmatter, thematic breaks, fenced/indented code, blockquotes, inline typographic quotations, links including their visible labels and destinations, image alt/title/destination, explicit caption-like paragraphs, image-containing paragraphs and their immediately adjacent following prose paragraph, tables, reference definitions, footnotes, math, HTML, entities, escapes, emphasis markers, task markers, bare URLs and line breaks are barriers.
- YAML/TOML frontmatter, including a leading blank-line preamble, is scanned as opaque data, never parsed/evaluated. Ambiguous leading `---` without closure quarantines the record.
- CommonMark line offsets alone are not treated as character offsets. Paragraph maps reconstruct the parser's exact `getLines` slicing against its current container state. Partial tab expansion or any content/map disagreement quarantines the record. Identical repeated substrings are never aligned using global search.
- Inline rules are instrumented with exact consumed spans. Recursive link/image scopes override interior labels. Resolved emphasis contents may remain prose, but their removed markers create explicit gaps. Entities and escapes are whole barriers, so there is no partial decoded entity output.
- Display math has conservative line-delimited `$$` and `\\[...\\]` handling; inline `$...$`, `$$...$$`, `\\(...\\)` and `\\[...\\]` are barriers. Unsupported TeX/dialect syntax quarantines the record rather than becoming prose.
- Footnote definition scope includes its initial lazy paragraph and subsequent indented continuations; references are barriers. No footnote content is body prose.
- Balanced HTML element scopes, void elements, comments and declarations are barriers, expanded to complete source lines before the final block parse. Unknown/unclosed/mismatched HTML scope quarantines the record. No browser or HTML renderer is used.
- Any template/control-language marker outside recognized code scopes quarantines the whole record. This intentionally sacrifices recall instead of claiming to evaluate arbitrary Liquid/Jinja/ERB/MDX/custom container control scope.
- Encoded structural delimiters or escaped quotation delimiters quarantine the whole record; nested/closing quotation ambiguity does likewise. Suspicious unparsed syntax, unresolved references/emphasis/backticks/math/quotes, duplicate reference definitions, unmapped nonwhitespace source or an unknown AST type quarantines the complete record. Quarantined records emit zero projected segments, although full source-role partitions remain available privately.

This is deliberately conservative. It is not a universal Markdown renderer, caption detector, plagiarism adjudicator or semantic role oracle. Literal technical underscores, dollar signs and quotation marks can trigger quarantine. Unlabeled captions outside conservative image-adjacency barriers, unmarked quotations, assignment statements, translated/reposted prose and borrowed prose cannot reliably be identified from structural syntax alone. Such absence is never permission for downstream admission.

## Frozen output interface

`project_bytes(raw_utf8_bytes)` is a pure input API. It performs no file discovery or I/O. The caller owns pre-read authorization, provenance and exposure accounting.

The distinct profile is `historical-blog-markdown-conservative-prose/0.1.0`, with `source_frame=historical_blog_markdown`. It must not be forced into the prior three-source wikitext enum or used as evidence for a repaired v04/v03 source mix.

The common interface carries `profile`, `source_sha256`, `source_codepoints`, `source_frame`, `source_role`, `projection_sha256`, `segments`, `barriers`, and `flags`:

- Every segment has `index`, exact `text`, `source_spans=[[lo,hi]]`, and one `source_map=[lo,hi,"identity",0]` row per emitted codepoint. The additional affine map and UTF-8 boundary array allow exact reconstruction in either Unicode-codepoint or byte coordinates, including astral characters, combining marks and CRLF gaps.
- Every segment is one contiguous original raw-source span. Each removed syntax marker, line break or non-prose scope splits the segment. There is no text concatenation or synthetic whitespace. Joining across gaps is prohibited.
- `regions` partitions every original raw codepoint exactly once. `gaps` is precisely its non-emitted complement. `barriers` carries the same complementary spans with explicit reasons. Region/segment maps are monotone; byte offsets are exact strict UTF-8 offsets.
- `nodes` exposes structural token types, ancestors and normalized-source line/codepoint spans for diagnostics only. Its normalized coordinates must never be substituted for raw segment coordinates.
- `structural_status` means projected or quarantined. A projected record can still have zero segments. It does not mean admitted.
- `author_attribution=unverified`, `rights_status=unverified`, `human_origin=unknown`, `assistance_status=unknown`, `model_admitted=false`, `split_eligible=false` are mandatory. Frontmatter, Git account names, unsigned dates and repository licenses cannot promote these fields.

A result hash binds all fields before optional enclosing diagnostic metadata. The consumer must verify both this projection hash and any envelope/compressed-file hash. Reconstructing source maps establishes identity, not role correctness. Independent structural adjudication remains required.

## Copy/lineage interface

A later authorized copy gate must retain the complete raw Markdown view even when a record is quarantined or produces no prose. It must additionally index every emitted projected segment and its mapped contiguous raw source span without joining across barriers. Canonical blog members are JSON arrays `["gitblog", repository, "post:" + original_repository_path]`; commit identity is separate. Every alias, source binding and contaminated component must survive closure. No exposed diagnostic becomes a fresh independent work.

The existing signature-domain contract remains Unicode 15.0 NFKC then `isspace` removal, with `nfkc-no-ws/v1\0` and `char5-nfkc-no-ws/v1\0`. This projector does not compute those signatures, reopen old source text, alter fingerprint databases or assert universal old-prose coverage. In particular, the old bounded projected-exclusion certificate covers its frozen wiki profile, not this new Markdown profile. A separately reviewed, bounded compatibility extension is required wherever old raw/wiki-projected views cannot cover changed Markdown view denominators/adjacency; the consumer must not label that comparison complete. Raw and projected views do not confer semantic equivalence, authorship or licensing.

## Resource and failure contract

The pure function rejects inputs over 2 MiB raw UTF-8, 1,000,000 codepoints, 100,000 inline characters, or 100,000 structural tokens; grammar nesting is capped at 64. The bounded executor is still responsible for wall time, memory, storage and per-stage controls.

The one-time three-diagnostic smoke has its own root-authorized limits: 4 MiB for this package and derivatives, 60 seconds, 512 MiB address-space/RSS ceiling, at most two CPU affinity slots and two numerical threads. These do not change or consume the locked prior v03 1 GiB/90-minute budget. A 64 KiB terminal-evidence reserve is inside the 4 MiB cap.

The smoke verifies an externally supplied manifest digest, exact code/dependency-source hashes and exactly three allowlisted raw identities. It writes an exclusive consumed marker and each pre-read ledger before opening the corresponding raw source. It verifies the raw hash before projection. Dependencies are executed from checked source bytes, bypassing unbound `.pyc` caches. Linux seccomp denies network and child execution; GPU is disabled and NLP/model imports are denied. Results/maps/gaps and source identities remain private. Public output is aggregate counts, status and hashes only. Attempted reads, completed reads and completed projections are separately counted, with durable post-read events before projection. Gzip outputs and their directory are fsynced before they are counted. Terminal evidence may consume the reserved 64 KiB; success is durable only when the terminal seal binds both receipt and aggregate.

The marker survives failure. No automatic retry, marker deletion, alternate directory, larger cap, new source or substitute source is authorized. A failed run is a terminal instrument failure requiring a new explicit decision. The initial authorized parser-design inspection is recorded separately and is not falsely claimed to have been preceded by the smoke ledger.

## Evidence and reproduction

Run synthetic tests only:

    PYTHONDONTWRITEBYTECODE=1 /workspace/shared/style-ml-env/bin/python -m unittest -v test_markdown_projection.py

Do not rerun the natural smoke. Its consumed marker and receipt are evidence. The default test suite opens no natural source files. The independent reviewer should use additional synthetic fixtures and private smoke output only within root authorization. Any later code change requires a new version/hash and a new review; the prior smoke is not silently relabeled as testing revised code.

Primary parser documentation: https://markdown-it-py.readthedocs.io/en/latest/using.html and https://github.com/executablebooks/markdown-it-py .
