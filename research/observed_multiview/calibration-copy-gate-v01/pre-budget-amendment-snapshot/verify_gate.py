"""Signature-only author readback; permits an independent reviewer to replay.

Uses separate varint decoding, matching/alias verification, and DSU closure.
Never opens raw objects or calibration gzip body caches. Not an independent
review certificate merely because this source exists or its tests pass.
"""
from collections import defaultdict, Counter
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import zlib
import resource
import signal
import os
import calibration_gate as g


def ids(blob,count,maxid):
    dec=zlib.decompressobj();raw=dec.decompress(blob,count*5+1)
    g.require(dec.eof and not dec.unused_data and not dec.unconsumed_tail and len(raw)<=count*5,'verify_packed_ids_invalid')
    out=[];last=0;n=0;shift=0;start=0
    for i,b in enumerate(raw):
        n+=(b&127)*(2**shift)
        if b&128:
            shift+=7;g.require(shift<35,'verify_varint_overflow')
        else:
            g.require(n>0 and not(i>start and b==0),'verify_varint_noncanonical')
            last+=n;g.require(last<=maxid,'verify_unknown_gram_id');out.append(last)
            n=shift=0;start=i+1
    g.require(not shift and len(out)==count,'verify_gram_count_mismatch')
    return out


def replay(package,sigs,guard,budget):
    """Independent full old-signature scan, no plaintext comparisons."""
    db=package.db
    raw_index=defaultdict(set);norm_index=defaultdict(set);block_index=defaultdict(set)
    dictionary={}
    gramset=sorted(set().union(*(s.grams for s in sigs)))
    for start in range(0,len(gramset),300):
        part=gramset[start:start+300]
        dictionary.update(db.execute('SELECT sha256,id FROM grams WHERE sha256 IN ('+','.join('?' for _ in part)+')',part))
    inverse=defaultdict(list)
    for n,s in enumerate(sigs):
        if s.normalized_codepoints:
            raw_index[s.raw_sha256].add(n);norm_index[s.normalized_sha256].add(n)
        if s.normalized_codepoints>=64:block_index[s.normalized_sha256].add(n)
        for _,_,h,_ in s.blocks:block_index[h].add(n)
        if len(s.grams)>=40:
            for digest in s.grams:
                if digest in dictionary:inverse[dictionary[digest]].append(n)
    hits={};scanned=0
    def add(n,tid,reason,common=None,refcount=None):
        k=(sigs[n].key,tid)
        v=hits.setdefault(k,{'reasons':set(),'candidate_full_gram_count':len(sigs[n].grams)})
        v['reasons'].add(reason)
        if common is not None:v.update(shared_distinct_grams=common,reference_full_gram_count=refcount)
        else:budget['used']+=1
        g.require(budget['used']<=g.INCREMENT_CAP,'verify_comparison_cap')
    for tid,raw,norm,npoints,count,packed in db.execute('SELECT id,raw_sha256,normalized_sha256,normalized_codepoints,gram_count,gram_ids_delta_zlib FROM texts'):
        scanned+=1
        for n in raw_index.get(raw,()):add(n,tid,'raw_exact')
        if npoints:
            for n in norm_index.get(norm,()):add(n,tid,'normalized_full_exact')
        if npoints>=64:
            for n in block_index.get(norm,()):add(n,tid,'candidate_long_block_to_reference_full_exact')
        # Decode every stored set, including short signatures, so malformed
        # compressed representations cannot hide behind a matching threshold.
        decoded=ids(packed,count,package.max_gram_id)
        if count>=40 and inverse:
            commons=Counter()
            for gid in decoded:
                postings=inverse.get(gid,())
                commons.update(postings);budget['used']+=len(postings)
                g.require(budget['used']<=g.INCREMENT_CAP,'verify_comparison_cap')
            for n,common in commons.items():
                denominator=min(len(sigs[n].grams),count)
                if common>=40 and denominator and 5*common>=4*denominator:
                    add(n,tid,'near_copy_full_distinct_grams',common,count)
        if scanned%500==0:guard.check()
    for n,(tid,digest) in enumerate(db.execute('SELECT text_id,normalized_sha256 FROM blocks')):
        for i in block_index.get(digest,()):add(i,tid,'long_block_exact')
        if n%500==0:guard.check()
    g.require(scanned==package.text_count,'verify_reference_scan_count')
    return hits


def evidence_key(edge):
    return (edge['left_member_key'],edge['right_member_key'],edge['package'],edge['candidate_view'],edge['reference_text_id'])


