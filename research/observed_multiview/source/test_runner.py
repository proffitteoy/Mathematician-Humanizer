"""Synthetic-only registry/runner verification. No natural body adapters executed."""
import bz2
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import zipfile
import registry as R
import runner as U


def synthetic_records(n=34):
    rows=[]
    for source in R.SOURCES:
        for i in range(n):
            member=R.member_key('synthetic',source,str(i));component=R.digest([member])
            rows.append({'record_key':source+':'+str(i),'source_frame':source,'member_key':member,'component_id':component,'source_sha256':hashlib.sha256(b'not a body').hexdigest(),'source_codepoints':222,'locator':{},'metadata':{}})
    return rows

class RegistryTests(unittest.TestCase):
    def test_alias_integer_identity(self):
        self.assertEqual(R.wiki_member('wikiconv','zhwiki','0001'),R.wiki_member('mediawiki','zhwiki','1'))
        self.assertNotEqual(R.wiki_member('mediawiki','zhwikinews','1'),R.wiki_member('mediawiki','zhwikivoyage','1'))
    def test_unknown_alias_rejected(self):
        with self.assertRaisesRegex(R.GateError,'unknown_source_alias'):R.wiki_member('owner-blog','zhwiki','1')
        with self.assertRaisesRegex(R.GateError,'invalid_page_id'):R.wiki_member('discussion','zhwiki','-1')
    def test_old_component_contamination_after_new_union(self):
        d=R.DSU();a,b,c=[R.member_key('synthetic','p',str(i)) for i in range(3)]
        d.expose(a);d.union(a,b,'old_component');old=d.freeze()[0][a]
        d.union(b,c,'concrete_unresolved');m,e=d.freeze();self.assertNotEqual(old,m[a]);self.assertEqual(len(set(m.values())),1);self.assertIn(m[c],e)
    def test_broad_geography_is_not_union_kind(self):
        d=R.DSU()
        with self.assertRaisesRegex(R.GateError,'unknown_lineage_kind'):d.union(R.member_key('s','p','a'),R.member_key('s','p','b'),'broad_region')
    def test_exact96_stable_and_component_first(self):
        rows=synthetic_records();a,c=R.choose_calibration(rows,set());b,_=R.choose_calibration(list(reversed(rows)),set());self.assertEqual(a,b);self.assertEqual(Counter(r['source_frame'] for r in a),Counter({s:32 for s in R.SOURCES}))
        dup=dict(rows[0],record_key='a-hash-other-record');rows.append(dup);a,_=R.choose_calibration(rows,set());self.assertEqual(len({r['component_id'] for r in a}),96)
    def test_excluded_component_cannot_be_selected(self):
        rows=synthetic_records();excluded={rows[0]['component_id']};chosen,_=R.choose_calibration(rows,excluded);self.assertFalse({r['component_id'] for r in chosen}&excluded)
    def test_underfilled_no_replacement_from_other_source(self):
        with self.assertRaisesRegex(R.GateError,'underfilled'):R.choose_calibration(synthetic_records(31),set())
    def test_new_merge_cannot_replenish_calibration(self):
        rows,_=R.choose_calibration(synthetic_records(),set());m={r['member_key']:r['component_id'] for r in rows};m[rows[1]['member_key']]=m[rows[0]['member_key']]
        with self.assertRaisesRegex(R.GateError,'calibration_underfilled'):R.check_final_calibration(rows,m)
    def test_calibration_old_contamination_stops(self):
        rows,_=R.choose_calibration(synthetic_records(),set());m={r['member_key']:r['component_id'] for r in rows}
        with self.assertRaisesRegex(R.GateError,'calibration_old_contamination'):R.check_final_calibration(rows,m,{rows[0]['component_id']})
    def test_final_graph_rebuild_rejects_lost_contamination(self):
        a,b=[R.member_key('synthetic','p',str(i)) for i in range(2)];component=R.digest(sorted([a,b]));db=sqlite3.connect(':memory:');db.execute('create table members(member_key,component_id,excluded)');db.executemany('insert into members values(?,?,?)',[(a,'old',1),(b,'old',1)])
        with self.assertRaisesRegex(R.GateError,'lost_old_contamination'):R.verify_final_graph({'member_to_component':{a:component,b:component},'contaminated_components':[]},db)
        self.assertEqual(R.verify_final_graph({'member_to_component':{a:component,b:component},'contaminated_components':[component]},db)[2],{component});db.close()
    def test_final_graph_rebuild_rejects_split_ancestor(self):
        a,b=[R.member_key('synthetic','p',str(i)) for i in range(2)];db=sqlite3.connect(':memory:');db.execute('create table members(member_key,component_id,excluded)');db.executemany('insert into members values(?,?,?)',[(a,'old',0),(b,'old',0)])
        with self.assertRaisesRegex(R.GateError,'split_known_ancestor'):R.verify_final_graph({'member_to_component':{a:R.digest([a]),b:R.digest([b])},'contaminated_components':[]},db)
        db.close()
    def test_candidate_freeze_before_review_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);rev=root/'review.json';graph=root/'graph.json';R.write_new(rev,{'decision':'IMPLEMENTATION_ONLY'});R.write_new(graph,{})
            with patch.object(R,'PRIVATE',root):
                with self.assertRaises((R.GateError,FileNotFoundError)):R.freeze_candidates(rev,R.filehash(rev),graph,R.filehash(graph))

