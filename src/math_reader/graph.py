"""Validate model-supplied proof roles and evidence; never certify a proof."""
import hashlib
import json

from .document import validate_document


RELATIONS = {"construction", "reduction", "estimate", "contradiction", "local_to_global",
             "necessity", "sufficiency", "application", "definition"}
CLAIM_KINDS = {"author_motivation", "mathematical_motivation", "historical_origin",
               "method_difference", "limitation", "transferable_idea", "innovation"}


def validate_evidence(items, sources):
    if not isinstance(items, list) or not items:
        raise ValueError("Every dependency/claim requires source evidence")
    for item in items:
        source = sources.get(item.get("document_id"))
        start, end = item.get("start"), item.get("end")
        if source is None or type(start) is not int or type(end) is not int:
            raise ValueError("Evidence needs a known document and integer offsets")
        if not 0 <= start < end <= len(source["text"]):
            raise ValueError("Evidence offsets outside source")
        if source["text"][start:end] != item.get("quote"):
            raise ValueError("Evidence quotation differs from the unchanged source")


def reconstruct(document, annotations, targets=None):
    validate_document(document)
    if not isinstance(annotations, dict):
        raise ValueError("Annotations must be a JSON object")
    if annotations.get("document_id") != document["document_id"]:
        raise ValueError("Annotations belong to a different document")
    sources = {document["document_id"]: document}
    for external in annotations.get("external_sources", []):
        validate_document(external)
        if external["document_id"] in sources:
            raise ValueError("Duplicate evidence source")
        sources[external["document_id"]] = external

    def evidence(items):
        validate_evidence(items, sources)

    nodes = {n["id"]: n for n in document["nodes"]}
    # Unrecognized definitions, assumptions and imported results can be anchored manually.
    for node in annotations.get("nodes", []):
        if node["id"] in nodes or not isinstance(node["id"], str) or not node["id"]:
            raise ValueError("Duplicate or invalid mathematical node id")
        if node.get("kind") not in {"assumption", "definition", "theorem", "lemma", "proposition", "external_result", "proof"}:
            raise ValueError("Unsupported manually anchored node kind")
        evidence([node["anchor"]])
        nodes[node["id"]] = node
    targets = targets if targets is not None else annotations.get("main_theorems", [])
    if not isinstance(targets, list) or not targets or any(t not in nodes for t in targets):
        raise ValueError("Select known main theorem ids")
    if any(nodes[t]["kind"] not in {"theorem", "proposition", "lemma", "external_result"} for t in targets):
        raise ValueError("A target must be a mathematical result")
    edges = annotations.get("edges", [])
    parents = {key: [] for key in nodes}
    children = {key: [] for key in nodes}
    seen = set()
    for edge in edges:
        a, b = edge["from"], edge["to"]
        if a not in nodes or b not in nodes or a == b or (a, b) in seen:
            raise ValueError("Unknown, self-referential or duplicate proof dependency")
        if (edge.get("kind") not in RELATIONS or not str(edge.get("role", "")).strip()
                or edge.get("basis") not in {"explicit_source", "reconstruction"}):
            raise ValueError("Dependency needs a mathematical kind and an explanation of its role")
        evidence(edge.get("evidence"))
        seen.add((a, b))
        parents[b].append(a)
        children[a].append(b)
    # Kahn's algorithm also checks disconnected cycles, without recursion depth limits.
    degrees = {key: len(value) for key, value in parents.items()}
    ready = [key for key in nodes if degrees[key] == 0]
    order = []
    for key in ready:
        order.append(key)
        for child in children[key]:
            degrees[child] -= 1
            if degrees[child] == 0:
                ready.append(child)
    if len(order) != len(nodes):
        raise ValueError("Proof dependencies contain a cycle")
    needed, pending = set(targets), list(targets)
    while pending:
        for parent in parents[pending.pop()]:
            if parent not in needed:
                needed.add(parent)
                pending.append(parent)
    claims = annotations.get("claims", [])
    findings = []
    reading = annotations.get("reading_coverage", [])
    for item in reading:
        evidence([item])
    cursor, unread = 0, []
    for item in sorted(reading, key=lambda e: e["start"]):
        if item["document_id"] != document["document_id"]:
            raise ValueError("Reading coverage must refer to the main document")
        if item["start"] > cursor:
            unread.append({"start": cursor, "end": item["start"]})
        cursor = max(cursor, item["end"])
    if cursor < len(document["text"]):
        unread.append({"start": cursor, "end": len(document["text"])})
    if unread:
        findings.append({"id": "incomplete_source_reading", "ranges": unread,
                         "requires": "Re-read and register missing source ranges; coverage records are model declarations, not proof of comprehension"})
    for i, claim in enumerate(claims):
        if claim.get("kind") not in CLAIM_KINDS or not str(claim.get("text", "")).strip():
            raise ValueError("Unsupported or empty conceptual claim")
        if not claim.get("nodes") or any(n not in nodes for n in claim["nodes"]):
            raise ValueError("Conceptual claim must identify its mathematical steps")
        evidence(claim.get("evidence"))
        basis = claim.get("basis")
        if basis not in {"explicit_source", "reconstruction", "unverified"}:
            raise ValueError("Claim basis must distinguish explicit source, reconstruction and unverified")
        if claim["kind"] in {"author_motivation", "historical_origin", "innovation"} and basis != "explicit_source":
            findings.append({"id": "unsupported_attribution", "claim": i,
                             "requires": "Use an explicit source or label the explanation as a mathematical reconstruction"})
        if claim["kind"] == "historical_origin" and not (
                any(e["document_id"] == document["document_id"] for e in claim["evidence"])
                and any(e["document_id"] != document["document_id"] for e in claim["evidence"])):
            findings.append({"id": "primary_source_not_checked", "claim": i,
                             "requires": "Inspect and register the cited original work; a citation alone does not verify history"})
        if basis == "unverified":
            findings.append({"id": "unverified_claim", "claim": i})
    arguments = annotations.get("arguments", {})
    for target in targets:
        argument = arguments.get(target)
        if argument is None:
            findings.append({"id": "missing_argument_record", "node": target})
            continue
        evidence([argument["statement"]])
        evidence([argument["conclusion"]])
        if not isinstance(argument.get("hypotheses"), list):
            raise ValueError("MAR hypotheses must be a list of exact evidence anchors")
        for hypothesis in argument["hypotheses"]:
            evidence([hypothesis])
        for key in ("obstruction", "mechanism", "idea"):
            field = argument.get(key, {})
            if not str(field.get("text", "")).strip():
                raise ValueError("MAR needs a substantive " + key)
            evidence(field.get("evidence"))
        if argument.get("status") not in {"reviewed", "unresolved"}:
            raise ValueError("MAR status must be reviewed or unresolved")
        if argument["status"] == "unresolved":
            findings.append({"id": "unresolved_argument", "node": target})
    coverage = annotations.get("coverage", {})
    for key in [n for n in order if n in needed]:
        record = coverage.get(key, {})
        if record.get("status") not in {"reviewed", "assumed", "gap"}:
            findings.append({"id": "missing_proof_review", "node": key})
            continue
        evidence(record.get("evidence"))
        if record["status"] in {"assumed", "gap"}:
            findings.append({"id": "proof_" + record["status"], "node": key, "note": record.get("note", "")})
        elif (nodes[key]["kind"] not in {"definition", "assumption", "external_result"}
              and not parents[key] and not str(record.get("note", "")).strip()):
            findings.append({"id": "leaf_result_needs_review", "node": key,
                             "requires": "Check for omitted hypotheses, external results or an independent proof"})
    result = {"schema": "proof-reconstruction/1", "document_id": document["document_id"],
            "targets": targets, "nodes": [{k: v for k, v in n.items() if k != "text"} for n in nodes.values()],
            "edges": edges, "claims": claims,
            "arguments": arguments,
            "coverage": coverage,
            "sources": [{"document_id": d["document_id"], "source": d["source"], "characters": len(d["text"])}
                        for d in sources.values()],
            "unread_ranges": unread,
            "prerequisite_order": [n for n in order if n in needed],
            "excluded_nodes": [n for n in order if n not in needed], "findings": findings,
            "evidence_integrity": "checked", "mathematical_validity": "not_certified",
            "limits": "Exact evidence and an acyclic graph do not establish entailment, completeness, novelty or historical truth"}
    result["reconstruction_sha256"] = hashlib.sha256(
        json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")).hexdigest()
    return result
