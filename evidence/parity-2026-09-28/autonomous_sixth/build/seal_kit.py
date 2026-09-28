from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]/'kit/autocase'
previous=Path(__file__).resolve().parents[2]/'autonomous_fifth/kit/autocase'
def sha(b):return hashlib.sha256(b).hexdigest()
model=[p for p in (previous/'model').rglob('*') if p.is_file()]
assert len(model)==99
for p in model:assert p.read_bytes()==(root/p.relative_to(previous)).read_bytes(),p
native=[p for p in (previous/'ref/native').iterdir() if p.is_file()]
assert len(native)==4
for p in native:assert p.read_bytes()==(root/p.relative_to(previous)).read_bytes(),p
reuse=json.loads((root/'ref/accepted/reuse_proof.json').read_text())
for r in reuse['unchanged_natural_source_files']:
 assert sha((root/r['path']).read_bytes())==r['sha256'],r['path']
assert sha((root/'+ac/Streams.m').read_bytes())==reuse['current_streams_sha256']
for name in ['Fixture.m','TxSignature.m','nativeImportPreflight.m','Trace.m']:
 assert (root/'+ac'/name).read_bytes()==(previous/'+ac'/name).read_bytes(),name
runner=(root/'run_autonomous_tests.m').read_text();oldrunner=(previous/'run_autonomous_tests.m').read_text()
for start,end in [('function [reused,item,details]=reuseNatural','function item=runCase'),('function output=comparePrefix','function resolved=bindSource')]:
 assert runner[runner.index(start):runner.index(end)]==oldrunner[oldrunner.index(start):oldrunner.index(end)]
assert "runCase(root,out,config,'I_control_wire','native')" in runner
assert "runCase(root,out,config,'G_population','native')" not in runner
assert "runCase(root,out,config,'H_admission_route','native')" not in runner
for name in ['ControlWireProbe.m','requestWirePreflight.m','noPathWirePreflight.m']:
 assert (root/'+ac'/name).exists(),name
proof=json.loads((root/'candidate_transform.json').read_text());assert len(proof['transforms'])==16
for r in proof['transforms']:
 source=(root/r['source']).read_bytes();target=(root/r['target']).read_bytes()
 assert sha(source)==r['source_sha256'] and sha(target)==r['target_sha256']
 text=target.decode()
 for e in reversed(r['edits']):
  assert text.count(e['new'])==1
  text=text.replace(e['new'],e['old'])
 assert text.encode()==source
files=[]
for p in sorted(root.rglob('*')):
 if not p.is_file() or p.name=='FILES.json':continue
 raw=p.read_bytes();files.append(dict(path=p.relative_to(root).as_posix(),sha256=sha(raw),bytes=len(raw)))
manifest=dict(schema='csr-autonomous-issued-kit-v6',scope='I retains H; origin-tagged compact REQUEST and metadata-only NoPath wire sizing',
 matlab_executed=False,accepted_natural_matlab_executed=True,previous_B_C_D_E_F_G_H_matlab_executed=True,
 previous_key_neighbor_population_route_preflights_matlab_executed=True,new_I_matlab_executed=False,new_request_no_path_preflights_matlab_executed=False,
 production_model_changed=False,isolated_candidate_source_reverse_verified=True,numerical_parity_established=False,target_percent=15,files=files)
(root/'FILES.json').write_text(json.dumps(manifest,indent=2)+'\n')
receipt=dict(schema='csr-autonomous-i-seal-v1',files=len(files),matlab_files=sum(x['path'].endswith('.m') for x in files),
 unchanged_model_artifacts=99,unchanged_native_fixture_files=4,total_bound_bytes=sum(x['bytes'] for x in files),
 manifest_sha256=sha((root/'FILES.json').read_bytes()),runtime_validation='I and new REQUEST/NoPath preflights pending owner MATLAB execution',
 candidate_reverse_verified=True,candidate_transform_count=16,accepted_natural_sources_unchanged=True,natural_reuse_function_unchanged=True,
 exact_prefix_comparator_unchanged=True,semantic_guards_unchanged=True,max_relative_path=max(len(x['path']) for x in files))
(Path(__file__).resolve().parents[1]/'matlab/kit_seal.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
