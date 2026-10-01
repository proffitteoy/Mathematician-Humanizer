"""Independent synthetic final-review checks. Never edits reviewed sources."""
import hashlib
import os
import json
import math
import random
import statistics
import unittest
import unicodedata
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from research.linguistic.adapter import measure
from research.linguistic.contracts import ParsedSource, SentenceParse, Token
from research.linguistic.fixtures import annotated, BASIC, source, full
from research.linguistic.schema import CUES, CHANNEL_IDS, POS, RELATIONS, SENSORS, schema_document
from research.linguistic.build_schema import crosswalk
from research.linguistic.stanza_local import LocalStanza
from research.linguistic.unicode_scripts import SCRIPT_RANGES, SCRIPTS_SHA256
from research.surface.adapter import Interval, make_projection


def usable(token):
    return token.upos != 'PUNCT' and bool(''.join(c for c in token.form if not c.isspace() and not unicodedata.category(c).startswith('P')))


def H(xs):
    return sum(-n/len(xs)*math.log2(n/len(xs)) for n in Counter(xs).values()) if xs else 0


def oracle(sentences, groups, prior=()):
    """Direct independent definitions, ordinary successful parse case."""
    ws=[[t for t in s.tokens if usable(t)] for s in sentences]
    flat=sum(ws,[])
    values={}
    def rate(k,n,d): values['zh:'+k]=(n/d if d else None,d)
    def avg(k,x): rate(k,sum(x),len(x))
    for pos in POS: rate('upos.'+pos,sum(t.upos==pos for t in flat),len(flat))
    for rel in RELATIONS:
        arcs=[t for s,w in zip(sentences,ws) for t in w if t.head and t.deprel.split(':')[0]!='punct' and t.head in {a.local_id for a in w}]
        rate('deprel.'+rel,sum(t.deprel.split(':')[0]==rel for t in arcs),len(arcs))
    lengths=[sum(not c.isspace() and not unicodedata.category(c).startswith('P') for c in t.form) for t in flat]
    avg('word_length.mean',lengths)
    rate('word_length.ge4',sum(n>=4 for n in lengths),len(flat))
    scripts={k:set(i for a,b in ranges for i in range(a,b+1)) for k,ranges in SCRIPT_RANGES.items()}
    rate('word.single_han',sum(len(t.form)==1 and ord(t.form) in scripts['Han'] for t in flat),len(flat))
    rate('word.latin',sum(any(unicodedata.category(c).startswith('L') and ord(c) in scripts['Latin'] for c in t.form) for t in flat),len(flat))
    rate('word.decimal_digit',sum(any(unicodedata.category(c)=='Nd' for c in t.form) for t in flat),len(flat))
    for key,(pos,forms) in CUES.items():
        allowed={pos} if isinstance(pos,str) else set(pos)
        rate('cue.'+key,sum(t.upos in allowed and t.form in forms for t in flat),len(flat))
    components=defaultdict(list)
    for s,w in zip(sentences,ws): components[groups[s.source_sentence_index]].extend(w)
    windows=[w[i-99:i+1] for w in components.values() for i in range(99,len(w))]
    avg('lexical.mattr100',[len(set(t.form for t in w))/100 for w in windows])
    avg('lexical.entropy100',[H([t.form for t in w])/math.log2(100) for w in windows])
    avg('upos.bigram_entropy100',[H([(w[i].upos,w[i+1].upos) for i in range(99)])/math.log2(289) for w in windows])
    prior=list(prior);overlaps=[];reuse=trials=initial=initial_trials=0
    for s,w in zip(sentences,ws):
        old=[p for p in prior if groups[p.source_sentence_index]==groups[s.source_sentence_index]]
        if old and old[-1].source_sentence_index==s.source_sentence_index-1:
            sets=[{t.form for t in p.tokens if usable(t) and t.upos in {'NOUN','PROPN','VERB','ADJ'}} for p in (old[-1],s)]
            if sets[0]|sets[1]:overlaps.append(len(sets[0]&sets[1])/len(sets[0]|sets[1]))
        older_words=[[t for t in p.tokens if usable(t)] for p in old]
        seen={tuple(t.form for t in ow[i:i+3]) for ow in older_words for i in range(len(ow)-2)}
        current=[tuple(t.form for t in w[i:i+3]) for i in range(len(w)-2)]
        trials+=len(current);reuse+=sum(x in seen for x in current)
        initial_seen={tuple(t.upos for t in ow[:3]) for ow in older_words if len(ow)>=3}
        if len(w)>=3 and initial_seen:
            initial_trials+=1;initial+=tuple(t.upos for t in w[:3]) in initial_seen
        prior.append(s)
    avg('lexical.content_overlap',overlaps)
    rate('lexical.trigram_reuse',reuse,trials)
    rate('syntax.initial_pos_reuse',initial,initial_trials)
    distance=[];scaled=[];depths=[];maxima=[];predicates=[];sub=0;modifiers=[];roots=[];preposed=[]
    for s,w in zip(sentences,ws):
        rank={t.local_id:i for i,t in enumerate(w)}
        byid={t.local_id:t for t in s.tokens}
        children=defaultdict(list)
        for t in s.tokens: children[t.head].append(t.local_id)
        sd=[]
        for t in w:
            node=t.local_id;d=0
            while byid[node].head:
                node=byid[node].head;d+=1
            sd.append(d)
            base=t.deprel.split(':')[0]
            if t.head in rank and base!='punct':
                distance.append(abs(rank[t.local_id]-rank[t.head]));scaled.append(distance[-1]/(len(w)-1))
                if base in {'amod','nmod','acl','advmod'}:preposed.append(rank[t.local_id]<rank[t.head])
                sub+=base in {'ccomp','xcomp','advcl','acl'}
            if t.upos in {'VERB','ADJ','AUX'} and (not t.head or base in {'ccomp','xcomp','advcl','acl','conj','parataxis'}):predicates.append(t)
            if t.upos=='VERB' and not t.head:roots.append(not any(byid[c].deprel.split(':')[0] in {'nsubj','csubj'} for c in children[t.local_id]))
            if t.upos in {'NOUN','PROPN'}:
                stack=[c for c in children[t.local_id] if byid[c].deprel.split(':')[0] in {'acl','nmod'}];seen=set()
                while stack:
                    c=stack.pop()
                    if c not in seen:seen.add(c);stack+=children[c]
                modifiers.append(len(seen&rank.keys()))
        depths+=sd
        if sd:maxima.append(max(sd))
    avg('dependency.span_mean',distance);avg('dependency.span_normalized',scaled);avg('dependency.depth_mean',depths)
    values['zh:dependency.maxdepth_median']=(statistics.median(maxima) if maxima else None,len(maxima))
    rate('syntax.predicate_heads',len(predicates),len(sentences));rate('syntax.subordinate_arcs',100*sub,len(sentences))
    rate('syntax.predicate_conj_share',sum(t.deprel.split(':')[0]=='conj' for t in predicates),len(predicates))
    avg('syntax.nominal_modifier_size',modifiers);avg('syntax.verb_root_without_subject',roots);avg('syntax.preposed_modifiers',preposed)
    return values


