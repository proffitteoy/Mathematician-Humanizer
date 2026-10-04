#!/usr/bin/env python3
"""Offline, non-mutating prose diagnostics. No authorship score or automatic edits."""
from collections import Counter
import hashlib
import json
import re
import unicodedata

# Conservative protection. Explicit literals cover semantic/format boundaries regex cannot infer.
PROTECTED = re.compile(r'(?ms)^ {0,3}(?P<fence>`{3,}|~{3,})[^\n]*\n.*?^ {0,3}(?P=fence)[^\n]*(?:\n|$)|(?P<ticks>`+)(?!`)(?:(?!(?P=ticks))[^\n])+?(?P=ticks)(?!`)|\$\$.*?\$\$|(?<!\$)\$[^$\n]+\$|\\\[.*?\\\]|\\\(.*?\\\)|^>[^\n]*(?:\n|$)|https?://[^\s<>\]\)]+')
NUMBER = re.compile(r'(?<![\w])(?:\d[\d,]*(?:\.\d+)?)(?:%|％)?|\d+(?:\.\d+)?(?:年|月|日|元|人|次|小时|分钟|公里|米|倍)')
LOGIC = re.compile(r'不超过|不少于|至少|至多|最多|仅限|仅|只有|除非|否则|如果|可能|推测|尚未|不得|不能|并非|不|未|no\b|not\b|only\b|unless\b|may\b', re.I)
SOFT = {
 'generic_opening': r'在(?:当今|这个|如今).{0,16}(?:时代|世界|背景)|In (?:today.s|the rapidly)',
 'automatic_closure': r'总而言之|综上所述|未来可期|Only time will tell|In conclusion',
 'inflated_significance': r'具有里程碑意义|彰显了|赋能|注入.{0,8}活力|game.chang|testament to',
 'performative_chat': r'希望这对你有帮助|问得好|让我们深入|I hope this helps|Great question',
 'balanced_template': r'不仅.{0,50}而且|不只是.{0,50}更是|虽然.{0,50}但是|not only.{0,60}but also',
 'citation_leak': r'contentReference\[|oaicite:|turn\d+(?:search|fetch)\d+|cite_start|\[INSERT [^\]]+\]',
}

def sha(raw): return hashlib.sha256(raw).hexdigest()
def protected(text): return [m.group() for m in PROTECTED.finditer(text)]
def prose(text): return PROTECTED.sub(lambda m: ' ' * len(m.group()), text)
def words(text): return re.findall(r'[\u3400-\u9fff]|\b[\w]+\b', text)
def summary(text):
    p = prose(text)
    lengths = [len(words(s)) for s in re.split(r'[。！？!?\n]+|\.(?:\s|$)', p) if words(s)]
    paragraphs = [len(words(s)) for s in re.split(r'\n\s*\n', p) if words(s)]
    return {'sentence_proxy_lengths': lengths, 'paragraph_proxy_lengths': paragraphs,
            'note': 'Surface counts mix Han characters and word tokens; NOT the fixed Chinese parser, no reference threshold or pass band.'}

def lint(original, candidate, locks=()):
    original.decode('utf-8'); candidate.decode('utf-8')
    a, b = original.decode('utf-8'), candidate.decode('utf-8')
    blockers, warnings = [], []
    if protected(a) != protected(b): blockers.append({'id':'protected_content_changed', 'reason':'Code, math, block quote or URL changed; inspect exact diff. Intentional edits require task-specific authorization and a fresh baseline.'})
    for literal in locks:
        if not isinstance(literal, str) or not literal: raise ValueError('Every lock must be a nonempty string')
        if a.count(literal) == 0: raise ValueError('Lock absent from original: ' + literal)
        if a.count(literal) != b.count(literal): blockers.append({'id':'explicit_lock_changed', 'literal':literal})
    for label, rx in [('quantity', NUMBER), ('logic_or_uncertainty', LOGIC)]:
        old, new = Counter(rx.findall(prose(a))), Counter(rx.findall(prose(b)))
        if old != new: warnings.append({'id':label+'_changed','removed':dict(old-new),'added':dict(new-old),'requires':'semantic review; lexical differences do not prove changed meaning, equality does not prove preservation'})
    old_math, new_math = Counter(c for c in a if c in '−≤≥≠∀∃∈∉⇒⇔'), Counter(c for c in b if c in '−≤≥≠∀∃∈∉⇒⇔')
    if old_math != new_math: warnings.append({'id':'mathematical_unicode_changed','removed':dict(old_math-new_math),'added':dict(new_math-old_math),'requires':'inspect mathematical meaning; never normalize minus, quantifiers or relations automatically'})
    for match in re.finditer(r'[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\u200b\u200c\u200d\u202a-\u202e\u2060\u2066-\u2069\ufeff]', b):
        c = match.group(); warnings.append({'id':'unicode_review','offset':match.start(),'codepoint':f'U+{ord(c):04X}','name':unicodedata.name(c,'CONTROL'),'requires':'inspect context; joiners in emoji/scripts, BOM and bidi text may be legitimate; never strip automatically'})
    body = prose(b)
    for kind, pattern in SOFT.items():
        for m in re.finditer(pattern, body, re.I):
            warnings.append({'id':kind,'offset':m.start(),'span':b[m.start():m.end()], 'requires':'contextual judgment; isolated match is not evidence of AI or an instruction to delete'})
    paragraphs = [s.strip() for s in re.split(r'\n\s*\n', body) if s.strip()]
    dupes = [s for s,n in Counter(paragraphs).items() if n > 1]
    if dupes: warnings.append({'id':'repeated_paragraph','spans':dupes,'requires':'check intentional refrain versus redundant restatement'})
    return {'schema':'prose-lint/1','original_sha256':sha(original),'candidate_sha256':sha(candidate),
            'status':'BLOCKED_PROTECTED_CHANGE' if blockers else 'REVIEW_REQUIRED' if warnings else 'NO_MECHANICAL_FINDINGS',
            'blockers':blockers,'warnings':warnings,'surface_summary':summary(b),
            'semantic_equivalence_proven':False,'quality_or_authorship_score':None,
            'limits':'No script can establish factual preservation, writer identity, reader knowledge, proof validity or prose quality. This tool never rewrites or normalizes text.'}
