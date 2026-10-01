"""Synthetic certificate and alias tests: never reads historical source bodies."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from compatibility import (ARTIFACT_NAMES, DECISION, RESTRICTIONS, THREE_BLOG_SHA256,
    ReviewedCompatibility, certificate_template, expand_coverage_aliases, validate_certificate_schema)
from matcher import CompatibilityError, OLD_DATABASE_SHA256, SignaturePackage, filehash, sha, signature
from test_matcher import fixture_db


def shaped_certificate():
    c=certificate_template()
    for name in ARTIFACT_NAMES:c['artifacts'][name]={'sha256':'a'*64,'bytes':123}
    c['artifacts']['old_raw_database']['sha256']=OLD_DATABASE_SHA256
    c['artifacts']['three_blog_raw_database']['sha256']=THREE_BLOG_SHA256
    c['coverage']['segment_rows']=12345
    return c


class CertificateTests(unittest.TestCase):
    def test_schema_accepts_review_shaped_data(self):
        self.assertIs(validate_certificate_schema(c:=shaped_certificate()),c)
    def test_template_is_not_certificate(self):
        with self.assertRaises(CompatibilityError):validate_certificate_schema(certificate_template())
    def test_reject_unreviewed_decision(self):
        for key,value in [('decision','package_built'),('independent_review',False)]:
            c=shaped_certificate();c[key]=value
            with self.assertRaises(CompatibilityError):validate_certificate_schema(c)
    def test_reject_claim_of_universal_coverage(self):
        c=shaped_certificate();c['restrictions']['universal_clean_prose_coverage']=True
        with self.assertRaises(CompatibilityError):validate_certificate_schema(c)
    def test_reject_missing_old_view(self):
        c=shaped_certificate();c['coverage']['old_missing_source_views']=1
        with self.assertRaises(CompatibilityError):validate_certificate_schema(c)
    def test_reject_old_source_hash_change(self):
        c=shaped_certificate();c['artifacts']['old_raw_database']['sha256']='b'*64
        with self.assertRaises(CompatibilityError):validate_certificate_schema(c)
    def test_reject_unverified_references(self):
        c=shaped_certificate();c['coverage']['all_segment_references_verified']=False
        with self.assertRaises(CompatibilityError):validate_certificate_schema(c)
    def test_reject_added_or_missing_fields(self):
        c=shaped_certificate();c['trusted']=True
        with self.assertRaises(CompatibilityError):validate_certificate_schema(c)
        c=shaped_certificate();del c['artifacts']['validator']
        with self.assertRaises(CompatibilityError):validate_certificate_schema(c)
    def test_reject_lowered_threshold(self):
        c=shaped_certificate();c['signature_contract']['min_shared']=39
        with self.assertRaises(CompatibilityError):validate_certificate_schema(c)
    def test_reject_higher_candidate_cap(self):
        c=shaped_certificate();c['limits']['candidate_view_codepoints']=200000
        with self.assertRaises(CompatibilityError):validate_certificate_schema(c)
    def test_reject_unknown_frame(self):
        c=shaped_certificate();c['candidate_source_frames']=['raw_html']
        with self.assertRaises(CompatibilityError):validate_certificate_schema(c)
    def test_global_resource_blockers_require_stage_stop(self):
        from compatibility import requires_stage_stop
        for blocker in ('aggregate_comparison_increment_cap','operator_stop','private_byte_limit','wall_time_limit','rss_limit'):
            self.assertTrue(requires_stage_stop({'blocker':blocker}))
        self.assertFalse(requires_stage_stop({'blocker':'projection_source_hash_mismatch'}))
    def test_loader_requires_actual_artifact_hashes(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'cert.json';p.write_text(json.dumps(shaped_certificate()))
            with self.assertRaisesRegex(CompatibilityError,'certificate_hash_mismatch'):
                ReviewedCompatibility(p,'0'*64,artifact_paths={},package_by_artifact={})
            with self.assertRaisesRegex(CompatibilityError,'artifact_paths_scope'):
                ReviewedCompatibility(p,filehash(p),artifact_paths={},package_by_artifact={})


class AnnotationTests(unittest.TestCase):
    """Unit-test annotation separately; end-to-end needs the real reviewed bundle."""
    def adapter(self, directory):
        from project_wikitext import project
        from projection_contract import validate_projection
        c=shaped_certificate()
        root=Path(__file__).parent
        obj=ReviewedCompatibility.__new__(ReviewedCompatibility)
        obj.certificate=c;obj.sha256='c'*64
        obj.paths={'validator':root/'projection_contract.py'}
        stat=obj.paths['validator'].stat();obj.stats={'validator':(stat.st_size,stat.st_mtime_ns,stat.st_ino)}
        obj.coverage=sqlite3.connect(':memory:')
        obj.coverage.execute('CREATE TABLE segments(old_raw_sha256 TEXT,segment_index INTEGER,coverage_kind TEXT,reference_text_id INTEGER)')
        packages={}
        for artifact,name in c['package_names'].items():
            package=fixture_db(Path(directory)/(name+'.sqlite'),[signature('reference','ref','raw')])
            package.close()
            package=SignaturePackage(Path(directory)/(name+'.sqlite'),filehash(Path(directory)/(name+'.sqlite')),name)
            packages[artifact]=package
        obj.packages=packages
        text='This is a synthetic plain source sentence with a valid map.'
        projected=project(text,'discussion')
        result={'status':'quarantine_unmatched_cross_projection_coverage','source_sha256':sha(text.encode()),
                'signature_scan_complete':True,'complete_declared_view_comparisons':True,
                'admission_authorized':False,'packages':[]}
        for artifact,name in c['package_names'].items():
            # This fixture exercises annotate only; constructor enforces real hashes.
            c['artifacts'][artifact]['sha256']=packages[artifact].sha256
            result['packages'].append({'package':name,'package_sha256':packages[artifact].sha256,
                                       'complete_signature_scan':True,'hits':[],'bindings':[]})
        return obj,result,text,projected,validate_projection
    def test_annotation_never_authorizes_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter,receipt,text,projection,validator=self.adapter(directory)
            result=adapter.annotate(receipt,raw_text=text,projection=projection,candidate_member_key='["candidate"]',validate_projection=validator)
            self.assertTrue(result['bounded_cross_projection_coverage_reviewed'])
            self.assertFalse(result['cross_projection_coverage_certified'])
            self.assertFalse(result['admission_authorized'])
            self.assertTrue(result['requires_separate_G2_review'])
            self.assertEqual(result['status'],'no_known_signature_match_bounded_views_not_admission')
            adapter.close()
            for p in adapter.packages.values():p.close()
    def test_missing_comparison_package_quarantines(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter,receipt,text,projection,validator=self.adapter(directory)
            receipt['packages'].pop()
            result=adapter.annotate(receipt,raw_text=text,projection=projection,candidate_member_key='["candidate"]',validate_projection=validator)
            self.assertEqual(result['status'],'quarantine')
            self.assertFalse(result['bounded_cross_projection_coverage_reviewed'])
            adapter.close()
            for p in adapter.packages.values():p.close()
    def test_unbound_validator_quarantines(self):
        with tempfile.TemporaryDirectory() as directory:
            adapter,receipt,text,projection,validator=self.adapter(directory)
            result=adapter.annotate(receipt,raw_text=text,projection=projection,candidate_member_key='["candidate"]',validate_projection=lambda *_:{'status':'source_map_verified'})
            self.assertEqual(result['status'],'quarantine')
            self.assertEqual(result['compatibility_blocker'],'unbound_candidate_validator')
            adapter.close()
            for p in adapter.packages.values():p.close()


class AliasTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.packages=[]
    def tearDown(self):
        for p in self.packages:p.close()
        self.temp.cleanup()
    def package(self,text,name,second_binding=False):
        path=Path(self.temp.name)/(name+'.sqlite')
        p=fixture_db(path,[signature(text,'ref','raw')]);p.close()
        if second_binding:
            db=sqlite3.connect(path)
            db.execute('INSERT INTO bindings VALUES(?,?,?,?,?,?,?,?)',(2,'other','["second_member"]','old_test_exposed','history',sha(text.encode()),1,'{}'))
            db.commit();db.close()
        p=SignaturePackage(path,filehash(path),name);self.packages.append(p);return p
    def setup_alias(self,kind='new_projected_signature',old_raw='Old original'):
        old=self.package('Old original','old',True)
        three=self.package('Third party blog','three')
        projected=self.package('Projected signature','projected')
        db=sqlite3.connect(':memory:');db.execute('CREATE TABLE segments(old_raw_sha256 TEXT,segment_index INTEGER,coverage_kind TEXT,reference_text_id INTEGER)')
        db.execute('INSERT INTO segments VALUES(?,?,?,?)',(sha(old_raw.encode()),0,kind,1))
        name='old' if kind.startswith('old_') else 'projected'
        package=old if name=='old' else projected
        receipt={'source_sha256':sha(b'new'),'packages':[{'package':name,'package_sha256':package.sha256,'bindings':[],
            'hits':[{'candidate_view':'projected_segment:0','reference_text_id':1,'reasons':['normalized_full_exact']}]}]}
        return db,receipt,{'old_raw_database':old,'three_blog_raw_database':three,'projected_database':projected},
    def test_projected_hit_expands_all_original_members(self):
        db,receipt,packages=self.setup_alias()
        edges=expand_coverage_aliases(receipt,'["candidate"]',coverage_db=db,package_by_artifact=packages,
            package_names={'old_raw_database':'old','three_blog_raw_database':'three','projected_database':'projected'})
        self.assertEqual({e['right_member_key'] for e in edges},{'["synthetic","member"]','["second_member"]'})
        self.assertEqual({e['reference_exposure_role'] for e in edges},{'exclusion_only','old_test_exposed'})
        db.close()
    def test_raw_equivalent_projection_expands_aliases(self):
        for kind in ('old_normalized_full','old_normalized_long_block'):
            with self.subTest(kind=kind):
                # Different filenames for the second iteration.
                self.tearDown();self.setUp()
                db,receipt,packages=self.setup_alias(kind)
                edges=expand_coverage_aliases(receipt,'["candidate"]',coverage_db=db,package_by_artifact=packages,
                    package_names={'old_raw_database':'old','three_blog_raw_database':'three','projected_database':'projected'})
                self.assertEqual(len(edges),2);db.close()
    def test_missing_original_raw_alias_fails_closed(self):
        db,receipt,packages=self.setup_alias(old_raw='Missing original')
        with self.assertRaisesRegex(CompatibilityError,'projection_alias_missing_original_raw_binding'):
            expand_coverage_aliases(receipt,'["candidate"]',coverage_db=db,package_by_artifact=packages,
                package_names={'old_raw_database':'old','three_blog_raw_database':'three','projected_database':'projected'})
        db.close()
    def test_direct_large_fanout_stops_before_oversized_allocation(self):
        import compatibility
        from unittest.mock import patch
        db=sqlite3.connect(':memory:');db.execute('CREATE TABLE segments(old_raw_sha256 TEXT,segment_index INTEGER,coverage_kind TEXT,reference_text_id INTEGER)')
        reads=[]
        class CountedBinding(dict):
            def __getitem__(self,key):
                if key=='member_key':reads.append(super().__getitem__(key))
                return super().__getitem__(key)
        bindings=[CountedBinding(reference_text_id=1,member_key='member:'+str(i),exposure_role='old',source_view_role='raw',source_object_sha256='a'*64) for i in range(100)]
        receipt={'packages':[{'package':'unaliased','package_sha256':'b'*64,'bindings':bindings,
                  'hits':[{'reference_text_id':1,'candidate_view':'raw','reasons':['raw_exact']}]}]}
        callbacks=[]
        with patch.object(compatibility,'MAX_ALIAS_BINDINGS',2):
            with self.assertRaisesRegex(CompatibilityError,'projection_alias_edge_cap'):
                expand_coverage_aliases(receipt,'candidate',coverage_db=db,
                    package_by_artifact={'old_raw_database':None,'three_blog_raw_database':None},
                    package_names={'old_raw_database':'old','three_blog_raw_database':'three','projected_database':'projected'},
                    resource_callback=callbacks.append)
        self.assertEqual(len(reads),3)
        self.assertEqual(max(s.get('expanded_edges',0) for s in callbacks),2)
        db.close()
    def test_duplicate_fanout_still_consumes_attempt_budget(self):
        import compatibility
        from unittest.mock import patch
        db=sqlite3.connect(':memory:');db.execute('CREATE TABLE segments(old_raw_sha256 TEXT,segment_index INTEGER,coverage_kind TEXT,reference_text_id INTEGER)')
        binding={'reference_text_id':1,'member_key':'member','exposure_role':'old','source_view_role':'raw','source_object_sha256':'a'*64}
        receipt={'packages':[{'package':'unaliased','package_sha256':'b'*64,'bindings':[binding],
                 'hits':[{'reference_text_id':1,'candidate_view':'raw','reasons':['raw_exact']}]*100}]}
        with patch.object(compatibility,'MAX_ALIAS_ROWS',3):
            with self.assertRaisesRegex(CompatibilityError,'projection_alias_row_cap'):
                expand_coverage_aliases(receipt,'candidate',coverage_db=db,
                    package_by_artifact={'old_raw_database':None,'three_blog_raw_database':None},
                    package_names={'old_raw_database':'old','three_blog_raw_database':'three','projected_database':'projected'})
        db.close()
    def test_same_member_edges_are_removed(self):
        db,receipt,packages=self.setup_alias()
        edges=expand_coverage_aliases(receipt,'["second_member"]',coverage_db=db,package_by_artifact=packages,
            package_names={'old_raw_database':'old','three_blog_raw_database':'three','projected_database':'projected'})
        self.assertEqual(len(edges),1);self.assertNotEqual(edges[0]['left_member_key'],edges[0]['right_member_key']);db.close()

if __name__=='__main__':unittest.main()
