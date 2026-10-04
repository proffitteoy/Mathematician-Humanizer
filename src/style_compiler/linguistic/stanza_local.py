"""Opt-in offline Stanza adapter. No downloads, authentication or text upload.

Caller supplies an existing hash-verified model directory. Imports stanza only
when constructing the parser; no weights/dependencies bundled in this project.
"""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
from dataclasses import asdict
from style_compiler.surface import _digest
from style_compiler.segmentation import segment
from .contracts import ParserProfile, ParsedSource, SentenceParse, Token, require, MAX_SENTENCE_TOKENS, MAX_SOURCE_CODEPOINTS, MAX_SOURCE_SENTENCES, MAX_TOTAL_TOKENS

STANZA_VERSION='1.10.1'
MODEL_COMMIT='82f2856d1cf4f933738a8a84b5ad959d156040a0'
MODEL_FILES={
 'tokenize/gsdsimp.pt':(1383326,'962f2578e2a3dabeb4671053372eb1bd092357921904233556c8d77a46440882'),
 'pos/gsdsimp_nocharlm.pt':(21285503,'0dea6b43c267b408fc7c353e41b449a06bff309a93ba75fa63db32bf9f388cb7'),
 'lemma/gsdsimp_nocharlm.pt':(6592066,'8fe38f6b081d939662a4e78a4350a2253f879c41004327ac6fb78d7078bdeea2'),
 'depparse/gsdsimp_nocharlm.pt':(103928202,'7a3f038233a772c50372a58b58a05ca0c3b0be9c88d6ed7b2664373c0ef741f6'),
 'pretrain/fasttext157.pt':(306614467,'630daf461d1dc6f49642ee534102bf08783866949f7f046cf2df3667dcc5e112'),
}
RESOURCES_SHA='3efb2833a67c0184fac2ea9986c04f9585bfb89fb943a4ab1a6bcbed641d6be0'


def hash_file(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while b:=f.read(1024*1024):h.update(b)
    return h.hexdigest()


def verify_models(directory):
    root=Path(directory)
    for name,(size,digest) in MODEL_FILES.items():
        p=root/'zh-hans'/name
        require(p.is_file() and p.stat().st_size==size and hash_file(p)==digest,'local_model_hash_mismatch:'+name)
    p=root/'resources.json'
    require(p.is_file() and hash_file(p)==RESOURCES_SHA,'resources_hash_mismatch')
    return _digest({'files':MODEL_FILES,'resources_sha256':RESOURCES_SHA,'commit':MODEL_COMMIT})


class LocalStanza:
    """Sentence-local automatic analysis, unvalidated for target domains.

    No document context reaches any per-sentence parser invocation. Boundaries
    come from existing full-source operational segmentation, not from Stanza.
    """
    def __init__(self,directory,threads=2):
        require(type(threads)is int and 1<=threads<=8,'thread_resource_limit')
        digest=verify_models(directory)
        require(importlib.metadata.version('stanza')==STANZA_VERSION,'stanza_version_mismatch')
        import stanza
        import torch
        torch.set_num_threads(threads)
        self.pipeline=stanza.Pipeline(lang='zh-hans',dir=str(directory),package=None,
          processors={'tokenize':'gsdsimp','pos':'gsdsimp_nocharlm','lemma':'gsdsimp_nocharlm','depparse':'gsdsimp_nocharlm'},
          download_method=None,use_gpu=False,tokenize_no_ssplit=True,verbose=False)
        self.profile=ParserProfile('stanza',STANZA_VERSION,'stanfordnlp/stanza-zh-hans@'+MODEL_COMMIT+';nocharlm;resources1.10.0',digest,
            runtime=(('python',platform.python_version()),('torch',str(torch.__version__)),
                     ('numpy',importlib.metadata.version('numpy')),('threads',str(threads)),
                     ('device','cpu'),('tokenize_no_ssplit','true'),('download_method','none')))
        self.vocabulary={}
        for name in ('pos','depparse'):
            vocab=self.pipeline.processors[name].vocab
            self.vocabulary[name]={k:tuple(vocab[k]._id2unit) for k in ('upos','deprel') if k in vocab.keys()}

    def parse(self,observation):
        observation.__post_init__()
        require(len(observation.text)<=MAX_SOURCE_CODEPOINTS,'source_resource_limit')
        rows=[];total_tokens=0
        spans=segment(observation.text)[1]
        require(len(spans)<=MAX_SOURCE_SENTENCES,'sentence_count_resource_limit')
        for span in spans:
            text=observation.text[span.start:span.end]
            # Pre-parser bound also prevents O(n^2) parse on oversized source
            # units. This is an engineering guard, not linguistic eligibility.
            if len(text)>MAX_SENTENCE_TOKENS or total_tokens>=MAX_TOTAL_TOKENS:
                rows.append(SentenceParse(span.index,span.start,span.end,(),'failed','resource_limit'));continue
            try:
                doc=self.pipeline(text)
                require(len(doc.sentences)==1,'unexpected_parser_sentence_split')
                words=doc.sentences[0].words
                require(len(words)<=MAX_SENTENCE_TOKENS,'token_resource_limit')
                if total_tokens+len(words)>MAX_TOTAL_TOKENS:
                    total_tokens=MAX_TOTAL_TOKENS
                    rows.append(SentenceParse(span.index,span.start,span.end,(),'failed','resource_limit'));continue
                toks=[]
                for w in words:
                    require(type(w.id)is int and type(w.start_char)is int and type(w.end_char)is int,'mwt_or_missing_offsets')
                    require(text[w.start_char:w.end_char]==w.text,'alignment_failed')
                    feats=tuple(tuple(p.split('=',1)) for p in w.feats.split('|')) if w.feats else ()
                    toks.append(Token(w.id,span.start+w.start_char,span.start+w.end_char,w.text,w.upos,w.head,w.deprel,feats))
                parsed=SentenceParse(span.index,span.start,span.end,tuple(toks))
                parsed.validate(observation.text,span)
                rows.append(parsed);total_tokens+=len(toks)
            except (ValueError,RuntimeError,IndexError,TypeError) as e:
                # Never echo parser exception text that could contain user text.
                reason='alignment_failed' if any(x in str(e) for x in ('align','offset','uncovered','mwt')) else 'parse_failed'
                rows.append(SentenceParse(span.index,span.start,span.end,(),'failed',reason,
                                          warnings=('automatic_parse_unavailable',type(e).__name__)))
        result=ParsedSource(observation.source,self.profile,tuple(rows));result.validate(observation)
        return result