def verify_batch(batch,rows,own,packages,coverage,by_artifact,package_names,guard,budget):
    g.require(batch['record_keys']==[r['record_key'] for r in rows],'verify_batch_record_order')
    g.require([r['record_key'] for r in batch['receipts']]==batch['record_keys'],'verify_receipt_record_order')
    sigmap=g.package_record_signatures(own,rows)
    sigs=[s for row in rows for s in sigmap[row['record_key']]]
    allkeys=set()
    for package in packages:
        expected=replay(package,sigs,guard,budget);observed={}
        for row,r in zip(rows,batch['receipts']):
            prs=[p for p in r['packages'] if p['package']==package.name]
            g.require(len(prs)==1,'verify_package_missing_or_duplicate');pr=prs[0]
            g.require(pr['package_sha256']==package.sha256 and pr['complete_signature_scan'] is True and
                      pr['reference_texts_scanned']==pr['reference_texts_expected']==package.text_count,'verify_package_scope')
            g.require(r['source_sha256']==row['source_sha256'],'verify_record_source_sha')
            tids={h['reference_text_id'] for h in pr['hits']};bindings=[]
            for tid in sorted(tids):
                bindings.extend(dict(zip(('reference_text_id','source_id','member_key','exposure_role','source_view_role','source_object_sha256','locator_json'),x))
                    for x in package.db.execute('SELECT text_id,source_id,member_key,exposure_role,source_view_role,source_object_sha256,locator_json FROM bindings WHERE text_id=?',(tid,)))
            g.require(sorted(g.canonical(b) for b in bindings)==sorted(g.canonical(b) for b in pr['bindings']),'verify_missing_reference_alias_binding')
            bm=defaultdict(list)
            for b in bindings:bm[b['reference_text_id']].append(b['member_key'])
            for hit in pr['hits']:
                key=(hit['candidate_view'],hit['reference_text_id'])
                g.require(key not in observed,'verify_duplicate_hit');g.require(hit['candidate_view'] in {s.key for s in sigmap[row['record_key']]},'verify_wrong_candidate_view')
                observed[key]={'reasons':set(hit['reasons']),'candidate_full_gram_count':hit['candidate_full_gram_count']}
                for fld in ('shared_distinct_grams','reference_full_gram_count'):
                    if fld in hit:observed[key][fld]=hit[fld]
                for m in bm[key[1]]:
                    if m!=row['member_key']:allkeys.add((row['member_key'],m,package.name,key[0],key[1]))
                # Independent coverage fanout: every raw alias behind the stored
                # projected/old-normalized signature must join the calibration.
                kinds=[]
                if package.name==package_names['old_raw_database']:kinds=['old_normalized_full','old_normalized_long_block']
                elif package.name==package_names['projected_database']:kinds=['new_projected_signature']
                for kind in kinds:
                    for raw, in coverage.execute('SELECT old_raw_sha256 FROM segments WHERE coverage_kind=? AND reference_text_id=?',(kind,key[1])):
                        found=False
                        for artifact in ('old_raw_database','three_blog_raw_database'):
                            ref=by_artifact[artifact]
                            for m, in ref.db.execute('SELECT b.member_key FROM bindings b JOIN texts t ON t.id=b.text_id WHERE t.raw_sha256=?',(raw,)):
                                found=True
                                if m!=row['member_key']:allkeys.add((row['member_key'],m,package.name,key[0],key[1]))
                        g.require(found,'verify_projected_alias_raw_missing')
        g.require(observed==expected,'verify_matching_evidence_or_negative_scan_mismatch')
    got=[evidence_key(e) for e in batch['expanded_edges']]
    g.require(len(got)==len(set(got)) and set(got)==allkeys,'verify_alias_edge_set_mismatch')
    return batch['expanded_edges']


def independent_graph(db,rows,edges):
    parent={}; groups=defaultdict(list);exposed=set();oldmap={}
    def add(m):g.validate_member(m);parent.setdefault(m,m)
    def find(m):
        g.require(m in parent,'verify_unknown_member')
        while parent[m]!=m:parent[m]=parent[parent[m]];m=parent[m]
        return m
    def union(a,b):
        x,y=find(a),find(b);parent[max(x,y)]=min(x,y)
    def mapping():
        parts=defaultdict(list)
        for m in sorted(parent):parts[find(m)].append(m)
        return {m:hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest() for v in parts.values() for m in v}
    for m,c,x in db.execute('SELECT member_key,component_id,excluded FROM members'):
        add(m);groups[c].append(m);oldmap[m]=c
        if x:exposed.add(m)
    for group in groups.values():
        for m in group[1:]:union(group[0],m)
    g.require(mapping()==oldmap,'verify_base_component_hash')
    for a,b,_ in db.execute('SELECT a,b,kind FROM lineage'):
        g.require(oldmap[a]==oldmap[b],'verify_lineage_ancestor');union(a,b)
    for e in edges:union(e['left_member_key'],e['right_member_key'])
    final=mapping();oldcontam={final[m] for m in exposed}
    source={s:len({final[r['member_key']] for r in rows if r['source_frame']==s}) for s in g.SOURCES}
    n=len({final[r['member_key']] for r in rows});oldhits=sum(final[r['member_key']] in oldcontam for r in rows)
    status='calibration_underfilled' if oldhits or n<96 or any(x<32 for x in source.values()) else 'calibration_copy_gate_complete_pending_independent_review'
    contam=oldcontam|{final[r['member_key']] for r in rows}
    return final,oldcontam,contam,status,source,oldhits


def load_gzip(path,cap=128*1024**2):
    with gzip.open(path,'rb') as f:
        raw=f.read(cap+1);g.require(len(raw)<=cap and not f.read(1),'verify_output_expansion_cap')
    return g.strict_json(raw)


