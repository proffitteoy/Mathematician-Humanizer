"""Consume independent, hash-pinned bounded old-projection exclusion reviews.

This is deliberately separate from frozen matcher v1. A certificate verifies
bounded compatible-view comparisons, never universal copying/prose eligibility
or G2 admission. All returned aliases/edges remain private.
"""
from __future__ import annotations
from collections import defaultdict
import copy
import json
from pathlib import Path
import re
import sqlite3
from matcher import (ALGORITHM, OLD_DATABASE_SHA256, UNICODE_VERSION, CompatibilityError,
                     BoundExceeded, canonical, filehash, sha)

CERTIFICATE_SCHEMA = 'bounded-old-projection-exclusion-review/1'
DECISION = 'PASS_BOUNDED_OLD_PROJECTED_EXCLUSION_PACKAGE'
THREE_BLOG_SHA256 = '225d002fa7dc3436cb50075e712bff8d263fbf1bc802823fe43ef76a925c5a08'
ARTIFACT_NAMES = frozenset({'old_raw_database','three_blog_raw_database','projected_database',
    'coverage_database','derivation_receipt','derivation_plan','projector','validator','independent_review_report'})
PACKAGE_ARTIFACTS = frozenset({'old_raw_database','three_blog_raw_database','projected_database'})
RESTRICTIONS = {
    'purpose':'exclusion_only',
    'omitted_role_policy':'raw_only_never_prose_admitted',
    'unsupported_candidate_policy':'quarantine',
    'negative_match_policy':'separate_G2_review_required',
    'universal_clean_prose_coverage':False,
    'semantic_copy_absence':False,
    'unknown_external_lineage_absence':False,
    'source_admission_authorized':False,
    'body_role_eligibility_certified':False,
}
EXPECTED_SCOPE = {'old_source_view_bindings':324320,'old_unique_raw_texts':100541,
                  'new_blog_source_view_bindings':3,'new_blog_unique_raw_texts':3,
                  'old_missing_source_views':0}
MAX_ALIAS_ROWS = 1_000_000
MAX_ALIAS_BINDINGS = 400_000
STAGE_STOP_BLOCKERS = frozenset({'aggregate_comparison_increment_cap','matching_resource_cap',
    'operator_stop','invalid_control','wall_time_limit','rss_limit','private_byte_limit',
    'all_private_derivatives_cap','memory_cap','wall_cap','projection_alias_row_cap','projection_alias_edge_cap'})

def requires_stage_stop(receipt):
    """Promote global caps/operator failures; never retry after consuming a cap."""
    return (receipt.get('stage_stop_required') is True or
            receipt.get('blocker') in STAGE_STOP_BLOCKERS or
            receipt.get('compatibility_blocker') in STAGE_STOP_BLOCKERS)


def require(condition, reason):
    if not condition: raise CompatibilityError(reason)


def _keys(value, keys, reason):
    require(isinstance(value, dict) and set(value)==set(keys),reason)


def _digest(value):
    return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def validate_certificate_schema(certificate):
    """Strict public schema; only an independent reviewer may issue this object."""
    _keys(certificate,{'schema_version','decision','independent_review','artifacts','package_names',
                      'projection_profile','candidate_source_frames','signature_contract','coverage','limits','restrictions'},
          'certificate_top_level_schema')
    require(certificate['schema_version']==CERTIFICATE_SCHEMA and certificate['decision']==DECISION,'certificate_decision_or_schema')
    require(certificate['independent_review'] is True,'independent_review_required')
    require(certificate['restrictions']==RESTRICTIONS,'certificate_restrictions_changed')
    _keys(certificate['artifacts'],ARTIFACT_NAMES,'artifact_scope')
    for name, binding in certificate['artifacts'].items():
        _keys(binding,{'sha256','bytes'},'artifact_binding_schema')
        require(_digest(binding['sha256']) and type(binding['bytes']) is int and binding['bytes']>0,'artifact_binding_invalid')
    require(certificate['artifacts']['old_raw_database']['sha256']==OLD_DATABASE_SHA256,'wrong_old_source_package')
    require(certificate['artifacts']['three_blog_raw_database']['sha256']==THREE_BLOG_SHA256,'wrong_three_blog_package')
    _keys(certificate['package_names'],PACKAGE_ARTIFACTS,'package_name_scope')
    require(all(isinstance(v,str) and v for v in certificate['package_names'].values()) and
            len(set(certificate['package_names'].values()))==3,'package_names_invalid')
    require(isinstance(certificate['projection_profile'],str) and certificate['projection_profile'],'profile_missing')
    frames=certificate['candidate_source_frames']
    require(isinstance(frames,list) and frames and len(frames)==len(set(frames)) and
            set(frames)<={'discussion','news_prose','guide_prose'},'candidate_frames_invalid')
    require(certificate['signature_contract']=={'algorithm':ALGORITHM,'unicode_version':UNICODE_VERSION,
            'normalized_domain':'nfkc-no-ws/v1','gram_domain':'char5-nfkc-no-ws/v1','min_shared':40,
            'containment_numerator':4,'containment_denominator':5},'signature_contract_changed')
    coverage=certificate['coverage']
    _keys(coverage,set(EXPECTED_SCOPE)|{'coverage_rows','segment_rows','zero_segment_views','quarantined_views',
                                     'all_source_bindings_verified','all_segment_references_verified'},'coverage_schema')
    for key,value in EXPECTED_SCOPE.items():
        require(type(coverage[key]) is int and coverage[key]==value,'coverage_scope_'+key)
    for key in ('coverage_rows','segment_rows','zero_segment_views','quarantined_views'):
        require(type(coverage[key]) is int and coverage[key]>=0,'coverage_count_invalid')
    require(coverage['coverage_rows']==100544,'coverage_raw_row_count')
    require(coverage['all_source_bindings_verified'] is True and coverage['all_segment_references_verified'] is True,
            'independent_coverage_verification_missing')
    require(certificate['limits']=={'historical_view_codepoints':200000,'candidate_view_codepoints':20000,
            'total_private_bytes':1073741824,'peak_rss_bytes':3221225472,
            'shared_gram_pair_increments':300000000},'certificate_limits_changed')
    return certificate


