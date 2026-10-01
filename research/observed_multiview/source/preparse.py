"""Pure character-only qualification; frozen segmentation and Unicode tables.

No POS, NLP parser, measured features, model targets or prediction reads.
"""
import hashlib,importlib.util,json,pathlib,sys,unicodedata
from project_wikitext import canonical
from projection_contract import validate_projection

ROOT=pathlib.Path('/workspace/shared/style-compiler')
SEGMENT_PATH=ROOT/'src/style_compiler/segmentation.py'
UNICODE_PATH=ROOT/'research/linguistic/unicode_scripts.py'
SEGMENT_HASH='be78057bc27f9d8480c37c1e6160b5cc466385803fb094e1e0878e1171a288e8'
UNICODE_HASH='2da9eb8e6162e67c3b4b468c538e0a75251feb6f2bc6f9c9d446969e80c309a4'
SEED='style-observed-multiview-scale10-v1-20261001'
PROFILE='scale10-character-preparse/0.1.0'


def _load(path,digest,name):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('frozen_dependency_changed')
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module

_seg=_load(SEGMENT_PATH,SEGMENT_HASH,'_scale10_segment_frozen')
_uni=_load(UNICODE_PATH,UNICODE_HASH,'_scale10_unicode_frozen')
if unicodedata.unidata_version!='15.0.0' or _uni.UNICODE_VERSION!='15.0.0':raise ValueError('unicode_version_changed')


def _han_fraction(text):
    letters=[c for c in text if unicodedata.category(c)[0] in 'LN']
    return sum(_uni.in_script(c,'Han') for c in letters)/len(letters) if letters else 0.


def qualify(projection,record_key,raw_text):
    validate_projection(raw_text,projection)
    if not isinstance(record_key,str) or not record_key:raise ValueError('stable_record_key_required')
    result={'profile':PROFILE,'source_sha256':projection['source_sha256'],'projection_sha256':projection['projection_sha256'],'preparse_eligible':False,'selected_segment':None,'segment_checks':[],'natural_language_parser_run':False}
    if not 200<=len(raw_text)<=20000:
        result['record_rejection']='source_codepoint_count_outside_200_20000';return result
    eligible=[]
    for s in projection['segments']:
        text=s['text'];mapping=s['source_map'];units=_seg.segment(text)[1];reasons=[];hfrac=_han_fraction(text)
        if not 8<=len(units)<=64:reasons.append('unit_count_outside_8_64')
        if any(u.end-u.start>512 for u in units):reasons.append('unit_over512_codepoints')
        if hfrac<.5:reasons.append('han_LN_fraction_under_half')
        points=[];point_reasons={}
        for target in range(4,min(32,len(units))):
            prev,after=units[target-1],units[target];gap=text[prev.end:after.start]
            reason=None
            if not gap or not gap.isspace():reason='projected_whitespace_boundary_unconfirmed'
            else:
                prefix=_seg.segment(text[:after.start])[1]
                if [(u.start,u.end) for u in prefix]!=[(u.start,u.end) for u in units[:target]]:reason='prefix_segmentation_changed'
                else:
                    # Whitespace must already exist in raw source, not arise by
                    # deleting markup or entity conversion into an invented gap.
                    raw_start=mapping[prev.end-1][1];raw_end=mapping[after.start][0]
                    if raw_start>=raw_end or not raw_text[raw_start:raw_end].isspace():reason='raw_whitespace_boundary_unconfirmed'
                    elif any(row[2]!='identity' for row in mapping[prev.end:after.start]):reason='nonidentity_boundary_whitespace'
            if reason:point_reasons[str(target)]=reason
            else:points.append({'target_unit_index':target,'projected_cutoff':after.start,'raw_cutoff':mapping[after.start][0]})
        if len(points)<4:reasons.append('fewer_than4_closed_points')
        entry={'segment_index':s['index'],'unit_count':len(units),'units_used':min(32,len(units)),'han_LN_fraction':hfrac,'closed_points_count':len(points),'rejections':reasons,'candidate_point_rejections':point_reasons}
        result['segment_checks'].append(entry)
        if not reasons:
            key=hashlib.sha256(canonical([SEED,'projected-segment',[record_key,hashlib.sha256(text.encode()).hexdigest(),s['source_spans']]])).hexdigest()
            eligible.append((key,s['index'],{'segment_index':s['index'],'segment_sha256':hashlib.sha256(text.encode()).hexdigest(),'source_spans':s['source_spans'],'unit_spans':[[u.start,u.end] for u in units[:32]],'full_segment_unit_count':len(units),'closed_points':points,'hash_rank':key}))
    if eligible:
        result['preparse_eligible']=True;result['selected_segment']=min(eligible)[2]
    return result
