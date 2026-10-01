"""Offline conservative structural Markdown projection. No file/network access.

Only `project_bytes` is an input API. It does not certify authorship or rights.
Pinned markdown-it-py supplies CommonMark block/inline grammar. The getLines
source-map reconstruction below follows its MIT-licensed StateBlock.getLines;
the upstream license is bundled in THIRD_PARTY_LICENSES.txt.
"""
from __future__ import annotations

import hashlib
import html
import importlib.metadata
import json
import re
from collections import Counter
from dataclasses import dataclass

from markdown_it import MarkdownIt
from markdown_it.common.html_re import HTML_TAG_RE
from markdown_it.parser_inline import ParserInline, _rules as INLINE_RULES
from markdown_it.rules_block.paragraph import paragraph
from markdown_it.rules_inline.state_inline import StateInline

VERSION = "historical-markdown-projection/1.0"
PROFILE = "historical-blog-markdown-conservative-prose/0.1.0"
SOURCE_FRAME = "historical_blog_markdown"
DEPENDENCIES = {"markdown-it-py": "4.2.0", "mdurl": "0.1.2"}
MAX_BYTES = 2 * 1024 * 1024
MAX_CODEPOINTS = 1_000_000
MAX_AST_TOKENS = 100_000
MAX_INLINE_CHARS = 100_000
MAX_NESTING = 64
PROSE_ROLES = {"body_prose_candidate", "list_prose_candidate"}
VOID_TAGS = set("area base br col embed hr img input link meta param source track wbr".split())
HTML_LEX = re.compile(HTML_TAG_RE.pattern.removeprefix("^"))


class ProjectionError(ValueError):
    """Fail-closed input, dependency, invariant or resource error."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_dependencies():
    for name, version in DEPENDENCIES.items():
        if importlib.metadata.version(name) != version:
            raise ProjectionError("dependency_version_mismatch:" + name)


def normalized_source(raw: str):
    """CommonMark newline normalization with lossless raw codepoint boundaries."""
    out, mapping, i = [], [], 0
    while i < len(raw):
        start = i
        c = raw[i]
        if c == "\r":
            i += 2 if raw[i:i+2] == "\r\n" else 1
            out.append("\n")
        else:
            i += 1
            out.append(c)
        mapping.append((start, i))
    return "".join(out), mapping


def get_lines_with_map(state, begin, end, indent):
    """Rebuild the parser's exact line slicing; tabs requiring expansion fail."""
    chars, offsets = [], []
    for line in range(begin, end):
        column = 0
        first = line_start = state.bMarks[line]
        last = state.eMarks[line] + (1 if line + 1 < end else 0)
        while first < last and column < indent:
            c = state.src[first]
            if c in " \t":
                column += 4 - (column + state.bsCount[line]) % 4 if c == "\t" else 1
            elif first - line_start < state.tShift[line]:
                column += 1
            else:
                break
            first += 1
        if column > indent:
            raise ProjectionError("partial_tab_expansion")
        chars.extend(state.src[first:last])
        offsets.extend(range(first, last))
    joined = "".join(chars)
    left = len(joined) - len(joined.lstrip())
    right = len(joined.rstrip())
    return joined[left:right], offsets[left:right]


def mapped_paragraph(state, start, end, silent):
    before = len(state.tokens)
    matched = paragraph(state, start, end, silent)
    if matched and not silent:
        for token in state.tokens[before:]:
            if token.type == "inline":
                try:
                    content, offsets = get_lines_with_map(state, *token.map, state.blkIndent)
                    if content != token.content:
                        raise ProjectionError("paragraph_mapping_disagreement")
                    token.meta["source_offsets"] = offsets
                except ProjectionError as exc:
                    token.meta["mapping_error"] = str(exc)
    return matched


class TracedInline(ParserInline):
    """Record exact rule-consumed source spans, including recursive link spans."""
    def __init__(self):
        super().__init__()
        for name, function in INLINE_RULES:
            def traced(state, silent, name=name, function=function):
                start, count = state.pos, len(state.tokens)
                matched = function(state, silent)
                if matched and not silent:
                    state.projection_events.append({
                        "rule": name, "start": start, "end": state.pos,
                        "tokens": [t.type for t in state.tokens[count:]],
                    })
                return matched
            self.ruler.at(name, traced)

    def parse(self, src, md, env, tokens):
        state = StateInline(src, md, env, tokens)
        state.projection_events = []
        self.tokenize(state)
        for rule in self.ruler2.getRules(""):
            rule(state)
        self.last_events = state.projection_events
        return state.tokens