class IndependentReview(unittest.TestCase):
    def check_oracle(self, actual, expected):
        self.assertEqual(set(actual),set(expected))
        for key,(value,opportunities) in expected.items():
            with self.subTest(channel=key):
                if value is None:self.assertIsNone(actual[key]['value'])
                else:self.assertAlmostEqual(actual[key]['value'],value,places=12)
                self.assertEqual(actual[key]['opportunities'],opportunities)
                self.assertFalse(actual[key]['comparison_eligible'])
                if value is not None:self.assertIsNone(actual[key]['missing_reason'])

    def test_71_formulas_global_and_local_randomized_gap_profiles(self):
        forms=['字','我','我们','你','她','其','不','的','地','得','了','着','过','AB12','ª','Ⅻ','〇','𠀀','长长长词','１２','e\u0301','🙂']
        for seed in range(12):
            rng=random.Random(seed);specs=[]
            for sent in range(5):
                n=rng.randint(20,65);spec=[]
                for i in range(n):
                    form=rng.choice(forms);pos=rng.choice(POS+('SYM','X','INTJ'))
                    spec.append((form,pos,0 if i==0 else rng.randrange(1,i+1),'root' if i==0 else rng.choice(RELATIONS+('dep','orphan','fixed','reparandum'))))
                spec.append(('。','PUNCT',1,'punct'));specs.append(spec)
            obs,projection,parsed=annotated(specs)
            for split in (False,True):
                if split:
                    projection=make_projection(obs.source,tuple(Interval(s.start,s.end) for s in parsed.sentences),annotation_profile='separated-fixture')
                actual=measure(obs,projection,parsed)['target'];groups={s.source_sentence_index:s.source_sentence_index if split else 0 for s in parsed.sentences}
                self.check_oracle(actual['global_measurements'],oracle(parsed.sentences,groups))
                for i,s in enumerate(parsed.sentences):self.check_oracle(actual['sequence'][i]['measurements'],oracle([s],groups,parsed.sentences[:i]))

    def test_schema_crosswalk_and_legacy_set_exact(self):
        root=Path(__file__).resolve().parent
        self.assertEqual(json.loads(json.dumps(schema_document())),json.loads((root/'feature-schema.json').read_text()))
        c=crosswalk();self.assertEqual(json.loads(json.dumps(c)),json.loads((root/'catalog-crosswalk.json').read_text()))
        legacy={'F002','F003','F013','F014','F015','F016','F024','F025'}
        mapped={r['catalog_id'] for r in c['rows'] if r['catalog_id']}
        self.assertEqual(len(mapped),28);self.assertFalse(legacy&mapped)
        self.assertEqual(len(c['rows'])-len(mapped),43);self.assertEqual(len(c['not_implemented_original_catalog_ids']),64)
        self.assertEqual(legacy|mapped|set(c['not_implemented_original_catalog_ids']),{f'F{i:03}' for i in range(1,101)})

    def test_unicode_tables_match_full_official_local_data(self):
        location=os.environ.get('STYLE_UNICODE_SCRIPTS_FILE')
        if not location:
            self.skipTest('Set STYLE_UNICODE_SCRIPTS_FILE to the pinned official Unicode15 Scripts.txt')
        p=Path(location);self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),SCRIPTS_SHA256)
        expected={k:[] for k in SCRIPT_RANGES}
        for line in p.read_text().splitlines():
            line=line.split('#')[0].strip()
            if line:
                field,script=map(str.strip,line.split(';'))
                if script in expected:
                    a,*b=field.split('..');expected[script].append((int(a,16),int(b[0] if b else a,16)))
        self.assertEqual({k:tuple(v) for k,v in expected.items()},SCRIPT_RANGES)

    def test_all_pos_only_dependency_abstentions_and_history_survival(self):
        o,p,a=annotated([BASIC,BASIC]);a=replace(a,sentences=tuple(replace(s,status='pos_only',reason='dependency_unavailable',tokens=tuple(replace(t,head=None,deprel=None) for t in s.tokens)) for s in a.sentences))
        r=measure(o,p,a)['target']
        self.assertEqual(r['global_measurements']['zh:syntax.initial_pos_reuse']['value'],1)
        for spec in SENSORS:
            if spec.dependency=='dep':self.assertEqual(r['global_measurements'][spec.id]['missing_reason'],'dependency_unavailable')
        self.assertFalse(any(e['relation'].startswith('ud:') for e in r['graph']['edges']))

    def test_failed_history_does_not_cross_excluded_whitespace(self):
        o,p,a=annotated([BASIC,BASIC,BASIC]);s=a.sentences[0];a=replace(a,sentences=(replace(s,status='failed',reason='annotation_unresolved',tokens=()),)+a.sentences[1:])
        p=make_projection(o.source,(Interval(0,s.end),Interval(a.sentences[1].start,len(o.text))),annotation_profile='gap')
        rows=measure(o,p,a)['target']['sequence']
        self.assertEqual(rows[1]['measurements']['zh:lexical.trigram_reuse']['value'],0)
        self.assertEqual(rows[2]['measurements']['zh:lexical.trigram_reuse']['value'],1)
        self.assertEqual(rows[2]['measurements']['zh:syntax.initial_pos_reuse']['value'],1)

    def test_graph_spans_types_and_availability_exact(self):
        o,p,a=annotated([[('𠀀','NOUN',2,'nsubj:pass'),('e\u0301','VERB',0,'root'),('🙂','SYM',2,'discourse'),('。','PUNCT',2,'punct')],BASIC])
        r=measure(o,p,a)['target'];nodes=r['graph']['nodes']
        for node in nodes:
            s=a.sentences[node['source_sentence_index']]
            self.assertEqual(node['available_after_codepoint'],s.end)
            if node['kind'].startswith('token:'):
                match=[t for t in s.tokens if [t.start,t.end]==node['source_span']];self.assertEqual(len(match),1)
                self.assertEqual(node['kind'],'token:'+match[0].upos)
        for edge in r['graph']['edges']:
            self.assertGreaterEqual(edge['available_after_codepoint'],max(nodes[edge['source']]['available_after_codepoint'],nodes[edge['target']]['available_after_codepoint']))
        self.assertEqual(len([e for e in r['graph']['edges'] if e['relation'].startswith('ud:')]),sum(len(s.tokens)-1 for s in a.sentences))

    def test_hashes_bind_metadata_profile_annotation_and_projection(self):
        o,p,a=annotated([BASIC]);base=measure(o,p,a)['identity']
        for key in ('model_sha256','parser_version','runtime'):
            value={'model_sha256':'a'*64,'parser_version':'other','runtime':(('test','other'),)}[key]
            changed=measure(o,p,replace(a,profile=replace(a.profile,**{key:value})))['identity']
            self.assertNotEqual(changed['profile_sha256'],base['profile_sha256'])
            self.assertNotEqual(changed['observation_key_sha256'],base['observation_key_sha256'])
            self.assertEqual(changed['source_projection_join_key_sha256'],base['source_projection_join_key_sha256'])
        for key,value in [('archive_sha256','a'*64),('member_name','other'),('record_index',2),('record_byte_offset',2),('scanner_version','other'),('view_index',2),('json_pointer','/other'),('role','other')]:
            so=replace(o,source=replace(o.source,**{key:value}));pr=replace(p,source=so.source);pa=replace(a,source=so.source)
            changed=measure(so,pr,pa)['identity'];self.assertNotEqual(changed['source_sha256'],base['source_sha256']);self.assertNotEqual(changed['source_projection_join_key_sha256'],base['source_projection_join_key_sha256'])

    def test_extra_root_invalid_head_overlap_uncovered_mismatch_rejected(self):
        o,p,a=annotated([BASIC]);s=a.sentences[0]
        mutations=[replace(s.tokens[0],head=999),replace(s.tokens[0],head=1),replace(s.tokens[0],head=0,deprel='root'),replace(s.tokens[0],start=-1),replace(s.tokens[0],end=2),replace(s.tokens[0],form='你')]
        for bad in mutations:
            with self.subTest(bad=repr(bad)),self.assertRaises(ValueError):measure(o,p,replace(a,sentences=(replace(s,tokens=(bad,)+s.tokens[1:]),)))

    def test_limits_source_sentence_count_and_token_manifest(self):
        o,p,a=annotated([BASIC])
        large=source('字'*200001)
        with self.assertRaisesRegex(ValueError,'source_resource_limit'):replace(a,source=large.source,sentences=()).validate(large)
        many=source('甲。\n'*513)
        with self.assertRaisesRegex(ValueError,'sentence_count_resource_limit'):replace(a,source=many.source,sentences=()).validate(many)
        long=[('甲','NOUN',0 if i==0 else 1,'root' if i==0 else 'conj') for i in range(2048)]+[('。','PUNCT',1,'punct')]
        with self.assertRaisesRegex(ValueError,'token_tuple_or_resource_limit'):annotated([long])

    def test_unicode_runtime_mismatch_fails_closed(self):
        o,p,a=annotated([BASIC])
        with patch('research.linguistic.adapter.unicodedata.unidata_version','14.0.0'),self.assertRaisesRegex(ValueError,'unicode_script_category_version_mismatch'):measure(o,p,a)

    def test_total_token_limit_rejects_otherwise_bounded_sentences(self):
        spec=[('字','NOUN',0 if i==0 else 1,'root' if i==0 else 'conj') for i in range(2047)]+[('。','PUNCT',1,'punct')]
        with self.assertRaisesRegex(ValueError,'total_token_resource_limit'):annotated([spec]*9)

    def test_median_is_global_median_and_nominal_subtrees_are_unions(self):
        short=[('甲','NOUN',0,'root'),('。','PUNCT',1,'punct')]
        long=[('甲','NOUN',0,'root'),('乙','NOUN',1,'nmod'),('丙','ADJ',2,'acl'),('丁','ADJ',3,'amod'),('戊','ADJ',4,'amod'),('。','PUNCT',1,'punct')]
        o,p,a=annotated([short,short,long]);r=measure(o,p,a)['target']['global_measurements']
        self.assertEqual(r['zh:dependency.maxdepth_median']['value'],0)
        self.assertEqual(r['zh:dependency.maxdepth_median']['opportunities'],3)
        # Four nominal heads: two singleton roots (0), the long root (4), its
        # nmod child (3). Descendants may belong to different head opportunities.
        self.assertEqual(r['zh:syntax.nominal_modifier_size']['value'],7/4)


if __name__=='__main__':unittest.main(verbosity=2)
