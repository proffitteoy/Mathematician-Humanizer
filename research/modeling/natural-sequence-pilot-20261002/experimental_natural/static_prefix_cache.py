"""Bounded, in-memory static summaries, keyed by owned prefix content and provenance.

Only derived aggregate tensors are cached. Cache hashes/provenance never enter a
model head or forward call. Projection removes all excluded family value paths.
"""
from collections import OrderedDict
from dataclasses import dataclass
import hashlib, re, weakref
import torch
from .schema import PrefixPacket
from .models import InputView
from .evaluation_reuse import OnlineMoments


@dataclass(frozen=True)
class CacheNamespace:
    transform_sha256: str
    measurement_profile_sha256: str
    def __post_init__(self):
        for value in (self.transform_sha256,self.measurement_profile_sha256):
            if re.fullmatch('[0-9a-f]{64}',value) is None:
                raise ValueError('Exact TRAIN-transform and measurement-profile hashes required')


class StaticPrefixCache:
    _instances=weakref.WeakSet()
    PROCESS_CACHE_LIMIT=1 << 30
    def __init__(self, dimensions, namespace, max_bytes=1 << 30):
        if type(namespace) is not CacheNamespace:
            raise TypeError('An immutable transform/profile cache namespace is required')
        if type(max_bytes) is not int or not 0 < max_bytes <= 1 << 30:
            raise ValueError('Derived cache must stay within the approved 1GiB ceiling')
        self.dimensions=dimensions;self._namespace=namespace;self.max_bytes=max_bytes
        self._reserve=min(8 << 20,max_bytes//4)
        self._entries=OrderedDict();self._maps={};self.bytes=0;self.hits=0;self.misses=0;self.evictions=0
        self._map_bytes=0
        self._full=InputView(dimensions,tuple(range(dimensions)))
        self._namespace_bytes=(namespace.transform_sha256+namespace.measurement_profile_sha256).encode()
        if self.retained_budget_bytes()+self._reserve>self.PROCESS_CACHE_LIMIT:
            raise MemoryError('Aggregate static-cache metadata reservation exceeds 1GiB')
        self._instances.add(self)

    @property
    def namespace(self):return self._namespace

    @classmethod
    def retained_budget_bytes(cls):
        return sum(x.bytes+x._reserve+512*len(x._entries) for x in cls._instances)

    def _content(self, packet):
        fields=[getattr(packet,k) for k in ('prefix_values','prefix_observed','prefix_opportunity','prefix_opportunity_known')]
        if any(x.device.type != 'cpu' for x in fields):raise ValueError('This bounded cache is CPU only')
        dtypes=tuple(str(x.dtype) for x in fields)
        packed=torch.cat([x.detach().double() for x in fields],dim=1)
        return dtypes,hashlib.sha256(packed.numpy().tobytes()).digest()

    def key(self, packet):
        if type(packet) is not PrefixPacket:
            raise TypeError('Only an owned prefix packet is cacheable')
        packet.validate(self.dimensions)
        dtypes,content=self._content(packet)
        digest=hashlib.sha256(self._namespace_bytes+str((self.dimensions,packet.prefix_unit_count,dtypes)).encode()+content)
        return digest.digest()

    def get(self, packet, online=None):
        key=self.key(packet)
        if key in self._entries:
            self.hits+=1;value=self._entries.pop(key);self._entries[key]=value
            return value.clone()
        self.misses+=1
        if online is None:
            online=OnlineMoments(self.dimensions)
            for i in range(packet.prefix_unit_count):
                online.append(packet.prefix_values[i],packet.prefix_observed[i],packet.prefix_opportunity[i],packet.prefix_opportunity_known[i])
        elif online.t != packet.prefix_unit_count or online.dimensions != self.dimensions:
            raise ValueError('Online static state must match the current prefix')
        dtypes,content=self._content(packet)
        if online.content_dtypes != dtypes or online._content_digest.digest() != content:
            raise ValueError('Online moments do not describe this exact prefix')
        value=torch.cat([online.summary(self._full,True),
                         (online.opportunity_log64_sum/online.known_count.clamp_min(1)).float()]).detach()
        size=value.numel()*value.element_size()
        if size+512<=self.max_bytes-self._reserve:
            while self._entries and (self.bytes+size+512*(len(self._entries)+1)>self.max_bytes-self._reserve or
                                    self.retained_budget_bytes()+size+512>self.PROCESS_CACHE_LIMIT):
                _,old=self._entries.popitem(last=False);self.bytes-=old.numel()*old.element_size();self.evictions+=1
            if self.retained_budget_bytes()+size+512<=self.PROCESS_CACHE_LIMIT:
                self._entries[key]=value.clone();self.bytes+=size
        return value

    def project(self, canonical, view, include_covariance):
        if view.dimensions != self.dimensions:raise ValueError('Cache/view coordinate mismatch')
        mapping_key=(view,include_covariance)
        if mapping_key not in self._maps:
            d=self.dimensions;p=d*(d+1)//2;ix=view.indices;selected=[]
            selected.extend(ix[i] for i in view.active_local)
            selected.extend(d+j for j in ix);selected.extend(2*d+j for j in ix)
            if view.mode!='length':
                if view.has_opportunity:selected.extend(3*d+j for j in ix)
                selected.extend(4*d+j for j in ix);selected.extend(5*d+j for j in ix)
            pairs=[(j,k) for j in range(view.n) for k in range(j,view.n)]
            def pair_index(a,b):
                a,b=min(a,b),max(a,b)
                return a*d-a*(a-1)//2+(b-a)
            global_pairs=[pair_index(ix[j],ix[k]) for j,k in pairs]
            for group in range(4):selected.extend(6*d+group*p+index for index in global_pairs)
            active=set(view.active_local)
            if view.has_values:
                selected.extend(6*d+(4 if ix[j]<=ix[k] else 5)*p+index for (j,k),index in zip(pairs,global_pairs) if j in active)
                selected.extend(6*d+(5 if ix[j]<=ix[k] else 4)*p+index for (j,k),index in zip(pairs,global_pairs) if k in active)
                if include_covariance:selected.extend(6*d+6*p+index for (j,k),index in zip(pairs,global_pairs) if j in active and k in active)
            selected.append(6*d+7*p)
            if view.nuisance_indices:
                ni=view.nuisance_indices
                for offset in (d,2*d,6*d+7*p+1,4*d,5*d):selected.extend(offset+j for j in ni)
            mapping=torch.tensor(selected,dtype=torch.long)
            cost=mapping.numel()*mapping.element_size()+512
            if self._map_bytes+cost<=self._reserve:
                self._maps[mapping_key]=mapping;self._map_bytes+=cost
        else:mapping=self._maps[mapping_key]
        expected=7*self.dimensions+7*(self.dimensions*(self.dimensions+1)//2)+1
        if canonical.shape!=(expected,):raise ValueError('Malformed canonical summary')
        return canonical[mapping].clone()

    def stats(self):
        return {'tensor_bytes':self.bytes,'max_tensor_bytes':self.max_bytes,'entries':len(self._entries),
                'hits':self.hits,'misses':self.misses,'evictions':self.evictions,
                'conservative_bookkeeping_bytes':self._reserve+512*len(self._entries),
                'process_retained_cache_budget_bytes':self.retained_budget_bytes(),'process_cache_limit_bytes':self.PROCESS_CACHE_LIMIT,
                'storage':'private_in_memory_derived_summaries','disk_bytes':0}