def parser():
    md = MarkdownIt()
    md.inline = TracedInline()
    md.configure("commonmark")
    md.options.update({"maxNesting": MAX_NESTING, "html": True,
                       "linkify": False, "typographer": False, "inline_definitions": True})
    md.enable("table")
    md.core.ruler.disable(["normalize", "inline", "text_join"])
    md.block.ruler.at("paragraph", mapped_paragraph)
    return md


@dataclass
class Scope:
    start: int
    end: int
    role: str
    unresolved: bool = False


def line_offsets(src):
    starts = [0]
    starts.extend(i + 1 for i, c in enumerate(src) if c == "\n")
    if starts[-1] != len(src):
        starts.append(len(src))
    return starts


def block_bounds(token, starts, n):
    if token.map is None:
        raise ProjectionError("missing_block_map")
    a, b = token.map
    if not 0 <= a <= b < len(starts):
        # A trailing newline supplies a sentinel; no-newline EOF uses the final
        # appended boundary as sentinel. Both share this exact bound.
        raise ProjectionError("invalid_block_map")
    return starts[a], starts[b]


def blank_regions(src, regions):
    out = list(src)
    for region in regions:
        for i in range(region.start, region.end):
            if out[i] != "\n":
                out[i] = " "
    return "".join(out)


def frontmatter_scope(src):
    lines = src.splitlines(keepends=True)
    if not lines:
        return []
    first = next((i for i,line in enumerate(lines) if line.lstrip("\ufeff").strip()),None)
    if first is None:
        return []
    delimiter = lines[first].lstrip("\ufeff").strip()
    if delimiter not in {"---", "+++"}:
        return []
    end = sum(len(line) for line in lines[:first+1])
    for line in lines[first+1:]:
        end += len(line)
        if line.strip() in ({"---", "..."} if delimiter == "---" else {"+++"}):
            return [Scope(0, end, "frontmatter")]
    return [Scope(0, len(src), "unresolved_frontmatter", True)]


def extension_scopes(src, protected):
    """Conservative dialect barriers. No YAML, HTML or template evaluation."""
    visible = blank_regions(src, protected)
    regions = []
    # Encoded/escaped role delimiters may hide quotation, HTML, math or code
    # scope across paragraphs. Never rewrite source and accidentally certify it.
    dangerous = set('[]{}<>#$`*_\\|"\'“”‘’「」『』«»')
    for hit in re.finditer(r'&(?:#[xX][0-9A-Fa-f]+|#[0-9]+|[A-Za-z][A-Za-z0-9]+);',visible):
        decoded = html.unescape(hit[0])
        if decoded != hit[0] and (any(c in dangerous for c in decoded) or re.search(r'&[^;]+;',decoded)):
            return [Scope(0,len(src),'unresolved_encoded_role_delimiter',True)]
    if re.search(r'\\["\'“”‘’「」『』«»]',visible):
        return [Scope(0,len(src),'unresolved_escaped_quote_scope',True)]
    # Template languages have unconstrained control scope. Rather than pretend
    # to parse every dialect, quarantine the complete document on a marker.
    if re.search(r"\{%|\{\{|\{#|<%|<\?|^\s*:::", visible, re.M):
        return [Scope(0, len(src), "unresolved_template_scope", True)]
    starts = line_offsets(src)
    lines = visible.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        # Only unambiguous line-delimited display math is handled here.
        closing = {"$$": "$$", r"\[": r"\]"}.get(stripped)
        if closing:
            j = i + 1
            while j < len(lines) and lines[j].strip() != closing:
                j += 1
            done = j < len(lines)
            end_line = j + 1 if done else len(lines)
            regions.append(Scope(starts[i], starts[end_line],
                                 "display_math" if done else "unresolved_display_math", not done))
            i = end_line
            continue
        if re.match(r"^ {0,3}\[\^[^\]\n]+\]:", lines[i]):
            # Include the initial lazy paragraph, then all indented continuations
            # (and intervening blank lines). No footnote prose enters body views.
            j = i + 1
            while j < len(lines) and lines[j].strip():
                j += 1
            while j < len(lines):
                if not lines[j].strip() or re.match(r"^(?: {4}|\t)", lines[j]):
                    j += 1
                else:
                    break
            regions.append(Scope(starts[i], starts[j], "footnote_definition"))
            i = j
            continue
        i += 1
    # Entire paired HTML scopes, including intervening blank lines, are excluded.
    visible = blank_regions(visible, regions)
    stack = []
    pos = 0
    while pos < len(visible):
        pos = visible.find("<", pos)
        if pos < 0:
            break
        hit = HTML_LEX.match(visible, pos)
        if not hit:
            if re.match(r"<(?:/?[A-Za-z]|!|\?)", visible[pos:]):
                # Autolinks are resolved by the inline grammar, not HTML.
                if not re.match(r"<(?:[A-Za-z][A-Za-z0-9+.-]{1,31}:[^ <>]*|[^ <>@]+@[^ <>@]+)>", visible[pos:]):
                    regions.append(Scope(pos, len(src), "unresolved_html", True))
                    break
            pos += 1
            continue
        text = hit.group()
        name_hit = re.match(r"</?([A-Za-z][A-Za-z0-9-]*)", text)
        if not name_hit:
            regions.append(Scope(pos, hit.end(), "html_comment_or_declaration"))
        else:
            name = name_hit[1].lower()
            if text.startswith("</"):
                if not stack or stack[-1][0] != name:
                    regions.append(Scope(stack[0][1] if stack else pos,
                                         len(src), "unresolved_html_nesting", True))
                    break
                _, opener = stack.pop()
                regions.append(Scope(opener, hit.end(),
                                     "html_caption" if name == "figcaption" else "html_element"))
            elif name in VOID_TAGS or text.rstrip().endswith("/>"):
                regions.append(Scope(pos, hit.end(), "html_void_element"))
            else:
                stack.append((name, pos))
        pos = hit.end()
    if stack:
        regions.append(Scope(stack[0][1], len(src), "unresolved_html_scope", True))
    return regions


