"""Pure synthetic tests. No representative bodies or frozen raw sources opened."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zlib
from matcher import (ALGORITHM, CompatibilityError, Signature, SignaturePackage,
    distinct_grams, filehash, gram_hash, long_blocks, match_record, match_records, near_copy,
    norm_hash, normalize, pack_ids, record_signatures, sha, signature, unpack_ids)

SCHEMA = '''
CREATE TABLE control(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE grams(id INTEGER PRIMARY KEY,sha256 BLOB UNIQUE NOT NULL);
CREATE TABLE texts(id INTEGER PRIMARY KEY,raw_sha256 TEXT UNIQUE NOT NULL,utf8_bytes INTEGER,codepoints INTEGER,normalized_sha256 BLOB,normalized_codepoints INTEGER,gram_count INTEGER,gram_ids_delta_zlib BLOB);
CREATE TABLE blocks(text_id INTEGER,kind TEXT,ordinal INTEGER,normalized_sha256 BLOB,normalized_codepoints INTEGER,PRIMARY KEY(text_id,kind,ordinal));
CREATE TABLE bindings(id INTEGER PRIMARY KEY,source_id TEXT,member_key TEXT,exposure_role TEXT,source_view_role TEXT,source_object_sha256 TEXT,text_id INTEGER,locator_json TEXT);
'''

def fixture_db(path, signatures, reverse=False):
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    db.executemany('INSERT INTO control VALUES(?,?)', [('status','complete'),('algorithm',ALGORITHM),('unicode_version','15.0.0')])
    ordered = sorted(set().union(*(s.grams for s in signatures)), reverse=reverse)
    ids = {digest: i+1 for i, digest in enumerate(ordered)}
    db.executemany('INSERT INTO grams VALUES(?,?)', [(i,digest) for digest,i in ids.items()])
    for tid,sig in enumerate(signatures,1):
        db.execute('INSERT INTO texts VALUES(?,?,?,?,?,?,?,?)', (tid,sig.raw_sha256,0,0,sig.normalized_sha256,sig.normalized_codepoints,len(sig.grams),pack_ids(ids[g] for g in sig.grams)))
        db.executemany('INSERT INTO blocks VALUES(?,?,?,?,?)', [(tid,*block) for block in sig.blocks])
        db.execute('INSERT INTO bindings VALUES(?,?,?,?,?,?,?,?)',(tid,'synthetic','["synthetic","member"]','exclusion_only','raw',sig.raw_sha256,tid,'{}'))
    db.commit(); db.close()
    return SignaturePackage(path,filehash(path),path.stem)

def projection(raw, text=None, span=None):
    text = raw if text is None else text
    lo,hi = span or (0,len(raw))
    return {'source_sha256':sha(raw.encode()), 'profile':'synthetic/1',
            'segments':[{'text':text,'source_spans':[[lo,hi]],
                         'source_map':[[lo+i,lo+i+1,'identity',0] for i in range(len(text))]}],
            'barriers':[], 'flags':[]}

def fake_sig(label, digests):
    return Signature(label,'synthetic',sha(label.encode()),norm_hash(label),max(100,len(digests)+4),frozenset(digests),())

class MatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.packages=[]
    def tearDown(self):
        for package in self.packages: package.close()
        self.temp.cleanup()
    def package(self, signatures, name='one', reverse=False):
        p=fixture_db(Path(self.temp.name)/(name+'.sqlite'),signatures,reverse)
        self.packages.append(p); return p
    def test_nfkc_whitespace_and_punctuation(self):
        self.assertEqual(normalize('Ａ \nＢ！'),'AB!')
        self.assertNotEqual(normalize('ab,c'),normalize('abc'))
    def test_hash_domains(self):
        self.assertNotEqual(norm_hash('abcde'),gram_hash('abcde'))
    def test_id_roundtrip(self):
        self.assertEqual(unpack_ids(pack_ids([1000000,1,129,128,1]),4),[1,128,129,1000000])
    def test_empty_id_roundtrip(self): self.assertEqual(unpack_ids(pack_ids([]),0),[])
    def test_reject_bad_varints(self):
        for blob,count in [(zlib.compress(b'\x80\x00'),1),(zlib.compress(b'\x81'),1),(zlib.compress(b'\x00'),1),(zlib.compress(b'\x01')+b'tail',1)]:
            with self.assertRaises(CompatibilityError): unpack_ids(blob,count)
    def test_reject_count_and_dictionary_overflow(self):
        with self.assertRaises(CompatibilityError): unpack_ids(pack_ids([1,2]),1)
        with self.assertRaises(CompatibilityError): unpack_ids(pack_ids([99]),1,98)
    def test_minimum_shared(self):
        self.assertFalse(near_copy(39,39,39)); self.assertTrue(near_copy(40,40,40))
    def test_threshold_exact_and_below(self):
        self.assertTrue(near_copy(40,50,100)); self.assertFalse(near_copy(40,51,100))
    def test_ids_independent_of_insertion_order(self):
        gs=[gram_hash(str(i)) for i in range(60)]
        a=self.package([fake_sig('reference',gs)],'a')
        b=self.package([fake_sig('reference',gs)],'b',reverse=True)
        self.assertNotEqual(a.map_digests(gs)[gs[0]],b.map_digests(gs)[gs[0]])
        s=fake_sig('query',gs)
        for p in (a,b):
            hits=p.compare([s])['hits']; self.assertEqual(len(hits),1)
            self.assertEqual(hits[0]['shared_distinct_grams'],60)
    def test_unseen_grams_keep_full_candidate_denominator(self):
        shared=[gram_hash('shared'+str(i)) for i in range(40)]
        ref=shared+[gram_hash('reference'+str(i)) for i in range(60)]
        qry=shared+[gram_hash('query'+str(i)) for i in range(60)]
        p=self.package([fake_sig('reference',ref)])
        r=p.compare([fake_sig('query',qry)])
        self.assertEqual(r['candidate_mapped_gram_counts'],[40])
        self.assertEqual(r['candidate_full_gram_counts'],[100])
        self.assertEqual(r['hits'],[])
    def test_short_full_exact(self):
        p=self.package([signature('短文','ref','raw')])
        r=match_record('短文',projection('短文'),packages=[p],expected_raw_sha256=sha('短文'.encode()))
        self.assertEqual(r['status'],'excluded_known_exposure_match')
    def test_empty_does_not_match_empty(self):
        p=self.package([signature('','ref','raw')]); self.assertEqual(p.compare([signature('','q','raw')])['hits'],[])
    def test_raw_view_catches_clean_transform(self):
        clean=''.join(chr(0x4e00+i) for i in range(100))
        raw=''.join('**'+c+'**' for c in clean)
        p=self.package([signature(raw,'ref','raw')])
        projected=projection(raw,clean)
        projected['segments'][0]['source_map']=[[5*i+2,5*i+3,'identity',0] for i in range(len(clean))]
        self.assertEqual(p.compare([signature(clean,'q','clean')])['hits'],[])
        result=match_record(raw,projected,packages=[p],expected_raw_sha256=sha(raw.encode()))
        self.assertTrue(result['signature_scan_complete'])
        self.assertEqual(result['status'],'excluded_known_exposure_match')
    def test_adversarial_old_markup_new_plain_raw_misses_and_quarantines(self):
        clean=''.join(chr(0x4e00+i) for i in range(100))
        old_raw=''.join('**'+c+'**' for c in clean)
        p=self.package([signature(old_raw,'ref','raw')])
        result=match_record(clean,projection(clean),packages=[p],expected_raw_sha256=sha(clean.encode()))
        self.assertTrue(result['complete_declared_view_comparisons'])
        self.assertFalse(result['cross_projection_coverage_certified'])
        self.assertEqual(result['status'],'quarantine_unmatched_cross_projection_coverage')
        self.assertEqual(result['packages'][0]['hits'],[])
    def test_raw_span_catches_removed_syntax(self):
        snippet=''.join('**'+chr(0x4e00+i)+'**' for i in range(100))
        raw='prefix\n\n'+snippet+'\n\nsuffix'
        p=self.package([signature(snippet,'ref','raw')])
        lo=8; clean=''.join(chr(0x4e00+i) for i in range(100))
        projected=projection(raw,clean,(lo,lo+len(snippet)))
        projected['segments'][0]['source_map']=[[lo+5*i+2,lo+5*i+3,'identity',0] for i in range(len(clean))]
        result=match_record(raw,projected,packages=[p],expected_raw_sha256=sha(raw.encode()))
        self.assertTrue(any(h['candidate_role']=='mapped_contiguous_raw_source_span' and 'raw_exact' in h['reasons'] for h in result['packages'][0]['hits']))
    def test_never_joins_segments_across_barriers(self):
        raw='left BLOCK right'; p=projection(raw,'left',(0,4))
        p['segments'].append({'text':'right','source_spans':[[11,16]],'source_map':[[11+i,12+i,'identity',0] for i in range(5)]})
        sigs=record_signatures(raw,p,sha(raw.encode()))
        self.assertEqual(len(sigs),5)
        self.assertNotIn(sha(b'leftright'),{s.raw_sha256 for s in sigs})
    def test_missing_map_quarantines(self):
        p=self.package([signature('hello','r','raw')]); projected=projection('world')
        projected['segments'][0]['source_map']=[]
        r=match_record('world',projected,packages=[p],expected_raw_sha256=sha(b'world'))
        self.assertEqual(r['status'],'quarantine'); self.assertFalse(r['signature_scan_complete'])
    def test_changed_raw_quarantines(self):
        p=self.package([signature('hello','r','raw')])
        r=match_record('world',projection('world'),packages=[p],expected_raw_sha256=sha(b'hello'))
        self.assertEqual(r['status'],'quarantine')
    def test_missing_required_package_quarantines(self):
        p=self.package([signature('hello','r','raw')])
        r=match_record('world',projection('world'),packages=[p],expected_raw_sha256=sha(b'world'),require_package_names=['one','missing'])
        self.assertEqual(r['status'],'quarantine')
    def test_unmatched_is_not_admission(self):
        p=self.package([signature('other','r','raw')])
        r=match_record('world',projection('world'),packages=[p],expected_raw_sha256=sha(b'world'))
        self.assertEqual(r['status'],'quarantine_unmatched_cross_projection_coverage')
        self.assertFalse(r['admission_authorized'])
    def test_hash_identity_checked(self):
        p=self.package([signature('hello','r','raw')])
        with self.assertRaises(CompatibilityError): SignaturePackage(p.path,'0'*64,'bad')
    def test_long_block_exact(self):
        block=''.join(chr(0x4e00+i) for i in range(80))
        p=self.package([signature('before\n\n'+block+'\n\nafter','r','raw')])
        self.assertIn('long_block_exact',p.compare([signature(block,'q','projected')])['hits'][0]['reasons'])
    def test_batched_records_preserve_independent_results(self):
        p=self.package([signature('hello','r','raw')])
        records=[{'record_key':x,'raw_text':x,'projection':projection(x),'raw_sha256':sha(x.encode())} for x in ('hello','world')]
        result=match_records(records,packages=[p],require_package_names=['one'])
        self.assertEqual(result[0]['status'],'excluded_known_exposure_match')
        self.assertEqual(result[1]['status'],'quarantine_unmatched_cross_projection_coverage')
        self.assertEqual(result[1]['packages'][0]['bindings'],[])
    def test_shared_comparison_budget_stops(self):
        p=self.package([signature('hello','r','raw')]); budget={'used':0,'cap':0}
        result=match_record('hello',projection('hello'),packages=[p],expected_raw_sha256=sha(b'hello'),comparison_budget=budget)
        self.assertEqual(result['status'],'quarantine')
        self.assertEqual(result['blocker'],'aggregate_comparison_increment_cap')
        self.assertGreater(budget['used'],0)
    def test_shared_gram_pair_increments_count_each_gram(self):
        gs=[gram_hash(str(i)) for i in range(100)]
        p=self.package([fake_sig('reference',gs)])
        budget={'used':0,'cap':50}
        with self.assertRaisesRegex(CompatibilityError,'aggregate_comparison_increment_cap'):
            p.compare([fake_sig('query',gs)],comparison_budget=budget)
        self.assertEqual(budget['used'],51)
    def test_signature_writer_and_edge_binding(self):
        from matcher import SignatureWriter,exclusion_edges
        path=Path(self.temp.name)/'written.sqlite'; writer=SignatureWriter(path)
        for member in ('["one"]','["two"]'):
            writer.add('hello',source_id='synthetic',member_key=member,exposure_role='exclusion',source_view_role='raw',source_object_sha256=sha(b'hello'),locator={})
        receipt=writer.finish(); self.assertEqual(receipt['text_count'],1)
        p=SignaturePackage(path,receipt['sha256'],'written');self.packages.append(p)
        result=match_record('hello',projection('hello'),packages=[p],expected_raw_sha256=sha(b'hello'))
        edges=exclusion_edges(result,'["one"]')
        self.assertTrue(edges);self.assertEqual({e['right_member_key'] for e in edges},{'["two"]'})
    def test_diagnostic_projection_maps_and_barriers(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('incremental_blog_exclusion',Path(__file__).with_name('incremental-blog-exclusion.py'))
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        raw='---\ntitle: synthetic\n---\n# heading\n\nhello **world** [label](https://example.invalid/)\n\n```\ncode\n```\n'
        projected=module.diagnostic_projection(raw)
        self.assertEqual([s['text'].strip() for s in projected['segments']],['heading','hello world label'])
        self.assertEqual(len(record_signatures(raw,projected,sha(raw.encode()))),5)
        for segment in projected['segments']:
            for char,(lo,hi,op,index) in zip(segment['text'],segment['source_map']):
                self.assertEqual(raw[lo:hi],char)
                self.assertEqual((op,index),('identity',0))
    def test_long_block_threshold(self):
        self.assertEqual(long_blocks('x'*63),[])
        self.assertTrue(long_blocks('x'*64))

if __name__=='__main__': unittest.main()
