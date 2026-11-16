"""Optional local MCP adapter; computation and source documents stay in this process."""
import argparse
from pathlib import Path
import uuid

from math_reader.document import parse_document
from math_reader.graph import reconstruct
from .prompts import CONTROLLER, PROMPT_VERSION
from .workflow import audit_exposition, prepare_stage, statistical_feedback


def build_server(resources):
    from mcp.server.fastmcp import FastMCP

    resources = Path(resources)
    server = FastMCP("Mathematician Humanizer v2", host="127.0.0.1", port=8765)
    documents, uploads = {}, {}
    max_chars = 2_000_000

    def store(text, format, source):
        if len(text) > max_chars:
            raise ValueError("Document exceeds 2,000,000 Unicode code points; split into explicitly scoped sources")
        document = parse_document(text, format, source)
        if document["document_id"] not in documents and len(documents) >= 64:
            raise ValueError("64 documents in memory; restart the server to clear this local workspace")
        documents[document["document_id"]] = document
        return {"document_id": document["document_id"], "characters": len(text),
                "nodes": [{k: n[k] for k in ("id", "kind", "start", "end", "labels", "section")} for n in document["nodes"]],
                "sections": document["sections"], "citations": document["citations"], "bibliography": document["bibliography"],
                "reference_candidates": document["reference_candidates"], "warnings": document["warnings"]}

    def source(document_id):
        if document_id not in documents:
            raise ValueError("Unknown document; submit it to this server process first")
        return documents[document_id]

    def annotations_with_sources(annotations):
        result = dict(annotations)
        ids = result.pop("external_document_ids", [])
        result["external_sources"] = [*result.get("external_sources", []), *(source(i) for i in ids)]
        return result

    @server.tool()
    def get_writing_guide() -> dict:
        """Read the skill and the staged mathematical understanding controller."""
        return {"skill": (resources / "SKILL.md").read_text(encoding="utf-8"),
                "controller": CONTROLLER, "prompt_version": PROMPT_VERSION}

    @server.tool()
    def get_reference(name: str) -> str:
        """Read style, statistics, example, understanding or license; no arbitrary file access."""
        names = {"style": "references/mathematician-style.md", "statistics": "references/statistical-style.md",
                 "example": "examples/rewrite.md", "license": "references/upstream-LICENSE.txt",
                 "understanding": "references/mathematical-understanding.md"}
        if name not in names:
            raise ValueError("Unknown reference")
        return (resources / names[name]).read_text(encoding="utf-8")

    @server.tool()
    def analyze_paper(text: str, format: str = "latex", source: str = "caller-supplied") -> dict:
        """Parse source-preserving structure. References are candidates, not logical proof edges."""
        return store(text, format, source)

    @server.tool()
    def upload_paper_chunk(text: str, index: int, total: int, upload_id: str = "",
                           format: str = "latex", source: str = "caller-supplied") -> dict:
        """Upload ordered chunks with exact concatenation. First call uses index=0 and empty upload_id."""
        if not 1 <= total <= 1000 or not 0 <= index < total:
            raise ValueError("Invalid chunk index/total")
        if not upload_id:
            if index != 0 or len(uploads) >= 16:
                raise ValueError("Start with index 0; at most 16 incomplete uploads")
            upload_id = uuid.uuid4().hex
            uploads[upload_id] = {"total": total, "format": format, "source": source, "parts": {}}
        if upload_id not in uploads:
            raise ValueError("Unknown or completed upload")
        upload = uploads[upload_id]
        if (total, format, source) != (upload["total"], upload["format"], upload["source"]):
            raise ValueError("Chunk metadata changed")
        if index in upload["parts"] and upload["parts"][index] != text:
            raise ValueError("Conflicting chunk retry")
        size = sum(len(part) for i, part in upload["parts"].items() if i != index) + len(text)
        if size > max_chars:
            raise ValueError("Document exceeds 2,000,000 Unicode code points")
        upload["parts"][index] = text
        if len(upload["parts"]) != total:
            return {"upload_id": upload_id, "received": sorted(upload["parts"]), "complete": False}
        result = store("".join(upload["parts"][i] for i in range(total)), format, source)
        del uploads[upload_id]
        return result | {"complete": True}

    @server.tool()
    def read_paper_source(document_id: str, start: int = 0, max_chars: int = 12000) -> dict:
        """Re-read exact Unicode source spans; page through the entire paper without truncation."""
        text = source(document_id)["text"]
        if not 0 <= start <= len(text) or not 1 <= max_chars <= 20000:
            raise ValueError("Invalid source window")
        end = min(len(text), start + max_chars)
        return {"document_id": document_id, "start": start, "end": end, "quote": text[start:end],
                "next_start": end if end < len(text) else None}

    @server.tool()
    def query_proof_dependencies(document_id: str, annotations: dict, targets: list[str] | None = None) -> dict:
        """Validate exact evidence, proof DAG, theorem prerequisites, MAR and attribution findings."""
        return reconstruct(source(document_id), annotations_with_sources(annotations), targets)

    @server.tool()
    def prepare_explanation_task(stage: str, document_id: str, annotations: dict | None = None,
                                 reader: str = "unspecified", known_nodes: list[str] | None = None,
                                 baseline: str | None = None, candidate: str | None = None,
                                 audit: dict | None = None) -> dict:
        """Return a versioned stage prompt with computed dependencies and enforced writing/audit gates."""
        result = prepare_stage(stage, source(document_id), annotations_with_sources(annotations) if annotations else None,
                               reader, known_nodes, baseline, candidate, audit, resources / "research")
        if stage in {"exposition", "editorial"}:
            result["writing_guide"] = (resources / "SKILL.md").read_text(encoding="utf-8")
        return result

    @server.tool()
    def audit_mathematical_exposition(document_id: str, annotations: dict, baseline: str, candidate: str,
                                      language: str = "zh", genre: str = "math_exposition", reader: str = "unspecified",
                                      reference_source: str | None = None, review: dict | None = None) -> dict:
        """Execute separate source/MAR, protected-content and statistical audits; no proof certification."""
        return audit_exposition(source(document_id), annotations_with_sources(annotations), baseline, candidate,
                                language, genre, reader, resources / "research", reference_source, review)

    @server.tool()
    def prepare_mathematical_rewrite(text: str, language: str = "zh", reader: str = "unspecified") -> dict:
        """Compatibility task for short rewrites, with actual measurements; the caller model writes."""
        return {"text": text, "guide": (resources / "SKILL.md").read_text(encoding="utf-8"),
                "statistics": statistical_feedback(text, language, reader=reader),
                "instruction": "For paper understanding use analyze_paper and the staged protocol; this call does not reconstruct proofs"}

    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resources", type=Path, default=Path.cwd(), help="Repository containing SKILL.md, references and research")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    args = parser.parse_args(argv)
    try:
        if not (args.resources / "SKILL.md").is_file():
            raise ValueError("--resources must point to the repository containing SKILL.md")
        build_server(args.resources).run(transport=args.transport)
    except (ImportError, ValueError, OSError) as exc:
        parser.exit(2, f"mathematician-humanizer-mcp: {exc}; install optional 'mcp' dependencies if missing\n")


if __name__ == "__main__":
    main()
