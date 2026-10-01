"""Bounded saved-checkpoint editing controller; experimental, not generic style.

No network, models/downloads, natural-corpus discovery, owner data or file writes
at import. Generator and semantic-review receipts are explicit trusted inputs.
Synthetic checkpoints are accepted only by the synthetic-test execution mode.
"""
from __future__ import annotations
import hashlib,json,math,re
from dataclasses import dataclass
from pathlib import Path

VERSION='bounded-structural-edit-controller/0.3'
CONDITIONS=('short_early','short_late','mixed_early','mixed_late')
GENRES=('general_explanation','process_description','event_summary','reflective_commentary')
FEATURES=('log_chars','log_sentences','mean_sentence_chars','sd_sentence_chars','sentence_cv','short_sentence_fraction','long_sentence_fraction','adjacent_length_change','log_paragraphs','punctuation_fraction','mainpoint_start_fraction','mainpoint_end_fraction')
SCHEMA_SHA=hashlib.sha256(json.dumps([VERSION,FEATURES],separators=(',',':')).encode()).hexdigest()
PROTECTED_WORDS=('不','没有','禁止','必须','可以','可能','至少','至多','所有','每个','任意','仅当','如果','否则')
FORMAL_MATH=re.compile(r'∀|∃|\\(?:forall|exists|begin|frac|sum|int)\b|\$|[=∑∫]')

class ContractError(ValueError):pass