def inline_roles(md, content, env, list_context=False):
    if len(content) > MAX_INLINE_CHARS:
        raise ProjectionError("inline_character_cap")
    children = []
    md.inline.parse(content, md, env, children)
    events = md.inline.last_events
    roles = ["prose"] * len(content)
    errors = []
    def mark(a, b, role):
        if not 0 <= a <= b <= len(content):
            raise ProjectionError("invalid_inline_trace")
        roles[a:b] = [role] * (b-a)
    # Shorter recursive events first; encompassing links/images override labels.
    for e in sorted(events, key=lambda x: x["end"]-x["start"]):
        name, a, b = e["rule"], e["start"], e["end"]
        if name in {"link", "image", "autolink", "html_inline", "entity", "escape"}:
            mark(a, b, {"link":"link_label_and_destination", "image":"image_alt_title_destination",
                         "autolink":"autolink", "html_inline":"html_inline",
                         "entity":"entity_encoding", "escape":"escape_encoding"}[name])
        elif name == "backticks":
            if "code_inline" not in e["tokens"]:
                errors.append("unresolved_backtick")
            mark(a, b, "inline_code")
        elif name == "emphasis":
            mark(a, b, "emphasis_marker")
        elif name == "newline":
            # Every source newline is a hard segment boundary. Preserve its raw
            # bytes in a gap rather than silently joining visible words.
            while a > 0 and content[a-1] in " \t":
                a -= 1
            mark(a, b, "line_break")
    # Leftover emphasis characters in text tokens are unresolved for this policy.
    # Literal technical identifiers are conservatively quarantined too.
    for child in children:
        if child.type == "text" and re.search(r"[*_]", child.content):
            errors.append("unresolved_emphasis_or_literal_marker")
    if list_context and re.match(r"^\[[ xX]\]\s", content):
        mark(0,3,"task_list_marker")
    # Math/footnote syntax is an explicit extension, never interpreted as prose.
    i = 0
    while i < len(content):
        if roles[i] not in {"prose", "escape_encoding"}:
            i += 1
            continue
        foot = re.match(r"\[\^[^\]\n]+\]", content[i:])
        if foot and all(r == "prose" for r in roles[i:i+len(foot[0])]):
            mark(i, i+len(foot[0]), "footnote_reference")
            i += len(foot[0]); continue
        opener = next((s for s in (r"\(", r"\[", "$$", "$")
                       if content.startswith(s, i) and (s.startswith("\\") or roles[i] == "prose")), None)
        if opener:
            closer = {r"\(":r"\)", r"\[":r"\]", "$$":"$$", "$":"$"}[opener]
            j = content.find(closer, i + len(opener))
            if j < 0 or "\n" in content[i:j]:
                errors.append("unresolved_inline_math")
                mark(i, len(content), "unresolved_inline_math")
                break
            mark(i, j+len(closer), "inline_math")
            i = j+len(closer); continue
        i += 1
    # Typographically delimited quotations are separate structural roles. This
    # does not decide who is quoted, or whether any unmarked text is original.
    quote_pairs = {"“":"”", "「":"」", "『":"』", "‘":"’", "«":"»", '"':'"'}
    i = 0
    while i < len(content):
        if roles[i] == "prose" and content[i] in quote_pairs:
            closer = quote_pairs[content[i]]
            j = i + 1
            while j < len(content) and not (content[j] == closer and roles[j] == "prose"):
                if roles[j] == "prose" and content[j] in quote_pairs:
                    errors.append("unresolved_quote_nesting")
                j += 1
            if j == len(content):
                errors.append("unresolved_inline_quote")
                mark(i,j,"unresolved_inline_quote")
            else:
                mark(i,j+1,"inline_quote")
            i = j+1
        else:
            i += 1
    for i,c in enumerate(content):
        if roles[i] == 'prose' and c in '”’」』»':
            errors.append('unresolved_closing_quote')
    # Unparsed bracket, extension and tag markers must not silently become prose.
    for i, c in enumerate(content):
        if roles[i] == "prose" and c in "[]{}$`~^<>\\|":
            errors.append("unresolved_inline_syntax")
            break
    for match in re.finditer(r"&(?:#[A-Za-z0-9]+|[A-Za-z][A-Za-z0-9]+);",content):
        if any(r == "prose" for r in roles[match.start():match.end()]):
            errors.append("unresolved_entity")
    for match in re.finditer(r"(?:https?://|www\.)[^\s<>]+", content):
        if all(x == "prose" for x in roles[match.start():match.end()]):
            mark(match.start(), match.end(), "bare_url")
    return roles, sorted(set(errors)), [t.type for t in children]