def certificate_template():
    """Reviewers fill measured hashes/counts; this placeholder cannot pass loading."""
    return {'schema_version':CERTIFICATE_SCHEMA,'decision':DECISION,'independent_review':True,
            'artifacts':{name:{'sha256':'REPLACE_WITH_VERIFIED_SHA256','bytes':0} for name in sorted(ARTIFACT_NAMES)},
            'package_names':{'old_raw_database':'old_exposure_v01','three_blog_raw_database':'incremental_blog_diagnostic3',
                             'projected_database':'old_projected_exclusion'},
            'projection_profile':'historical-wikitext-conservative-prose/0.1.0',
            'candidate_source_frames':['discussion','news_prose','guide_prose'],
            'signature_contract':{'algorithm':ALGORITHM,'unicode_version':UNICODE_VERSION,'normalized_domain':'nfkc-no-ws/v1',
                                  'gram_domain':'char5-nfkc-no-ws/v1','min_shared':40,'containment_numerator':4,'containment_denominator':5},
            'coverage':dict(EXPECTED_SCOPE,coverage_rows=100544,segment_rows=0,zero_segment_views=0,quarantined_views=0,
                            all_source_bindings_verified=True,all_segment_references_verified=True),
            'limits':{'historical_view_codepoints':200000,'candidate_view_codepoints':20000,'total_private_bytes':1073741824,
                      'peak_rss_bytes':3221225472,'shared_gram_pair_increments':300000000},
            'restrictions':dict(RESTRICTIONS)}


