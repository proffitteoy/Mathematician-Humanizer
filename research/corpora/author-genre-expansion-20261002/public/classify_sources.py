"""Curated provisional document metadata, never labels for sentence authorship."""
import json
from acquire_sources import ROOT
G={
'604':'public_social_commentary','5111':'ethnographic_field_or_travel_essay','6616':'film_book_performance_review','6896':'film_book_performance_review',
'3512':'film_book_performance_review','6454':'public_social_commentary','6754':'film_book_performance_review','6906':'personal_or_research_reflection',
'131':'public_social_commentary','5386':'film_book_performance_review','6605':'personal_or_research_reflection','6903':'ethnographic_field_or_travel_essay',
'190':'film_book_performance_review','3261':'film_book_performance_review','6323':'personal_or_research_reflection','6759':'ethnographic_field_or_travel_essay',
'121':'personal_or_research_reflection','2443':'film_book_performance_review','5997':'public_social_commentary','6721':'public_social_commentary',
'1269':'ethnographic_field_or_travel_essay','6280':'ethnographic_field_or_travel_essay','6613':'ethnographic_field_or_travel_essay','6886':'ethnographic_field_or_travel_essay',
'808':'ethnographic_field_or_travel_essay','2737':'ethnographic_field_or_travel_essay','6259':'personal_or_research_reflection','6870':'ethnographic_field_or_travel_essay',
'226':'public_social_commentary','1870':'ethnographic_field_or_travel_essay','6548':'public_social_commentary','6805':'ethnographic_field_or_travel_essay',
'4741':'public_social_commentary','6452':'public_social_commentary','6696':'public_social_commentary','6859':'public_social_commentary',
'63':'public_social_commentary','1357':'public_social_commentary','4200':'public_social_commentary','6907':'public_social_commentary','6857':'personal_or_research_reflection'}
NOTES={
'5111':{'embedded_material':'Contains an explicitly attributed opening tourism/DM excerpt; do not attribute all words to the bylined author.'},
'3512':{'publication_role':'author-attributed republication','earlier_outlet':'放映週報, 電影特寫','earlier_date_claim':'11月2日; displayed article date 2012-11-02','dedup_group':'guava-3512-and-original-Funscreen-version'},
'6906':{'publication_role':'author-attributed republication','earlier_outlet':'聯合副刊','earlier_date_claim':'2021-12-09','dedup_group':'guava-6906-and-UDN-20211209-version'},
'6605':{'publication_role':'original blog-specific translator afterword','role_note':'A translator writes about translating a book; this is not itself the translated book.'},
'6805':{'publication_role':'republication or cross-publication disclosed','earlier_outlet':'人類學視界 26:40–44','earlier_date_claim':'not independently established here','dedup_group':'guava-6805-and-Anthropological-Horizons-v26'},
'6452':{'publication_role':'public-talk-linked authored essay','privacy_review':'Public account discusses identifiable adolescents and trauma; never publish raw text, perform span/privacy review before any broader use.'},
'6907':{'publication_role':'coauthored public essay','author_unit':'蔡侑霖、傅偉哲、鄧家洋、莊雅仲','sole_author_eligible':False,'role_note':'Author index used 莊雅仲; article itself explicitly credits four people. Do not count this as sole-author evidence or as three new trajectories.'},
'6857':{'structure_note':'Six long structural blocks. Low block count does not make this a short text; preserved without fragmenting into artificial paragraphs.'},
'6886':{'structure_note':'Main prose uses div elements. A p-only view yielded 10 characters; corrected full-body inspection preserves it.'}}
p=ROOT/'public/ARTICLE_CATALOG.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()]
for r in rows:
 id=r['url'].rsplit('/',1)[-1]
 r.pop('model_admission',None)
 r.update({'genre':G[id],'genre_label_status':'provisional human-curated content/paratext review; mixed genres possible, not gold annotation','sole_author_eligible':r['byline_matches'],'publication_role':'bylined public essay; first-publication exclusivity not assumed','author_identity_evidence':'platform author biography, stable author URL and repeated article byline','human_provenance':'published writing attributed to identified human contributors; assistance status unknown','model_status':'candidate for future stratified analysis; no model features extracted or fit performed','linguistic_variety':'Chinese, predominantly Taiwan traditional-character publishing context','source_role_boundaries':'HTML body and structural blocks preserved privately; comments and navigation excluded from inspection view; inline quotes, speech, citations and borrowing unresolved'})
 r.update(NOTES.get(id,{}))
p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
print('classified',len(rows))
