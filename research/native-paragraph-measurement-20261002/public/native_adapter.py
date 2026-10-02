"""Offline native-source measurement. Real-data return values are PRIVATE.

No fetching, fitting, rewrite, author-attribution or rhetorical parsing. This
profile is deliberately not compatible with the frozen legacy feature cache.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
import statistics
import unicodedata
from collections import Counter
from lxml import html

VERSION = 'native-source-paragraphs/1.0.0'
SENTENCE_VERSION = 'native-boundary-punctuation/1.0.0'
HEADINGS = {f'h{i}' for i in range(1, 7)}
BOUNDARIES = {'p', 'li', 'figcaption', 'blockquote', 'pre', 'table', 'dt', 'dd'} | HEADINGS
CONTAINERS = {'figure', 'ul', 'ol'}
TYPED = BOUNDARIES | CONTAINERS
INLINE = {'q', 'cite', 'a', 'em', 'strong', 'br', 'wbr'}
TERMINALS = frozenset('。！？!?．')
CLOSERS = frozenset('”’」』）》】〕〗〙〛"\'')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def content_chars(text):
    """Same Unicode L/N codepoint definition as style_compiler.segmentation."""
    return sum(unicodedata.category(c)[0] in {'L', 'N'} for c in text)


def missing(code, detail):
    return {'status': 'unavailable', 'value': None, 'missing_reason': code, 'detail': detail}


def role(tag, ancestors):
    tags = set(ancestors) | {tag}
    if 'figcaption' in tags:
        return 'caption'
    if tags & {'pre', 'table'}:
        return 'code_or_table'
    if 'blockquote' in tags:
        return 'marked_quotation'
    if 'li' in tags or tags & {'dt', 'dd'}:
        return 'list_item'
    if tag in HEADINGS:
        return 'heading'
    if 'figure' in tags:
        return 'figure_text_unclassified'
    if tag == 'p':
        return 'paragraph_mixed_attribution'
    return 'inline_gap'


def check_partition(text, units):
    cursor = 0
    for unit in units:
        if unit['start'] != cursor or unit['end'] <= cursor or unit['end'] > len(text):
            raise ValueError('Body partition is incomplete, overlapping, duplicated or out of order')
        if unit['text'] != text[unit['start']:unit['end']]:
            raise ValueError('Body partition text mismatch')
        cursor = unit['end']
    if cursor != len(text) or ''.join(u['text'] for u in units) != text:
        raise ValueError('Body partition must reconstruct exact admitted text')


def _finish(text, nodes, units, annotations, captions, source_format):
    check_partition(text, units)
    paragraphs = []
    for node in nodes:
        if node['boundary_kind'] != 'paragraph':
            continue
        start, end = node['start'], node['end']
        contained = [u for u in units if start <= u['start'] and u['end'] <= end]
        complete = sum(u['end'] - u['start'] for u in contained) == end - start
        all_owned = all(u['owner_id'] == node['node_id'] for u in contained)
        chars = content_chars(text[start:end])
        reason = ('excluded_source_role' if node['role'] != 'paragraph_mixed_attribution' else
                  'nested_structural_content' if not complete or not all_owned else
                  'no_content_characters' if not chars else None)
        paragraphs.append({'node_id': node['node_id'], 'start': start, 'end': end,
                           'content_chars': chars, 'eligible': reason is None,
                           'exclusion_reason': reason, 'role': node['role']})
    out = {'schema_version': VERSION, 'source_format': source_format,
           'body_sha256': sha256(text.encode()), 'body_codepoints': len(text),
           'offset_unit': 'unicode_codepoint', 'normalization': 'none',
           'nodes': nodes, 'units': units, 'paragraphs': paragraphs,
           'inline_annotations': annotations, 'out_of_body_entity_text': captions,
           'unsupported': {
               'semantic_paragraphs': missing('semantic_paragraph_annotation_absent', 'Only explicit source paragraph boundaries are observed'),
               'quotation_attribution': missing('speaker_and_borrowed_span_annotation_absent', 'Markup is not speaker identity or exhaustive quotation annotation'),
               'clean_author_prose': missing('authorship_span_annotation_absent', 'Eligible paragraphs may contain quoted or borrowed language'),
               'rhetorical_hierarchy': missing('discourse_annotation_absent', 'Typed source containment is not rhetorical structure'),
               'argument_structure': missing('argument_annotation_absent', 'No premises, conclusions or argument edges inferred'),
           }, 'fit_authorized': False, 'experiment_id': None, 'split': None}
    out['view_sha256'] = sha256(json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode())
    return out


def adapt_html(body_html, admitted_text):
    """Traverse saved HTML text/tails once. Never fuzzy-find repeated strings."""
    root = html.fromstring(body_html)
    if root.text_content() != admitted_text:
        raise ValueError('Saved HTML text differs from admitted body')
    nodes, units, annotations, chunks = [], [], [], []
    cursor = 0

    def append(value, owner, source_id, slot, ancestry):
        nonlocal cursor
        if not value:
            return
        tag = nodes[owner]['source_type'] if owner is not None else ''
        effective = role(tag, [nodes[i]['source_type'] for i in ancestry])
        if effective == 'inline_gap' and not value.strip():
            effective = 'source_separator'
        units.append({'start': cursor, 'end': cursor + len(value), 'text': value,
                      'role': effective, 'owner_id': owner,
                      'source_node_id': source_id, 'source_slot': slot})
        chunks.append(value)
        cursor += len(value)

    def walk(element, parent, ancestors, owner):
        nonlocal cursor
        if not isinstance(element.tag, str):
            return  # comments/PIs have no text_content; their tail is handled by parent
        tag = element.tag.lower()
        idx = len(nodes)
        typed_ancestors = [i for i in ancestors if nodes[i]['source_type'] in TYPED]
        tags = [nodes[i]['source_type'] for i in ancestors]
        current_owner = idx if tag in BOUNDARIES else owner
        r = role(tag, tags)
        node = {'node_id': idx, 'source_type': tag, 'source_parent_id': parent,
                'typed_parent_id': typed_ancestors[-1] if typed_ancestors else None,
                'start': cursor, 'end': None, 'role': r,
                'boundary_kind': 'paragraph' if tag == 'p' else 'heading' if tag in HEADINGS else
                                 'list_item' if tag in {'li', 'dt', 'dd'} else
                                 'caption' if tag == 'figcaption' else 'quotation_container' if tag == 'blockquote' else
                                 'code_or_table' if tag in {'pre', 'table'} else None,
                'heading_level': int(tag[1]) if tag in HEADINGS else None,
                'list_nesting_level': sum(t in {'ul', 'ol'} for t in tags) if tag == 'li' else None,
                'quoted_container_ids': [i for i in ancestors if nodes[i]['source_type'] == 'blockquote'],
                'hierarchy_meaning': 'explicit_source_containment_only'}
        nodes.append(node)
        append(element.text, current_owner, idx, 'text', ancestors + [idx])
        for child in element:
            walk(child, idx, ancestors + [idx], current_owner)
            append(child.tail, current_owner, idx, 'child_tail', ancestors + [idx])
        node['end'] = cursor
        if tag in INLINE:
            annotations.append({'node_id': idx, 'kind': tag, 'start': node['start'], 'end': cursor,
                                'meaning': 'source_markup_only', 'body_text_insertion': False})

    walk(root, None, [], None)
    if ''.join(chunks) != admitted_text:
        raise ValueError('HTML text traversal mismatch')
    return _finish(admitted_text, nodes, units, annotations, [], 'html')


def _utf16_to_codepoints(text, offset):
    if type(offset) is not int or offset < 0:
        raise ValueError('Invalid UTF-16 offset')
    consumed = 0
    for index, char in enumerate(text):
        if consumed == offset:
            return index
        consumed += 2 if ord(char) > 0xffff else 1
        if consumed > offset:
            raise ValueError('UTF-16 range splits a surrogate pair')
    if consumed == offset:
        return len(text)
    raise ValueError('UTF-16 offset exceeds block')


def adapt_draftjs(structure, admitted_text):
    blocks = structure['blocks']
    if '\n\n'.join(b.get('text', '') for b in blocks if b.get('text', '')) != admitted_text:
        raise ValueError('Saved DraftJS text differs from admitted body')
    if len({b['key'] for b in blocks}) != len(blocks):
        raise ValueError('Duplicate DraftJS block keys')
    nodes, units, annotations, captions = [], [], [], []
    cursor, nonempty = 0, 0
    heading_levels = {f'header-{name}': i for i, name in enumerate(('one','two','three','four','five','six'), 1)}
    for i, block in enumerate(blocks):
        value, kind = block.get('text', ''), block['type']
        depth = block.get('depth', 0)
        if type(depth) is not int or depth < 0:
            raise ValueError('Invalid DraftJS depth')
        if value and nonempty:
            units.append({'start': cursor, 'end': cursor+2, 'text': '\n\n', 'role': 'source_separator',
                          'owner_id': None, 'source_node_id': None, 'source_slot': 'serialization_separator'})
            cursor += 2
        r = ('paragraph_mixed_attribution' if kind == 'unstyled' else
             'heading' if kind in heading_levels else 'marked_quotation' if kind == 'blockquote' else
             'list_item' if kind in {'ordered-list-item','unordered-list-item'} else
             'atomic_entity' if kind == 'atomic' else 'code_or_table' if kind == 'code-block' else 'unknown_block')
        node = {'node_id': i, 'source_type': kind, 'source_key': block['key'],
                'source_pointer': f'/blocks/{i}', 'source_parent_id': None, 'typed_parent_id': None,
                'start': cursor, 'end': cursor+len(value), 'role': r,
                'boundary_kind': 'paragraph' if kind == 'unstyled' else r,
                'heading_level': heading_levels.get(kind), 'declared_depth': depth,
                'list_nesting_level': depth if r == 'list_item' else None,
                'quoted_container_ids': [], 'hierarchy_meaning': 'flat_block_order_and_declared_depth_only',
                'parent_relation': missing('draftjs_parent_not_serialized', 'No parent identity inferred from flat block sequence')}
        nodes.append(node)
        for category in ('entityRanges', 'inlineStyleRanges'):
            for j, ran in enumerate(block.get(category, [])):
                a = _utf16_to_codepoints(value, ran['offset'])
                b = _utf16_to_codepoints(value, ran['offset'] + ran['length'])
                if b < a:
                    raise ValueError('Inverted DraftJS range')
                if category == 'entityRanges' and str(ran['key']) not in structure.get('entityMap', {}):
                    raise ValueError('DraftJS entity reference missing')
                annotations.append({'node_id': i, 'kind': category, 'source_pointer': f'/blocks/{i}/{category}/{j}',
                                    'start': cursor+a, 'end': cursor+b, 'source_range': ran,
                                    'source_offset_unit': 'utf16_code_unit', 'meaning': 'source_markup_only'})
        if value:
            units.append({'start': cursor, 'end': cursor+len(value), 'text': value, 'role': r,
                          'owner_id': i, 'source_node_id': i, 'source_slot': 'text'})
            cursor += len(value)
            nonempty += 1
    for key, entity in sorted(structure.get('entityMap', {}).items()):
        data = entity.get('data', {})
        caption = data.get('captionRichText')
        caption_matches_desc = False
        references = sorted({a['node_id'] for a in annotations if a['kind']=='entityRanges' and str(a['source_range']['key'])==str(key)})
        if isinstance(caption, dict) and isinstance(caption.get('blocks'), list):
            caption_matches_desc = '\n\n'.join(b.get('text','') for b in caption['blocks'] if b.get('text','')) == data.get('desc')
            for j, b in enumerate(caption['blocks']):
                if b.get('text', ''):
                    captions.append({'entity_key': key, 'source_pointer': f'/entityMap/{key}/data/captionRichText/blocks/{j}/text',
                                     'text': b['text'], 'role': 'caption', 'body_start': None, 'body_end': None,
                                     'scope': 'out_of_admitted_body', 'missing_reason': 'caption_not_in_admitted_body',
                                     'referencing_node_ids': references, 'duplicate_description_not_appended': caption_matches_desc})
        if isinstance(data.get('desc'), str) and data['desc'] and not caption_matches_desc:
            captions.append({'entity_key': key, 'source_pointer': f'/entityMap/{key}/data/desc',
                             'text': data['desc'], 'role': 'entity_description_unclassified',
                             'body_start': None, 'body_end': None, 'scope': 'out_of_admitted_body',
                             'missing_reason': 'description_not_in_admitted_body', 'referencing_node_ids': references})
    return _finish(admitted_text, nodes, units, annotations, captions, 'draftjs')


def _terminal(text, pos, end):
    """Whitespace-invariant punctuation rule; not linguistic sentence parsing.

    Same terminal/closer inventory as legacy; ASCII dot is terminal except between
    logical digits. Unlike legacy, neither whitespace nor initial-letter regexes
    decide boundaries. Abbreviations and initials can therefore over-segment.
    """
    if text[pos] in TERMINALS:
        return True
    return text[pos] == '.' and not (pos and pos+1 < end and text[pos-1].isdigit() and text[pos+1].isdigit())


def punctuation_spans(text, start, end, paragraph_id):
    # Whitespace only controls display inside a source paragraph in this profile.
    # This decision stream is not a rewritten source body; offsets remain exact.
    positions = [i for i in range(start, end) if not text[i].isspace()]
    logical = ''.join(text[i] for i in positions)
    out, cursor, pos, limit = [], 0, 0, len(logical)
    def emit(a, b):
        while a < b and logical[a].isspace(): a += 1
        while b > a and logical[b-1].isspace(): b -= 1
        n = content_chars(logical[a:b])
        if n:
            out.append({'start': positions[a], 'end': positions[b-1]+1,
                        'content_chars': n, 'paragraph_id': paragraph_id})
    while pos < limit:
        if _terminal(logical, pos, limit):
            boundary = pos+1
            while boundary < limit and (logical[boundary] in TERMINALS or logical[boundary] in CLOSERS or logical[boundary] == '.'):
                boundary += 1
            emit(cursor, boundary)
            cursor = pos = boundary
        else:
            pos += 1
    emit(cursor, limit)
    return out


def quantile(values, q):
    ordered = sorted(values)
    h = (len(ordered)-1)*q
    return ordered[math.floor(h)] + (ordered[math.ceil(h)]-ordered[math.floor(h)])*(h-math.floor(h))


def ranks(values):
    groups = {}
    for i, v in enumerate(values): groups.setdefault(v, []).append(i)
    result, offset = [0.0]*len(values), 1
    for v in sorted(groups):
        indexes = groups[v]
        for i in indexes: result[i] = offset + (len(indexes)-1)/2
        offset += len(indexes)
    return result


def measure(text, view):
    if view['schema_version'] != VERSION or sha256(text.encode()) != view['body_sha256']:
        raise ValueError('Measurement requires exact source/profile identity')
    fingerprint = {k:v for k,v in view.items() if k != 'view_sha256'}
    if sha256(json.dumps(fingerprint, ensure_ascii=False, sort_keys=True, separators=(',',':')).encode()) != view.get('view_sha256'):
        raise ValueError('Native view changed after adaptation')
    check_partition(text, view['units'])
    ps = [p for p in view['paragraphs'] if p['eligible']]
    sentences, pairs = [], []
    for p in ps:
        ss = punctuation_spans(text, p['start'], p['end'], p['node_id'])
        pairs.extend(zip(ss, ss[1:]))  # never cross a paragraph, excluded role, or gap
        sentences.extend(ss)
    lengths = [s['content_chars'] for s in sentences]
    p, n, chars = len(ps), len(sentences), sum(x['content_chars'] for x in ps)
    med = statistics.median(lengths) if n else None
    mad = statistics.median(abs(x-med) for x in lengths) if n else None
    diff = statistics.mean(abs(a['content_chars']-b['content_chars']) for a,b in pairs) if pairs else None
    rho_num = rho_den = rho = None
    if len(pairs) >= 3:
        x, y = ranks([a['content_chars'] for a,b in pairs]), ranks([b['content_chars'] for a,b in pairs])
        xm, ym = statistics.mean(x), statistics.mean(y)
        rho_num = sum((a-xm)*(b-ym) for a,b in zip(x,y))
        rho_den = math.sqrt(sum((a-xm)**2 for a in x)*sum((b-ym)**2 for b in y))
        rho = rho_num/rho_den if rho_den else None
    singles = sum(len(punctuation_spans(text, x['start'], x['end'], x['node_id'])) == 1 for x in ps)
    features = {}
    def add(fid, value, unit, support, reason, numerator=None, denominator=None):
        features['NP'+fid[1:]] = {'feature_id': 'NP'+fid[1:], 'formula_lineage': fid,
            'profile': VERSION, 'value': value, 'unit': unit,
            'status': 'unavailable' if value is None else 'zero_observed' if value == 0 else 'observed',
            'missing_reason': reason if value is None else None, 'support_count': support,
            'support_unit': 'selected_native_paragraphs' if fid in {'F002','F003'} else 'within_paragraph_pairs' if fid in {'F024','F025'} else 'selected_punctuation_units',
            'raw_numerator': numerator, 'denominator': denominator,
            'descriptive_analysis_available': value is not None,
            'comparison_eligibility': {'status': 'not_assessed', 'reason': 'Population contrasts require an explicit matched design; this does not exclude operational descriptive analysis'}}
    add('F002', 1000*p/chars if chars else None, 'native_paragraphs_per_1000_selected_LN', p, 'no_eligible_paragraph_content', p, chars)
    add('F003', singles/p if p else None, 'single_punctuation_unit_paragraph_share', p, 'no_eligible_paragraphs', singles, p)
    add('F013', med, 'content_chars', n, 'no_eligible_punctuation_units')
    add('F014', quantile(lengths,.75)-quantile(lengths,.25) if n else None, 'content_chars', n, 'no_eligible_punctuation_units')
    add('F015', quantile(lengths,.9) if n else None, 'content_chars', n, 'no_eligible_punctuation_units')
    add('F016', mad/med if n else None, 'ratio', n, 'no_eligible_punctuation_units', mad, med)
    add('F024', diff/med if pairs else None, 'within_paragraph_adjacent_difference_over_median', len(pairs), 'no_within_paragraph_pairs', diff, med)
    add('F025', rho, 'within_paragraph_pair_spearman_rho', len(pairs), 'fewer_than_three_pairs' if len(pairs)<3 else 'constant_pair_rank_vector', rho_num, rho_den)
    return {'schema_version': 'native-source-measurement/1.0.0', 'profile': VERSION,
            'sentence_profile': SENTENCE_VERSION, 'unicode_version': unicodedata.unidata_version,
            'body_sha256': view['body_sha256'], 'counts': {'body_codepoints': len(text), 'body_LN': content_chars(text),
                'eligible_paragraphs': p, 'selected_LN': chars, 'excluded_LN': content_chars(text)-chars,
                'punctuation_units': n, 'within_paragraph_pairs': len(pairs),
                'out_of_body_entity_texts': len(view['out_of_body_entity_text']),
                'out_of_body_caption_blocks': sum(x['role']=='caption' for x in view['out_of_body_entity_text']),
                'out_of_body_unclassified_descriptions': sum(x['role']=='entity_description_unclassified' for x in view['out_of_body_entity_text'])},
            'features': features, 'paragraphs': ps, 'punctuation_units': sentences,
            'unsupported': view['unsupported'], 'fit_authorized': False,
            'reference_statistics': None, 'authorial_attribution': 'unresolved_mixed_published_text'}
