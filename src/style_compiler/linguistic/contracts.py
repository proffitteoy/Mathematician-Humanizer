"""Exact-source, sentence-local parser contracts. No empirical admission claim."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
import re
from style_compiler.surface import SourceObservation, SourceView, _digest, _sha256
from style_compiler.segmentation import SEGMENTER_VERSION, segment
from .schema import ALL_POS, ALL_RELATIONS

PROFILE_VERSION = 'zh-source-sentence-local/0.1.0'
MAX_SOURCE_CODEPOINTS = 200000
MAX_SENTENCE_TOKENS = 2048
MAX_SOURCE_SENTENCES = 512
MAX_TOTAL_TOKENS = 16384


def require(ok, message):
    if not ok:
        raise ValueError(message)

@dataclass(frozen=True)
class ParserProfile:
    parser_name: str
    parser_version: str
    model_id: str
    model_sha256: str
    scope: str = 'each_original_source_sentence_independently'
    normalization: str = 'none'
    segmenter_version: str = SEGMENTER_VERSION
    version: str = PROFILE_VERSION
    runtime: tuple[tuple[str,str], ...] = ()

    def validate(self):
        require(all(type(x) is str and x.strip() for x in (self.parser_name,self.parser_version,self.model_id)), 'missing_parser_identity')
        _sha256(self.model_sha256,'model_sha256')
        require(type(self.runtime) is tuple and all(type(kv) is tuple and len(kv)==2 and all(type(x) is str and x for x in kv) for kv in self.runtime), 'immutable_runtime_profile')
        require(len(dict(self.runtime))==len(self.runtime), 'duplicate_runtime_profile')
        require(self.scope == 'each_original_source_sentence_independently' and
                self.normalization == 'none' and self.segmenter_version == SEGMENTER_VERSION and
                self.version == PROFILE_VERSION, 'unsupported_parser_profile')

@dataclass(frozen=True)
class Token:
    local_id: int
    start: int
    end: int
    form: str = field(repr=False)
    upos: str
    head: int | None
    deprel: str | None
    feats: tuple[tuple[str,str], ...] = ()

    @property
    def base_relation(self):
        return self.deprel.split(':')[0] if self.deprel else None

@dataclass(frozen=True)
class SentenceParse:
    source_sentence_index: int
    start: int
    end: int
    tokens: tuple[Token, ...]
    status: str = 'ok'
    reason: str | None = None
    analysis_status: str = 'automatic_unvalidated'
    warnings: tuple[str, ...] = ('ambiguity_not_estimated',)

    def validate(self, text, expected):
        require(type(self.source_sentence_index) is int and self.source_sentence_index == expected.index and
                type(self.start) is int and self.start == expected.start and type(self.end) is int and self.end == expected.end,
                'source_sentence_identity_mismatch')
        require(self.status in {'ok','pos_only','failed'}, 'unknown_parse_status')
        require(self.analysis_status in {'automatic_unvalidated','synthetic_fixture','unresolved_annotation'}, 'analysis_status')
        require(type(self.warnings) is tuple and all(type(x) is str and x for x in self.warnings), 'immutable_parse_warnings')
        require(type(self.tokens) is tuple and len(self.tokens)<=MAX_SENTENCE_TOKENS, 'token_tuple_or_resource_limit')
        if self.status == 'failed':
            require(self.reason in {'parse_failed','alignment_failed','annotation_unresolved','dependency_unavailable','resource_limit'} and not self.tokens, 'failed_parse_requires_reason_and_no_tokens')
            return
        require(self.analysis_status!='unresolved_annotation','unresolved_analysis_must_fail')
        require(self.reason is None if self.status=='ok' else self.reason=='dependency_unavailable', 'parse_reason')
        require(bool(self.tokens), 'successful_parse_without_tokens')
        cursor=self.start
        for i,t in enumerate(self.tokens,1):
            require(type(t) is Token and type(t.local_id) is int and t.local_id==i, 'dense_token_ids')
            require(type(t.start) is int and type(t.end) is int and cursor<=t.start<t.end<=self.end,'token_offsets')
            require(type(t.form) is str and t.form==text[t.start:t.end] and not t.form.isspace(), 'token_exact_form_alignment')
            require(all(c.isspace() for c in text[cursor:t.start]), 'uncovered_nonwhitespace_source')
            require(t.upos in ALL_POS,'invalid_upos')
            require(type(t.feats) is tuple and all(type(kv) is tuple and len(kv)==2 and all(type(x)is str and x for x in kv) for kv in t.feats),'immutable_features')
            require(len(dict(t.feats))==len(t.feats),'duplicate_morphological_feature')
            if self.status=='pos_only':
                require(t.head is None and t.deprel is None,'pos_only_has_dependencies')
            else:
                require(type(t.head) is int and 0<=t.head<=len(self.tokens) and t.head!=i,'invalid_dependency_head')
                require(type(t.deprel) is str and re.fullmatch(r'[a-z]+(?::[a-z]+)?',t.deprel) is not None and t.base_relation in ALL_RELATIONS,'invalid_dependency_relation')
                require((t.head==0)==(t.deprel=='root'),'root_relation_mismatch')
            cursor=t.end
        require(all(c.isspace() for c in text[cursor:self.end]), 'uncovered_nonwhitespace_source')
        if self.status=='ok':
            require(sum(t.head==0 for t in self.tokens)==1,'single_root_required')
            for t in self.tokens:
                seen=set();node=t
                while node.head:
                    require(node.local_id not in seen,'cyclic_dependency_tree')
                    seen.add(node.local_id);node=self.tokens[node.head-1]

@dataclass(frozen=True)
class ParsedSource:
    source: SourceView
    profile: ParserProfile
    sentences: tuple[SentenceParse,...]

    def validate(self, observation):
        require(type(observation) is SourceObservation,'expected_source_observation')
        observation.__post_init__()
        require(self.source == observation.source,'exact_source_view_mismatch')
        self.source.__post_init__()
        require(type(self.profile) is ParserProfile,'parser_profile_type');self.profile.validate()
        require(len(observation.text)<=MAX_SOURCE_CODEPOINTS,'source_resource_limit')
        expected=segment(observation.text)[1]
        require(len(expected)<=MAX_SOURCE_SENTENCES,'sentence_count_resource_limit')
        require(type(self.sentences) is tuple and len(self.sentences)==len(expected),'every_source_sentence_required')
        require(sum(len(s.tokens) for s in self.sentences if type(s) is SentenceParse)<=MAX_TOTAL_TOKENS,'total_token_resource_limit')
        for actual,span in zip(self.sentences,expected):
            require(type(actual) is SentenceParse,'sentence_parse_type')
            actual.validate(observation.text,span)

    @property
    def fingerprint(self):
        # Hash complete annotation including forms without exposing the source.
        return _digest(asdict(self))
