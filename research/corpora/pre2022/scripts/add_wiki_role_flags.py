"""Deterministic metadata-only flags; labels are not original-authorship truth."""
import argparse,collections,json,pathlib,re
KEYS=('headline_roundup_template','voa_template','original_reporting_category_or_template','outline_template','guide_or_star_template','has_listing_template','raw_ge200_han_half_without_headline_template')
LIMITATIONS=[
 'Source-role flags are lexical checks of archived template/category markup, not validated content genres. News headline-roundup and guide outline/listing flags must guide manual projection review, not count as author-origin labels.',
 'The exploratory Han fraction counts only CJK Unified Ideographs basic and Extension A ranges; it is a rough capacity flag, not a validated Unicode-script language filter.',
 'parser_run=false refers to the linguistic/model parser; XML parsing has occurred.',
 'Person-attribution category labels are suppressed in public aggregates; private source metadata remains unchanged.'
]
def flags(record):
    ts={x.lower() for x in record['template_names']};headline='headline item/header' in ts
    return dict(zip(KEYS,(
        headline,
        'voa' in ts,
        'original' in ts or any(re.search('原創|原创',x) for x in record['categories']),
        any(x.startswith('outline') for x in ts),
        any(x.startswith(('guide','star')) for x in ts),
        bool(ts.intersection({'listing','see','do','eat','drink','sleep','buy'})),
        record['source_codepoints']>=200 and record['letter_number_codepoints']>0 and record['han_codepoints']/record['letter_number_codepoints']>=.5 and not headline)))
def apply_role_flags(private_dir,census_file):
    census=json.loads(census_file.read_text())
    for report in census['reports']:
        counts=collections.Counter({k:0 for k in KEYS})
        with (private_dir/(report['source_id']+'.page-manifest.jsonl')).open() as stream:
            for line in stream:
                record=json.loads(line)
                if record['namespace']!='0' or record['redirect']:continue
                counts.update({k:int(v) for k,v in flags(record).items()})
        report['source_role_markup_flags']=dict(counts)
        report['most_frequent_category_markup']=[['[person-attribution category omitted]' if re.search(r'記者|记者',label) else label,count] for label,count in report['most_frequent_category_markup']]
    for limitation in LIMITATIONS:
        if limitation not in census['limitations']:census['limitations'].append(limitation)
    census_file.write_text(json.dumps(census,ensure_ascii=False,indent=2)+'\n')
    return census
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source_root',type=pathlib.Path);a=parser.parse_args()
    r=apply_role_flags(a.source_root/'private',a.source_root/'public/wiki-census.aggregate.json')
    print(json.dumps({x['source_id']:x['source_role_markup_flags'] for x in r['reports']},ensure_ascii=False))