def expand_coverage_aliases(receipt, candidate_member_key, *, coverage_db, package_by_artifact,
                            package_names, resource_callback=None):
    """Map reused/projected signature hits to ALL original source members.

    The ledger's old-raw aliases, rather than one first-seen writer binding, are
    authoritative for provenance. Both raw-equivalent and new projected views are
    expanded. Matching a larger raw reference conservatively taints all aliases.
    """
    originals={name:package_by_artifact[name] for name in ('old_raw_database','three_blog_raw_database')}
    hit_evidence=defaultdict(list)
    kinds_by_name={package_names['old_raw_database']:('old_normalized_full','old_normalized_long_block'),
                   package_names['projected_database']:('new_projected_signature',)}
    processed=0
    for package_receipt in receipt.get('packages',[]):
        kinds=kinds_by_name.get(package_receipt['package'],())
        if not kinds: continue
        for hit in package_receipt.get('hits',[]):
            for kind in kinds:
                for old_raw,segment_index in coverage_db.execute('SELECT old_raw_sha256,segment_index FROM segments WHERE coverage_kind=? AND reference_text_id=?',
                                                                 (kind,hit['reference_text_id'])):
                    processed+=1
                    if processed>MAX_ALIAS_ROWS: raise BoundExceeded('projection_alias_row_cap')
                    hit_evidence[old_raw].append({'via_package':package_receipt['package'],
                        'via_package_sha256':package_receipt['package_sha256'],'reference_text_id':hit['reference_text_id'],
                        'candidate_view':hit['candidate_view'],'reasons':hit['reasons'],'old_segment_index':segment_index,
                        'coverage_kind':kind})
                    if resource_callback and processed%500==0: resource_callback({'projection_alias_rows':processed})
    # Never call the frozen unbounded edge-list helper: fanout is guarded before
    # each append. Attempted traversals count even when deduplication drops edges.
    edges=[];seen_keys=set();direct_attempts=0;binding_rows=0
    for package_receipt in receipt.get('packages',[]):
        by_text=defaultdict(list)
        for binding in package_receipt.get('bindings',[]):
            binding_rows+=1
            if binding_rows>MAX_ALIAS_ROWS:raise BoundExceeded('projection_alias_row_cap')
            by_text[binding['reference_text_id']].append(binding)
            if resource_callback and binding_rows%500==0:resource_callback({'direct_binding_rows':binding_rows})
        for hit in package_receipt.get('hits',[]):
            for binding in by_text.get(hit['reference_text_id'],()):
                direct_attempts+=1
                if direct_attempts>MAX_ALIAS_ROWS:raise BoundExceeded('projection_alias_row_cap')
                if resource_callback and direct_attempts%500==0:
                    resource_callback({'direct_edge_attempts':direct_attempts,'expanded_edges':len(edges)})
                member=binding['member_key']
                if member==candidate_member_key:continue
                key=(candidate_member_key,member,package_receipt['package'],hit['candidate_view'],hit['reference_text_id'])
                if key in seen_keys:continue
                if len(edges)>=MAX_ALIAS_BINDINGS:raise BoundExceeded('projection_alias_edge_cap')
                seen_keys.add(key)
                edges.append({'left_member_key':candidate_member_key,'right_member_key':member,
                    'edge_type':'copy_signature_match','package':package_receipt['package'],
                    'package_sha256':package_receipt['package_sha256'],'candidate_view':hit['candidate_view'],
                    'reference_text_id':hit['reference_text_id'],'reference_exposure_role':binding['exposure_role'],
                    'reference_source_view_role':binding['source_view_role'],
                    'reference_source_object_sha256':binding['source_object_sha256'],
                    'candidate_source_sha256':receipt.get('source_sha256'),'reasons':hit['reasons']})
                if resource_callback and len(edges)==MAX_ALIAS_BINDINGS:
                    resource_callback({'direct_edge_attempts':direct_attempts,'expanded_edges':len(edges)})
    found=set();raws=list(hit_evidence);alias_attempts=0
    for name,package in originals.items():
        for start in range(0,len(raws),300):
            part=raws[start:start+300]
            if not part:continue
            rows=package.db.execute('SELECT t.raw_sha256,b.member_key,b.exposure_role,b.source_view_role,b.source_object_sha256 '
                'FROM texts t JOIN bindings b ON b.text_id=t.id WHERE t.raw_sha256 IN ('+','.join('?' for _ in part)+')',part)
            for raw,member,exposure,role,obj in rows:
                found.add(raw)
                if member==candidate_member_key:continue
                for evidence in hit_evidence[raw]:
                    alias_attempts+=1
                    if alias_attempts>MAX_ALIAS_ROWS:raise BoundExceeded('projection_alias_row_cap')
                    if resource_callback and alias_attempts%500==0:resource_callback({'alias_edge_attempts':alias_attempts,'expanded_edges':len(edges)})
                    key=(candidate_member_key,member,evidence['via_package'],evidence['candidate_view'],evidence['reference_text_id'])
                    if key in seen_keys:continue
                    seen_keys.add(key)
                    if len(edges)>=MAX_ALIAS_BINDINGS:raise BoundExceeded('projection_alias_edge_cap')
                    edges.append({'left_member_key':candidate_member_key,'right_member_key':member,
                                  'edge_type':'projected_copy_signature_alias','package':evidence['via_package'],
                                  'package_sha256':evidence['via_package_sha256'],'candidate_view':evidence['candidate_view'],
                                  'reference_text_id':evidence['reference_text_id'],'reference_exposure_role':exposure,
                                  'reference_source_view_role':role,'reference_source_object_sha256':obj,
                                  'candidate_source_sha256':receipt.get('source_sha256'),'old_raw_sha256':raw,
                                  'coverage_kind':evidence['coverage_kind'],'reasons':evidence['reasons']})
            if resource_callback:resource_callback({'projection_alias_rows':processed,'expanded_edges':len(edges)})
    require(set(raws)<=found,'projection_alias_missing_original_raw_binding')
    return edges


