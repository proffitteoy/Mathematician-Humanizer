"""Synthetic adversarial tests only. Never opens natural exact96 body/cache."""
from collections import Counter
import copy
import gzip
import hashlib
import json
from pathlib import Path
import random
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import calibration_gate as g
from matcher import SignaturePackage, SignatureWriter, signature, near_copy, sha
from compatibility import expand_coverage_aliases


def member(n,project='zhwiki'):
    return g.canonical(['wikimedia',project,'page:'+str(n)]).decode()


def text(n=0):
    rand=random.Random(n)
    return ''.join(chr(0x4e00+rand.randrange(8000)) for _ in range(240))+'。'


def row(n,source='discussion',raw=None):
    raw=text(n) if raw is None else raw
    return {'record_key':'synthetic:'+str(n),'source_frame':source,'member_key':member(n),
            'component_id':g.digest([member(n)]),'source_sha256':sha(raw.encode()),
            'source_codepoints':len(raw),'metadata':{},'locator':{'synthetic_id':n}}


def record(r,raw):
    md,risks=g.gated_metadata(raw,r['metadata'])
    return {'source_risks':risks,'metadata':r,'source_sha256':r['source_sha256'],
            'projection':g.project(raw,r['source_frame'],md),'preparse':{'not_used':True},
            'rights_review':'pending_independent_record_review','human_gold':False,'raw_source_text':raw}


def cache(path,obj):
    path.write_bytes(gzip.compress(g.canonical(obj),mtime=0));return g.binding(path)


def package(path,items,name):
    w=SignatureWriter(path)
    for n,(raw,m) in enumerate(items):
        w.add(raw,source_id='synthetic',member_key=m,exposure_role='old_exposed',source_view_role='raw',
              source_object_sha256=sha(b'synthetic-object'),locator={'synthetic':n})
    b=w.finish();return SignaturePackage(path,b['sha256'],name)


