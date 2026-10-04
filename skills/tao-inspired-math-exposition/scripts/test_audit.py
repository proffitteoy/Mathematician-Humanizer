import copy,hashlib,json
from audit import audit,BASE
text='设x为实数。证明需要逐项展开，条件不满足时需重新检验。'
review={'mode':'exposition','text_sha256':hashlib.sha256(text.encode()).hexdigest(),'checks':{k:{'status':'pass','quote':'设x为实数','reason':'这是测试审核合同的具体占位理由，不是数学正确性认证。'} for k in BASE}}
cases=[]
def check(name,r,t=text,expected=False):
 got=audit(t,r)['mechanical_contract_pass'];assert got==expected,(name,got);cases.append({'case':name,'expected':expected,'observed':got})
check('valid evidence contract',review,expected=True)
check('changed text',review,t=text+'改动')
r=copy.deepcopy(review);del r['checks']['assumptions'];check('missing assumptions',r)
r=copy.deepcopy(review);r['checks']['reasoning']['quote']='不存在的证据';check('fabricated evidence',r)
r=copy.deepcopy(review);r['checks']['reasoning']['status']='unresolved';check('unresolved proof',r)
r=copy.deepcopy(review);r['mode']='learning';check('missing learning test',r)
print(json.dumps({'tests':cases,'all_tests_pass':True},ensure_ascii=False,indent=2))