def require(ok,reason):
    if not ok:raise ContractError(reason)
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def text_hash(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()
def finite(xs):return all(type(x) in (int,float) and not isinstance(x,bool) and math.isfinite(x) for x in xs)
def softmax(z):
    m=max(z);e=[math.exp(v-m) for v in z];total=math.fsum(e);return [v/total for v in e]
def sigmoid(z):
    return 1/(1+math.exp(-z)) if z>=0 else math.exp(z)/(1+math.exp(z))

def features(text,mainpoint_span):
    require(isinstance(text,str) and text.strip(),'empty_or_invalid_text')
    require(isinstance(mainpoint_span,(list,tuple)) and len(mainpoint_span)==2,'mainpoint_span_required')
    a,b=mainpoint_span;require(type(a)is int and type(b)is int and 0<=a<b<=len(text),'mainpoint_span_invalid')
    sentences=[x for x in re.split(r'[。！？!?]+',text) if x.strip()]
    lengths=[sum(not c.isspace() for c in s) for s in sentences]
    require(lengths and all(n>0 for n in lengths),'sentence_support_missing')
    n=math.fsum(lengths);mean=n/len(lengths);var=math.fsum((x-mean)**2 for x in lengths)/len(lengths);sd=math.sqrt(var)
    adjacent=math.fsum(abs(x-y) for x,y in zip(lengths,lengths[1:]))/max(1,len(lengths)-1)/mean
    paragraph_count=len([s for s in re.split(r'\n[\t ]*\n',text) if s.strip()])
    result=[math.log1p(n),math.log1p(len(lengths)),mean,sd,sd/mean,sum(x<=24 for x in lengths)/len(lengths),sum(x>=40 for x in lengths)/len(lengths),adjacent,math.log1p(paragraph_count),sum(c in '，、；：,;:' for c in text)/len(text),sum(not c.isspace() for c in text[:a])/sum(not c.isspace() for c in text),sum(not c.isspace() for c in text[:b])/sum(not c.isspace() for c in text)]
    require(len(result)==len(FEATURES) and finite(result),'invalid_feature_values');return result


def supported_plain_text(text):
    nonspace=sum(not c.isspace() for c in text)
    han=sum('\u3400'<=c<='\u4dbf' or '\u4e00'<=c<='\u9fff' for c in text)
    sentences=[x for x in re.split(r'[。！？!?]+',text) if x.strip()]
    disallowed=re.search(r'(?m)^\s*(?:#{1,6}\s|[-*+]\s|[0-9]+[.)、]\s)|```|~~~|[“”‘’「」『』"\[\]<>]',text)
    return bool(nonspace and han/nonspace>=.5 and len(sentences)>=4 and not disallowed and text.rstrip().endswith(tuple('。！？!?')))


def mechanical_preservation(source,candidate,protected):
    """Necessary checks only. Equal string counts do NOT prove preserved meaning."""
    require(isinstance(protected,list) and all(isinstance(s,str) and s for s in protected),'invalid_protected_strings')
    reasons=[]
    for token in sorted(set(protected)|set(PROTECTED_WORDS)|set(re.findall(r'\d+(?:\.\d+)?',source))):
        if source.count(token)!=candidate.count(token):reasons.append('protected_count_changed')
    if sorted(re.findall(r'\d+(?:\.\d+)?',source))!=sorted(re.findall(r'\d+(?:\.\d+)?',candidate)):reasons.append('numeric_multiset_changed')
    return {'mechanical_pass':not reasons,'reasons':sorted(set(reasons)),'semantic_guarantee':False}


def semantic_receipt_ok(source,candidate,receipt,approved_hashes):
    if not isinstance(receipt,dict) or set(receipt)!={'source_sha256','candidate_sha256','decision','reviewer_profile','review_id','checks'} or digest(receipt) not in approved_hashes:return False
    return (receipt.get('source_sha256')==text_hash(source) and receipt.get('candidate_sha256')==text_hash(candidate)
            and receipt.get('decision')=='pass' and receipt.get('reviewer_profile')=='independent_preservation_review/v1'
            and bool(receipt.get('review_id')) and receipt.get('checks')==['facts','negation','modality','quantifiers','scope'])


def scale_fit(xs):
    require(xs and all(len(x)==len(FEATURES) and finite(x) for x in xs),'invalid_training_features')
    center=[];scale=[];constant=[]
    for j in range(len(FEATURES)):
        v=[x[j] for x in xs];c=math.fsum(v)/len(v);fixed=all(x==v[0] for x in v)
        variance=0 if fixed else math.fsum((x-c)**2 for x in v)/len(v)
        require(fixed or variance>0,'nonconstant_scale_underflow')
        center.append(v[0] if fixed else c);scale.append(1. if fixed else math.sqrt(variance));constant.append(fixed)
    return {'center':center,'scale':scale,'constant':constant,'fit_partition':'train'}

def scaled(x,t):
    return [0. if t['constant'][i] else (x[i]-t['center'][i])/t['scale'][i] for i in range(len(FEATURES))]+[1.]

def fit(rows,preference_pairs,*,provenance,authorization=None,epochs=150,lr=.05):
    """Train actual condition and pairwise-preference weights. No corpus file I/O.

    Only caller-supplied train rows are admitted. Empirical execution requires
    separately hash-bound protocol/dataset/independent-label/root-GO artifacts.
    """
    require(provenance in ('synthetic_fixture','assistant_authored_controlled'),'unsupported_training_provenance')
    require(rows and type(epochs)is int and 1<=epochs<=500 and 0<lr<=.2,'invalid_fit_budget')
    require(all(r.get('partition')=='train' for r in rows),'fit_may_read_train_rows_only')
    require(len({r['id'] for r in rows})==len(rows),'duplicate_training_row')
    require(all(r.get('condition') in CONDITIONS and r.get('meaning_verified') is True and r.get('realized_condition_verified') is True for r in rows),'reviewed_realized_labels_required')
    family_splits={}
    for r in rows:
        require(isinstance(r.get('family'),str) and r['family'],'content_family_required')
        family_splits.setdefault(r['family'],set()).add(r['partition'])
    dataset_sha=digest(rows);labels_sha=digest([{'id':r['id'],'condition':r['condition'],'meaning_verified':r['meaning_verified'],'realized_condition_verified':r['realized_condition_verified']} for r in rows])
    if provenance!='synthetic_fixture':
        require(isinstance(authorization,dict),'empirical_training_GO_required')
        require(authorization.get('action')=='CONTROLLED_STYLE_TRAIN_GO' and authorization.get('actor')=='root' and authorization.get('dataset_sha256')==dataset_sha and authorization.get('labels_sha256')==labels_sha and authorization.get('independent_label_review') is True and len(authorization.get('protocol_sha256',''))==64,'empirical_training_authority_mismatch')
    if provenance!='synthetic_fixture':
        require(all(r.get('features')==features(r.get('text'),r.get('mainpoint_span')) for r in rows),'empirical_features_must_reconstruct')
    require({r['condition'] for r in rows}==set(CONDITIONS),'all_supported_conditions_need_training_support')
    xs=[r['features'] for r in rows];transform=scale_fit(xs);x=[scaled(v,transform) for v in xs];d=len(x[0]);w=[[0.]*d for _ in CONDITIONS];u=[[0.]*d for _ in CONDITIONS]
    byid={r['id']:i for i,r in enumerate(rows)}
    for pair in preference_pairs:
        require(set(pair)=={'better','worse','target','independently_reviewed'},'pair_schema')
        require(pair['better'] in byid and pair['worse'] in byid and pair['target'] in CONDITIONS and pair['independently_reviewed'] is True,'invalid_preference_pair')
        a,b=rows[byid[pair['better']]],rows[byid[pair['worse']]];require(a['family']==b['family'],'preference_pair_must_share_content_family')
    pair_family_counts={}
    for pair in preference_pairs:
        family=rows[byid[pair['better']]]['family'];pair_family_counts[family]=pair_family_counts.get(family,0)+1
    # Equal family weighting, then equal eligible realizations within each family.
    family_counts={k:sum(r['family']==k for r in rows) for k in family_splits};nf=len(family_counts)
    for _ in range(epochs):
        dw=[[0.]*d for _ in CONDITIONS];du=[[0.]*d for _ in CONDITIONS]
        for i,r in enumerate(rows):
            z=[math.fsum(a*b for a,b in zip(wc,x[i])) for wc in w];probs=softmax(z);target=CONDITIONS.index(r['condition']);weight=1/(nf*family_counts[r['family']])
            for c in range(4):
                e=(probs[c]-(c==target))*weight
                for j in range(d):dw[c][j]+=e*x[i][j]
        for pair in preference_pairs:
            c=CONDITIONS.index(pair['target']);a,b=x[byid[pair['better']]],x[byid[pair['worse']]];delta=[aa-bb for aa,bb in zip(a,b)];family=rows[byid[pair['better']]]['family'];e=-sigmoid(-math.fsum(v*q for v,q in zip(u[c],delta)))/(len(pair_family_counts)*pair_family_counts[family])
            for j in range(d):du[c][j]+=e*delta[j]
        for c in range(4):
            for j in range(d):w[c][j]-=lr*dw[c][j];u[c][j]-=lr*du[c][j]
    require(all(finite(v) for v in w+u),'nonfinite_fit')
    model={'schema':VERSION,'feature_names':list(FEATURES),'feature_schema_sha256':SCHEMA_SHA,'conditions':list(CONDITIONS),'transform':transform,'condition_weights':w,'preference_weights':u,
           'training':{'status':'completed_actual_gradient_fit','provenance':provenance,'dataset_sha256':dataset_sha,'labels_sha256':labels_sha,'epochs':epochs,'lr':lr,'families':len(family_counts),'realizations':len(rows),'preference_pairs':len(preference_pairs),'training_only':True,'counts_towards_1280_natural_works':False},
           'support':{'genres':list(GENRES),'min_source_codepoints':120,'max_source_codepoints':400,'candidate_count':4,'formal_math_supported':False,'minimum_score_margin':.02,'semantic_review_required_for_nonidentity':True,'generic_stage_complete':False,'personalization_authorized':False},
           'authorization_sha256':digest(authorization) if authorization else None}
    return model


def save_checkpoint(model,path):
    blob=canonical(model);payload={'model':model,'model_sha256':hashlib.sha256(blob).hexdigest()}
    with Path(path).open('xb') as f:f.write(canonical(payload)+b'\n')
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_checkpoint(path,expected_file_sha256):
    with Path(path).open('rb') as f:raw=f.read(1024**2+1)
    require(len(raw)<=1024**2,'checkpoint_size_limit')
    require(hashlib.sha256(raw).hexdigest()==expected_file_sha256,'checkpoint_file_hash_mismatch')
    def pairs(xs):
        d={}
        for k,v in xs:
            require(k not in d,'duplicate_checkpoint_key');d[k]=v
        return d
    def bad_constant(x):raise ContractError('nonfinite_checkpoint_json')
    p=json.loads(raw,object_pairs_hook=pairs,parse_constant=bad_constant);m=p['model'];require(p['model_sha256']==digest(m),'checkpoint_payload_hash_mismatch')
    require(m.get('schema')==VERSION and m.get('feature_schema_sha256')==SCHEMA_SHA and m.get('feature_names')==list(FEATURES) and m.get('conditions')==list(CONDITIONS),'checkpoint_schema_mismatch')
    require(m.get('training',{}).get('provenance') in ('synthetic_fixture','assistant_authored_controlled'),'checkpoint_provenance_invalid')
    require(m.get('training',{}).get('status')=='completed_actual_gradient_fit' and m['training'].get('training_only') is True,'trained_checkpoint_required')
    d=len(FEATURES)+1
    require(all(len(m[k])==4 and all(len(v)==d and finite(v) for v in m[k]) for k in ('condition_weights','preference_weights')),'checkpoint_tensor_invalid')
    t=m['transform'];require(t.get('fit_partition')=='train' and all(len(t[k])==len(FEATURES) for k in ('center','scale','constant')) and finite(t['center']+t['scale']) and all(x>0 for x in t['scale']) and all(type(x) is bool for x in t['constant']),'checkpoint_transform_invalid')
    return m


def score(model,x,target):
    require(target in CONDITIONS,'unsupported_condition');z=scaled(x,model['transform']);prob=softmax([math.fsum(a*b for a,b in zip(w,z)) for w in model['condition_weights']]);c=CONDITIONS.index(target)
    return math.log(max(prob[c],1e-300))+math.fsum(a*b for a,b in zip(model['preference_weights'][c],z))


@dataclass
class EditLimits:
    checkpoint: str
    checkpoint_sha256: str
    genre: str
    mainpoint_text: str
    protected_strings: list
    generator: object
    generator_profile_sha256: str
    approved_semantic_review_hashes: frozenset
    mode: str='empirical'


def edit(text,target,limits):
    """Actual saved-model score is used here; no implicit generator/network exists.

    Generator contract: .profile (JSON mapping), .generate(text,target,k)->list
    of {text, semantic_review}. Review receipts cannot carry preference/style labels.
    """
    result={'schema':VERSION,'status':'abstain','text':text,'reason':None,'scores':[],'semantic_guarantee':False,'generic_stage_complete':False}
    try:
        require(isinstance(limits,EditLimits),'limits_contract_required');require(limits.mode in ('synthetic_test','empirical'),'execution_mode_invalid');model=load_checkpoint(limits.checkpoint,limits.checkpoint_sha256)
        if model['training']['provenance']=='synthetic_fixture':require(limits.mode=='synthetic_test','synthetic_checkpoint_not_for_empirical_editing')
        require(target in CONDITIONS,'unsupported_condition');s=model['support']
        require(limits.genre in s['genres'],'unsupported_genre');require(s['min_source_codepoints']<=len(text)<=s['max_source_codepoints'],'unsupported_source_length')
        require(not FORMAL_MATH.search(text),'formal_math_out_of_support')
        require(supported_plain_text(text),'source_plain_chinese_prose_out_of_support')
        require(isinstance(limits.mainpoint_text,str) and limits.mainpoint_text and text.count(limits.mainpoint_text)==1,'unique_verified_mainpoint_required')
        require(digest(limits.generator.profile)==limits.generator_profile_sha256,'generator_profile_changed')
        candidates=limits.generator.generate(text,target,s['candidate_count'])
        require(isinstance(candidates,list) and len(candidates)==s['candidate_count'],'fixed_candidate_budget_required')
        eligible={};failures=[]
        for c in candidates:
            require(isinstance(c,dict) and set(c)=={'text','semantic_review'},'candidate_fields_only_no_labels')
            t=c['text'];require(isinstance(t,str),'candidate_text_invalid')
            if not s['min_source_codepoints']<=len(t)<=s['max_source_codepoints']:failures.append('candidate_length');continue
            if t.count(limits.mainpoint_text)!=1:failures.append('mainpoint_missing_or_duplicated');continue
            if FORMAL_MATH.search(t):failures.append('formal_math_candidate');continue
            if not supported_plain_text(t):failures.append('candidate_plain_chinese_prose_out_of_support');continue
            mech=mechanical_preservation(text,t,limits.protected_strings)
            if not mech['mechanical_pass']:failures.extend(mech['reasons']);continue
            if t!=text and not semantic_receipt_ok(text,t,c['semantic_review'],limits.approved_semantic_review_hashes):failures.append('meaning_not_independently_verified');continue
            a=t.index(limits.mainpoint_text);value=score(model,features(t,[a,a+len(limits.mainpoint_text)]),target)
            require(math.isfinite(value),'nonfinite_score');eligible[text_hash(t)]=(value,t)
        result['scores']=[{'candidate_sha256':h,'score':v[0]} for h,v in sorted(eligible.items())]
        require(len(eligible)>=2,'fewer_than_two_distinct_preserved_candidates')
        ranked=sorted(((v,t,h) for h,(v,t) in eligible.items()),key=lambda x:(-x[0],x[2]));margin=ranked[0][0]-ranked[1][0]
        require(margin>=s['minimum_score_margin'],'insufficient_score_margin')
        result.update(status='selected' if ranked[0][1]!=text else 'no_change',text=ranked[0][1],selected_sha256=ranked[0][2],score_margin=margin,checkpoint_sha256=limits.checkpoint_sha256,generator_profile_sha256=limits.generator_profile_sha256,training_provenance=model['training']['provenance'],reason=None,rejected_candidate_reasons=sorted(set(failures)))
    except (ContractError,KeyError,TypeError,ValueError,OverflowError,OSError) as e:
        result['reason']=str(e) if isinstance(e,ContractError) else type(e).__name__
    return result
