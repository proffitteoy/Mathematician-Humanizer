"""Source-justified candidate sensors, not independent or validated constructs."""
from dataclasses import asdict, dataclass, replace

SCHEMA_VERSION = 'zh-linguistic-sensors/0.1.0'
UD = 'https://universaldependencies.org/'
SOURCES = {
 'ud_zh': UD + 'zh/index.html',
 'unicode_scripts':'https://www.unicode.org/Public/15.0.0/ucd/Scripts.txt',
 'ud_gsd': UD + 'treebanks/zh_gsd/index.html',
 'ud_pos': UD + 'u/pos/',
 'ud_dep': UD + 'u/dep/',
 'conllu': UD + 'format.html',
 'zh_pron': UD + 'zh/pos/PRON.html',
 'zh_part': UD + 'zh/pos/PART.html',
 'zh_aux': UD + 'zh/pos/AUX.html',
 'catalog': 'https://github.com/proffitteoy/style-compiler/blob/62b31458185e20d4ba88a667adbc6b7c0f14b14f/docs/design/feature-schema-100.zh.json',
 'projection': 'https://github.com/proffitteoy/style-compiler/blob/62b31458185e20d4ba88a667adbc6b7c0f14b14f/research/surface/README.zh.md',
 'referential': 'https://github.com/proffitteoy/style-compiler/blob/62b31458185e20d4ba88a667adbc6b7c0f14b14f/docs/design/referential-continuity-contract-v0.1.zh.md',
}
# These 13 lexical/functional POS classes are listed in Chinese GSD. PUNCT,
# SYM and X remain in the parse/quality audit, not counted as style channels.
POS = ('ADJ','ADP','ADV','AUX','CCONJ','DET','NOUN','NUM','PART','PRON','PROPN','SCONJ','VERB')
# Main-class composition, chosen by grammatical role. Rarer discourse repairs,
# vocatives, generic dep and punctuation are retained in graph/audit but not
# multiplied into extra style channels. Subtypes remain on graph edges.
RELATIONS = ('acl','advcl','advmod','amod','appos','aux','case','cc','ccomp','clf',
             'compound','conj','cop','csubj','det','discourse','dislocated','flat',
             'iobj','mark','nmod','nsubj','nummod','obj','obl','parataxis','xcomp')
ALL_POS = frozenset(POS + ('INTJ','PUNCT','SYM','X'))
ALL_RELATIONS = frozenset(RELATIONS + ('dep','expl','fixed','goeswith','list','orphan','punct','reparandum','root','vocative'))

@dataclass(frozen=True)
class Sensor:
    id: str
    family: str
    label: str
    formula: str
    opportunity: str
    dependency: str
    sources: tuple[str, ...]
    catalog_relation: str | None = None
    interpretation_limit: str = 'Parser/segmentation-dependent descriptive candidate; not validated style or author evidence.'


def sensor(name, family, label, formula, opportunity, dependency='pos', sources=('catalog',), catalog=None, limit=None):
    return Sensor('zh:' + name, family, label, formula, opportunity, dependency,
                  tuple(SOURCES[s] for s in sources), catalog,
                  limit or Sensor.__dataclass_fields__['interpretation_limit'].default)

SENSORS = tuple(sensor('upos.' + p, 'upos_composition', p + ' token share',
                     f'count(UPOS={p}) / T', 'nonpunctuation nonwhitespace model tokens T',
                     sources=('ud_pos','ud_gsd'), catalog={
                     'NOUN':'F041','VERB':'F042','ADJ':'F043','ADV':'F044','PRON':'F045',
                     'ADP':'F046','PART':'F048','AUX':'F049'}.get(p)) for p in POS)
SENSORS += tuple(sensor('deprel.' + r, 'dependency_composition', r + ' attachment share',
                       f'count(base(DEPREL)={r}) / A',
                       'basic nonroot nonpunct arcs with both endpoints in T, A', 'dep',
                       ('ud_dep','ud_gsd'),
                       limit='Main-relation component of one correlated syntactic composition; subtypes retained, not separate evidence.') for r in RELATIONS)
