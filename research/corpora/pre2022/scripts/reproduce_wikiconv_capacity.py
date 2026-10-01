"""Read metadata only; do not decompress utterances or inspect evaluation targets.
Requires the audited project's Archive/object_items reader in --audit-tools.
Output is a capacity ceiling under an already frozen dependency graph, not admission.
"""
import argparse,collections,hashlib,json,pathlib,sqlite3,sys
ARCHIVE_SHA256='635500ba887cef0c9d2bfaef03659de2974b5fd84b8a0cd90a9bd7bdef7f492a'
SELECTION_SHA256='ddbe04ae3a3a1d289fbb53e35872b2eb9df27407d92f6002066c992c1580b0b8'
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus-dir',type=pathlib.Path,required=True);p.add_argument('--selection',type=pathlib.Path,required=True);p.add_argument('--audit-tools',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args()
    b=a.selection.read_bytes()
    if hashlib.sha256(b).hexdigest()!=SELECTION_SHA256:raise ValueError('frozen_selection_hash_mismatch')
    s=json.loads(b)
    if s['raw_text_in_output'] is not False:raise ValueError('selection_must_be_metadata_only')
    selected={r['component_id'] for r in s['selected_records']};excluded=set(s['excluded_component_ids']);mapping=s['all_page_component_map']
    if len(selected)!=192 or len(excluded)!=475 or selected&excluded:raise ValueError('unexpected_exclusion_frame')
    reader_hashes={'wikiconv_annual_census.py':'e5051bd239812935096a035daadb3350a63ca151c7acd24021fa6eb6e39710b5','wikiconv_zip_audit.py':'84ced8137313f6d81c54b4fa6c271ef7f65ff110dc3d395330ce9cf603997e73'}
    for name,digest in reader_hashes.items():
        if hashlib.sha256((a.audit_tools/name).read_bytes()).hexdigest()!=digest:raise ValueError('audited_metadata_reader_hash_mismatch')
    sys.path.insert(0,str(a.audit_tools))
    from wikiconv_annual_census import Archive,object_items
    from wikiconv_zip_audit import metadata
    archive=Archive(a.corpus_dir/'full.corpus.zip',ARCHIVE_SHA256,80074478,871024181)
    page={}
    try:
        for key,r in object_items(archive.chunks('conversations.json')):page[key]=metadata(r)['page_id']
        if set(archive.verified)!={'conversations.json'}:raise ValueError('unexpected_archive_member_read')
    finally:archive.close()
    db=sqlite3.connect((a.corpus_dir/'structural-frame.sqlite').resolve().as_uri()+'?mode=ro',uri=True);db.execute('PRAGMA query_only=ON')
    control=dict(db.execute('SELECT key,value FROM control'))
    if control['archive_sha256']!=ARCHIVE_SHA256 or control['status']!='structural_census_complete':raise ValueError('structural_database_identity_mismatch')
    counts={}
    for name,condition in [('nonempty','nonempty=1'),('size_200_20000','chars BETWEEN 200 AND 20000')]:
        rows=db.execute("SELECT conversation FROM views WHERE role='top_level' AND header=0 AND "+condition);pages=set();n=0
        for (conversation,) in rows:pages.add(page[conversation]);n+=1
        components={mapping[x] for x in pages}
        counts[name]=dict(source_records=n,pages=len(pages),known_components_before_exclusions=len(components),known_components_after_old192_and_exposed_exclusions=len(components-selected-excluded))
    db.close()
    result=dict(schema_version='style-pre2022-metadata-capacity/1',raw_text_read=False,parser_run=False,train_admission=False,old_selection_sha256=SELECTION_SHA256,counts=counts,limitations=[
      'Only metadata size checks; unit count, Han fraction, role projection, quote or bot filtering and causal boundary eligibility not evaluated.',
      'Prior copy graph includes complete annual long exact views but near-duplicate edges only prior candidate/exposure texts; all new candidates need a new cross-frame near-copy audit.',
      'Counts are ceilings under known dependencies, not guarantees of independent usable records.',
      'Old selected192 and all475 known exposed components excluded. Old32 test is a consumed benchmark and remains excluded as full components; this metadata-only census reads no test bodies. New generalization claims require a separate fresh holdout.'
    ])
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(counts,ensure_ascii=False))
if __name__=='__main__':main()
