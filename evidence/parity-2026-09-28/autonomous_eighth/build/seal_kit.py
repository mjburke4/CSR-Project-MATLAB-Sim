from pathlib import Path
import hashlib
import json

base = Path(__file__).resolve().parents[1]
root = base / 'kit/autocase'
previous = base.parent / 'autonomous_seventh/kit/autocase'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

model = [p for p in (previous / 'model').rglob('*') if p.is_file()]
assert len(model) == 99
for p in model:
    assert p.read_bytes() == (root / p.relative_to(previous)).read_bytes(), p
native = [p for p in (previous / 'ref/native').iterdir() if p.is_file()]
assert len(native) == 4
for p in native:
    assert p.read_bytes() == (root / p.relative_to(previous)).read_bytes(), p
old_helpers = list((previous / '+ac').glob('*.m'))
for p in old_helpers:
    assert p.read_bytes() == (root / p.relative_to(previous)).read_bytes(), p
reuse = json.loads((root / 'ref/accepted/reuse_proof.json').read_text())
for row in reuse['unchanged_natural_source_files']:
    assert sha((root / row['path']).read_bytes()) == row['sha256'], row['path']
assert sha((root / '+ac/Streams.m').read_bytes()) == reuse['current_streams_sha256']
runner = (root / 'run_autonomous_tests.m').read_text()
old = (previous / 'run_autonomous_tests.m').read_text()
for start, end in [
    ('function [reused,item,details]=reuseNatural', 'function item=runCase'),
    ('function output=comparePrefix', 'function resolved=bindSource'),
]:
    assert runner[runner.index(start):runner.index(end)] == old[old.index(start):old.index(end)]
assert "runCase(root,out,config,'K_receiver_timers','native')" in runner
assert "runCase(root,out,config,'J_discovery_identity','native')" not in runner
assert 'ac.receiverTimerPreflight' in runner
assert 'receiver_timing_summary.json' in runner
proof = json.loads((root / 'candidate_transform.json').read_text())
assert len(proof['transforms']) == 22
for row in proof['transforms']:
    source = (root / row['source']).read_bytes()
    target = (root / row['target']).read_bytes()
    assert sha(source) == row['source_sha256'] and sha(target) == row['target_sha256']
    text = target.decode()
    for edit in reversed(row['edits']):
        assert text.count(edit['new']) == 1
        text = text.replace(edit['new'], edit['old'])
    assert text.encode() == source
for source, target in [
    ('native/candidate_scope_review.json', 'candidate_scope_review.json'),
    ('native/evidence_receipt.json', 'evidence_receipt.json'),
    ('review/receiver_timer_preflight_review.json', 'preflight_review.json'),
]:
    assert (base / source).read_bytes() == (root / 'ref/receiver_timers' / target).read_bytes()
files = []
for p in sorted(root.rglob('*')):
    if not p.is_file() or p.name == 'FILES.json':
        continue
    raw = p.read_bytes()
    files.append(dict(path=p.relative_to(root).as_posix(), sha256=sha(raw), bytes=len(raw)))
manifest = dict(
    schema='csr-autonomous-issued-kit-v8',
    scope='K retains J comparison and protocol paths; isolated native-relative receiver timers and paired TX completion',
    matlab_executed=False, accepted_natural_matlab_executed=True,
    previous_B_through_J_matlab_executed=True, previous_45_component_checks_matlab_executed=True,
    new_K_matlab_executed=False, new_receiver_timer_preflight_matlab_executed=False,
    production_model_changed=False, model_bit_allocation_changed=False,
    prior_J_random_and_tx_guards_changed=False, isolated_candidate_source_reverse_verified=True,
    numerical_parity_established=False, target_percent=15, files=files,
)
(root / 'FILES.json').write_text(json.dumps(manifest, indent=2) + '\n')
receipt = dict(
    schema='csr-autonomous-k-seal-v1', files=len(files),
    matlab_files=sum(x['path'].endswith('.m') for x in files),
    unchanged_model_artifacts=99, unchanged_native_fixture_files=4,
    unchanged_prior_ac_matlab_files=len(old_helpers), total_bound_bytes=sum(x['bytes'] for x in files),
    manifest_sha256=sha((root / 'FILES.json').read_bytes()),
    runtime_validation='K and eight receiver-timer preflight checks pending owner MATLAB execution',
    previous_component_checks_passed=45, new_component_checks_pending=8,
    candidate_reverse_verified=True, candidate_transform_count=22,
    accepted_natural_sources_unchanged=True, natural_reuse_function_unchanged=True,
    exact_prefix_comparator_unchanged=True, model_bit_allocation_unchanged=True,
    prior_J_random_and_tx_guards_unchanged=True,
    max_relative_path=max(len(x['path']) for x in files),
)
(base / 'matlab/kit_seal.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
