from pathlib import Path
import sys,json,time,socket,dataclasses,hashlib,resource
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R/'repo/src'),str(R/'repo')]
def deny(*a,**k):raise RuntimeError('Network disabled in parser verification')
socket.socket.connect=deny;socket.create_connection=deny
from research.linguistic.stanza_local import LocalStanza
from research.linguistic.fixtures import source,full
from research.linguistic.adapter import measure
from research.linguistic.schema import schema_document,CHANNEL_IDS
start=time.monotonic();p=LocalStanza(R/'models',threads=2);loaded=time.monotonic();obs=source('我读书。我们认真地记录结果。');parsed=p.parse(obs);bundle=measure(obs,full(obs),parsed)
assert len(CHANNEL_IDS)==71 and all(s.status=='ok' for s in parsed.sentences)
expected='221323897ea20205d0801383537558b4411cb47eb945c2deac51e24ccb2549a3'
receipt={'status':'verified_synthetic_parser_only','synthetic_units':len(parsed.sentences),'channels':len(CHANNEL_IDS),'parser_profile':dataclasses.asdict(p.profile),'measurement_profile_sha256':bundle['identity']['profile_sha256'],'historical_measurement_profile_sha256':expected,'profile_matches_historical':bundle['identity']['profile_sha256']==expected,'historical_entire_environment_byte_identity_claimed':False,'model_load_seconds':loaded-start,'total_wall_seconds':time.monotonic()-start,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'corpus_bodies_read_for_parser_smoke':0,'network_connections_allowed':False,'reference_distributions_fitted':False}
(R/'public/parser_smoke_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');(R/'public/current_channel_schema.json').write_text(json.dumps(schema_document(),ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,indent=2))
