"""Independent offline acquisition audit. Corpus bytes are data, never code.

Writes only this review's safe aggregate and private hash bindings. Does not
import acquisition code, project Markdown, load fingerprints, or create splits.
"""
import argparse
import collections
import datetime
import hashlib
import json
import pathlib
import re
import unicodedata

PACKAGE_SHA = '86c8503e5594007fd89124a7b7836029f2b0bae4860ba0fa008a3eef764d45c4'
PINNED = {
    'harttle-land': ('harttle/harttle.github.io', 'f08a4c0e4525c985a1e091f860524a794ce134b6', 'CC-BY-4.0', 375),
    'wu-kan': ('wu-kan/wu-kan.github.io', '96cc63b0569f82ceb7fb991b8846369267d9ebe4', 'CC-BY-4.0', 388),
    'ddadaal': ('ddadaal/ddadaal.me', '92be42e96af71699b7f8d7ef08b21b2f37092836', 'CC-BY-SA-4.0', 25),
}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def object_sha(kind, data):
    return hashlib.sha1(kind.encode() + b' ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def strict_pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ValueError('duplicate JSON key')
        result[k] = v
    return result

def decode_json(data):
    return json.loads(data, object_pairs_hook=strict_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def norm(text):
    if unicodedata.unidata_version != '15.0.0':
        raise ValueError('Unicode 15.0.0 required')
    return ''.join(c for c in unicodedata.normalize('NFKC', text) if not c.isspace())

def norm_sha(text):
    return sha(b'nfkc-no-ws/v1\0' + norm(text).encode())

def reconstruct_tree(metadata):
    assert metadata.get('truncated') is False
    rows = {r['path']: r for r in metadata['tree']}
    assert len(rows) == len(metadata['tree'])
    children = collections.defaultdict(list)
    for path, row in rows.items():
        p = pathlib.PurePosixPath(path)
        assert not p.is_absolute() and '..' not in p.parts and str(p) == path
        parent = str(p.parent) if str(p.parent) != '.' else ''
        children[parent].append((p.name, row))
        if parent:
            assert rows[parent]['type'] == 'tree'
    calculated = {}
    for directory in sorted(children, key=lambda x: (x.count('/'), len(x)), reverse=True):
        data = bytearray()
        for name, row in sorted(children[directory], key=lambda item: (item[0] + ('/' if item[1]['type'] == 'tree' else '')).encode()):
            digest = calculated[row['path']] if row['type'] == 'tree' else row['sha']
            assert digest == row['sha']
            mode = row['mode'].lstrip('0')
            data.extend(mode.encode() + b' ' + name.encode() + b'\0' + bytes.fromhex(digest))
        calculated[directory] = object_sha('tree', data)
    return calculated[''], rows

PATTERNS = {
    'repost_attribution_marker': r'转载|轉載|转自|轉自|reposted\s+from|reproduced\s+from',
    'translation_marker': r'翻译|翻譯|译自|譯自|译文|譯文|translated\s+from|translation\s+of',
    'problem_assignment_or_paper_marker': r'题目描述|題目描述|题面|題面|作业|作業|homework|problem\s+statement|论文|論文',
    'license_exception_review_marker': r'除特别声明|除特別聲明|未经.{0,12}许可|未經.{0,12}許可|禁止转载|禁止轉載|谢绝转载|謝絕轉載|保留所有权利|保留所有權利|all\s+rights\s+reserved|noncommercial|非商业|非商業|CC[ -]?BY[ -]?NC',
    'generated_content_marker': r'<!--\s*(?:automatically\s+)?generated|automatically\s+generated|auto[- ]generated|由.{0,20}自动生成|由.{0,20}自動生成',
    'html_pre_or_script_marker': r'<(?:pre|script)(?:\s|>)',
    'liquid_template_marker': r'\{%|\{\{',
}

def structural(text):
    lines = text.splitlines(keepends=True)
    fm, claims, unclosed = '', collections.defaultdict(list), False
    if lines and lines[0].lstrip('\ufeff').strip() == '---':
        closing = next((i for i in range(1, min(len(lines), 1000)) if lines[i].strip() in ('---', '...')), None)
        if closing is None:
            fm, unclosed = ''.join(lines[:1000]), True
        else:
            fm = ''.join(lines[:closing+1])
            for line in lines[1:closing]:
                m = re.fullmatch(r'([A-Za-z_][A-Za-z_0-9-]*):\s*(.*?)(?:\r?\n)?', line)
                if m:
                    claims[m[1].lower()].append(m[2])
    active, fence_count, fence_chars = None, 0, 0
    for line in lines:
        m = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if active:
            fence_chars += len(line)
            if m and m[1][0] == active[0] and len(m[1]) >= active[1] and not m[2].strip():
                active = None
        elif m:
            active, fence_count = (m[1][0], len(m[1])), fence_count + 1
            fence_chars += len(line)
    code = {'fenced_block_markers': fence_count, 'fenced_region_codepoints': fence_chars,
            'unclosed_fence': bool(active),
            'indented_line_markers': sum(bool(re.match(r'^(?: {4}|\t)\S', l)) for l in text.splitlines()),
            'blockquote_line_markers': sum(bool(re.match(r'^ {0,3}>', l)) for l in text.splitlines()),
            'inline_backtick_marker_pairs': len(re.findall(r'(?<!`)`[^`\r\n]+`(?!`)', text))}
    flags = {k: bool(re.search(p, text, re.I)) for k, p in PATTERNS.items()}
    flags.update(fenced_code_marker=bool(fence_count), blockquote_marker=bool(code['blockquote_line_markers']),
                 frontmatter_license_or_copyright_claim=bool(set(claims) & {'license','copyright','copy','rights'}),
                 frontmatter_author_claim=bool(set(claims) & {'author','authors'}), frontmatter_unclosed=unclosed,
                 frontmatter_layout_or_template_claim=bool(set(claims) & {'layout','template'}))
    return fm, dict(claims), code, flags

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=pathlib.Path, required=True)
    ap.add_argument('--original', type=pathlib.Path, required=True)
    ap.add_argument('--review', type=pathlib.Path, required=True)
    ap.add_argument('--diagnostic-allowlist', type=pathlib.Path, required=True)
    args = ap.parse_args()
    root, original, review = args.root.resolve(), args.original.resolve(), args.review.resolve()
    private = root / 'private'
    bindings = {}

    def read(p):
        assert p.is_file() and not p.is_symlink()
        data = p.read_bytes()
        bindings[str(p)] = {'sha256': sha(data), 'bytes': len(data)}
        return data

    def js(p):
        return decode_json(read(p))

    package_bytes = read(root / 'public/FILE_HASHES.json')
    assert sha(package_bytes) == PACKAGE_SHA
    package = decode_json(package_bytes)
    for relative, expected in package['files'].items():
        path = root / 'public' / relative
        assert path.resolve().is_relative_to(root / 'public')
        data = read(path)
        assert {'sha256':sha(data), 'bytes':len(data)} == expected
    aggregate = js(root / 'public/blog-acquisition.aggregate.json')
    provenance = js(root / 'public/provenance.json')
    catalogue = js(original / 'public/catalogue.json')
    assert bindings[str(original / 'public/catalogue.json')] == provenance['approved_frame']['source_catalogue']
    prior_review = original.parent / 'style-pre2022-corpora-review/public/INDEPENDENT_REVIEW.zh.md'
    read(prior_review)
    assert bindings[str(prior_review)] == provenance['approved_frame']['prior_review']
    receipt = js(private / 'acquisition-receipt.json')
    plan = js(private / 'acquisition-plan.json')
    ledger = js(private / 'transfer-ledger.json')
    assert ledger == receipt['transfer_ledger']
    assert receipt['completed'] is True
    assert sha(read(private / 'acquisition-receipt.json')) == aggregate['acquisition_receipt_sha256']
    assert sha(read(private / 'runtime/acquire_blog_texts.executed.py')) == package['files']['scripts/acquire_blog_texts.py']['sha256']
    post_bytes = read(private / 'post-manifest.jsonl')
    assert sha(post_bytes) == aggregate['post_manifest_sha256']
    posts = [decode_json(line) for line in post_bytes.splitlines()]
    reps = js(original / 'private/representative-receipt.json')
    assert bindings[str(original / 'private/representative-receipt.json')] == provenance['diagnostic_source_receipt']
    old_allowlist = js(args.diagnostic_allowlist)
    assert old_allowlist['receipt_sha256'] == sha(read(original / 'private/representative-receipt.json'))
    assert old_allowlist['purpose'] == 'exclusion_only'
    rep_map = {(r['repository'],r['path']):r for r in reps}
    assert len(rep_map) == len(reps) == old_allowlist['source_count'] == 3
    for r in old_allowlist['sources']:
        prior = rep_map[(r['repository'],r['path'])]
        assert all(prior[k] == r[k] for k in ('commit','git_blob_sha1','sha256','bytes'))
        assert r['exposure_role'] == 'prior_diagnostic_exclusion_only'
    counts, source_rows, trees, expected_jobs = {}, {}, {}, {}
    for source in receipt['sources']:
        sid = source['source_id']
        repo, commit, license_name, count = PINNED[sid]
        assert source['repository'] == repo and source['commit'] == commit and source['text_license'] == license_name
        catalogue_source = next(s for s in catalogue['sources'] if s['source_id'] == sid)
        tree_path = private / 'metadata' / (repo.replace('/','__') + '.tree.json')
        metadata = js(tree_path)
        # The preserved connector wrapper echoes the requested commit in sha.
        # Its header is not used as root-tree evidence; reconstruct every tree.
        assert metadata['sha'] == commit
        assert read(tree_path) == read(original / 'private/metadata' / tree_path.name)
        tree_sha, entries = reconstruct_tree(metadata)
        assert tree_sha == source['git_tree_sha1'] == catalogue_source['version']['git_tree_sha1']
        assert sha(read(tree_path)) == source['manifest_sha256'] == catalogue_source['version']['manifest_sha256']
        commit_path = tree_path.with_name(tree_path.name.replace('.tree.', '.commit.'))
        commit_metadata = js(commit_path)
        assert sha(read(commit_path)) == source['commit_response_sha256']
        assert commit_metadata['sha'] == commit and commit_metadata['tree']['sha'] == tree_sha
        assert commit_metadata['committer']['date'] == catalogue_source['version']['git_committer_timestamp']
        assert datetime.datetime.fromisoformat(commit_metadata['committer']['date']) < datetime.datetime.fromisoformat(catalogue['cutoff_exclusive'])
        assert commit_metadata['verification']['verified'] is False
        selected = {p:r for p,r in entries.items() if r['type']=='blob' and
                    (bool(re.fullmatch(r'contents/\d{8}[^/]+/cn\.md', p)) if sid=='ddadaal' else p.startswith('_posts/'))}
        assert len(selected) == count == source['candidate_files'] == catalogue_source['counts']['candidate_files']
        assert sum(r['size'] for r in selected.values()) == source['candidate_bytes'] == catalogue_source['size']['candidate_source_bytes']
        expected_jobs.update({(sid,p):'candidate_text' for p in selected})
        notices = {'harttle-land':['README.md'],'wu-kan':['_config.yml'],'ddadaal':['src/components/Footer/Brief.tsx','src/i18n/cn.ts']}[sid]
        expected_jobs.update({(sid,p):'historical_license_evidence' for p in notices})
        trees[sid], source_rows[sid], counts[sid] = entries, source, collections.Counter()
    assert len(source_rows) == 3
    jobs = {(r['source_id'],r['path']):r for r in plan['jobs']}
    results = {(r['source_id'],r['path']):r for r in receipt['results']}
    assert len(jobs) == len(plan['jobs']) == len(results) == len(receipt['results']) == 792
    assert set(jobs) == set(results) == set(expected_jobs)
    article_data = {}
    for key, record in results.items():
        sid, path = key
        job, src, tree_entry = jobs[key], source_rows[sid], trees[sid][path]
        assert record['purpose'] == job['purpose'] == expected_jobs[key]
        assert tree_entry['type']=='blob' and tree_entry['mode']=='100644'
        destination = private / ('raw' if record['purpose']=='candidate_text' else 'license-raw') / sid / path
        assert pathlib.Path(record['dest']) == destination and destination.resolve().is_relative_to(private)
        raw = read(destination)
        assert len(raw) == record['bytes'] == job['expected_bytes'] == tree_entry['size']
        assert sha(raw) == record['sha256'] and object_sha('blob', raw) == record['git_blob_sha1'] == tree_entry['sha']
        assert record['commit'] == src['commit'] and record['repository'] == src['repository']
        text = raw.decode('utf-8', errors='strict')
        is_diagnostic = (record['repository'],path) in rep_map
        assert record['diagnostic_exposure'] == is_diagnostic
        assert record['model_admitted'] is False
        if is_diagnostic:
            rep = rep_map[(record['repository'],path)]
            assert all(record[k] == rep[k] for k in ('sha256','git_blob_sha1','bytes'))
            assert raw == read(original / 'private/representatives' / rep['file'])
            assert record['transfer_status'] == 'reused_exposed_diagnostic'
        else:
            assert record['transfer_status'] == 'downloaded'
        if record['purpose'] == 'candidate_text':
            article_data[key] = (record, raw, text)
        elif sid == 'harttle-land':
            assert '主题和内容使用 [CC-BY 4.0]' in text
        elif sid == 'wu-kan':
            assert '我的文章' in text and 'CC BY 4.0' in text and '除特别声明或转载文章外' in text
        elif path.endswith('.tsx'):
            assert 'root("license")' in text and 'https://creativecommons.org/licenses/by-sa/4.0/' in text
        else:
            assert 'license: "本站文章在{}协议下授权"' in text
    assert len(posts) == len(article_data) == 788
    seen, raw_groups, normal_groups, blocks = set(), collections.defaultdict(set), collections.defaultdict(set), collections.defaultdict(set)
    for post in posts:
        sid, path = post['source_id'], post['path']
        record, raw, text = article_data[(sid,path)]
        key = canonical(['gitblog',record['repository'],'post:' + path])
        assert post['member_key'] == key and key not in seen
        seen.add(key)
        assert post['sha256'] == record['sha256'] and post['commit'] == record['commit']
        assert post['historical_root_license'] == PINNED[sid][2] and post['effective_text_license'] is None
        assert post['per_item_rights_status'] == 'unreviewed_root_license_with_possible_exceptions'
        assert post['assistance_status'] == 'unknown' and post['human_verified'] is False and post['admitted'] is False
        assert post['source_view_role'] == 'raw_markdown' and post['structural_flags_are_not_semantic_truth'] is True
        assert post['diagnostic_exposure'] == record['diagnostic_exposure']
        assert post['exclusion_role'] == ('permanent_exposed_diagnostic' if record['diagnostic_exposure'] else 'not_yet_assigned_acquisition_only')
        normalized = norm(text)
        assert post['raw_codepoints'] == len(text) and post['normalized_codepoints'] == len(normalized)
        assert post['normalized_sha256'] == norm_sha(text)
        fm, claims, code, flags = structural(text)
        assert fm == post['frontmatter_raw'] and claims == post['unparsed_top_level_field_claims']
        assert code == post['code_structure'] and flags == post['structural_flags']
        count = counts[sid]
        count.update(candidate_text_files=1, utf8_bytes=len(raw), raw_codepoints=len(text),
                     diagnostic_permanent_exclusions=int(record['diagnostic_exposure']), frontmatter_present=bool(fm),
                     path_date_1999_placeholder_claim=bool(re.search(r'(?:^|/)1999[-]?\d\d[-]?\d\d', path)),
                     unclosed_code_fence=code['unclosed_fence'])
        count.update(flags)
        raw_groups[sha(raw)].add(key)
        normal_groups[norm_sha(text)].add(key)
        for block in re.split(r'(?:\r?\n[\t ]*){2,}', text):
            if len(norm(block)) >= 200:
                blocks[norm_sha(block)].add(key)
    copy_expected = {kind:[{'hash':h,'members':sorted(keys)} for h,keys in sorted(groups.items()) if len(keys)>1]
                     for kind,groups in [('raw_sha256',raw_groups),('normalized_sha256',normal_groups),('shared_raw_blankline_block_ge200_normalized_chars',blocks)]}
    assert copy_expected == js(private / 'copy-groups.json')
    lineage = []
    for (sid,path),(record,_,_) in article_data.items():
        p = pathlib.PurePosixPath(path)
        for other, entry in trees[sid].items():
            q = pathlib.PurePosixPath(other)
            if entry['type']=='blob' and other!=path:
                if (p.with_suffix('')==q.with_suffix('') and q.suffix.lower() in ('.md','.rmd','.html','.markdown')) or (sid=='ddadaal' and p.parent==q.parent and q.name=='en.md'):
                    lineage.append((sid,path,other))
    assert not lineage and js(private / 'lineage-hints.json') == []
    for src in aggregate['source_records']:
        assert dict(counts[src['source_id']]) == src['counts']
        assert src['share_alike_required'] == (src['source_id']=='ddadaal')
    assert ledger['attempts'] == 789 and ledger['completed'] == 792 and ledger['reused'] == 3 and ledger['failures'] == []
    downloaded = sum(r['bytes'] for r in results.values() if r['transfer_status']=='downloaded')
    assert downloaded == ledger['network_entity_bytes'] == 13857155
    assert downloaded + ledger['prior_metadata_entity_allowance'] < 30*1024**2
    assert sum(r['bytes'] for r in results.values()) == receipt['total_retained_source_bytes'] == 13909834
    assert sum(len(raw) for _,raw,_ in article_data.values()) == aggregate['candidate_utf8_bytes'] == 13869106
    retained = sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    assert retained < 100*1024**2
    shared = copy_expected['shared_raw_blankline_block_ge200_normalized_chars']
    assert len(raw_groups)==len(normal_groups)==788 and len(shared)==41
    assert len({k for group in shared for k in group['members']})==46
    for relative in ('post-manifest.jsonl','copy-groups.json','lineage-hints.json'):
        assert read(private / relative) == read(private / 'replay/private' / relative)
    assert read(root / 'public/blog-acquisition.aggregate.json') == read(private / 'replay/public/blog-acquisition.aggregate.json')
    for key in ('model_admitted','model_fit_performed','split_created','linguistic_parser_run','markdown_body_projector_run','old_labelled_test_text_read','personal_author_stage_accessed'):
        assert aggregate[key] is False
    output = dict(status='PASS_ACQUISITION_IDENTITY_AND_DECLARED_CENSUS_ONLY', package_sha256=PACKAGE_SHA,
        verified_public_files=len(package['files']), reconstructed_git_trees=3, verified_article_blobs=788,
        verified_license_blobs=4, verified_canonical_member_ids=788, verified_unicode_normalizations=788,
        diagnostic_exclusions_verified_against_prior_allowlist=3, unicode_version=unicodedata.unidata_version,
        article_bytes=13869106, all_source_and_license_bytes=13909834, raw_unique=788, normalized_unique=788,
        shared_long_blankline_block_groups=41, affected_article_members=46, unresolved_metadata_lineage_hints=0,
        source_counts={k:dict(v) for k,v in counts.items()}, new_http_entity_bytes=downloaded,
        prior_metadata_entity_allowance=ledger['prior_metadata_entity_allowance'], charged_entity_bytes=downloaded+ledger['prior_metadata_entity_allowance'],
        retained_acquisition_directory_bytes=retained, network_cap_bytes=30*1024**2, expanded_cap_bytes=100*1024**2,
        deterministic_replay_outputs_verified=4, body_projection_performed=False, third_party_code_executed=False,
        linguistic_analysis_performed=False, model_fit_performed=False, split_created=False,
        model_admission_approved=False, human_origin_verified=False, independent_natural_semantic_review=False,
        fingerprint_databases_read=False, remote_writes=False, new_network_reads=False)
    for directory in (review/'public', review/'private'):
        directory.mkdir(parents=True, exist_ok=True)
    (review/'private/input-bindings.private.json').write_text(json.dumps(bindings,ensure_ascii=False,indent=2)+'\n')
    output['private_input_bindings_sha256'] = sha((review/'private/input-bindings.private.json').read_bytes())
    (review/'public/independent-checks.aggregate.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:output[k] for k in ('status','verified_article_blobs','verified_license_blobs','shared_long_blankline_block_groups','charged_entity_bytes','retained_acquisition_directory_bytes')}))

if __name__ == '__main__':
    main()
