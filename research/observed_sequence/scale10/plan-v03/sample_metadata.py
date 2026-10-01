"""Original metadata-only allocation kernel; not a data-admission verifier.

No I/O, parser, training or network. Inputs must come from the independently
audited projection/lineage frame; labels and text are explicitly not accepted.
"""
from collections import Counter, defaultdict
import hashlib
import json
import re

SEED = "style-observed-multiview-scale10-v1-20261001"
QUOTAS = {"discussion": (640, 160, 160), "news_prose": (320, 80, 80),
          "guide_prose": (320, 80, 80)}
FIELDS = {"record_key", "component_id", "source_frame", "source_sha256",
          "projection_sha256", "projection_profile", "preparse_eligible"}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def rank(purpose, key):
    return hashlib.sha256(canonical([SEED, purpose, key])).hexdigest(), key


def member_key(source, project, object_id):
    """Never equate page/object integers from different source namespaces."""
    if any(not isinstance(v, str) or not v for v in (source, project, object_id)):
        raise ValueError("invalid_namespaced_member")
    return canonical([source, project, object_id]).decode("utf-8")


def wiki_member_key(dataset_alias, project, page_id):
    """Dataset/source-view aliases never create different wiki page identities."""
    if dataset_alias not in {"wikiconv", "discussion", "mediawiki", "wikimedia"}:
        raise ValueError("unknown_wiki_dataset_alias")
    if project not in {"zhwiki", "zhwikinews", "zhwikivoyage"}:
        raise ValueError("unknown_wiki_project")
    if not isinstance(page_id, str) or not re.fullmatch(r"[0-9]+", page_id):
        raise ValueError("invalid_wiki_page_id")
    return member_key("wikimedia", project, "page:" + str(int(page_id)))


def freeze_components(members, hard_edges, unresolved_edges, excluded_members):
    """Union concrete unresolved links conservatively, then propagate exposure.

    Expand old component membership/ancestry into member-level edges *before*
    calling. Exclusion is member contamination, never old/new ID equality.
    """
    nodes = set(members)
    excluded_ancestors = set(excluded_members)
    edges = tuple(hard_edges) + tuple(unresolved_edges)
    for n in nodes:
        try:
            parts = json.loads(n)
        except (ValueError, TypeError):
            raise ValueError("unnamespaced_member") from None
        if not isinstance(parts, list) or len(parts) != 3 or member_key(*parts) != n:
            raise ValueError("unnamespaced_member")
    if not excluded_ancestors <= nodes:
        raise ValueError("excluded_ancestor_missing")
    parent = {n: n for n in nodes}
    def find(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    for a, b in edges:
        if a not in nodes or b not in nodes:
            raise ValueError("edge_endpoint_missing")
        x, y = find(a), find(b)
        parent[max(x, y)] = min(x, y)
    groups = defaultdict(list)
    for n in nodes: groups[find(n)].append(n)
    mapping, excluded = {}, set()
    for group in groups.values():
        component = hashlib.sha256(canonical(sorted(group))).hexdigest()
        for n in group: mapping[n] = component
        if set(group) & excluded_ancestors: excluded.add(component)
    assert all(mapping[a] == mapping[b] for a, b in edges)
    return mapping, excluded


def allocate(rows, excluded_components, quotas=None):
    """Return a proposal, including underfill; never replace by another source.

    One component may contain multiple sources. Its globally hash-first eligible
    record determines source ownership before any source-specific quota/split.
    `preparse_eligible` cannot depend on model outputs. Caller must verify it.
    """
    quotas = QUOTAS if quotas is None else quotas
    if set(quotas) != set(QUOTAS):
        raise ValueError("source_frame_set")
    if any(len(q) != 3 or any(type(n) is not int or n < 0 for n in q)
           for q in quotas.values()):
        raise ValueError("invalid_quotas")
    if not isinstance(excluded_components, (set, frozenset)):
        raise ValueError("exclusions_must_be_set")
    grouped = defaultdict(list)
    seen = set()
    counts = Counter()
    for r in rows:
        if not isinstance(r, dict) or set(r) != FIELDS:
            raise ValueError("metadata_fields_only")
        if any(not isinstance(r[k], str) or not r[k] for k in FIELDS - {"preparse_eligible"}):
            raise ValueError("missing_stable_identity")
        for name in ("source_sha256", "projection_sha256"):
            if len(r[name]) != 64 or any(c not in "0123456789abcdef" for c in r[name]):
                raise ValueError("bad_content_hash")
        if r["source_frame"] not in quotas or type(r["preparse_eligible"]) is not bool:
            raise ValueError("invalid_source_or_flag")
        if r["record_key"] in seen:
            raise ValueError("duplicate_record_key")
        seen.add(r["record_key"])
        counts["input_records"] += 1
        if r["component_id"] in excluded_components:
            counts["old_or_diagnostic_component_records"] += 1
        elif not r["preparse_eligible"]:
            counts["preparse_ineligible"] += 1
        else:
            grouped[r["component_id"]].append(r)
    owned = defaultdict(list)
    for component, group in grouped.items():
        representative = min(group, key=lambda r: rank("representative", r["record_key"]))
        owned[representative["source_frame"]].append(representative)
    selected, coverage = [], {}
    for source in sorted(quotas):
        a, b, c = quotas[source]
        ordered = sorted(owned[source], key=lambda r: rank("component", r["component_id"]))
        for i, r in enumerate(ordered[:a+b+c]):
            split = "train" if i < a else "development" if i < a+b else "test"
            selected.append(dict(r, partition=split))
        coverage[source] = {"available_components": len(ordered),
                            "requested_components": a+b+c,
                            "selected_components": min(len(ordered), a+b+c)}
    selected.sort(key=lambda r: (r["source_frame"], r["partition"], r["component_id"]))
    assert len({r["component_id"] for r in selected}) == len(selected)
    assert not ({r["component_id"] for r in selected} & excluded_components)
    complete = all(v["available_components"] >= v["requested_components"]
                   for v in coverage.values())
    return {"status": "proposal_complete_not_admitted" if complete else "underfilled_stop",
            "seed": SEED, "selection_sha256": hashlib.sha256(canonical(selected)).hexdigest(),
            "selected_records": selected, "coverage": coverage, "counts": dict(counts),
            "fit_authorized": False}
