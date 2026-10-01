"""Conservative offline source-markup projection. No linguistic parsing or I/O.

This is an allowlist projection, not a MediaWiki renderer or rights adjudicator.
Unknown/non-prose constructs become barriers. Never join across a removed line.
"""
from __future__ import annotations
import hashlib, html, json, re, unicodedata

PROFILE = 'historical-wikitext-conservative-prose/0.1.0'
FRAMES = {'discussion', 'news_prose', 'guide_prose'}
SOURCE_ROLE = {'discussion': 'discussion_prose_task_unknown',
               'news_prose': 'news_narrative_candidate',
               'guide_prose': 'guide_narrative_candidate'}
FORBIDDEN_NAMESPACES = {'file','image','category','template','help','special','user','user talk','talk','wikipedia','mediawiki','wikiproject','portal','文件','檔案','图像','圖像','分类','分類','模板','帮助','幫助','特殊','用户','用戶','使用者','討論','讨论'}
QUOTE_PAIRS = {'“':'”', '「':'」', '『':'』', '‘':'’'}
ENTITY = re.compile(r'&(?:#[xX][0-9a-fA-F]+|#[0-9]+|[A-Za-z][A-Za-z0-9]+);')
CONTACT = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|(?:\+?\d[\d() -]{7,}\d)')


def sha(text): return hashlib.sha256(text.encode('utf-8')).hexdigest()
def canonical(x): return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(',',':')).encode('utf-8')


def entity_value(raw):
    if not ENTITY.fullmatch(raw): raise ValueError('unknown_entity')
    value = html.unescape(raw)
    if not value or value == raw or '\ufffd' in value or any(unicodedata.category(c) in {'Cc','Cs'} and c not in '\t\r\n' for c in value):
        raise ValueError('invalid_entity')
    return value


def _construct_ranges(text):
    """Return non-prose source ranges. Range coordinates never target projections."""
    ranges = []
    # Comments, nested templates, tables and HTML regions are never expanded.
    i = 0
    while i < len(text):
        if text.startswith('<!--', i):
            end = text.find('-->', i+4)
            end = len(text) if end < 0 else end+3
            ranges.append((i,end,'comment')); i=end
        elif text.startswith('{{', i):
            depth=1; j=i+2
            while j<len(text) and depth:
                if text.startswith('{{',j):depth+=1;j+=2
                elif text.startswith('}}',j):depth-=1;j+=2
                else:j+=1
            ranges.append((i,j,'template' if depth==0 else 'unclosed_template'));i=j
        elif text.startswith('{|',i):
            end=text.find('|}',i+2);end=len(text) if end<0 else end+2
            ranges.append((i,end,'table'));i=end
        elif text[i]=='<' and re.match(r'</?[A-Za-z!]', text[i:]):
            m=re.match(r'<([A-Za-z][A-Za-z0-9]*)\b[^>]*>',text[i:])
            if m:
                tag=m.group(1).lower(); head=m.group(0);j=i+len(head)
                if head.endswith('/>') or tag in {'br','hr','img','input','meta','link','wbr'}:
                    ranges.append((i,j,'html_'+tag));i=j
                else:
                    depth=1; end=len(text); closed=False
                    token_re=re.compile(r'<(/?)'+re.escape(tag)+r'\b[^>]*>',re.I)
                    for token in token_re.finditer(text,j):
                        if token.group(1):depth-=1
                        elif not token.group(0).endswith('/>'):depth+=1
                        if depth==0:end=token.end();closed=True;break
                    ranges.append((i,end,'html_'+tag if closed else 'unclosed_html_'+tag));i=end
            else:
                end=text.find('>',i+1);end=len(text) if end<0 else end+1
                ranges.append((i,end,'unknown_html'));i=end
        elif text[i] in QUOTE_PAIRS:
            end=text.find(QUOTE_PAIRS[text[i]],i+1);end=len(text) if end<0 else end+1
            ranges.append((i,end,'quotation_rights_unresolved'));i=end
        elif text[i]=='"':
            end=text.find('"',i+1)
            if end<0:
                end=text.find('\n',i+1);end=len(text) if end<0 else end
            else:end+=1
            ranges.append((i,end,'quotation_rights_unresolved'));i=end
        else:i+=1
    return ranges