class Temp(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(dir=g.PRIVATE,prefix='synthetic-');self.root=Path(self.t.name)
        self.control=self.root/'control.json';self.control.write_text('{"state":"run"}')
        self.caps={'wall_seconds':30,'rss_bytes':3*1024**3,'private_bytes':512*1024**2,'old_fingerprint_minimum_bytes':0}
        self.guard=g.Guard(roots=[self.root],old_root=self.root/'empty',control=self.control,
                           baseline=0,reserve=256*1024**2,caps=self.caps)
    def tearDown(self):self.t.cleanup()


class RecordTests(Temp):
    def test_frozen_source_bytes_used_without_bytecode_loader(self):
        self.assertIsNone(g.sys.modules['matcher'].__loader__)
        self.assertEqual(g.sys.modules['matcher'].__file__,str(g.SP/'matcher.py'))
        self.assertEqual(hashlib.sha256(g._frozen_sources['matcher.py']).hexdigest(),g.SOURCE_PINS['matcher.py'])
    def test_valid_identity_raw_projection_and_map(self):
        raw=text();r=row(0,raw=raw);obj=record(r,raw)
        out=g.load_bound_record(cache(self.root/'record.gz',obj),r)
        self.assertEqual(out,obj)
        v,s=g.record_views(out,r);self.assertEqual(len(v),3)
    def test_raw_hash_mismatch(self):
        raw=text();r=row(0,raw=raw);obj=record(r,raw);obj['raw_source_text']=raw[:-1]+'!'
        with self.assertRaisesRegex(g.GateError,'raw_source_hash'):
            g.load_bound_record(cache(self.root/'record.gz',obj),r)
    def test_mapping_mismatch_even_if_projection_digest_rehashed(self):
        raw=text();r=row(0,raw=raw);obj=record(r,raw)
        obj['projection']['segments'][0]['source_map'][0][0]=1
        p=obj['projection'];p['projection_sha256']=hashlib.sha256(g.canonical({k:v for k,v in p.items() if k!='projection_sha256'})).hexdigest()
        with self.assertRaises((ValueError,g.GateError)):
            g.load_bound_record(cache(self.root/'record.gz',obj),r)
    def test_projection_replay_rejects_omitted_segment(self):
        raw=text();r=row(0,raw=raw);obj=record(r,raw);p=obj['projection'];p['segments']=[]
        p['projection_sha256']=hashlib.sha256(g.canonical({k:v for k,v in p.items() if k!='projection_sha256'})).hexdigest()
        with self.assertRaisesRegex(g.GateError,'frozen_projection_replay'):
            g.load_bound_record(cache(self.root/'record.gz',obj),r)
    def test_record_identity_mismatch(self):
        raw=text();r=row(0,raw=raw);obj=record(r,raw);obj['metadata']['member_key']=member(99)
        with self.assertRaisesRegex(g.GateError,'cache_record_identity'):
            g.load_bound_record(cache(self.root/'record.gz',obj),row(0,raw=raw))
    def test_expansion_cap(self):
        r=row(0);obj=record(r,text())
        with patch.object(g,'RECORD_EXPANDED_CAP',100):
            with self.assertRaisesRegex(g.GateError,'cache_expansion_cap'):
                g.load_bound_record(cache(self.root/'record.gz',obj),r)
    def test_dedup_retains_all_views_and_members(self):
        raw=text();rows=[row(1,raw=raw),row(2,raw=raw)]
        caches=[cache(self.root/f'{n}.gz',record(r,raw)) for n,r in enumerate(rows)]
        artifact,counts,ids=g.build_signature_package(rows,caches,self.root/'signatures.sqlite',self.guard)
        p=SignaturePackage(artifact['path'],artifact['sha256'],'exact96_calibration')
        self.assertEqual(p.text_count,1);self.assertEqual(p.db.execute('select count(*) from bindings').fetchone()[0],6)
        sigmap=g.package_record_signatures(p,rows);self.assertEqual(len(sigmap),2)
        self.assertEqual({s.raw_sha256 for sigs in sigmap.values() for s in sigs},{sha(raw.encode())});p.close()
    def test_quarantined_zero_segment_keeps_raw_signature(self):
        raw='```\n'+text()+'\n```';r=row(0,raw=raw);obj=record(r,raw)
        artifact,counts,_=g.build_signature_package([r],[cache(self.root/'x.gz',obj)],self.root/'s.sqlite',self.guard)
        self.assertEqual(counts['role_or_zero_segment_quarantines'],1)
        p=SignaturePackage(artifact['path'],artifact['sha256'],'exact96_calibration')
        self.assertGreaterEqual(p.text_count,1);self.assertTrue(g.package_record_signatures(p,[r]));p.close()


class MatchingTests(Temp):
    def test_different_package_ids_do_not_change_digests(self):
        target=text(8);a=package(self.root/'a.sqlite',[(target,member(1))],'a')
        b=package(self.root/'b.sqlite',[(text(7),member(2)),(target,member(3))],'b')
        try:
            sig=signature(target,'target','raw')
            self.assertNotEqual(a.map_digests(sig.grams),b.map_digests(sig.grams))
            self.assertTrue(a.compare([sig])['hits']);self.assertTrue(b.compare([sig])['hits'])
        finally:a.close();b.close()
    def test_full_unmapped_denominator_not_mapped_count(self):
        rand=random.Random(30)
        shared=''.join(chr(0x4e00+rand.randrange(500)) for _ in range(64))
        left=shared+''.join(chr(0x5000+rand.randrange(500)) for _ in range(180))
        right=shared+''.join(chr(0x6000+rand.randrange(500)) for _ in range(180))
        p=package(self.root/'p.sqlite',[(right,member(2))],'p')
        try:
            sig=signature(left,'left','raw');out=p.compare([sig])
            self.assertGreater(out['candidate_full_gram_counts'][0],out['candidate_mapped_gram_counts'][0])
            self.assertFalse(out['hits'])
            self.assertFalse(near_copy(60,240,240))
        finally:p.close()
    def test_calibration_mutual_collision_and_all_binding_aliases(self):
        raw=text(12);rows=[row(1,raw=raw),row(2,raw=raw)]
        own=package(self.root/'own.sqlite',[(raw,member(1)),(raw,member(2))],'exact96_calibration')
        c=sqlite3.connect(':memory:');c.execute('create table segments(old_raw_sha256,segment_index,coverage_kind,reference_text_id)')
        try:
            comp=own.compare([signature(raw,'candidate','raw')])
            receipt={'packages':[comp],'source_sha256':sha(raw.encode())}
            edges=expand_coverage_aliases(receipt,member(1),coverage_db=c,
                   package_by_artifact={'old_raw_database':own,'three_blog_raw_database':own},
                   package_names={'old_raw_database':'old','projected_database':'projected'})
            self.assertEqual({e['right_member_key'] for e in edges},{member(2)})
        finally:own.close();c.close()
    def test_incomplete_package_rejected(self):
        p=package(self.root/'p.sqlite',[(text(),member(1))],'p');p.close()
        db=sqlite3.connect(self.root/'p.sqlite');db.execute("update control set value='partial' where key='status'");db.commit();db.close()
        with self.assertRaisesRegex(g.CompatibilityError,'package_contract_incomplete'):
            SignaturePackage(self.root/'p.sqlite',g.filehash(self.root/'p.sqlite'),'p')
    def test_pair_cap_fails_no_implicit_retry(self):
        p=package(self.root/'p.sqlite',[(text(),member(1))],'p');budget={'used':0,'cap':1}
        try:
            with self.assertRaisesRegex(g.BoundExceeded,'aggregate_comparison_increment_cap'):
                p.compare([signature(text(),'new','raw')],comparison_budget=budget)
            self.assertGreater(budget['used'],budget['cap'])
        finally:p.close()
    def test_missing_fourth_package_rejected(self):
        r=row(1)
        with self.assertRaisesRegex(g.GateError,'required_four_signature_packages'):
            g.compare_batch([r],{r['record_key']:[signature(text(1),'v','raw')]},[],self.guard,{'used':0,'cap':100})


class GraphTests(unittest.TestCase):
    def graph(self):
        d=g.DSU();rows=[]
        for i in range(96):
            r=row(i, g.SOURCES[i//32]);rows.append(r);d.add(r['member_key'])
        d.expose(member(1000));d.add(member(1001));d.union(member(1000),member(1001),'old_component')
        return d,rows
    def test_valid_32_each_checked_before_exclusion(self):
        d,rows=self.graph();graph,agg=g.finish_graph(d,rows)
        self.assertEqual(agg['status'],'calibration_copy_gate_complete_pending_independent_review')
        self.assertEqual(len(graph['contaminated_components']),97)
        self.assertEqual(agg['calibration_records_connected_to_old_exclusion'],0)
    def test_cal_to_cal_same_source_underfilled(self):
        d,rows=self.graph();d.union(member(0),member(1),'copy_edge');graph,a=g.finish_graph(d,rows)
        self.assertEqual(a['status'],'calibration_underfilled');self.assertEqual(a['calibration_final_components']['discussion'],31)
    def test_cross_source_collision_underfilled(self):
        d,rows=self.graph();d.union(member(0),member(32),'copy_edge');_,a=g.finish_graph(d,rows)
        self.assertEqual(a['status'],'calibration_underfilled');self.assertEqual(set(a['calibration_final_components'].values()),{32})
    def test_old_new_component_id_changes_but_exclusion_propagates(self):
        d,rows=self.graph();oldid=d.freeze()[0][member(1000)];d.union(member(0),member(1001),'copy_edge')
        graph,a=g.finish_graph(d,rows)
        self.assertNotEqual(oldid,graph['member_to_component'][member(1000)])
        self.assertEqual(a['status'],'calibration_underfilled');self.assertEqual(a['calibration_records_connected_to_old_exclusion'],1)
    def test_reconstruct_full_namespaced_dsu(self):
        d,rows=self.graph();mapping,excluded=d.freeze();db=sqlite3.connect(':memory:')
        db.executescript('create table members(member_key,component_id,excluded);create table lineage(a,b,kind);')
        db.executemany('insert into members values(?,?,?)',[(m,c,int(c in excluded)) for m,c in mapping.items()])
        db.execute('insert into lineage values(?,?,?)',(member(1000),member(1001),'old_component'))
        rebuilt,old,exp=g.reconstruct_graph(db);self.assertEqual(rebuilt.freeze()[0],mapping)
        self.assertEqual(rebuilt.freeze()[1],excluded);db.close()
    def test_metadata_noncanonical_component_rejected(self):
        db=sqlite3.connect(':memory:');db.executescript('create table members(member_key,component_id,excluded);create table lineage(a,b,kind);')
        db.execute('insert into members values(?,?,?)',(member(1),'a'*64,0))
        with self.assertRaisesRegex(g.GateError,'base_component_hash_mismatch'):g.reconstruct_graph(db)
        db.close()
    def test_unknown_member_edge_fails_closed(self):
        d,rows=self.graph()
        with self.assertRaisesRegex(g.GateError,'copy_edge_member_missing'):
            g.apply_edges(d,[{'left_member_key':member(0),'right_member_key':member(9999),'reasons':['raw_exact']}])


class ControlTests(Temp):
    def test_no_implicit_retry_marker_persists(self):
        p=self.root/'marker.json';g.acquire_marker(p,self.guard,{'synthetic':True})
        with self.assertRaisesRegex(g.GateError,'one_time_stage_already_consumed'):g.acquire_marker(p,self.guard,{'synthetic':True})
        self.assertTrue(p.exists())
    def test_stop(self):
        self.control.write_text('{"state":"stop"}')
        with self.assertRaisesRegex(g.GateError,'operator_stop'):self.guard.check()
    def test_pause_consumes_wallclock(self):
        self.guard.caps['wall_seconds']=.04;self.control.write_text('{"state":"pause"}')
        with self.assertRaisesRegex(g.GateError,'wall_time_limit'):self.guard.check()
    def test_pause_run(self):
        self.control.write_text('{"state":"pause"}')
        def release():time.sleep(.05);self.control.write_text('{"state":"run"}')
        thread=threading.Thread(target=release);thread.start();self.guard.check();thread.join()
    def test_invalid_control(self):
        self.control.write_text('{"state":"run","anything":true}')
        with self.assertRaisesRegex(g.GateError,'invalid_control'):self.guard.check()
    def test_shared_stage_cap_counts_other_root_and_temporary(self):
        other=self.root/'source';other.mkdir();(other/'temp-journal').write_bytes(b'x'*100)
        self.guard.reserve=100
        with self.assertRaisesRegex(g.GateError,'shared_exact96'):self.guard.check()
    def test_global_cap_counts_old_and_gate(self):
        self.guard.caps['private_bytes']=4096
        with self.assertRaisesRegex(g.GateError,'all_private_derivatives_cap'):self.guard.check()
    def test_prior_shared_wallclock_charged(self):
        self.guard.prior_seconds=31
        with self.assertRaisesRegex(g.GateError,'wall_time_limit'):self.guard.check()
    def test_no_candidate_frame_creation_api(self):
        self.assertFalse(hasattr(g,'freeze_candidates'))
        source=Path(g.__file__).read_text()
        self.assertNotIn('registry.freeze_candidates(',source)
        self.assertNotIn('candidate6000.freeze.private.json',source)
    def test_source_implementation_GO_is_not_matching_GO(self):
        # Policy is a distinct action string and real execute cannot skip authority.
        code=Path(g.__file__).read_text();self.assertIn("go.get('action')=='CALIBRATION_COPY_GATE_GO'",code)
        self.assertNotIn("go.get('action')=='SOURCE_IMPLEMENTATION_GO'",code)


class FullSyntheticTests(Temp):
    def test_exact96_batch_and_independent_readback_clean_calcal_calold(self):
        import verify_gate as v
        for mode in ('clean','calcal','calold'):
            with self.subTest(mode=mode):
                root=self.root/mode;root.mkdir();rows=[];caches=[]
                for i in range(96):
                    raw=text(i)
                    if mode=='calcal' and i==33:raw=text(0)
                    if mode=='calold' and i==0:raw=text(1000)
                    r=row(i,g.SOURCES[i//32],raw);rows.append(r);caches.append(cache(root/f'{i}.gz',record(r,raw)))
                artifact,counts,_=g.build_signature_package(rows,caches,root/'own.sqlite',self.guard)
                own=SignaturePackage(artifact['path'],artifact['sha256'],'exact96_calibration')
                old=package(root/'old.sqlite',[(text(1000),member(1000)),(text(1000),member(1001))],'old')
                three=package(root/'three.sqlite',[(text(1002),member(1002))],'three')
                proj=package(root/'proj.sqlite',[(text(1003),member(1003))],'proj')
                packages=[old,three,proj,own]
                coverage=sqlite3.connect(':memory:');coverage.execute('create table segments(old_raw_sha256,segment_index,coverage_kind,reference_text_id)')
                names={'old_raw_database':'old','three_blog_raw_database':'three','projected_database':'proj'}
                by={'old_raw_database':old,'three_blog_raw_database':three,'projected_database':proj}
                dsu=g.DSU();db=sqlite3.connect(':memory:');db.executescript('create table members(member_key,component_id,excluded);create table lineage(a,b,kind);')
                for r in rows:dsu.add(r['member_key']);db.execute('insert into members values(?,?,?)',(r['member_key'],g.digest([r['member_key']]),0))
                for i in range(1000,1004):dsu.expose(member(i));db.execute('insert into members values(?,?,?)',(member(i),g.digest([member(i)]),1))
                all_edges=[];budget={'used':0,'cap':g.INCREMENT_CAP};verify_budget={'used':0}
                try:
                    for start in range(0,96,8):
                        batchrows=rows[start:start+8];sigmap=g.package_record_signatures(own,batchrows)
                        receipts=g.compare_batch(batchrows,sigmap,packages,self.guard,budget);edges=[]
                        for r,receipt in zip(batchrows,receipts):
                            edges.extend(expand_coverage_aliases(receipt,r['member_key'],coverage_db=coverage,
                                package_by_artifact=by,package_names=names))
                        g.apply_edges(dsu,edges);all_edges.extend(edges)
                        batch={'record_keys':[r['record_key'] for r in batchrows],'receipts':receipts,'expanded_edges':edges}
                        self.assertEqual(v.verify_batch(batch,batchrows,own,packages,coverage,by,names,self.guard,verify_budget),edges)
                    graph,agg=g.finish_graph(dsu,rows)
                    final,oldcontam,contam,status,sources,oldhits=v.independent_graph(db,rows,all_edges)
                    self.assertEqual(graph['member_to_component'],final);self.assertEqual(set(graph['contaminated_components']),contam)
                    self.assertEqual(status,agg['status'])
                    self.assertEqual(status,'calibration_copy_gate_complete_pending_independent_review' if mode=='clean' else 'calibration_underfilled')
                    if mode=='calold':
                        self.assertEqual(oldhits,1)
                        self.assertEqual(final[member(0)],final[member(1000)])
                        self.assertEqual(final[member(0)],final[member(1001)])
                finally:
                    for p in packages:p.close()
                    db.close();coverage.close()
    def test_projected_hit_expands_all_old_raw_aliases_and_verifies(self):
        import verify_gate as v
        raw=text(2000);oldraw=text(2001);r=row(0,raw=raw)
        artifact,_,_=g.build_signature_package([r],[cache(self.root/'x.gz',record(r,raw))],self.root/'own.sqlite',self.guard)
        own=SignaturePackage(artifact['path'],artifact['sha256'],'exact96_calibration')
        old=package(self.root/'old.sqlite',[(oldraw,member(1000)),(oldraw,member(1001))],'old')
        three=package(self.root/'three.sqlite',[(text(2002),member(1002))],'three')
        proj=package(self.root/'proj.sqlite',[(raw,member(1000))],'proj');packages=[old,three,proj,own]
        coverage=sqlite3.connect(':memory:');coverage.execute('create table segments(old_raw_sha256,segment_index,coverage_kind,reference_text_id)')
        coverage.execute('insert into segments values(?,?,?,?)',(sha(oldraw.encode()),0,'new_projected_signature',1))
        names={'old_raw_database':'old','three_blog_raw_database':'three','projected_database':'proj'}
        by={'old_raw_database':old,'three_blog_raw_database':three,'projected_database':proj}
        try:
            receipts=g.compare_batch([r],g.package_record_signatures(own,[r]),packages,self.guard,{'used':0,'cap':g.INCREMENT_CAP})
            edges=expand_coverage_aliases(receipts[0],r['member_key'],coverage_db=coverage,package_by_artifact=by,package_names=names)
            self.assertEqual({e['right_member_key'] for e in edges},{member(1000),member(1001)})
            batch={'record_keys':[r['record_key']],'receipts':receipts,'expanded_edges':edges}
            v.verify_batch(batch,[r],own,packages,coverage,by,names,self.guard,{'used':0})
            altered=copy.deepcopy(batch);altered['expanded_edges']=[e for e in edges if e['right_member_key']!=member(1001)]
            with self.assertRaisesRegex(g.GateError,'verify_alias_edge_set_mismatch'):
                v.verify_batch(altered,[r],own,packages,coverage,by,names,self.guard,{'used':0})
        finally:
            for p in packages:p.close()
            coverage.close()
    def test_verifier_rejects_full_denominator_tampering(self):
        import verify_gate as v
        p=package(self.root/'p.sqlite',[(text(),member(1))],'p')
        try:
            sig=signature(text(),'view','raw');truth=v.replay(p,[sig],self.guard,{'used':0})
            self.assertEqual(truth[('view',1)]['candidate_full_gram_count'],len(sig.grams))
            self.assertEqual(truth[('view',1)]['shared_distinct_grams'],len(sig.grams))
            with self.assertRaisesRegex(g.GateError,'verify_gram_count_mismatch'):
                v.ids(g.pack_ids([1,2]),3,2)
        finally:p.close()

class ComparisonBudgetTests(Temp):
    def test_prior_gate_and_readback_share_low_cap(self):
        gate={'used':2,'cap':6};g.precharge_comparisons(gate,3)
        receipt={'status':'calibration_copy_gate_complete_pending_independent_review','comparison_budget_scope':g.COMPARISON_SCOPE,'comparison_prior_increment_count':2,'comparison_increment_delta':3,'comparison_increment_count':gate['used']}
        prior=g.checked_comparison_total(2,receipt);self.assertEqual(prior,5)
        readback={'used':prior,'cap':6};g.precharge_comparisons(readback,1)
        with self.assertRaisesRegex(g.GateError,'global_comparison_increment_cap'):g.precharge_comparisons(readback,1)
        self.assertEqual(readback['used'],6)
    def test_partial_predecessor_stops(self):
        r={'status':'stopped_partial_no_retry','comparison_budget_scope':g.COMPARISON_SCOPE,'comparison_prior_increment_count':1,'comparison_increment_delta':1,'comparison_increment_count':2}
        with self.assertRaisesRegex(g.GateError,'incomplete'):g.checked_comparison_total(1,r)
    def test_changed_total_or_prior_rejected(self):
        r={'status':'calibration_underfilled','comparison_budget_scope':g.COMPARISON_SCOPE,'comparison_prior_increment_count':2,'comparison_increment_delta':3,'comparison_increment_count':4}
        with self.assertRaisesRegex(g.GateError,'total_invalid'):g.checked_comparison_total(2,r)
        r['comparison_increment_count']=5
        with self.assertRaisesRegex(g.GateError,'chain_mismatch'):g.checked_comparison_total(3,r)
    def test_natural_prior_requires_all_bound_completion_files(self):
        prior=self.root/'prior.json';marker=self.root/'marker.json';done=self.root/'done.json'
        prior.write_bytes(g.canonical({'comparison_budget':{'used':7,'cap':g.INCREMENT_CAP}}));h=g.filehash(prior)
        marker.write_text('{}');done.write_bytes(g.canonical({'status':'complete_pending_independent_review','public_aggregate_sha256':h}))
        with patch.multiple(g,COMPARISON_PRIOR=prior,COMPARISON_PRIOR_SHA=h,COMPARISON_MARKER=marker,COMPARISON_COMPLETE=done):
            history=g.comparison_history();self.assertEqual(history['used'],7);self.assertEqual(len(history['bindings']),3)
            done.unlink()
            with self.assertRaisesRegex(g.GateError,'missing_or_partial'):g.comparison_history()
    def test_replay_checks_cap_before_shared_Counter_update(self):
        import verify_gate as v
        p=package(self.root/'cap.sqlite',[(text(),member(1))],'p');events=[]
        class TrackingCounter(Counter):
            def update(self,iterable=None,**kwargs):
                if iterable:events.append(tuple(iterable))
                return super().update(iterable,**kwargs)
        try:
            budget={'used':7,'cap':10}
            with patch.object(v,'Counter',TrackingCounter),self.assertRaisesRegex(g.GateError,'global_comparison_increment_cap'):
                v.replay(p,[signature(text(),'v','raw')],self.guard,budget)
            self.assertEqual(events,[]);self.assertEqual(budget['used'],10)
        finally:p.close()
    def test_replay_exact_hit_precharge(self):
        import verify_gate as v
        p=package(self.root/'exactcap.sqlite',[(text(),member(1))],'p')
        try:
            budget={'used':1,'cap':1}
            with self.assertRaisesRegex(g.GateError,'global_comparison_increment_cap'):v.replay(p,[signature(text(),'v','raw')],self.guard,budget)
            self.assertEqual(budget['used'],1)
        finally:p.close()

class AuditStorageTests(Temp):
    def test_production_reserve_counts_audits_even_below_allowance(self):
        guard=g.Guard(roots=None,old_root=self.root/'old',control=self.control,baseline=0,reserve=10**9,caps=self.caps)
        guard.roots=[self.root/'empty']
        with patch.object(g,'audit_private_usage',return_value=123):self.assertEqual(guard.used(),g.AUDIT_ALLOWANCE)
    def test_audit_growth_beyond_allowance_stops(self):
        guard=g.Guard(roots=None,old_root=self.root/'old',control=self.control,baseline=0,reserve=10**9,caps=self.caps)
        guard.roots=[]
        with patch.object(g,'audit_private_usage',return_value=g.AUDIT_ALLOWANCE+1),self.assertRaisesRegex(g.GateError,'audit_private_allowance_exceeded'):guard.used()

if __name__=='__main__':unittest.main()