def project_bytes(data: bytes):
    """Return private raw-exact segments plus a total source partition.

    Caller owns authorization before acquiring/reading bytes. This pure function
    has no batch discovery, file opening, cache, execution, network, or NLP API.
    """
    check_dependencies()
    if not isinstance(data, bytes) or len(data) > MAX_BYTES:
        raise ProjectionError("raw_byte_cap_or_type")
    try:
        raw = data.decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise ProjectionError("invalid_utf8") from exc
    if len(raw) > MAX_CODEPOINTS:
        raise ProjectionError("raw_codepoint_cap")
    if "\0" in raw:
        raise ProjectionError("nul_not_supported")
    src, source_map = normalized_source(raw)
    n = len(src)
    starts = line_offsets(src)
    labels = ["unclassified"] * n
    node_ids = [None] * n
    errors, nodes = [], []
    def set_role(a, b, role, node=None):
        if not 0 <= a <= b <= n:
            raise ProjectionError("invalid_region_bounds")
        labels[a:b] = [role] * (b-a)
        node_ids[a:b] = [node] * (b-a)
    front = frontmatter_scope(src)
    if src.startswith("\ufeff") and not front:
        front = [Scope(0, 1, "bom")]
    masked = blank_regions(src, front)
    md = parser()
    preliminary = md.parse(masked, {})
    if len(preliminary) > MAX_AST_TOKENS:
        raise ProjectionError("preliminary_ast_token_cap")
    protected = list(front)
    for token in preliminary:
        if token.type in {"fence", "code_block"}:
            a, b = block_bounds(token, starts, n)
            protected.append(Scope(a, b, token.type))
        elif token.type == "inline" and "source_offsets" in token.meta:
            if len(token.content) > MAX_INLINE_CHARS:
                raise ProjectionError("preliminary_inline_character_cap")
            md.inline.parse(token.content, md, {}, [])
            for e in md.inline.last_events:
                if e["rule"] == "backticks" and "code_inline" in e["tokens"]:
                    offsets = token.meta["source_offsets"][e["start"]:e["end"]]
                    if offsets:
                        protected.append(Scope(offsets[0], offsets[-1]+1, "inline_code"))
    extra = extension_scopes(masked, protected)
    scopes = front + extra
    # Expand extra barriers to complete source lines before reparsing, so removed
    # inline HTML cannot turn two sides into a new Markdown construct.
    expanded = []
    for region in extra:
        a = src.rfind("\n", 0, region.start) + 1
        q = src.find("\n", region.end)
        b = q + 1 if q >= 0 else n
        if region.end > region.start and src[region.end-1:region.end] == "\n":
            b = region.end
        expanded.append(Scope(a, b, region.role, region.unresolved))
    scopes = front + expanded
    masked = blank_regions(src, scopes)
    env = {}
    tokens = md.parse(masked, env)
    if len(tokens) > MAX_AST_TOKENS:
        raise ProjectionError("ast_token_cap")
    if env.get("duplicate_refs"):
        errors.append("duplicate_link_reference")
    stack = []
    previous_paragraph_had_image = False
    for token in tokens:
        if token.nesting == -1:
            if not stack:
                raise ProjectionError("ast_stack_underflow")
            stack.pop()
            continue
        ancestors = tuple(stack)
        node = len(nodes)
        if token.map is not None:
            a, b = block_bounds(token, starts, n)
            nodes.append({"id":node, "type":token.type, "ancestors":list(ancestors),
                          "source_normalized_span":[a,b], "line_span":token.map})
        if token.type == "inline":
            a, b = block_bounds(token, starts, n)
            if "blockquote_open" in ancestors:
                previous_paragraph_had_image = False
                set_role(a,b,"blockquote",node)
            elif "heading_open" in ancestors:
                previous_paragraph_had_image = False
                set_role(a,b,"heading",node)
            elif "table_open" in ancestors:
                previous_paragraph_had_image = False
                set_role(a,b,"table",node)
            elif not ancestors or ancestors[-1] != "paragraph_open":
                set_role(a,b,"unresolved_ast_inline_context",node)
                errors.append("unresolved_ast_inline_context")
            else:
                set_role(a,b,"paragraph_structure",node)
                offsets = token.meta.get("source_offsets")
                if offsets is None or token.meta.get("mapping_error"):
                    errors.append(token.meta.get("mapping_error", "missing_inline_source_map"))
                    continue
                if len(offsets) != len(token.content) or any(masked[o] != c for o,c in zip(offsets,token.content)):
                    raise ProjectionError("inline_source_map_invariant")
                roles, inline_errors, child_types = inline_roles(md,token.content,env,"list_item_open" in ancestors)
                nodes[-1]["inline_types"] = child_types
                errors.extend(inline_errors)
                # An image-only paragraph and explicit caption-like paragraph
                # stay outside prose. Ambiguous unlabeled captions require review.
                caption = bool(re.match(r"^(?:(?:图|表)\s*(?:[0-9零〇一二三四五六七八九十百壹贰叁]+|[:：])|(?:图片说明|图片来源|图注|图说)\s*[:：]|(?:Figure|Table|Fig\.)\s+(?:\d+|[IVXLCDM]+)\b|:\s)", token.content,re.I))
                has_image = "image" in child_types
                adjacent_image = previous_paragraph_had_image
                previous_paragraph_had_image = has_image
                standalone_emphasis = bool(re.fullmatch(r"(\*\*|__|\*|_)(?=\S).+\1",token.content,re.S))
                prose_role = "list_prose_candidate" if "list_item_open" in ancestors else "body_prose_candidate"
                for j, offset in enumerate(offsets):
                    if not roles[j] == "prose":
                        set_role(offset,offset+1,roles[j],node)
                    else:
                        role = "caption_figure_candidate" if has_image else "image_adjacent_caption_candidate" if adjacent_image else "emphasis_heading_or_caption_candidate" if standalone_emphasis else "caption_candidate" if caption else prose_role
                        set_role(offset,offset+1,role,node)
        elif token.type in {"fence","code_block","html_block","hr","definition"}:
            previous_paragraph_had_image = False
            a,b = block_bounds(token,starts,n)
            set_role(a,b,{"fence":"fenced_code","code_block":"indented_code",
                          "html_block":"html_block","hr":"thematic_break",
                          "definition":"link_reference_definition"}[token.type],node)
            if token.type == "fence":
                tail = masked[a:b].splitlines()[-1] if masked[a:b].splitlines() else ""
                closing = re.fullmatch(r"\s*(?:>\s*)*"+re.escape(token.markup[0])+"{"+str(len(token.markup))+r",}\s*",tail)
                if token.map[1]-token.map[0] < 2 or not closing:
                    errors.append("unclosed_fenced_code")
        elif token.type == "table_open":
            previous_paragraph_had_image = False
            a,b = block_bounds(token,starts,n); set_role(a,b,"table",node)
        elif token.type in {"heading_open","blockquote_open"}:
            a,b = block_bounds(token,starts,n)
            set_role(a,b,"heading" if token.type == "heading_open" else "blockquote",node)
        elif token.type not in {"paragraph_open","bullet_list_open","ordered_list_open","list_item_open","thead_open","tbody_open","tr_open","th_open","td_open"}:
            errors.append("unknown_ast_token:"+token.type)
        if token.nesting == 1:
            stack.append(token.type)
    if stack:
        raise ProjectionError("unclosed_ast_stack")
    for region in scopes:
        set_role(region.start,region.end,region.role)
        if region.unresolved:
            errors.append(region.role)
    for i, role in enumerate(labels):
        if role == "unclassified":
            if src[i].isspace():
                labels[i] = "block_whitespace"
            else:
                labels[i] = "unresolved_unclassified_source"
                errors.append("unresolved_unclassified_source")
    # All emitted prose is raw-identical. Any unresolved syntax quarantines the
    # whole record; no deceptively clean partial prose view escapes a failure.
    errors = sorted(set(errors))
    if errors:
        labels = ["quarantined_candidate_prose" if r in PROSE_ROLES else r for r in labels]
    raw_labels, raw_nodes = [], []
    for i,(a,b) in enumerate(source_map):
        raw_labels.extend([labels[i]]*(b-a)); raw_nodes.extend([node_ids[i]]*(b-a))
    byte_offsets = [0]
    for c in raw:
        byte_offsets.append(byte_offsets[-1]+len(c.encode("utf-8")))
    regions, segments, gaps = [], [], []
    i = 0
    while i < len(raw):
        j = i+1
        while j < len(raw) and (raw_labels[j],raw_nodes[j]) == (raw_labels[i],raw_nodes[i]):
            j += 1
        region = {"source_char_span":[i,j], "source_byte_span":[byte_offsets[i],byte_offsets[j]],
                  "role":raw_labels[i], "node_id":raw_nodes[i]}
        regions.append(region)
        if raw_labels[i] in PROSE_ROLES and raw[i:j].strip():
            text = raw[i:j]
            segment = dict(region, segment_id=sha((sha(data)+f":{i}:{j}:{raw_labels[i]}").encode()),
                           text=text, text_sha256=sha(text.encode()),
                           source_char_map={"kind":"affine_identity", "segment_start":0,
                                            "source_start":i,"length":j-i},
                           source_utf8_boundaries=[b-byte_offsets[i] for b in byte_offsets[i:j+1]],
                           raw_spans=[[i,j]], internally_contiguous=True,
                           index=len(segments),source_spans=[[i,j]],
                           source_map=[[p,p+1,"identity",0] for p in range(i,j)])
            segments.append(segment)
        else:
            gaps.append(region)
        i = j
    result = {"schema_version":VERSION, "profile":PROFILE,"source_frame":SOURCE_FRAME,
              "source_role":"blog_structural_prose_candidate_unknown_origin",
              "source_sha256":sha(data),"source_codepoints":len(raw),
              "dependencies":DEPENDENCIES,
              "raw_sha256":sha(data), "raw_bytes":len(data),"raw_codepoints":len(raw),
              "structural_status":"quarantined" if errors else "projected",
              "issues":errors, "nodes":nodes,"regions":regions,"segments":segments,"gaps":gaps,
              "counts":{"segments":len(segments),"projected_codepoints":sum(len(x["text"]) for x in segments),
                        "role_codepoints":dict(sorted(Counter(raw_labels).items()))},
              "prose_means":"structural_candidate_only", "author_attribution":"unverified",
              "rights_status":"unverified", "human_origin":"unknown", "assistance_status":"unknown",
              "model_admitted":False, "split_eligible":False,
              "joining_across_gaps_permitted":False, "linguistic_parser_run":False}
    result["barriers"] = [{"start":r["source_char_span"][0],"end":r["source_char_span"][1],
                           "reasons":[r["role"]]} for r in gaps]
    result["flags"] = list(errors)
    result["projection_sha256"] = sha(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode())
    validate_projection(data,result)
    return result


