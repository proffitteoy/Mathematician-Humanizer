"""Offline structural census. No Markdown projection, linguistic parser or admission.

Private manifests retain source identities and untrusted source claims. Public
outputs contain source-level provenance and aggregate counts, never raw posts.
"""
import argparse, collections, hashlib, json, pathlib, re, unicodedata
from acquire_blog_texts import candidates, digest, dump, git_blob, tree_root_sha1

VERSION = 'historical-blog-structural-census/1.0'
FLAG_PATTERNS = {
    'repost_attribution_marker': r'(?:转载|轉載|转自|轉自|reposted\s+from|reproduced\s+from)',
    'translation_marker': r'(?:翻译|翻譯|译自|譯自|译文|譯文|translated\s+from|translation\s+of)',
    'problem_assignment_or_paper_marker': r'(?:题目描述|題目描述|题面|題面|作业|作業|homework|problem\s+statement|论文|論文)',
    'license_exception_review_marker': r'(?:除特别声明|除特別聲明|未经.{0,12}许可|未經.{0,12}許可|禁止转载|禁止轉載|谢绝转载|謝絕轉載|保留所有权利|保留所有權利|all\s+rights\s+reserved|noncommercial|非商业|非商業|CC[ -]?BY[ -]?NC)',
    'generated_content_marker': r'(?:<!--\s*(?:automatically\s+)?generated|automatically\s+generated|auto[- ]generated|由.{0,20}自动生成|由.{0,20}自動生成)',
    'html_pre_or_script_marker': r'<(?:pre|script)(?:\s|>)',
    'liquid_template_marker': r'\{%|\{\{',
}

def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def member(repo, path):
    return canonical(['gitblog', repo, 'post:' + path])

def normalize(text):
    if unicodedata.unidata_version != '15.0.0':
        raise RuntimeError('Unicode_15_0_0_required')
    return ''.join(c for c in unicodedata.normalize('NFKC', text) if not c.isspace())

def norm_hash(text):
    return digest(b'nfkc-no-ws/v1\0' + normalize(text).encode('utf-8'))

def frontmatter(text):
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].lstrip('\ufeff').strip() != '---':
        return '', {}, False
    for index, line in enumerate(lines[1:1000], 1):
        if line.strip() in ('---', '...'):
            raw = ''.join(lines[:index+1])
            fields = collections.defaultdict(list)
            for line in lines[1:index]:
                hit = re.match(r'^([A-Za-z_][A-Za-z_0-9-]*):\s*(.*?)(?:\r?\n)?$', line)
                if hit:
                    fields[hit[1].lower()].append(hit[2])
            return raw, dict(fields), False
    return ''.join(lines[:1000]), {}, True

def code_structure(text):
    fence, count, chars, unclosed = None, 0, 0, False
    for line in text.splitlines(keepends=True):
        hit = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence is None:
            if hit:
                fence = (hit[1][0], len(hit[1]))
                count += 1
                chars += len(line)
        else:
            chars += len(line)
            if hit and hit[1][0] == fence[0] and len(hit[1]) >= fence[1] and not hit[2].strip():
                fence = None
    unclosed = fence is not None
    return dict(fenced_block_markers=count, fenced_region_codepoints=chars,
                unclosed_fence=unclosed,
                indented_line_markers=sum(bool(re.match(r'^(?: {4}|\t)\S', l)) for l in text.splitlines()),
                blockquote_line_markers=sum(bool(re.match(r'^ {0,3}>', l)) for l in text.splitlines()),
                inline_backtick_marker_pairs=len(re.findall(r'(?<!`)`[^`\r\n]+`(?!`)', text)))

