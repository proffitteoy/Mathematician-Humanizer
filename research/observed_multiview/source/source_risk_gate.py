"""Stricter-only role quarantine; never transforms a retained source/projection.

Fences can be literal in MediaWiki but are unresolved code-role evidence. Tag
names over32 ASCII characters can amplify diagnostics; quarantine before mapping.
"""
import re
from project_wikitext import ENTITY,entity_value
PROFILE='scale10-source-role-quarantine/0.1.0'
FENCE=re.compile(r'^[ \t]*(?:`{3,}|~{3,})')
LONG_TAG=re.compile(r'</?[A-Za-z][A-Za-z0-9]{32,}\b')


def source_risks(text):
    if not isinstance(text,str):raise ValueError('source_must_be_string')
    risks=[]
    def decode(match):
        try:return entity_value(match.group())
        except ValueError:return match.group()
    # Detection only: one safe entity-decoding pass, all splitlines boundaries.
    # Never execute, transform, or return this view as admitted prose.
    decoded=ENTITY.sub(decode,text)
    if any(FENCE.search(line) for view in (text,decoded) for line in view.splitlines()):risks.append('markdown_fenced_code_role_unresolved')
    if LONG_TAG.search(text):risks.append('oversized_HTML_tag_role_unresolved')
    return risks


def gated_metadata(text,metadata):
    if not isinstance(metadata,dict):raise ValueError('metadata_must_be_mapping')
    risks=source_risks(text)
    return (dict(metadata,rights_unresolved=True) if risks else dict(metadata)),risks