def validate_projection(data,result):
    raw = data.decode("utf-8","strict")
    required = set('schema_version profile source_frame source_role source_sha256 source_codepoints dependencies raw_sha256 raw_bytes raw_codepoints structural_status issues nodes regions segments gaps counts prose_means author_attribution rights_status human_origin assistance_status model_admitted split_eligible joining_across_gaps_permitted linguistic_parser_run barriers flags projection_sha256'.split())
    if not isinstance(result,dict) or set(result)!=required:
        raise ProjectionError("projection_schema_fields")
    fixed = {'schema_version':VERSION,'dependencies':DEPENDENCIES,'source_role':'blog_structural_prose_candidate_unknown_origin',
             'prose_means':'structural_candidate_only','assistance_status':'unknown','linguistic_parser_run':False}
    for key,value in fixed.items():
        if result[key]!=value or isinstance(value,bool) and result[key] is not value:
            raise ProjectionError("projection_fixed_field:"+key)
    if type(result['raw_bytes']) is not int or type(result['raw_codepoints']) is not int or type(result['source_codepoints']) is not int or result['raw_bytes']!=len(data) or result['raw_codepoints']!=len(raw):
        raise ProjectionError("raw_size_binding")
    if not isinstance(result['issues'],list) or any(not isinstance(x,str) or not x for x in result['issues']) or result['issues']!=sorted(set(result['issues'])) or result['flags']!=result['issues']:
        raise ProjectionError("issue_schema")
    if result['structural_status']!=('quarantined' if result['issues'] else 'projected'):
        raise ProjectionError("status_issue_consistency")
    for field in ('nodes','regions','segments','gaps','barriers'):
        if not isinstance(result[field],list):raise ProjectionError('array_schema:'+field)
    if result["raw_sha256"] != sha(data):
        raise ProjectionError("raw_binding_mismatch")
    boundaries = [0]
    for c in raw:
        boundaries.append(boundaries[-1]+len(c.encode()))
    end = 0
    normalized,_ = normalized_source(raw)
    normalized_starts=line_offsets(normalized)
    for index,node in enumerate(result['nodes']):
        if set(node) not in ({'id','type','ancestors','source_normalized_span','line_span'}, {'id','type','ancestors','source_normalized_span','line_span','inline_types'}) or type(node['id']) is not int or node['id']!=index:
            raise ProjectionError('node_schema')
        lo,hi=node['source_normalized_span'];line_lo,line_hi=node['line_span']
        if not all(type(x) is int for x in (lo,hi,line_lo,line_hi)) or not 0<=lo<=hi<=len(normalized) or not 0<=line_lo<=line_hi<len(normalized_starts) or [lo,hi]!=[normalized_starts[line_lo],normalized_starts[line_hi]]:
            raise ProjectionError('node_coordinate_binding')
        if not isinstance(node['type'],str) or not isinstance(node['ancestors'],list) or any(not isinstance(x,str) for x in node['ancestors']):raise ProjectionError('node_type_schema')
    for region in result["regions"]:
        if set(region)!={'source_char_span','source_byte_span','role','node_id'}:
            raise ProjectionError('region_schema')
        a,b = region["source_char_span"]
        if not isinstance(region['source_char_span'],list) or not isinstance(region['source_byte_span'],list) or len(region['source_byte_span'])!=2 or any(type(x) is not int for x in region['source_byte_span']):
            raise ProjectionError('region_coordinate_schema')
        if type(a) is not int or type(b) is not int or a != end or not a < b <= len(raw):
            raise ProjectionError("nonpartitioning_regions")
        if not isinstance(region['role'],str) or not region['role'] or region['node_id'] is not None and (type(region['node_id']) is not int or not 0<=region['node_id']<len(result['nodes'])):
            raise ProjectionError('region_role_or_node')
        if not result['issues'] and (region['role'].startswith('unresolved_') or region['role']=='quarantined_candidate_prose'):
            raise ProjectionError('region_status_consistency')
        if region["source_byte_span"] != [boundaries[a],boundaries[b]]:
            raise ProjectionError("region_byte_mapping")
        end = b
    if end != len(raw):
        raise ProjectionError("incomplete_partition")
    expected_regions = [r for r in result["regions"] if r["role"] in PROSE_ROLES and raw[slice(*r["source_char_span"])].strip()]
    if len(expected_regions) != len(result["segments"]):
        raise ProjectionError("segment_region_coverage")
    last = -1
    for index,segment in enumerate(result["segments"]):
        segment_fields={'source_char_span','source_byte_span','role','node_id','segment_id','text','text_sha256','source_char_map','source_utf8_boundaries','raw_spans','internally_contiguous','index','source_spans','source_map'}
        if set(segment)!=segment_fields:raise ProjectionError('segment_schema')
        a,b = segment["source_char_span"]
        if any(segment[k] != v for k,v in expected_regions[index].items()) or type(segment["index"]) is not int or segment["index"] != index:
            raise ProjectionError("segment_region_identity")
        if segment['raw_spans']!=[[a,b]] or segment['internally_contiguous'] is not True or segment['segment_id']!=sha((sha(data)+f':{a}:{b}:{segment["role"]}').encode()):
            raise ProjectionError('segment_span_or_identity')
        if a < last or segment["text"] != raw[a:b] or segment["role"] not in PROSE_ROLES:
            raise ProjectionError("segment_source_invariant")
        if segment["source_char_map"] != {"kind":"affine_identity","segment_start":0,"source_start":a,"length":b-a}:
            raise ProjectionError("segment_char_mapping")
        if segment["source_spans"] != [[a,b]] or segment["source_map"] != [[p,p+1,"identity",0] for p in range(a,b)]:
            raise ProjectionError("common_source_map_shape")
        if any(not isinstance(row,list) or len(row)!=4 or any(type(row[k]) is not int for k in (0,1,3)) for row in segment['source_map']):
            raise ProjectionError('source_map_coordinate_schema')
        for key in ('raw_spans','source_spans'):
            if not isinstance(segment[key],list) or any(not isinstance(row,list) or len(row)!=2 or any(type(x) is not int for x in row) for row in segment[key]):
                raise ProjectionError('source_span_coordinate_schema')
        expected = [0]
        for c in raw[a:b]:
            expected.append(expected[-1]+len(c.encode()))
        if not isinstance(segment['source_utf8_boundaries'],list) or any(type(x) is not int for x in segment['source_utf8_boundaries']) or segment["source_utf8_boundaries"] != expected or segment["text_sha256"] != sha(raw[a:b].encode()):
            raise ProjectionError("segment_utf8_mapping")
        last = b
    segment_spans = {tuple(r["source_char_span"]) for r in result["segments"]}
    expected_gaps = [r for r in result["regions"] if tuple(r["source_char_span"]) not in segment_spans]
    if result["gaps"] != expected_gaps:
        raise ProjectionError("gap_partition")
    if result["barriers"] != [{"start":r["source_char_span"][0],"end":r["source_char_span"][1],"reasons":[r["role"]]} for r in expected_gaps]:
        raise ProjectionError("barrier_partition")
    if result["issues"] and result["segments"]:
        raise ProjectionError("quarantined_record_emitted_prose")
    role_counts=Counter()
    for region in result['regions']:role_counts[region['role']]+=region['source_char_span'][1]-region['source_char_span'][0]
    if result['counts']!={'segments':len(result['segments']),'projected_codepoints':sum(len(s['text']) for s in result['segments']),'role_codepoints':dict(sorted(role_counts.items()))}:
        raise ProjectionError('aggregate_count_binding')
    if any(type(result['counts'][x]) is not int for x in ('segments','projected_codepoints')) or any(type(x) is not int for x in result['counts']['role_codepoints'].values()):
        raise ProjectionError('aggregate_count_schema')
    if result["profile"] != PROFILE or result["source_frame"] != SOURCE_FRAME or result["source_sha256"] != sha(data) or result["source_codepoints"] != len(raw):
        raise ProjectionError("source_profile_binding")
    if result["human_origin"] != "unknown" or result["rights_status"] != "unverified" or result["author_attribution"] != "unverified" or result["model_admitted"] is not False or result["split_eligible"] is not False or result["joining_across_gaps_permitted"] is not False:
        raise ProjectionError("unwarranted_admission_or_origin_claim")
    payload = {k:v for k,v in result.items() if k != "projection_sha256"}
    if result["projection_sha256"] != sha(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()):
        raise ProjectionError("projection_hash_binding")
    return True
