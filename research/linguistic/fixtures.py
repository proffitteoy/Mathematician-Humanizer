"""Original synthetic fixtures. No public or personal corpus excerpts."""
from style_compiler.contracts import text_hash
from style_compiler.segmentation import segment
from research.surface.adapter import SourceObservation,SourceView,Interval,make_projection
from .contracts import ParserProfile,ParsedSource,SentenceParse,Token


def source(text):
    return SourceObservation(SourceView(text_hash('linguistic-original-synthetic-archive'),
       'original-synthetic.jsonl',0,0,'synthetic/1',0,'/text','synthetic',text_hash(text),len(text)),text)


def full(observation):
    return make_projection(observation.source,(Interval(0,len(observation.text)),) if observation.text else (),
        annotation_profile='synthetic-scope/1',annotation_status='synthetic_fixture')


def annotated(sentence_specs):
    """Specs: lists of (form,upos,head,deprel), each ending in punctuation.

    Caller-created invented sentences only. A newline is inserted between specs,
    preserving independent operational units and an explicit source character.
    """
    text='\n'.join(''.join(t[0] for t in spec) for spec in sentence_specs)
    obs=source(text);spans=segment(text)[1]
    if len(spans)!=len(sentence_specs):raise ValueError('fixture unit count')
    sentences=[]
    for span,spec in zip(spans,sentence_specs):
        cursor=span.start;tokens=[]
        for i,(form,pos,head,rel) in enumerate(spec,1):
            tokens.append(Token(i,cursor,cursor+len(form),form,pos,head,rel));cursor+=len(form)
        sentences.append(SentenceParse(span.index,span.start,span.end,tuple(tokens),analysis_status='synthetic_fixture',warnings=()))
    parsed=ParsedSource(obs.source,ParserProfile('original-synthetic','1','hand-constructed-UD-fixture',text_hash('synthetic-model')),tuple(sentences))
    parsed.validate(obs)
    return obs,full(obs),parsed

BASIC=[('我','PRON',2,'nsubj'),('读','VERB',0,'root'),('书','NOUN',2,'obj'),('。','PUNCT',2,'punct')]
