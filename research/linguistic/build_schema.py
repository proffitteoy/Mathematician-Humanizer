"""Regenerate documentation-only schema/crosswalk; no corpus or model IO."""
import json
from pathlib import Path
from .schema import SENSORS,schema_document

FORMULA_MAP={
 'word_length.mean':'F029','word_length.ge4':'F030','word.single_han':'F031','word.latin':'F032',
 'lexical.mattr100':'F034','lexical.entropy100':'F036','lexical.content_overlap':'F037',
 'lexical.trigram_reuse':'F038','upos.bigram_entropy100':'F054',
 'upos.NOUN':'F041','upos.VERB':'F042','upos.ADJ':'F043','upos.ADV':'F044','upos.PRON':'F045',
 'upos.ADP':'F046','upos.PART':'F048','upos.AUX':'F049',
 'dependency.span_mean':'F055','dependency.span_normalized':'F056','dependency.depth_mean':'F057',
 'dependency.maxdepth_median':'F058','syntax.predicate_heads':'F059','syntax.subordinate_arcs':'F060',
 'syntax.predicate_conj_share':'F061','syntax.nominal_modifier_size':'F062',
 'syntax.verb_root_without_subject':'F063','syntax.preposed_modifiers':'F067','syntax.initial_pos_reuse':'F068'}
LEGACY=('F002','F003','F013','F014','F015','F016','F024','F025')


def crosswalk():
    rows=[]
    for s in SENSORS:
        short=s.id.removeprefix('zh:');original=FORMULA_MAP.get(short)
        if original:kind='catalog_formula_reimplemented_under_distinct_parser_source_projection_profile'
        elif short in ('upos.CCONJ','upos.SCONJ'):kind='component_of_F047_not_the_combined_F047_channel'
        elif short.startswith('cue.'):kind='new_surface_POS_cue_not_semantic_F050_F053_F064_F066_F069_F100'
        elif short=='word.decimal_digit':kind='new_decimal_surface_proxy_not_F033_quantity_normalization'
        else:kind='new_explicit_candidate_sensor'
        rows.append({'channel_id':s.id,'family':s.family,'catalog_id':original,'relationship':kind,
                     'overlaps_legacy_eight':False,'independent_construct_claim':False})
    return {'vector_width':len(SENSORS),'legacy_eight_in_vector':0,'legacy_eight_recomputed_here':0,
      'legacy_ids':LEGACY,'catalog_formula_correspondences':len(FORMULA_MAP),
      'other_channel_count':len(SENSORS)-len(FORMULA_MAP),'rows':rows,
      'important':'This is one71-channel linguistic vector. The existing8-channel surface vector is separate. No79-channel combined model or100-channel catalogue implementation is asserted. Formula correspondence does not authorize merging different measurement profiles.',
      'not_implemented_original_catalog_ids':[f'F{i:03}' for i in range(1,101) if f'F{i:03}' not in set(LEGACY)|set(FORMULA_MAP.values())],
      'unimplemented_count_under_this_explicit_formula_crosswalk':100-len(LEGACY)-len(FORMULA_MAP),
      'interpretation':'The64 remaining catalogue IDs are not implemented at their original definitions by either this module or the8-channel baseline. The43 other new sensors do not fill these slots. This is a bookkeeping crosswalk, not construct validation or a full-model gate.'}


def main():
    root=Path(__file__).parent
    for name,value in [('feature-schema.json',schema_document()),('catalog-crosswalk.json',crosswalk())]:
        (root/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