def _inline(text, offset):
    """Only identity, literal visible links, entity decoding, emphasis delimiters."""
    chars=[];mapping=[];i=0;styles=[]
    def emit(value,start,end,op):
        for j,char in enumerate(value):
            chars.append(char);mapping.append([offset+start,offset+end,op,j])
    while i<len(text):
        if text.startswith('[[',i):
            end=text.find(']]',i+2)
            if end<0:raise ValueError('unclosed_internal_link')
            body=text[i+2:end]
            if any(x in body for x in ('[[',']','[','{','}','<','>','\n','\r')):raise ValueError('nested_or_unknown_link')
            parts=body.split('|')
            if len(parts)>2 or not parts[0].strip():raise ValueError('invalid_link')
            target=parts[0].strip().lstrip(':')
            if ':' in target:raise ValueError('namespaced_or_interwiki_link')
            label=parts[-1]
            if not label or label!=label.strip():raise ValueError('empty_or_implicit_link_label')
            # No pipe trick, language variants, fragments or escaped-label rewriting.
            if len(parts)==1 and '#' in label:raise ValueError('implicit_fragment_link')
            labelstart=i+2+(len(parts[0])+1 if len(parts)==2 else 0)
            sub,submap=_inline(label,offset+labelstart)
            chars.extend(sub);mapping.extend(submap);i=end+2
        elif text[i]=='[':
            end=text.find(']',i+1)
            if end<0:raise ValueError('unclosed_external_link')
            body=text[i+1:end]
            match=re.fullmatch(r'(https?://[^\s\[\]{}<>]+)[ \t]+([^\[\]{}<>\r\n]+)',body)
            if not match:raise ValueError('unsupported_external_link')
            label=match.group(2)
            sub,submap=_inline(label,offset+i+1+match.start(2))
            chars.extend(sub);mapping.extend(submap);i=end+1
        elif text[i]=='&':
            match=ENTITY.match(text,i)
            if match:
                value=entity_value(match.group());emit(value,i,match.end(),'entity');i=match.end()
            elif re.match(r'&(?:#|[A-Za-z])',text[i:]):raise ValueError('unknown_entity')
            else:emit('&',i,i+1,'identity');i+=1
        elif text.startswith("''",i):
            j=i
            while j<len(text) and text[j]=="'":j+=1
            n=j-i
            if n not in {2,3,5}:raise ValueError('unsupported_emphasis')
            if styles and styles[-1]==n:styles.pop()
            elif styles:raise ValueError('nested_emphasis')
            else:styles.append(n)
            i=j
        elif text.startswith(('http://','https://','ftp://','mailto:'),i):raise ValueError('bare_url')
        elif text[i] in '{}[]<>|' or text.startswith('~~~~',i):raise ValueError('unknown_markup')
        elif unicodedata.category(text[i]) in {'Cc','Cs'} and text[i] not in '\t\r\n':raise ValueError('control_codepoint')
        elif text[i] in '\u200b\u200c\u200d\u2060\ufeff':raise ValueError('invisible_format_codepoint')
        else:emit(text[i],i,i+1,'identity');i+=1
    if styles:raise ValueError('unclosed_emphasis')
    return ''.join(chars),mapping


def project(text, source_frame, metadata=None):
    """Candidate/calibration projection; original source maximum20000codepoints."""
    return _project(text,source_frame,metadata,20000)


def exclusion_project(text, source_frame="discussion", metadata=None):
    """Same transformation for excluded historical views, never candidate admission.

    Bound200000 comes from metadata-only old maximum192011. Large views are
    never windowed: unclosed constructs remain whole-range barriers.
    """
    return _project(text,source_frame,metadata,200000)


