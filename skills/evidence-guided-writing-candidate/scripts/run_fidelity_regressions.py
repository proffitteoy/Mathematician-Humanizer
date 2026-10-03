"""Measure actual added lexical sensitivity, separately from review declarations."""
import hashlib,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import bridge as b
from workflow import mechanical_checks
fixture=ROOT/'tests/synthetic_fidelity_cases.json';rows=[]
for c in json.loads(fixture.read_text())['cases']:
 j={'original':c['source'],'protected':c.get('protected',[]),'length_ratio_bounds':[0.1,5.0]}
 candidate={'text':c['candidate'],'review':{'ledger_completeness':'checked_no_omissions','relations_and_scope':'checked_preserved'}}
 base=mechanical_checks(j,candidate);strict=b.strict_checks(j,candidate)
 # Declarations are filled only to isolate lexical subchecks. They are not real passing semantic reviews.
 issues=[x for x in strict['issues'] if x['code'] not in {'ledger_completeness_not_reviewed','relations_and_scope_not_reviewed'}]
 passed=base['status']=='pass' and not issues
 rows.append({'id':c['id'],'source':c['source'],'candidate':c['candidate'],'expected_semantic_verdict':c['verdict'],'explanation':c['reason'],'baseline_mechanical_status':base['status'],'strict_lexical_issues':issues,'combined_lexical_status':'pass' if passed else 'fail'})
invalid=[r for r in rows if r['expected_semantic_verdict']=='fail'];valid=[r for r in rows if r['expected_semantic_verdict']=='pass']
r={'schema_version':'independent-bridge-fidelity/1','scope':'20 synthetic adversarial/control pairs. Measures lexical sensitivity only, not semantic verification or human writing quality. Dummy declarations isolate lexical rules and are not release reviews.','bridge_sha256':hashlib.sha256(pathlib.Path(b.__file__).read_bytes()).hexdigest(),'fixture_sha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),'summary':{'cases':len(rows),'invalid_cases':len(invalid),'valid_controls':len(valid),'invalid_blocked_lexically':sum(x['combined_lexical_status']=='fail' for x in invalid),'invalid_missed_lexically':sum(x['combined_lexical_status']=='pass' for x in invalid),'valid_controls_accepted':sum(x['combined_lexical_status']=='pass' for x in valid)},'results':rows}
(ROOT/'reports').mkdir(exist_ok=True)
(ROOT/'reports/ADVERSARIAL_FIDELITY.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r['summary']))