class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.private=self.root/'private';self.private.mkdir();self.old=self.root/'old';self.old.mkdir();self.control=self.private/'control.json';self.control.write_text('{"state":"run"}')
        self.caps={'wall_seconds':10,'rss_bytes':3*1024**3,'private_bytes':100000,'old_fingerprint_minimum_bytes':100}
        self.g=U.Guard(self.private,self.old,self.control,self.caps)
    def tearDown(self):self.temp.cleanup()
    def test_stop_per_record(self):
        self.g.check();self.control.write_text('{"state":"stop"}')
        with self.assertRaisesRegex(R.GateError,'operator_stop'):self.g.check()
    def test_pause_waits_until_run(self):
        self.control.write_text('{"state":"pause"}');thread=threading.Thread(target=lambda:(time.sleep(.15),self.control.write_text('{"state":"run"}')));thread.start();start=time.monotonic();self.g.check();thread.join();self.assertGreaterEqual(time.monotonic()-start,.15)
    def test_pause_can_stop(self):
        self.control.write_text('{"state":"pause"}');thread=threading.Thread(target=lambda:(time.sleep(.15),self.control.write_text('{"state":"stop"}')));thread.start()
        with self.assertRaisesRegex(R.GateError,'operator_stop'):self.g.check()
        thread.join()
    def test_bad_control_fails_closed(self):
        self.control.write_text('{"state":"go"}')
        with self.assertRaisesRegex(R.GateError,'invalid_control'):self.g.check()
    def test_wall_limit_includes_prior_elapsed(self):
        self.g.prior_seconds=11
        with self.assertRaisesRegex(R.GateError,'wall_time_limit'):self.g.check()
    def test_private_byte_limit_includes_old(self):
        self.g.caps['old_fingerprint_minimum_bytes']=100001
        with self.assertRaisesRegex(R.GateError,'private_byte_limit'):self.g.check()
    def test_actual_old_bytes_override_minimum(self):
        (self.old/'old').write_bytes(b'x'*100001)
        with self.assertRaisesRegex(R.GateError,'private_byte_limit'):self.g.check()
    def test_future_write_budget_checked(self):
        with self.assertRaisesRegex(R.GateError,'private_byte_limit'):self.g.write(self.private/'large',{'x':'x'*100000})
        self.assertFalse((self.private/'large').exists())
    def test_marker_never_overwritten(self):
        p=self.private/'ONE_TIME_STARTED.json';self.g.write(p,{'consumed':True})
        with self.assertRaisesRegex(R.GateError,'already_exists'):self.g.write(p,{'consumed':False})
        self.assertTrue(json.loads(p.read_text())['consumed'])
    def test_preread_exposure_full_list_is_durable(self):
        rows,_=R.choose_calibration(synthetic_records(),set());self.g.caps['private_bytes']=1000000;U.preread_exposure(self.g,'calibration',rows,'a'*64)
        entries=[json.loads(x) for x in (self.private/'exposure.private.jsonl').read_text().splitlines()];self.assertEqual(len(entries),96);self.assertTrue(all(e['body_opened_yet'] is False and e['exclude_entire_final_component'] for e in entries))
    def test_candidates_not_mislabeled_human_exposure(self):
        U.preread_exposure(self.g,'candidates',synthetic_records(),'a'*64);self.assertFalse((self.private/'exposure.private.jsonl').exists())
    def test_compressed_write_roundtrip(self):
        import gzip
        p=self.private/'artifact.gz';self.g.write_compressed(p,{'text':'synthetic'*500});self.assertEqual(json.loads(gzip.decompress(p.read_bytes())),{'text':'synthetic'*500})