def verify(manifest_sha,receipt_sha):
    g.runner.install_offline_sandbox()
    resource.setrlimit(resource.RLIMIT_AS,(g.CAPS['rss_bytes'],g.CAPS['rss_bytes']))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    receipt_path=g.PRIVATE/'calibration-gate.receipt.private.json'
    g.require(g.filehash(g.MANIFEST)==manifest_sha and g.filehash(receipt_path)==receipt_sha,'verify_external_hash_mismatch')
    m=g.load_json(g.MANIFEST);receipt=g.load_json(receipt_path)
    g.require(receipt['manifest_sha256']==manifest_sha and receipt['status'] in ('calibration_underfilled','calibration_copy_gate_complete_pending_independent_review'),'verify_gate_not_complete')
    for b in m['input_bindings']+list(m['artifact_bindings'].values())+m['code_bindings']+receipt['outputs']:g.verify_binding(b)
    prior=g.runner.prior_wall_seconds()+receipt['resources']['elapsed_seconds']
    guard=g.Guard(prior_seconds=prior);guard.check()
    def timeout(*_):raise g.GateError('wall_time_limit')
    signal.signal(signal.SIGALRM,timeout)
    signal.setitimer(signal.ITIMER_REAL,max(.001,g.CAPS['wall_seconds']-prior))
    marker=g.PRIVATE/'signature-readback.ONE_TIME_STARTED.private.json'
    g.acquire_marker(marker,guard,{'manifest_sha256':manifest_sha,'gate_receipt_sha256':receipt_sha,'source_bodies_read':0})
    packages=[];adapter=None;db=None;result={'schema_version':'calibration-signature-readback/0.1','status':'stopped_partial_no_retry','source_body_reads':0,'independent_review':False,'G2_admitted':False}
    try:
        cert=g.load_json(g.CERT);paths=g.artifact_paths();by_artifact={}
        for name in sorted(g.PACKAGE_ARTIFACTS):
            p=g.SignaturePackage(paths[name],cert['artifacts'][name]['sha256'],cert['package_names'][name]);packages.append(p);by_artifact[name]=p
        adapter=g.ReviewedCompatibility(g.CERT,g.CERT_SHA,artifact_paths=paths,package_by_artifact=by_artifact)
        b=next(b for b in receipt['outputs'] if Path(b['path']).name=='calibration.signatures.private.sqlite')
        own=g.SignaturePackage(b['path'],b['sha256'],'exact96_calibration');packages.append(own)
        rows=g.load_json(g.SV/'calibration96.freeze.private.json')['records'];edges=[];budget={'used':0}
        batchpaths=[b for b in receipt['outputs'] if Path(b['path']).name.startswith('comparison-batch-')]
        g.require(len(batchpaths)==12,'verify_batch_count')
        for start,b in enumerate(batchpaths):
            batch=load_gzip(b['path'])
            edges.extend(verify_batch(batch,rows[start*8:start*8+8],own,packages,adapter.coverage,by_artifact,cert['package_names'],guard,budget));guard.check()
        db=sqlite3.connect((g.SV/'metadata.registry.sqlite').as_uri()+'?mode=ro&immutable=1',uri=True)
        final,old,contam,status,counts,oldhits=independent_graph(db,rows,edges)
        graph=load_gzip(g.PRIVATE/'final-components.private.json.gz')
        g.require(graph['member_to_component']==final and set(graph['contaminated_components'])==contam and set(graph['old_contaminated_components_before_calibration_exclusion'])==old,'verify_final_graph_mismatch')
        g.require(receipt['status']==status and receipt['calibration_final_components']==counts and receipt['calibration_records_connected_to_old_exclusion']==oldhits,'verify_underfilled_decision_mismatch')
        result.update(status='signature_evidence_aliases_and_full_graph_replayed',matching_batches_verified=12,
                      full_namespaced_members=len(final),edge_evidence_count=len(edges),calibration_gate_status=status,
                      comparison_increment_count=budget['used'],manifest_sha256=manifest_sha,gate_receipt_sha256=receipt_sha)
    except BaseException as exc:
        result['error_type']=type(exc).__name__
    finally:
        if adapter:adapter.close()
        for p in packages:p.close()
        if db:db.close()
        result['resources']=guard.resources();signal.setitimer(signal.ITIMER_REAL,0);data=g.canonical(result)+b'\n'
        g.require(len(data)<=g.TERMINAL_RESERVE and guard.used()+len(data)<=g.CAPS['private_bytes'] and guard.used()-g.BASELINE+len(data)<=g.RESERVE,'verify_receipt_budget')
        with (g.PRIVATE/'signature-readback.receipt.private.json').open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest-sha256',required=True);p.add_argument('--receipt-sha256',required=True);a=p.parse_args()
    result=verify(a.manifest_sha256,a.receipt_sha256);print(json.dumps(result,sort_keys=True));sys.exit(0 if result['status']=='signature_evidence_aliases_and_full_graph_replayed' else 2)