def structural_row(raw, path):
    text = raw.decode('utf-8', errors='strict')
    fm, claims, fm_unclosed = frontmatter(text)
    flags, evidence = {}, {}
    for key, pattern in FLAG_PATTERNS.items():
        hits = list(re.finditer(pattern, text, re.IGNORECASE))
        flags[key] = bool(hits)
        evidence[key] = [dict(start=h.start(), end=h.end(), matched=h.group()) for h in hits[:20]]
    code = code_structure(text)
    flags['fenced_code_marker'] = bool(code['fenced_block_markers'])
    flags['blockquote_marker'] = bool(code['blockquote_line_markers'])
    flags['frontmatter_license_or_copyright_claim'] = any(k in claims for k in ('license', 'copyright', 'copy', 'rights'))
    flags['frontmatter_author_claim'] = any(k in claims for k in ('author', 'authors'))
    flags['frontmatter_unclosed'] = fm_unclosed
    flags['frontmatter_layout_or_template_claim'] = any(k in claims for k in ('layout', 'template'))
    date = re.search(r'(?:^|/)((?:19|20)\d\d)[-]?(\d\d)[-]?(\d\d)', path)
    return dict(raw_codepoints=len(text), normalized_codepoints=len(normalize(text)),
                normalized_sha256=norm_hash(text), frontmatter_raw=fm,
                unparsed_top_level_field_claims=claims,
                claimed_path_date='-'.join(date.groups()) if date else None,
                claimed_frontmatter_dates={k:v for k,v in claims.items() if k in ('date', 'created', 'updated', 'lastmod', 'modified')},
                structural_flags=flags, structural_evidence_offsets=evidence, code_structure=code,
                han_codepoints=sum('\u3400' <= c <= '\u4dbf' or '\u4e00' <= c <= '\u9fff' for c in text),
                alphanumeric_codepoints=sum(c.isalnum() for c in text))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=pathlib.Path, required=True)
    args = ap.parse_args()
    base, private = args.root, args.root / 'private'
    receipt_path = private / 'acquisition-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    assert receipt['completed'] and not receipt['model_admitted']
    manifest, lineage, counts = [], [], collections.defaultdict(collections.Counter)
    raw_groups, norm_groups, block_groups = collections.defaultdict(list), collections.defaultdict(list), collections.defaultdict(list)
    source_records = []
    for src in receipt['sources']:
        sid, repo, commit = src['source_id'], src['repository'], src['commit']
        tree_path = private / 'metadata' / (repo.replace('/', '__') + '.tree.json')
        assert digest(tree_path.read_bytes()) == src['manifest_sha256']
        tree = json.loads(tree_path.read_text())
        assert tree_root_sha1(tree) == src['git_tree_sha1']
        commit_metadata_path = private / 'metadata' / (repo.replace('/', '__') + '.commit.json')
        commit_metadata = json.loads(commit_metadata_path.read_text())
        assert digest(commit_metadata_path.read_bytes()) == src['commit_response_sha256']
        assert commit_metadata['sha'] == commit and commit_metadata['tree']['sha'] == src['git_tree_sha1']
        selected = candidates(sid, tree['tree'])
        expected = {r['path']:r for r in selected}
        inputs = [r for r in receipt['results'] if r['source_id'] == sid and r['purpose']=='candidate_text']
        assert set(r['path'] for r in inputs) == set(expected) and len(inputs) == len(expected)
        for row in inputs:
            data = pathlib.Path(row['dest']).read_bytes()
            assert digest(data) == row['sha256'] and len(data) == row['bytes'] == expected[row['path']]['size']
            assert git_blob(data) == row['git_blob_sha1'] == expected[row['path']]['sha']
            key = member(repo, row['path'])
            record = dict(row)
            record.pop('text_license', None)
            record.update(structural_row(data, row['path']))
            record.update(member_key=key, source_view_role='raw_markdown',
                git_committer_timestamp=commit_metadata['committer']['date'],
                historical_root_license=src['text_license'], per_item_rights_status='unreviewed_root_license_with_possible_exceptions',
                effective_text_license=None,
                attribution_role='site_account_not_per_passage_authorship', assistance_status='unknown',
                human_verified=False, admitted=False,
                exclusion_role='permanent_exposed_diagnostic' if row['diagnostic_exposure'] else 'not_yet_assigned_acquisition_only',
                declared_dates_are_source_claims=True, structural_flags_are_not_semantic_truth=True)
            manifest.append(record)
            c = counts[sid]
            c['candidate_text_files'] += 1
            c['utf8_bytes'] += len(data)
            c['raw_codepoints'] += record['raw_codepoints']
            c['diagnostic_permanent_exclusions'] += int(row['diagnostic_exposure'])
            c['frontmatter_present'] += bool(record['frontmatter_raw'])
            c['path_date_1999_placeholder_claim'] += bool(record['claimed_path_date'] and record['claimed_path_date'].startswith('1999'))
            c['unclosed_code_fence'] += record['code_structure']['unclosed_fence']
            for flag, value in record['structural_flags'].items():
                c[flag] += value
            raw_groups[row['sha256']].append(key)
            norm_groups[record['normalized_sha256']].append(key)
            text = data.decode('utf-8')
            for block in set(re.split(r'(?:\r?\n[\t ]*){2,}', text)):
                if len(normalize(block)) >= 200:
                    block_groups[norm_hash(block)].append(key)
            # This only links metadata paths. Translation text is not downloaded.
            same_stem = str(pathlib.PurePosixPath(row['path']).with_suffix(''))
            for other in tree['tree']:
                if other['type'] != 'blob' or other['path'] == row['path']:
                    continue
                other_path = pathlib.PurePosixPath(other['path'])
                relationship = None
                if str(other_path.with_suffix('')) == same_stem and other_path.suffix.lower() in ('.md','.rmd','.html','.markdown'):
                    relationship = 'same_stem_source_render_or_version'
                if sid == 'ddadaal' and other_path.parent == pathlib.PurePosixPath(row['path']).parent and other_path.name == 'en.md':
                    relationship = 'same_post_directory_language_sibling'
                if relationship:
                    lineage.append(dict(left=key, right=member(repo,other['path']), relationship=relationship,
                        status='metadata_hint_unresolved_union_or_quarantine_before_admission',
                        right_blob=other['sha'], right_text_acquired=False, source_commit=commit))
        license_records = []
        for row in receipt['results']:
            if row['source_id'] != sid or row['purpose'] != 'historical_license_evidence':
                continue
            data = pathlib.Path(row['dest']).read_bytes()
            assert digest(data) == row['sha256'] and git_blob(data) == row['git_blob_sha1']
            text = data.decode('utf-8')
            if sid == 'harttle-land':
                assert '主题和内容' in text and 'CC-BY 4.0' in text
            elif sid == 'wu-kan':
                assert '我的文章' in text and 'CC BY 4.0' in text and '除特别声明或转载文章外' in text
            elif row['path'].endswith('Brief.tsx'):
                assert 'creativecommons.org/licenses/by-sa/4.0/' in text
            else:
                assert '本站文章在{}协议下授权' in text
            license_records.append(dict(source_url='https://github.com/'+repo+'/blob/'+commit+'/'+row['path'],
                                        git_blob_sha1=row['git_blob_sha1'], sha256=row['sha256'], bytes=len(data)))
        source_records.append(dict(source_id=sid, source_url='https://github.com/'+repo+'/tree/'+commit,
            git_commit=commit, git_tree_sha1=src['git_tree_sha1'], manifest_sha256=src['manifest_sha256'],
            git_committer_timestamp=commit_metadata['committer']['date'],
            commit_signature_verified=commit_metadata['verification']['verified'],
            text_license=src['text_license'], attribution_required=True,
            share_alike_required=src['text_license']=='CC-BY-SA-4.0', third_party_exceptions=True,
            historical_license_blobs=license_records, counts=dict(counts[sid]),
            commit_identity_verification='Official GitHub commit response matches requested SHA and recomputed root tree; raw commit object not reconstructed',
            temporal_evidence='Maintainer Git history claim; unsigned commit date is not independently timestamped',
            status='all_catalogued_text_candidates_acquired_and_structurally_censused_not_admitted'))
    manifest.sort(key=lambda r:r['member_key'])
    manifest_path = private / 'post-manifest.jsonl'
    manifest_path.write_text(''.join(canonical(r)+'\n' for r in manifest))
    exact = {kind:[dict(hash=h,members=sorted(set(keys))) for h,keys in sorted(groups.items()) if len(set(keys))>1]
             for kind,groups in [('raw_sha256',raw_groups),('normalized_sha256',norm_groups),('shared_raw_blankline_block_ge200_normalized_chars',block_groups)]}
    dump(private / 'copy-groups.json', exact)
    dump(private / 'lineage-hints.json', lineage)
    aggregate = dict(schema_version=VERSION, source_count=len(source_records), candidate_files=len(manifest),
        candidate_utf8_bytes=sum(r['bytes'] for r in manifest), candidate_sha256_unique=len(raw_groups),
        candidate_normalized_unique=len(norm_groups), diagnostic_permanent_exclusions=sum(r['diagnostic_exposure'] for r in manifest),
        raw_exact_duplicate_groups=len(exact['raw_sha256']), normalized_exact_duplicate_groups=len(exact['normalized_sha256']),
        shared_long_raw_block_groups=len(exact['shared_raw_blankline_block_ge200_normalized_chars']),
        shared_long_raw_block_member_count=len({m for g in exact['shared_raw_blankline_block_ge200_normalized_chars'] for m in g['members']}),
        unresolved_metadata_lineage_hints=len(lineage), source_records=source_records,
        byte_budget=dict(new_download_body_bytes=receipt['transfer_ledger']['network_entity_bytes'],
            preliminary_metadata_body_allowance=receipt['transfer_ledger']['prior_metadata_entity_allowance'],
            raw_source_plus_license_bytes=receipt['total_retained_source_bytes'],
            max_new_download_body_bytes=30*1024**2,max_expanded_bytes=100*1024**2,
            wire_protocol_overhead_measured=False,separate_from_existing_v03_stage_budget=True),
        normalization=dict(unicode_version=unicodedata.unidata_version, recipe='NFKC then remove str.isspace',
            hash='SHA256',domain_hex=b'nfkc-no-ws/v1\0'.hex()),
        acquisition_receipt_sha256=digest(receipt_path.read_bytes()), post_manifest_sha256=digest(manifest_path.read_bytes()),
        assistance_status='unknown', human_verified=False, model_admitted=False, model_fit_performed=False,
        split_created=False, linguistic_parser_run=False, markdown_body_projector_run=False,
        old_labelled_test_text_read=False, personal_author_stage_accessed=False,
        limitations=['Three site sources do not establish broad author representativeness',
            'Structural marker hits are not semantic or authorship labels; absence is not clearance',
            'Source dates, account attribution and historical licensing do not prove unaided human composition',
            'Per-item licensing, sensitive-content screening, Markdown body projection and cross-source near-copy review remain open',
            'No new eligibility, independent-work count, training frame or holdout is established',
            'Normalization and block hashes are lineage-screening inputs only; no fingerprint database was read or changed'])
    dump(base/'public/blog-acquisition.aggregate.json',aggregate)
    print(json.dumps({k:aggregate[k] for k in ('candidate_files','candidate_utf8_bytes','diagnostic_permanent_exclusions','raw_exact_duplicate_groups','normalized_exact_duplicate_groups','shared_long_raw_block_groups','unresolved_metadata_lineage_hints')}))

if __name__ == '__main__':
    main()
