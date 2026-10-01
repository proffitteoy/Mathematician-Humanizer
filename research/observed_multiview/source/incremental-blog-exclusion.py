"""One-time, offline 3-blog raw-signature increment and diagnostic coverage checks.

No acquisition. Never opens old raw sources. Markdown projections below are
exclusion-only diagnostic probes, NOT the approved natural calibration profile.
Only hashes/counts/roles/source offsets/signature memberships are persisted privately.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import resource
import socket
import subprocess
import sys
import time
from matcher import (ALGORITHM, OLD_DATABASE_SHA256, SignaturePackage, SignatureWriter,
                     canonical, filehash, match_records, record_signatures, sha)

ROOT = Path('/workspace/shared/style-scale10-source-v01')
PRIVATE = ROOT/'private'
PUBLIC = ROOT/'public'
ALLOWLIST = PRIVATE/'incremental-blog-exclusion-allowlist.private.json'
ALLOWLIST_SHA256 = 'a3bbaf1bb352eeca4c10a96c5b6eb9817e94dc2ea28d20055a603973884a492f'
OLD = Path('/workspace/shared/style-compiler-data/exposure-fingerprints-v01')
BASE_PRIVATE_BYTES = 566_539_146
TOTAL_CAP = 1024**3
MEMORY_CAP = 3*1024**3
PROFILE = 'markdown-exclusion-diagnostic-probe/1.0.0'


def write_new(path, obj):
    with path.open('x') as f: json.dump(obj, f, ensure_ascii=False, indent=2); f.write('\n')
    return filehash(path)


def diagnostic_projection(text):
    """A deliberately narrow deletion-only probe with exact char source maps.

    Front matter/fences/blank lines delimit segments. Link destinations and simple
    style delimiters are omitted. HTML/template/table blocks are barriers. This is
    a stress probe for view compatibility, not an author/human/prose classifier.
    """
    barriers=[]; ranges=[]; current=None; fenced=None; front=text.startswith('---\n') or text.startswith('---\r\n')
    front_done=not front
    for m in re.finditer(r'.*(?:\r?\n|$)',text):
        lo,hi=m.span()
        if lo==hi: continue
        line=m.group().rstrip('\r\n')
        reason=None
        if not front_done:
            reason='front_matter'
            if lo>0 and line.strip()=='---': front_done=True
        elif fenced:
            reason='fenced_code'
            if re.match(r'^\s*'+re.escape(fenced)+r'{3,}',line): fenced=None
        elif re.match(r'^\s*(`{3,}|~{3,})',line):
            fenced=re.match(r'^\s*(`{3,}|~{3,})',line).group(1)[0];reason='fenced_code'
        elif not line.strip(): reason='blankline'
        elif any(token in line for token in ('<','{{','}}','|')): reason='unsupported_markup'
        if reason:
            if current is not None: ranges.append(current);current=None
            barriers.append({'start':lo,'end':hi,'reason':reason})
        else:
            if current is None: current=[lo,hi]
            else: current[1]=hi
    if current is not None:ranges.append(current)
    segments=[]
    for lo,hi in ranges:
        omitted=set()
        source=text[lo:hi]
        for m in re.finditer(r'!?\[([^]\n]+)\]\([^\n)]*\)',source):
            begin,end=m.span();label_start,label_end=m.span(1)
            omitted.update(range(begin,label_start));omitted.update(range(label_end,end))
        for m in re.finditer(r'[`*_]',source):omitted.add(m.start())
        for m in re.finditer(r'(?m)^\s{0,3}(?:#{1,6}\s+|>\s*|[-+]\s+)',source):omitted.update(range(*m.span()))
        accepted=[i for i in range(len(source)) if i not in omitted]
        clean=''.join(source[i] for i in accepted)
        if not clean.strip():continue
        segments.append({'text':clean,'source_spans':[[lo,hi]],
                         'source_map':[[lo+i,lo+i+1,'identity',0] for i in accepted]})
    return {'source_sha256':sha(text.encode()),'profile':PROFILE,'segments':segments,
            'barriers':barriers,'flags':['diagnostic_only_not_prose_admission']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--derive-once',action='store_true');args=parser.parse_args()
    if not args.derive_once:raise RuntimeError('explicit_one_time_flag_required')
    started=time.monotonic()
    def blocked(*args,**kwargs):raise RuntimeError('network_forbidden')
    socket.socket=blocked;socket.create_connection=blocked
    assert filehash(ALLOWLIST)==ALLOWLIST_SHA256
    allow=json.loads(ALLOWLIST.read_text());assert allow['source_count']==3 and len(allow['sources'])==3
    plan_path=PRIVATE/'incremental-blog-exclusion-plan.private.json';plan=json.loads(plan_path.read_text())
    assert plan['allowlist_sha256']==ALLOWLIST_SHA256
    for name,digest in plan['implementation_hashes'].items():assert filehash(PUBLIC/name)==digest
    # Synthetic tests run before any representative raw bytes are opened.
    ran=subprocess.run([sys.executable,'-m','unittest','-v','test_matcher'],cwd=PUBLIC,capture_output=True,text=True)
    assert ran.returncode==0
    write_new(PRIVATE/'incremental-blog-exclusion-presource-tests.private.json',
              {'status':'passed','before_raw_bodies':True,'returncode':ran.returncode,
               'test_log_sha256':sha((ran.stdout+ran.stderr).encode()),'implementation_hashes':plan['implementation_hashes']})
    marker={'purpose':'exclusion_only','allowlist_sha256':ALLOWLIST_SHA256,
            'execution_plan_sha256':filehash(plan_path),'raw_body_reads_started_after_this_marker':True}
    write_new(PRIVATE/'incremental-blog-exclusion-ONE_TIME_STARTED.private.json',marker)
    def guard(stats=None):
        current=BASE_PRIVATE_BYTES+sum(p.stat().st_size for p in PRIVATE.rglob('*') if p.is_file())
        if current>TOTAL_CAP:raise RuntimeError('all_private_derivatives_cap')
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>MEMORY_CAP:raise RuntimeError('memory_cap')
        if time.monotonic()-started>1800:raise RuntimeError('wall_cap')
    writer=None;packages=[]
    try:
        old=SignaturePackage(OLD/'fingerprints.private.sqlite',OLD_DATABASE_SHA256,'old_exposure_v01');packages.append(old)
        writer=SignatureWriter(PRIVATE/'incremental-blog-exclusion.private.sqlite',guard=guard)
        records=[];source_private=[]
        for row in allow['sources']:
            assert filehash(row['license_metadata_path'])==row['license_metadata_sha256']
            path=Path(row['local_path']);assert path.parent==Path('/workspace/shared/style-pre2022-corpora/private/representatives')
            # Exactly one body read per allowed representative, retained only in memory.
            raw=path.read_bytes();assert len(raw)==row['bytes'] and sha(raw)==row['sha256']
            assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==row['git_blob_sha1']
            text=raw.decode('utf-8')
            member=canonical(['gitblog',row['repository'],'post:'+row['path']]).decode()
            writer.add(text,source_id='pre2022_blog_diagnostic3',member_key=member,
                       exposure_role=row['exposure_role'],source_view_role='raw_markdown',
                       source_object_sha256=row['sha256'],locator={'receipt_sha256':allow['receipt_sha256'],'git_blob_sha1':row['git_blob_sha1'],'path':row['path']})
            projection=diagnostic_projection(text)
            assert projection['segments']
            key='diagnostic-'+str(len(records)+1)
            records.append({'record_key':key,'raw_text':text,'projection':projection,'raw_sha256':row['sha256']})
            source_private.append({'record_key':key,'member_key':member,'raw_sha256':row['sha256'],
                                   'diagnostic_segments':len(projection['segments']),
                                   'diagnostic_barriers':len(projection['barriers']),
                                   'source_span_offsets':[s['source_spans'] for s in projection['segments']],
                                   'projected_codepoints':sum(len(s['text']) for s in projection['segments'])})
            guard()
        increment_receipt=writer.finish();writer=None
        increment=SignaturePackage(increment_receipt['path'],increment_receipt['sha256'],'incremental_blog_diagnostic3');packages.append(increment)
        budget={'used':0,'cap':300_000_000}
        combined=match_records(records,packages=packages,require_package_names=[p.name for p in packages],resource_callback=guard,comparison_budget=budget)
        assert len(combined)==3 and all(r['signature_scan_complete'] for r in combined)
        for result in combined:
            assert result['status']=='excluded_known_exposure_match'
            assert any(h['candidate_role']=='full_raw_source_view' and 'raw_exact' in h['reasons'] for h in result['packages'][1]['hits'])
        # Independent view subsets against raw-only increment establish actual
        # projection sensitivity; full raw identity is not mistaken for clean recall.
        view_metrics=[]
        for record in records:
            sigs=record_signatures(record['raw_text'],record['projection'],record['raw_sha256'])
            projected=[s for s in sigs if s.role=='projected_segment']
            spans=[s for s in sigs if s.role=='mapped_contiguous_raw_source_span']
            p=increment.compare(projected,resource_callback=guard,comparison_budget=budget)
            r=increment.compare(spans,resource_callback=guard,comparison_budget=budget)
            pm={h['candidate_view'] for h in p['hits']};rm={h['candidate_view'] for h in r['hits']}
            view_metrics.append({'record_key':record['record_key'],
                                 'projected_segments':len(projected),'projected_segments_matched_raw_signatures':len(pm),
                                 'mapped_raw_spans':len(spans),'mapped_raw_spans_matched_raw_signatures':len(rm),
                                 'projected_unmatched_normalized_lengths':[s.normalized_codepoints for s in projected if s.key not in pm],
                                 'raw_span_unmatched_normalized_lengths':[s.normalized_codepoints for s in spans if s.key not in rm]})
        private_receipt={'scope':'three_existing_licensed_nonowner_diagnostics_exclusion_only',
                         'source_bindings':source_private,'package':increment_receipt,
                         'combined_matching_receipts':combined,'coverage':view_metrics}
        detailed=PRIVATE/'incremental-blog-exclusion-coverage.private.json'
        detailed_hash=write_new(detailed,private_receipt)
        guard()
        public={'schema_version':'incremental-blog-exclusion-coverage/1','status':'implemented_self_verified_pending_independent_review',
                'purpose':'exclusion_only','old_package_unchanged':filehash(OLD/'fingerprints.private.sqlite')==OLD_DATABASE_SHA256,
                'allowlist_sha256':ALLOWLIST_SHA256,'old_package_sha256':OLD_DATABASE_SHA256,
                'incremental_package_sha256':increment_receipt['sha256'],'incremental_package_bytes':increment_receipt['bytes'],
                'incremental_texts':increment_receipt['text_count'],'incremental_grams':increment_receipt['gram_count'],
                'incremental_bindings':increment_receipt['binding_count'],'raw_sources_read_once':3,
                'raw_source_bytes':sum(x['bytes'] for x in allow['sources']),'license_roles_and_raw_hashes_frozen_before_read':True,
                'diagnostic_projection_profile':PROFILE,'full_raw_self_exclusions':3,
                'all_three_compared_to_complete_old_signatures':all(r['packages'][0]['reference_texts_scanned']==100541 for r in combined),
                'projected_segments_total':sum(x['projected_segments'] for x in view_metrics),
                'projected_segments_matched_raw_signatures':sum(x['projected_segments_matched_raw_signatures'] for x in view_metrics),
                'mapped_raw_spans_total':sum(x['mapped_raw_spans'] for x in view_metrics),
                'mapped_raw_spans_matched_raw_signatures':sum(x['mapped_raw_spans_matched_raw_signatures'] for x in view_metrics),
                'coverage_gaps':['No universal clean-prose coverage claim; old raw sources were not reprojected.',
                                 'Short, fragmented, heavily transformed, or semantically rewritten excerpts may not reach 40 shared distinct grams or a 64-character exact block.',
                                 'Diagnostic Markdown probe is not a licensed-body/prose qualification or calibration.',
                                 'Negative matches never authorize admission; incompatible mappings and missing packages quarantine.'],
                'new_download_bytes':0,'owner_text_models_pos_targets_predictions_read':False,'new_natural_calibration_run':False,
                'private_detail_sha256':detailed_hash,'comparison_budget':budget,
                'resources':{'elapsed_seconds':time.monotonic()-started,'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                             'existing_private_derivatives_bytes':BASE_PRIVATE_BYTES,
                             'new_private_tree_bytes_at_receipt':sum(p.stat().st_size for p in PRIVATE.rglob('*') if p.is_file()),
                             'total_private_cap_bytes':TOTAL_CAP}}
        write_new(PUBLIC/'incremental-blog-exclusion-coverage.aggregate.json',public)
        write_new(PRIVATE/'incremental-blog-exclusion-COMPLETE.private.json',{'status':'complete_pending_independent_review','public_aggregate_sha256':filehash(PUBLIC/'incremental-blog-exclusion-coverage.aggregate.json')})
        guard();print(json.dumps(public))
    except Exception as error:
        if writer:writer.close_failed()
        write_new(PRIVATE/'incremental-blog-exclusion-FAILED_STOP.private.json',{'status':'failed_stop_no_raw_retry','error':type(error).__name__,'reason':str(error)})
        raise
    finally:
        for package in packages:package.close()

if __name__=='__main__':main()
