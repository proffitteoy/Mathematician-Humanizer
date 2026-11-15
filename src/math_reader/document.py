"""Extract inspectable structure without treating references as proof dependencies."""
import hashlib
from pathlib import Path
import re


KINDS = {"theorem", "lemma", "proposition", "corollary", "definition", "remark", "proof"}
ALIASES = {"thm": "theorem", "lem": "lemma", "prop": "proposition", "cor": "corollary",
           "defn": "definition", "def": "definition", "定理": "theorem", "引理": "lemma",
           "命题": "proposition", "推论": "corollary", "定义": "definition", "证明": "proof"}


def _mask(text, pattern):
    return re.sub(pattern, lambda m: "".join("\n" if c == "\n" else " " for c in m.group()), text)


def parse_document(text, format="latex", source="caller-supplied"):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("A nonempty document is required")
    if format not in {"latex", "markdown", "text"}:
        raise ValueError("Format must be latex, markdown or text")
    identity = hashlib.sha256(text.encode("utf-8")).hexdigest()
    view = text
    warnings = []
    if format == "latex":
        view = _mask(view, r"(?ms)\\begin\{(verbatim\*?|lstlisting|minted)\}.*?\\end\{\1\}")
        view = _mask(view, r"(?m)(?<!\\)%[^\n]*")
        names = {name: name for name in KINDS} | ALIASES
        # Support literal theorem declarations, without executing TeX macros or inputs.
        for match in re.finditer(r"\\newtheorem\*?\{([^{}]+)\}(?:\[[^\]]*\])?\{([^{}]+)\}", view):
            kind = match[2].lower()
            if kind in names:
                names[match[1]] = names[kind]
        stack, spans = [], []
        for match in re.finditer(r"\\(begin|end)\{([^{}]+)\}", view):
            kind = names.get(match[2].rstrip("*"))
            if not kind:
                continue
            if match[1] == "begin":
                stack.append((match[2], kind, match.start()))
            elif stack and stack[-1][0] == match[2]:
                _, kind, start = stack.pop()
                spans.append((start, match.end(), kind))
            else:
                warnings.append(f"Unmatched environment at offset {match.start()}")
        warnings.extend(f"Unclosed {name} at offset {start}" for name, _, start in stack)
        headings = list(re.finditer(r"\\(?:sub)*section\*?\{([^{}]+)\}", view))
    else:
        view = _mask(view, r"(?ms)^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?^ {0,3}\1[^\n]*(?:\n|$)")
        view = _mask(view, r"`[^`\n]+`")
        pattern = r"(?im)^[ \t]*(?:\#{1,6}\s+|\*\*)?(theorem|lemma|proposition|corollary|definition|remark|proof|定理|引理|命题|推论|定义|证明)(?=[\s\d:：.。*]|$)[^\n]*"
        starts = list(re.finditer(pattern, view))
        headings = list(re.finditer(r"(?m)^\#{1,6}\s+([^\n]+)", view))
        boundaries = sorted({m.start() for m in starts + headings} | {len(text)})
        spans = [(m.start(), next(b for b in boundaries if b > m.start()),
                  ALIASES.get(m[1].lower(), m[1].lower())) for m in starts]
        warnings.append("Plain-text/Markdown boundaries are heuristic; inspect statement/proof separation")
    nodes = []
    for start, end, kind in sorted(spans):
        body = text[start:end]
        section = next((h[1] for h in reversed(headings) if h.start() <= start), None)
        nodes.append({"id": f"n{len(nodes) + 1}", "kind": kind, "start": start, "end": end,
                      "text": body, "section": section,
                      "labels": re.findall(r"\\label\{([^{}]+)\}", view[start:end]),
                      "references": re.findall(r"\\(?:eqref|[cC]ref|ref)\*?\{([^{}]+)\}", view[start:end])})
    labels = {}
    for node in nodes:
        for label in node["labels"]:
            labels.setdefault(label, []).append(node["id"])
    candidates = []
    for node in nodes:
        for reference in node["references"]:
            for label in reference.split(","):
                targets = labels.get(label.strip(), [])
                candidates.append({"referencing_node": node["id"], "label": label.strip(),
                                   "possible_targets": targets, "status": "reference_only"})
    sections = [{"title": h[1], "start": h.start(),
                 "end": headings[i + 1].start() if i + 1 < len(headings) else len(text)}
                for i, h in enumerate(headings)]
    citations, bibliography = [], []
    if format == "latex":
        citations = [{"keys": [k.strip() for k in m[1].split(",")], "start": m.start(), "end": m.end(),
                      "text": text[m.start():m.end()]}
                     for m in re.finditer(r"\\cite[a-zA-Z]*\*?(?:\[[^\]]*\]){0,2}\{([^{}]+)\}", view)]
        entries = list(re.finditer(r"\\bibitem(?:\[[^\]]*\])?\{([^{}]+)\}", view))
        for i, entry in enumerate(entries):
            end = entries[i + 1].start() if i + 1 < len(entries) else len(text)
            closing = view.find(r"\end{thebibliography}", entry.end(), end)
            end = closing if closing >= 0 else end
            bibliography.append({"key": entry[1], "start": entry.start(), "end": end,
                                 "text": text[entry.start():end]})
    warnings.extend(f"Ambiguous label: {label}" for label, ids in labels.items() if len(ids) > 1)
    if not nodes:
        warnings.append("No recognized mathematical environments/headings; annotate spans in the original text")
    return {"schema": "math-document/1", "document_id": identity, "source": source,
            "format": format, "text": text, "offset_unit": "unicode_codepoint",
            "nodes": nodes, "sections": sections, "citations": citations, "bibliography": bibliography,
            "reference_candidates": candidates, "warnings": warnings,
            "limits": "No macro expansion, includes, OCR or automatic mathematical inference; references are not proof edges"}


def read_document(path, format="auto"):
    path = Path(path)
    raw = path.read_bytes()
    if format == "auto":
        format = {".tex": "latex", ".md": "markdown", ".pdf": "pdf"}.get(path.suffix.lower(), "text")
    if format != "pdf":
        return parse_document(raw.decode("utf-8"), format, str(path))
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("PDF extraction requires the optional 'pdf' dependency; no OCR is performed") from exc
    reader = PdfReader(path)
    parts, pages, offset = [], [], 0
    for number, page in enumerate(reader.pages, 1):
        body = page.extract_text() or ""
        parts.append(body)
        pages.append({"page": number, "start": offset, "end": offset + len(body), "empty": not body.strip()})
        offset += len(body) + 2
    result = parse_document("\n\n".join(parts), "text", str(path))
    result.update(source_sha256=hashlib.sha256(raw).hexdigest(), pages=pages)
    result["warnings"].append("PDF text is an extraction, not original formula fidelity; compare formulas with page images")
    return result


def validate_document(document):
    """Rebuild structure so edited offsets or text cannot masquerade as the same source."""
    if not isinstance(document, dict):
        raise ValueError("Document must be a JSON object")
    rebuilt = parse_document(document["text"], document["format"], document["source"])
    for key in ("schema", "document_id", "offset_unit", "nodes", "sections", "citations", "bibliography", "reference_candidates"):
        if document.get(key) != rebuilt[key]:
            raise ValueError(f"Document identity/structure mismatch: {key}")
    return document