class SyntheticAdapters(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.private=self.root/'private';self.private.mkdir();self.old=self.root/'old';self.old.mkdir();(self.private/'control.json').write_text('{"state":"run"}')
        self.guard=U.Guard(self.private,self.old,caps={'wall_seconds':10,'rss_bytes':3*1024**3,'private_bytes':1000000,'old_fingerprint_minimum_bytes':0})
        self.text=('这是合成测试文本，不属于任何自然来源。\n'*15)
    def tearDown(self):self.temp.cleanup()
    def row(self,source,loc):return {'record_key':'synthetic','source_frame':source,'member_key':'synthetic','source_sha256':hashlib.sha256(self.text.encode()).hexdigest(),'source_codepoints':len(self.text),'locator':loc,'metadata':{}}
    def wiki_spec(self,xml):
        p=self.root/'fixture.xml.bz2';p.write_bytes(bz2.compress(xml.encode()));return {'path':str(p),'sha256':R.filehash(p),'bytes':p.stat().st_size,'expanded_bytes':len(xml.encode())}
    def test_selected_xml_identity_and_unselected_discard(self):
        xml='<mediawiki><page><title>Ignored</title><ns>0</ns><id>99</id><revision><id>99</id><text>ignored</text></revision></page><page><title>Synthetic</title><ns>0</ns><id>1</id><revision><id>2</id><timestamp>2017-01-01T00:00:00Z</timestamp><contributor><id>999</id></contributor><text>'+self.text+'</text></revision></page></mediawiki>'
        row=self.row('news_prose',{'page_id':'1','revision_id':'2','revision_timestamp':'2017-01-01T00:00:00Z'});spec=self.wiki_spec(xml)
        with patch.dict(U.RAW_OBJECTS,{'news_prose':spec}):self.assertEqual(list(U.stream_wiki('news_prose',[row],self.guard)),[(row,self.text)])
    def test_dtd_is_refused(self):
        xml='<!DOCTYPE mediawiki [<!ENTITY x "test">]><mediawiki></mediawiki>';spec=self.wiki_spec(xml)
        with patch.dict(U.RAW_OBJECTS,{'news_prose':spec}):
            with self.assertRaisesRegex(R.GateError,'DTD'):list(U.stream_wiki('news_prose',[],self.guard))
    def test_missing_xml_selection_fails(self):
        spec=self.wiki_spec('<mediawiki></mediawiki>');row=self.row('news_prose',{'page_id':'1'})
        with patch.dict(U.RAW_OBJECTS,{'news_prose':spec}):
            with self.assertRaisesRegex(R.GateError,'selected_count'):list(U.stream_wiki('news_prose',[row],self.guard))
    def test_selected_source_hash_mismatch(self):
        row=self.row('discussion',{})
        with self.assertRaisesRegex(R.GateError,'identity_mismatch'):U.checked_text(row,self.text+'changed')
    def test_discussion_synthetic_archive_smoke(self):
        record={'id':'synthetic-id','speaker':'s','conversation_id':'c','reply-to':None,'timestamp':1483228800,'text':self.text,'meta':{'is_section_header':False}}
        payload={n:b'{}' for n in ('speakers.json','conversations.json','corpus.json','index.json')};payload['utterances.jsonl']=json.dumps(record,ensure_ascii=False).encode()+b'\n';p=self.root/'fixture.zip'
        with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
            for n,data in payload.items():z.writestr(n,data)
        spec={'path':str(p),'sha256':R.filehash(p),'bytes':p.stat().st_size,'expanded_bytes':sum(map(len,payload.values()))};row=self.row('discussion',{'rownum':1,'byte_offset':0,'id':'synthetic-id','conversation':'c'})
        with patch.dict(U.RAW_OBJECTS,{'discussion':spec}):self.assertEqual(list(U.stream_discussion([row],self.guard)),[(row,self.text)])

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.p=patch.object(U,'PRIVATE',self.root);self.p.start();self.codes=patch.object(U,'source_code_bindings',return_value=[]);self.codes.start()
        db=self.root/'metadata.registry.sqlite';db.write_bytes(b'synthetic metadata');registry={'input_bindings':[],'metadata_database':R.binding(db)};R.write_new(self.root/'source-registry.private.json',registry)
        records,_=R.choose_calibration(synthetic_records(),set());freeze={'records':records,'records_sha256':R.digest(records),'replacement_allowed':False,'registry_sha256':R.filehash(self.root/'source-registry.private.json')};R.write_new(self.root/'calibration96.freeze.private.json',freeze)
        self.contract={'schema_version':'scale10-source-execution-contract/1','stage':'calibration','fixed_private_root':str(self.root),'caps':U.CAPS,'stage_output_budget_bytes':U.CALIBRATION_OUTPUT_BUDGET,'candidates_execution_blocked_until_fingerprint_writer_integrated':True,'source_only':True,'replacement_allowed':False,'human_gold':False,'body_eligibility_before_freeze':False,'one_time_marker':str(self.root/'calibration.ONE_TIME_STARTED.json'),'runtime':{'python_version':sys.version,'unicode_version':U.unicodedata.unidata_version,'executable':R.binding(Path(sys.executable).resolve())},'code_bindings':[],'indirect_bindings':U.indirect_bindings(),'source_bindings':[],'prior_budget_bindings':U.prior_budget_bindings(),'registry':R.binding(self.root/'source-registry.private.json'),'freeze':R.binding(self.root/'calibration96.freeze.private.json'),'metadata_database':R.binding(db)}
        self.c=self.root/'contract.json';R.write_new(self.c,self.contract);self.ch=R.filehash(self.c);self.review=self.root/'review.json';R.write_new(self.review,{'decision':'APPROVE_CALIBRATION_EXECUTION','contract_sha256':self.ch,'reviewer':'synthetic independent reviewer','synthetic_tests_passed':True});self.rh=R.filehash(self.review);self.go=self.root/'go.json';R.write_new(self.go,{'action':'CALIBRATION_GO','actor':'root','contract_sha256':self.ch,'review_sha256':self.rh,'no_other_stages':True})
    def tearDown(self):self.codes.stop();self.p.stop();self.temp.cleanup()
    def verify(self,sha=None):return U.verify_contract('calibration',self.c,sha or self.ch,self.review,self.rh,self.go)
    def test_fully_bound_contract(self):self.assertEqual(len(self.verify()[1]['records']),96)
    def test_independently_supplied_hash_not_self_receipt(self):
        with self.assertRaisesRegex(R.GateError,'independent_contract_hash_mismatch'):self.verify('0'*64)
    def test_implementation_GO_cannot_read_bodies(self):
        data=json.loads(self.go.read_text());data['action']='SOURCE_IMPLEMENTATION_GO';self.go.write_bytes(R.canonical(data))
        with self.assertRaisesRegex(R.GateError,'explicit_stage_GO_required'):self.verify()
    def test_review_sha_changed(self):
        self.review.write_text('{}')
        with self.assertRaisesRegex(R.GateError,'independent_review_hash_mismatch'):self.verify()
    def test_freeze_tampering_rejected(self):
        (self.root/'calibration96.freeze.private.json').write_text('{}')
        with self.assertRaisesRegex(R.GateError,'bound_file_changed'):self.verify()
    def test_GO_other_stages_refused(self):
        data=json.loads(self.go.read_text());data['no_other_stages']=False;self.go.write_bytes(R.canonical(data))
        with self.assertRaisesRegex(R.GateError,'GO_scope_required'):self.verify()

class PipelineTests(unittest.TestCase):
    def test_full_synthetic_driver_preread96_and_qualify_raw_argument(self):
        with tempfile.TemporaryDirectory() as td:
            private=Path(td);(private/'control.json').write_text('{"state":"run"}');go=private/'go';go.write_text('synthetic')
            text='\n'.join('这是合成的中文叙述内容用于检查边界以及调用参数'+str(i)+'。' for i in range(12))
            rows,_=R.choose_calibration(synthetic_records(),set())
            for r in rows:r['source_sha256']=hashlib.sha256(text.encode()).hexdigest();r['source_codepoints']=len(text)
            freeze={'records':rows};fb=private/'freeze';R.write_new(fb,freeze);rb=private/'registry';R.write_new(rb,{'synthetic':True})
            contract={'code_bindings':[],'indirect_bindings':[],'freeze':R.binding(fb),'registry':R.binding(rb)}
            def check_before_read(wanted,guard):
                exposure=(private/'exposure.private.jsonl').read_text().splitlines();self.assertEqual(len(exposure),96)
                for row in wanted:yield row,text
            with patch.object(U,'PRIVATE',private),patch.object(U,'verify_contract',return_value=(contract,freeze)),patch.object(U,'install_offline_sandbox',return_value={'synthetic_only':True}),patch.object(U.resource,'setrlimit'),patch.object(U.signal,'signal'),patch.object(U.signal,'setitimer'),patch.object(U,'stream_discussion',side_effect=check_before_read),patch.object(U,'stream_wiki',side_effect=lambda source,wanted,guard:check_before_read(wanted,guard)):
                receipt=U.execute('calibration',fb,'a'*64,rb,'b'*64,go)
                self.assertEqual(sum(receipt['actual_read_counts'].values()),96);self.assertEqual(sum(receipt['projection_attempt_counts'].values()),96);self.assertEqual(sum(receipt['counts'].values()),96);self.assertEqual(receipt['model_or_POS_or_target_calls'],0)
                self.assertEqual(len(list((private/'calibration.records').glob('*.json.gz'))),96)
                with self.assertRaisesRegex(R.GateError,'already_consumed'):U.execute('calibration',fb,'a'*64,rb,'b'*64,go)


class AmendedAccountingTests(unittest.TestCase):
    def pipeline_fixture(self,private,text,fail):
        (private/'control.json').write_text('{"state":"run"}');go=private/'go';go.write_text('synthetic')
        row=synthetic_records(1)[0];row['source_sha256']=hashlib.sha256(text.encode()).hexdigest();row['source_codepoints']=len(text);freeze={'records':[row]};fb=private/'freeze';R.write_new(fb,freeze);rb=private/'registry';R.write_new(rb,{'synthetic':True});contract={'code_bindings':[],'indirect_bindings':[],'freeze':R.binding(fb),'registry':R.binding(rb)}
        import project_wikitext
        original=project_wikitext.project
        with patch.object(U,'PRIVATE',private),patch.object(U,'verify_contract',return_value=(contract,freeze)),patch.object(U,'install_offline_sandbox',return_value={'synthetic_only':True}),patch.object(U.resource,'setrlimit'),patch.object(U.signal,'signal'),patch.object(U.signal,'setitimer'),patch.object(U,'stream_discussion',return_value=iter([(row,text)])),patch.object(project_wikitext,'project',side_effect=RuntimeError('synthetic_projection_failure') if fail else original):
            if fail:
                with self.assertRaisesRegex(RuntimeError,'synthetic_projection_failure'):U.execute('calibration',fb,'a'*64,rb,'b'*64,go)
                return R.load_json(private/'calibration.receipt.private.json'),row
            return U.execute('calibration',fb,'a'*64,rb,'b'*64,go),row
    def test_failed_projection_has_actual_read_and_private_identity(self):
        with tempfile.TemporaryDirectory() as td:
            private=Path(td);receipt,row=self.pipeline_fixture(private,'中文合成测试。'*40,True)
            self.assertEqual(receipt['actual_read_counts'],{'discussion':1});self.assertEqual(receipt['source_attempt_counts'],{'discussion':1});self.assertEqual(receipt['projection_attempt_counts'],{'discussion':1});self.assertEqual(receipt['completed_counts'],{})
            self.assertEqual(receipt['current_record_at_failure']['member_key'],row['member_key'])
            events=[json.loads(x)['event'] for x in (private/'calibration.source-read.private.jsonl').read_text().splitlines()]
            self.assertLess(events.index('selected_source_view_read'),events.index('source_projection_attempt'))
    def test_risk_sidecar_preserves_original_metadata(self):
        import gzip
        with tempfile.TemporaryDirectory() as td:
            private=Path(td);receipt,row=self.pipeline_fixture(private,'```python\n'+('中文合成测试。'*40),False)
            artifact=json.loads(gzip.decompress(next((private/'calibration.records').glob('*.json.gz')).read_bytes()))
            self.assertIn('markdown_fenced_code_role_unresolved',artifact['source_risks']);self.assertEqual(artifact['metadata']['metadata'],row['metadata']);self.assertFalse(artifact['preparse']['preparse_eligible']);self.assertNotIn('current_record_at_failure',receipt)
    def test_SAX_stop_after_text_keeps_actual_read_identity(self):
        with tempfile.TemporaryDirectory() as td:
            private=Path(td);control=private/'control.json';control.write_text('{"state":"run"}');go=private/'go';go.write_text('synthetic')
            text='中文合成测试。'*40;row=synthetic_records(1)[1];row['source_sha256']=hashlib.sha256(text.encode()).hexdigest();row['source_codepoints']=len(text);row['locator']={'page_id':'1','revision_id':'2','revision_timestamp':'2017-01-01T00:00:00Z'}
            xml=('<mediawiki><page><ns>0</ns><id>1</id><revision><id>2</id><timestamp>2017-01-01T00:00:00Z</timestamp><text>'+text+'</text></revision></page></mediawiki>').encode();archive=private/'synthetic.xml.bz2';archive.write_bytes(bz2.compress(xml));raw={'path':str(archive),'sha256':R.filehash(archive),'bytes':archive.stat().st_size,'expanded_bytes':len(xml)}
            freeze={'records':[row]};fb=private/'freeze';R.write_new(fb,freeze);rb=private/'registry';R.write_new(rb,{});contract={'code_bindings':[],'indirect_bindings':[],'freeze':R.binding(fb),'registry':R.binding(rb)}
            actual_stream=U.stream_wiki
            def stopped_stream(source,rows,guard):
                original=guard.on_source_read
                def stop_before_log(row,text):control.write_text('{"state":"stop"}');original(row,text)
                guard.on_source_read=stop_before_log
                yield from actual_stream(source,rows,guard)
            with patch.object(U,'PRIVATE',private),patch.object(U,'verify_contract',return_value=(contract,freeze)),patch.object(U,'install_offline_sandbox',return_value={'synthetic_only':True}),patch.object(U.resource,'setrlimit'),patch.object(U.signal,'signal'),patch.object(U.signal,'setitimer'),patch.dict(U.RAW_OBJECTS,{'news_prose':raw}),patch.object(U,'stream_wiki',side_effect=stopped_stream):
                with self.assertRaisesRegex(R.GateError,'operator_stop'):U.execute('calibration',fb,'a'*64,rb,'b'*64,go)
            receipt=R.load_json(private/'calibration.receipt.private.json');self.assertEqual(receipt['actual_read_counts'],{'news_prose':1});self.assertEqual(receipt['source_attempt_counts'],{'news_prose':1});self.assertEqual(receipt['completed_counts'],{});self.assertEqual(receipt['current_record_at_failure']['member_key'],row['member_key'])
    def test_candidates_execute_explicitly_blocked(self):
        with self.assertRaisesRegex(R.GateError,'fingerprint_writer_integrated'):U.execute('candidates',None,None,None,None,None)
    def test_calibration_output_subbudget_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'control.json').write_text('{"state":"run"}');g=U.Guard(p,p/'absent',caps={'wall_seconds':10,'rss_bytes':3*1024**3,'private_bytes':100000,'old_fingerprint_minimum_bytes':0});g.stage_output_budget=4100
            with self.assertRaisesRegex(R.GateError,'stage_output_byte_limit'):g.write(p/'output',{'long':'x'*100})


class KernelSandboxTests(unittest.TestCase):
    def test_socket_syscall_denied_in_child(self):
        # Child uses only generated code; it attempts no remote destination.
        code='import sys;sys.path.insert(0,'+repr(str(Path(U.__file__).parent))+');import runner,socket;runner.install_offline_sandbox();\ntry: socket.socket();raise RuntimeError("socket_unexpectedly_allowed")\nexcept PermissionError: print("kernel_socket_denied")'
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),'kernel_socket_denied')

if __name__=='__main__':unittest.main(verbosity=2)
