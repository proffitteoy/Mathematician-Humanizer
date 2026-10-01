"""Synthetic and hash checks only; no corpus or model data opened."""
import argparse,collections,hashlib,importlib.util,json,pathlib,random
p=argparse.ArgumentParser();p.add_argument('proposal_dir',type=pathlib.Path);p.add_argument('out',type=pathlib.Path);a=p.parse_args()
manifest=json.loads((a.proposal_dir/'FILE_HASHES.json').read_text());checks=[]
for name,r in manifest.items():
 b=(a.proposal_dir/name).read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'];checks.append(name)
spec=importlib.util.spec_from_file_location('under_review',a.proposal_dir/'sample_metadata.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
old=m.member_key('wikimedia','zhwiki','page:7');new=m.member_key('wikimedia','zhwikinews','page:8')
_,exclude_gen=m.freeze_components([old,new],[(old,new)],[],(v for v in [old]))
results={'manifest_hash':hashlib.sha256((a.proposal_dir/'FILE_HASHES.json').read_bytes()).hexdigest(),'manifest_entries_verified':len(checks),'generator_exclusion_propagates':len(exclude_gen)==1,'random_graph_trials':0,'random_graph_failures':0}
rng=random.Random(20261001)
for trial in range(100):
 nodes=[m.member_key('source'+str(i%3),'project'+str(i%4),'page:'+str(i)) for i in range(12)]
 edges=[(nodes[i],nodes[j]) for i in range(12) for j in range(i) if rng.random()<.12];hard=edges[::2];unknown=edges[1::2];excluded=set(rng.sample(nodes,3))
 mapped,actual=m.freeze_components(nodes,hard,unknown,excluded)
 graph={n:set() for n in nodes}
 for x,y in edges:graph[x].add(y);graph[y].add(x)
 reached=set();expected_groups=[]
 for start in nodes:
  if start in reached:continue
  group={start};queue=[start]
  while queue:
   cur=queue.pop()
   for nei in graph[cur]-group:group.add(nei);queue.append(nei)
  reached|=group;expected_groups.append(group)
 expected_map={n:hashlib.sha256(m.canonical(sorted(g))).hexdigest() for g in expected_groups for n in g};expected_ex={expected_map[n] for n in excluded}
 shuffled=nodes[:];rng.shuffle(shuffled);hard2=hard[::-1];unknown2=unknown[::-1]
 mapped2,actual2=m.freeze_components(shuffled,hard2,unknown2,excluded)
 ok=(mapped==mapped2==expected_map and actual==actual2==expected_ex)
 results['random_graph_trials']+=1;results['random_graph_failures']+=not ok
lin=lambda i,o:(i+1)*o
S=lin(272,16)+lin(476,16)+lin(37,48)+lin(48,45);D=S+3*16*16*2+6*16
results['budget_arithmetic']={'records':1920,'training_records':1280,'fits':18,'updates':21600,'unit_parse_cap':61440,'12_record_all_prefix_parse_calls_upper_if32units':6336,'S_base_parameters':S,'D_base_parameters':D,'paired_relative_gap':(D-S)/D,'graph_parameters_not_implemented_or_certified':True}
# Show exact empirical weighting identity without corpus or stochastic fitting.
losses={'a':[1.,2.],'b':[3.],'c':[4.,5.,6.]};N=8
expected=sum(sum(v)/len(v) for v in losses.values())/3
weighted=sum(sum(N/(3*len(v))*x for x in v) for v in losses.values())/N
results['record_source_equal_weighting_synthetic']={'expected':expected,'weighted_with_two_zero_support_records':weighted,'matches':abs(expected-weighted)<1e-12,'N_must_be_total_records':True}
results['data_access']={'raw_text':False,'old_test_bodies':False,'new_parser':False,'model_fit':False}
a.out.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n');print(json.dumps(results,ensure_ascii=False,indent=2))