def _project(text, source_frame, metadata, source_cap):
    if not isinstance(text,str) or source_frame not in FRAMES:raise ValueError('invalid_projection_input')
    if len(text)>source_cap:raise ValueError('source_codepoint_cap')
    metadata={} if metadata is None else metadata
    if not isinstance(metadata,dict):raise ValueError('invalid_metadata')
    source_hash=sha(text)
    template_names={str(x).strip().lower() for x in metadata.get('template_names',[])}
    template_names.update(x.strip().lower() for x in re.findall(r'\{\{\s*([^{}|\r\n]+)',text))
    # These are source labels, not original-author/human-production judgments.
    record_block=[]
    if source_frame=='news_prose' and ('headline item/header' in template_names or re.search(r'\{\{\s*headline item/header\s*(?:\||\})',text,re.I)):
        record_block.append('headline_roundup_source')
    if 'voa' in template_names or re.search(r'\{\{\s*voa\s*(?:\||\})',text,re.I):record_block.append('third_party_voa_source')
    if any(re.search(r'翻譯|翻译|転載|转载|translation|translated|reprint',x,re.I) for x in template_names):record_block.append('translation_or_reprint_rights_unresolved')
    if metadata.get('rights_unresolved') is True:record_block.append('metadata_rights_unresolved')
    # Entity-emitted quote/markup scopes can cross physical lines. Quarantine
    # the whole record instead of leaking unmarked interior lines as prose.
    for entity in ENTITY.finditer(text):
        try:value=entity_value(entity.group())
        except ValueError:continue
        if any(c in value for c in '\"\'“”「」『』‘’'):record_block.append('entity_quotation_scope_unresolved')
        if any(c in value for c in '{}[]<>|'):record_block.append('entity_markup_scope_unresolved')
    quote_stack=[]
    closers=set(QUOTE_PAIRS.values())
    for char in text:
        if char=='"':
            if quote_stack and quote_stack[-1]=='"':quote_stack.pop()
            else:
                if quote_stack:record_block.append('nested_quotation_scope_unresolved')
                quote_stack.append('"')
        elif char in QUOTE_PAIRS:
            if quote_stack:record_block.append('nested_quotation_scope_unresolved')
            quote_stack.append(QUOTE_PAIRS[char])
        elif char in closers:
            if not quote_stack or quote_stack[-1]!=char:record_block.append('mismatched_quotation_scope_unresolved')
            else:quote_stack.pop()
    if quote_stack:record_block.append('unclosed_quotation_scope_unresolved')
    record_block=sorted(set(record_block))
    result={'profile':PROFILE,'source_sha256':source_hash,'source_codepoints':len(text),'source_frame':source_frame,'segments':[],'barriers':[],'flags':{'source_role':SOURCE_ROLE[source_frame],'authorship':'unknown','human_origin':'unknown','rights':'source_license_inherited_item_exceptions_not_certified','record_quarantine_reasons':record_block}}
    if record_block:
        if text:result['barriers']=[{'start':0,'end':len(text),'reasons':sorted(record_block)}]
        result['projection_sha256']=hashlib.sha256(canonical(result)).hexdigest();return result
    masks=_construct_ranges(text)
    pending=None
    def flush():
        nonlocal pending
        if pending is not None:
            if any(unicodedata.category(c)[0] in 'LN' for c in pending['text']):
                pending['index']=len(result['segments']);result['segments'].append(pending)
            pending=None
    offset=0
    for line in text.splitlines(keepends=True):
        start,end=offset,offset+len(line);offset=end
        reasons={reason for a,b,reason in masks if a<end and b>start}
        stripped=line.lstrip(' \t')
        if line.startswith((' ','\t')) and stripped.strip():reasons.add('indented_code_or_list_continuation')
        if re.match(r'^(?:[*#;:>]|={1,6}(?:[^=]|$)|[-+•●]\s|\d+[.)、]\s)',stripped):reasons.add('heading_list_or_quote')
        if CONTACT.search(line):reasons.add('personal_contact_or_structured_number')
        if re.search(r'--+\s*(?:\[|\{|[A-Za-z\u3400-\u9fff])|~{3,}',line):reasons.add('signature_or_horizontal_rule')
        if re.search(r'(?:機器人|机器人|bot)\s*(?:通知|留言|message|notice)',line,re.I):reasons.add('automated_notice_marker')
        if re.search(r'\b(?:ISBN|ISSN)\b|(?:地址|電話|电话|電郵|邮箱)\s*[:：]',line):reasons.add('structured_listing_field')
        if not reasons:
            try:
                visible,mapping=_inline(line,start)
                # Decode only visible text, then conservatively check role-risk
                # markers. Never expand or execute entity-decoded wiki/HTML.
                if any(c in visible for c in '“”「」『』‘’\"'):reasons.add('visible_quotation_rights_unresolved')
                if CONTACT.search(visible):reasons.add('visible_personal_contact_or_structured_number')
                if re.match(r'^(?:[*#;:>]|={1,6}(?:[^=]|$)|[-+•●]\s|\d+[.)、]\s)',visible.lstrip(' \t')):reasons.add('visible_heading_list_or_quote')
                if re.search(r'(?:地址|電話|电话|電郵|邮箱)\s*[:：]|~{3,}',visible):reasons.add('visible_structured_field_or_signature')
                if any(row[2]=='entity' and c in '{}[]<>|' for c,row in zip(visible,mapping)):reasons.add('entity_emitted_markup_unsupported')
            except ValueError as exc:reasons.add(str(exc))
        if reasons:
            flush();result['barriers'].append({'start':start,'end':end,'reasons':sorted(reasons)})
        else:
            if pending is None:pending={'text':'','source_spans':[[start,end]],'source_map':[]}
            else:pending['source_spans'][-1][1]=end
            pending['text']+=visible;pending['source_map'].extend(mapping)
    flush()
    result['projection_sha256']=hashlib.sha256(canonical(result)).hexdigest()
    return result
