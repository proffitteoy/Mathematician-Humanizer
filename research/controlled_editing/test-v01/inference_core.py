"""Inference-only exact descriptor/scoring extracts from frozen controller_v03. No fitter, editor, generator or network."""
import hashlib,json,math,re


VERSION='bounded-structural-edit-controller/0.3'

CONDITIONS=('short_early','short_late','mixed_early','mixed_late')

GENRES=('general_explanation','process_description','event_summary','reflective_commentary')

FEATURES=('log_chars','log_sentences','mean_sentence_chars','sd_sentence_chars','sentence_cv','short_sentence_fraction','long_sentence_fraction','adjacent_length_change','log_paragraphs','punctuation_fraction','mainpoint_start_fraction','mainpoint_end_fraction')

SCHEMA_SHA=hashlib.sha256(json.dumps([VERSION,FEATURES],separators=(',',':')).encode()).hexdigest()

class ContractError(ValueError):pass

def require(ok,reason):
    if not ok:raise ContractError(reason)

def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

def digest(x):return hashlib.sha256(canonical(x)).hexdigest()

def text_hash(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()

def finite(xs):return all(type(x) in (int,float) and not isinstance(x,bool) and math.isfinite(x) for x in xs)

def softmax(z):
    m=max(z);e=[math.exp(v-m) for v in z];total=math.fsum(e);return [v/total for v in e]

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

def scaled(x,t):
    return [0. if t['constant'][i] else (x[i]-t['center'][i])/t['scale'][i] for i in range(len(FEATURES))]+[1.]