SENSORS += (
 sensor('word_length.mean','lexical_shape','Mean lexical word codepoints','sum(nonspace non-P-category codepoints of tokens)/T','T',catalog='F029'),
 sensor('word_length.ge4','lexical_shape','Long lexical token share','count(word_codepoints>=4)/T','T',catalog='F030'),
 sensor('word.single_han','lexical_shape','Single Han token share','count(token exactly one Unicode15 Script=Han codepoint)/T','T',sources=('catalog','unicode_scripts'),catalog='F031'),
 sensor('word.latin','lexical_shape','Latin letter token share','count(token contains L-category codepoint with Unicode15 Script=Latin)/T','T',sources=('catalog','unicode_scripts'),catalog='F032; pinned Unicode15 Script property'),
 sensor('word.decimal_digit','lexical_shape','Decimal-digit token share','count(token contains Unicode Nd codepoint)/T','T',catalog='Proxy only; not F033 Chinese-number normalization'),
 sensor('lexical.mattr100','lexical_reuse','MATTR100','mean(distinct surface forms / 100) over all length100 contiguous-component windows','length100 token windows',catalog='F034'),
 sensor('lexical.entropy100','lexical_reuse','Window normalized lexical entropy','mean(plugin entropy of forms / log2(100)) over same windows','length100 token windows',catalog='F036'),
 sensor('lexical.content_overlap','lexical_reuse','Adjacent content-token Jaccard','mean(|Kleft & Kright| / |Kleft | Kright|), K=surface forms with POS NOUN/PROPN/VERB/ADJ','original adjacent target sentence pairs with nonempty union',catalog='F037'),
 sensor('lexical.trigram_reuse','lexical_reuse','Prior-sentence token trigram reuse','number of sentence-internal trigram positions seen in an earlier sentence in same component / all sentence-internal trigram positions','within-sentence token trigram positions',catalog='F038; gap resets prior history'),
 sensor('upos.bigram_entropy100','upos_sequence','Window normalized POS-bigram entropy','mean(plugin entropy of 99 consecutive POS bigrams / log2(17*17)) over length100 token windows','length100 token windows',catalog='F054'),
)
SENSORS += tuple(sensor(*args, dependency='dep', sources=('catalog','ud_dep','referential')) for args in (
 ('dependency.span_mean','dependency_geometry','Mean dependency span','sum(abs(rank_dep-rank_head))/A','A'),
 ('dependency.span_normalized','dependency_geometry','Sentence-normalized dependency span','sum(abs(rank_dep-rank_head)/(T_sentence-1))/A','A'),
 ('dependency.depth_mean','dependency_geometry','Mean dependency depth','sum(root depth0 path lengths for tokens in T)/T','T in legal rooted trees'),
 ('dependency.maxdepth_median','dependency_geometry','Median sentence maximum depth','median(max token depth per sentence)','legal sentences with tokens in T'),
 ('syntax.predicate_heads','syntactic_configuration','Candidate predicate heads per sentence','count(POS VERB/ADJ/AUX and root or base relation in ccomp/xcomp/advcl/acl/conj/parataxis)/S','legal parsed sentences S'),
 ('syntax.subordinate_arcs','syntactic_configuration','Subordination arcs per100 sentences','100*count(base relation in ccomp/xcomp/advcl/acl)/S','legal parsed sentences S'),
 ('syntax.predicate_conj_share','syntactic_configuration','Conjoined candidate predicate share','count(candidate predicate head and base relation conj)/candidate predicate heads','candidate predicate heads'),
 ('syntax.nominal_modifier_size','syntactic_configuration','Nominal modifier subtree size','sum(per-NOUN/PROPN-head union of nonpunct descendants under acl/nmod children)/number of NOUN/PROPN heads','NOUN/PROPN heads'),
 ('syntax.verb_root_without_subject','syntactic_configuration','VERB-root with no subject edge share','count(VERB root with no nsubj/csubj child)/VERB roots','VERB-root sentences; NOT referential subject sites'),
 ('syntax.preposed_modifiers','syntactic_configuration','Preposed modifier attachment share','count(dependent rank<head rank)/arcs of base amod/nmod/acl/advmod','amod/nmod/acl/advmod arcs'),
 ('syntax.initial_pos_reuse','syntactic_configuration','Sentence-initial POS triple reuse','count(initial triple seen in an earlier qualifying same-component sentence)/qualifying sentences except first in each component','sentences with >=3 tokens after first qualifying same-component sentence'),
))
# Small disclosed cue lists; these are lexical/POS matches, never semantic-role,
# scope, complete person-expression or aspect construction annotations. Traditional
# and simplified orthographic variants are explicit entries, never normalization.
CUES = {
 'pronoun_first': ('PRON', ('我','我们','我們')),
 'pronoun_second': ('PRON', ('你','妳','您','你们','你們','妳們','您们','您們')),
 'pronoun_third': ('PRON', ('他','她','它','牠','祂','他们','他們','她们','她們','它们','它們','牠們','祂們','其')),
 'negator': ('ADV', ('不','未','没','沒','别','別','无','無')),
 'de_function_form': (('PART','SCONJ'), ('的',)),
 'di_subordinator_form': ('SCONJ', ('地',)),
 'de_extent_form': ('PART', ('得',)),
 'le_auxiliary_form': ('AUX', ('了',)),
 'zhe_auxiliary_form': ('AUX', ('着','著')),
 'guo_auxiliary_form': ('AUX', ('过','過')),
}
SENSORS += tuple(sensor('cue.' + name, 'closed_class_cues', name,
                       f'count(exact form in {forms!r} and UPOS={pos})/T', 'T',
                       sources=('ud_zh','zh_pron','zh_part','zh_aux'),
                       limit='Incomplete frozen surface-form/POS cue set, not person role, referent identity, negation scope or aspect interpretation; errors and polysemy remain.')
                 for name, (pos, forms) in CUES.items())
SENSORS = tuple(replace(s, dependency='pos') if s.id=='zh:syntax.initial_pos_reuse' else s for s in SENSORS)
CHANNEL_IDS = tuple(s.id for s in SENSORS)
BY_ID = {s.id:s for s in SENSORS}
assert len(BY_ID) == len(SENSORS)


def schema_document():
    from collections import Counter
    return {
      'schema_version': SCHEMA_VERSION,
      'status': 'executable_candidate_sensors_not_construct_validation',
      'channels': [asdict(s) for s in SENSORS],
      'counts': {'implemented_linguistic_channels':len(SENSORS), 'by_family':dict(Counter(s.family for s in SENSORS))},
      'composition_warning':'Components within POS/dependency/cue families are correlated sensors, not independent linguistic constructs. Aliases, masks, denominators, graph edges and quality flags are not additional channels.',
      'comparison_eligible':False, 'reference_distributions_fitted':False,
      'missing_policy':'null with reason; observed zero only with a positive audited opportunity; no epsilon or zero imputation',
      'usage':'Descriptive observations for statistical summaries; channel counts do not establish independent style dimensions or writing benefit.',
    }