class ReviewedCompatibility:
    """Hash-check once, validate cheap file stats on use; keep artifacts immutable."""
    def __init__(self, certificate_path, certificate_sha256, *, artifact_paths, package_by_artifact):
        self.certificate_path=Path(certificate_path)
        require(self.certificate_path.stat().st_size<=128*1024,'certificate_size_cap')
        require(filehash(self.certificate_path)==certificate_sha256,'certificate_hash_mismatch')
        self.sha256=certificate_sha256
        self.certificate=validate_certificate_schema(json.loads(self.certificate_path.read_text()))
        require(set(artifact_paths)==ARTIFACT_NAMES,'artifact_paths_scope')
        require(set(package_by_artifact)==PACKAGE_ARTIFACTS,'loaded_package_scope')
        self.paths={name:Path(path) for name,path in artifact_paths.items()}
        self.stats={}
        self.packages=package_by_artifact
        for name,path in self.paths.items():
            expected=self.certificate['artifacts'][name]
            require(path.stat().st_size==expected['bytes'] and filehash(path)==expected['sha256'],'bound_artifact_changed_'+name)
            stat=path.stat();self.stats[name]=(stat.st_size,stat.st_mtime_ns,stat.st_ino)
            if name in PACKAGE_ARTIFACTS:
                package=self.packages[name]
                require(package.sha256==expected['sha256'] and package.path.resolve()==path.resolve() and
                        package.name==self.certificate['package_names'][name],'loaded_package_mismatch_'+name)
        self.coverage=sqlite3.connect(self.paths['coverage_database'].resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
        self.coverage.execute('PRAGMA query_only=ON');self.coverage.execute('PRAGMA cache_size=-8192')
        self._verify_coverage_receipt()

    def close(self):
        if getattr(self,'coverage',None) is not None:self.coverage.close();self.coverage=None

    def _verify_coverage_receipt(self):
        cert=self.certificate;c=cert['coverage'];art=cert['artifacts'];db=self.coverage
        control=dict(db.execute('SELECT key,value FROM control'))
        require(control.get('status')=='complete' and control.get('projector_profile')==cert['projection_profile'] and
                control.get('old_package_sha256')==art['old_raw_database']['sha256'] and
                control.get('old_projection_signature_package_sha256')==art['projected_database']['sha256'] and
                control.get('plan_sha256')==art['derivation_plan']['sha256'],'coverage_control_mismatch')
        rows,old_rows,new_rows,zero,quarantined,segments,maxcp=db.execute('SELECT count(*),sum(old_text_id IS NOT NULL),sum(old_text_id IS NULL),sum(segments=0),sum(quarantine!=0),sum(segments),max(source_codepoints) FROM coverage').fetchone()
        require((rows,old_rows,new_rows,zero,quarantined,segments)==(c['coverage_rows'],c['old_unique_raw_texts'],c['new_blog_unique_raw_texts'],c['zero_segment_views'],c['quarantined_views'],c['segment_rows']), 'coverage_ledger_counts_mismatch')
        require(maxcp<=cert['limits']['historical_view_codepoints'],'coverage_view_cap')
        require(db.execute('SELECT count(*) FROM segments').fetchone()[0]==segments,'segment_ledger_count_mismatch')
        require(db.execute('SELECT count(*) FROM segments s LEFT JOIN coverage c ON c.raw_sha256=s.old_raw_sha256 WHERE c.raw_sha256 IS NULL OR s.segment_index<0 OR s.segment_index>=c.segments OR s.source_start<0 OR s.source_end<=s.source_start OR s.source_end>c.source_codepoints').fetchone()[0]==0,'invalid_segment_ledger_reference')
        receipt=json.loads(self.paths['derivation_receipt'].read_text())
        require(receipt.get('purpose')=='exclusion_only' and receipt.get('G2_admitted') is False and
                receipt.get('source_bodies_written') is False and receipt.get('model_parser_target_prediction_calls')==0 and
                receipt.get('cross_projection_coverage_certified') is False,'derivation_scope_or_claim_mismatch')
        require(receipt.get('status')=='complete_projected_signature_package_pending_independent_review' and
                receipt.get('plan_sha256')==art['derivation_plan']['sha256'] and
                receipt.get('old_expected_views')==c['old_source_view_bindings'] and receipt.get('old_missing_views')==0 and
                receipt.get('old_unique_texts_expected')==c['old_unique_raw_texts'] and
                receipt.get('new_package',{}).get('sha256')==art['projected_database']['sha256'] and
                receipt.get('coverage_database',{}).get('sha256')==art['coverage_database']['sha256'],'derivation_receipt_mismatch')
        require(sum(receipt['source_counts'].values())==324323 and receipt['source_counts'].get('new_pre2022_blog3')==3,'source_binding_receipt_counts')
        require(receipt['counts']['unique_texts_projected']==rows and receipt['counts']['projected_segments']==segments and
                receipt['counts'].get('record_quarantines',0)==quarantined and receipt['counts'].get('zero_segment_views',0)==zero,'derivation_coverage_counts')
        resources=receipt['resources']
        require(resources['peak_rss_bytes']<=cert['limits']['peak_rss_bytes'] and
                resources['total_private_bytes_including_old']<=cert['limits']['total_private_bytes'],'derivation_resource_limits')
        plan=json.loads(self.paths['derivation_plan'].read_text())
        code={Path(b['path']).name:b for b in plan['code_bindings']}
        require(plan.get('purpose')=='exclusion_only' and plan.get('old_view_codepoints_cap')==200000 and
                plan.get('candidate_codepoints_cap_unchanged')==20000 and plan.get('model_parser_fit_target_calls_allowed')==0 and
                plan.get('new_download_bytes')==0 and plan.get('owner_text_allowed') is False and
                plan.get('rawtext_persisted') is False,'derivation_plan_scope_mismatch')
        require(plan['projector_profile']==cert['projection_profile'] and
                code['project_wikitext.py']['sha256']==art['projector']['sha256'] and
                code['projection_contract.py']['sha256']==art['validator']['sha256'],'plan_projection_code_mismatch')

    def annotate(self, receipt, *, raw_text, projection, candidate_member_key, validate_projection, resource_callback=None):
        """Return a private receipt with bounded coverage annotation and alias edges."""
        result=copy.deepcopy(receipt)
        result.update(bounded_cross_projection_coverage_reviewed=False,cross_projection_coverage_certified=False,
                      admission_authorized=False,requires_separate_G2_review=True,stage_stop_required=requires_stage_stop(receipt))
        try:
            require(not result['stage_stop_required'],'upstream_stage_stop_required')
            cert=self.certificate
            for name,path in self.paths.items():
                stat=path.stat();require((stat.st_size,stat.st_mtime_ns,stat.st_ino)==self.stats[name],'certificate_artifact_changed_after_load')
            require(len(raw_text)<=cert['limits']['candidate_view_codepoints'],'candidate_projection_cap')
            require(projection.get('profile')==cert['projection_profile'] and
                    projection.get('source_frame') in cert['candidate_source_frames'],'unsupported_candidate_profile_or_frame')
            require(projection.get('source_sha256')==sha(raw_text.encode())==receipt.get('source_sha256'),'candidate_hash_mismatch')
            require(Path(validate_projection.__code__.co_filename).resolve()==self.paths['validator'].resolve(),'unbound_candidate_validator')
            validation=validate_projection(raw_text,projection)
            require(validation.get('status')=='source_map_verified','candidate_projection_validation_failed')
            require(not projection.get('flags',{}).get('record_quarantine_reasons') and projection.get('segments'),'candidate_role_or_mapping_quarantine')
            require(receipt.get('complete_declared_view_comparisons') is True and receipt.get('signature_scan_complete') is True,
                    'candidate_declared_view_comparisons_incomplete')
            seen={p['package']:p for p in receipt.get('packages',[])}
            for name in PACKAGE_ARTIFACTS:
                package=seen.get(cert['package_names'][name]);require(package is not None,'reviewed_package_missing_from_comparison')
                require(package.get('package_sha256')==cert['artifacts'][name]['sha256'] and package.get('complete_signature_scan') is True,
                        'reviewed_package_comparison_mismatch')
            result['expanded_exclusion_edges']=expand_coverage_aliases(result,candidate_member_key,coverage_db=self.coverage,
                package_by_artifact=self.packages,package_names=cert['package_names'],resource_callback=resource_callback)
            result.update(bounded_cross_projection_coverage_reviewed=True,compatibility_certificate_sha256=self.sha256,
                          compatibility_scope='same_reviewed_profile_and_declared_source_views_only',
                          omitted_role_regions='raw_only',known_zero_segment_old_views=cert['coverage']['zero_segment_views'],
                          known_quarantined_old_views=cert['coverage']['quarantined_views'])
            if result.get('status')=='quarantine_unmatched_cross_projection_coverage':
                result['status']='no_known_signature_match_bounded_views_not_admission'
        except (CompatibilityError,OSError,sqlite3.Error,ValueError,KeyError,TypeError,AttributeError,RuntimeError) as error:
            result.update(status='quarantine',compatibility_blocker=str(error))
            if isinstance(error,(RuntimeError,BoundExceeded)) or str(error) in STAGE_STOP_BLOCKERS:
                result['stage_stop_required']=True
        return result
