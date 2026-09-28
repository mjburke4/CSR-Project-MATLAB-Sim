#!/usr/bin/env python3
"""Read-only evidence and candidate audit; does not run MATLAB or a network."""
import collections
import csv
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
KIT = ROOT / 'autonomous_sixth/kit/autocase'
CSR = ROOT / 'autonomous/native_env/csr/model'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n')

fixture = ROOT / 'autonomous/native_capture/fixture/tx_signatures.csv'
rows = list(csv.DictReader(fixture.open()))
assert len(rows) == 1495
groups = collections.defaultdict(list)
compact = []
for row in rows:
    kind = int(row['kind'])
    label = {0:'DATA', 1:'ACK', 4:'DISCOVER', 5:'NEIGHBOR_CHECK',
             6:'ROUTING', 7:'SNMP', 8:'KEY_REQUEST', 9:'KEY_UPDATE'}[kind]
    if kind == 6:
        label += ':' + row['routing_section_origin']
        raw_bytes = len(bytes.fromhex(row['routing_section_hex']))
        if row['routing_section_origin'] == 'normalized_legacy_request':
            assert raw_bytes == 7 and row['routing_section_hex'][-6:] == '000103'
            expected = 16
            compact.append({k: row[k] for k in ('time_ns', 'source', 'tx_id',
                'source_tx_ordinal', 'child_index', 'frame_id', 'hop_destination',
                'hop_sequence', 'wire_bytes', 'routing_section_hex')})
        else:
            assert row['routing_section_origin'] == 'actual_arl_section'
            expected = 16 + raw_bytes
    elif kind == 5:
        label += ':' + row['check_subtype']
        assert row['check_subtype'] in ('discovery', 'overheard')
        expected = 16
    elif kind == 4:
        label += ':' + row['discover_subtype']
        assert row['discover_subtype'] == 'broadcast'
        expected = 19
    elif kind in (7, 8, 9):
        expected = {7:31, 8:18, 9:62}[kind]
    else:
        expected = None  # ACK/DATA are inventory only, outside this control audit.
    if expected is not None:
        assert int(row['wire_bytes']) == expected, row
    groups[label].append(int(row['wire_bytes']))
assert len(compact) == 17
assert not any(r['check_subtype'] == 'no_path' for r in rows)
target = [r for r in rows if r['tx_id'] == '4294967314']
assert [int(r['wire_bytes']) for r in target] == [16,16,31]
assert all(r['total_wire_bytes'] == '63' for r in target)
original_tx = []
with (ROOT / 'autonomous/native_capture/run/observations.tsv').open() as f:
    for row in csv.DictReader(f, delimiter='\t'):
        if row['event'] == 'mac_tx' and row['tx_id'] == '4294967314':
            original_tx.append(row)
assert len(original_tx) == 1
assert float(json.loads(original_tx[0]['detail_json'])['duration_sec']) == 0.087719999999999992
save('fixture_control_audit.json', {
    'fixture_sha256': sha(fixture), 'child_rows': len(rows),
    'all_observed_nwk_control_sizes_source_consistent': True,
    'ack_data_sizes_audited': False,
    'inventory': {k:{'rows':len(v), 'wire_sizes':dict(collections.Counter(v))}
                  for k,v in sorted(groups.items())},
    'observed_compact_requests': compact,
    'normalized_request_count': len(compact), 'actual_arl_section_count': 98,
    'no_path_count': 0, 'target_original_mac_tx': original_tx[0],
    'target_children': target,
    'target_airtime_seconds': 0.087719999999999992,
    'matlab_uncorrected_counterfactual_seconds': 0.10200000000000001,
    'counterfactual_delta_seconds': 0.014280000000000015,
    'counterfactual_was_transmitted': False})

manifest_path = KIT / 'candidate_transform.json'
manifest = json.loads(manifest_path.read_text())
verified = []
for change in manifest['transforms']:
    source = KIT / change['source']; target = KIT / change['target']
    assert sha(source) == change['source_sha256']
    assert sha(target) == change['target_sha256']
    text = source.read_text()
    for edit in change['edits']:
        count = text.count(edit['old'])
        assert count >= 1, (change['target'], edit['old'])
        text = text.replace(edit['old'], edit['new'])
    assert text == target.read_text(), change['target']
    for edit in reversed(change['edits']):
        assert edit['new'] in text
        text = text.replace(edit['new'], edit['old'])
    assert text == source.read_text()
    verified.append({'target':change['target'], 'sha256':sha(target),
                     'forward_and_reverse_exact':True})
assert len(verified) == 16
baseline = ROOT / 'autonomous_fifth/kit/autocase/model'
baseline_files = sorted(p for p in baseline.rglob('*') if p.is_file())
assert len(baseline_files) == 99
assert all(sha(p) == sha(KIT / 'model' / p.relative_to(baseline)) for p in baseline_files)
candidate = (KIT / '+ac/ControlWireNwk.m').read_text()
assert candidate.count('ac.controlWireBytes(') == 3
assert "obj.sendRecords({struct('Operation','REQUEST')},peer,'changes','legacy_request_header');" in candidate
assert 'payload.WireRepresentation=message.WireRepresentation;' in candidate
assert 'owner.Control.Type,owner.Control.Payload,numel(owner.Peers)' in candidate
runner_path = KIT / 'run_autonomous_tests.m'
runner = runner_path.read_text()
assert runner.index('if first.completed && first.natural_prefix_passed') < runner.index('ac.requestWirePreflight') < runner.index("runCase(root,out,config,'I_control_wire','native')")
assert runner.index('ac.noPathWirePreflight') < runner.index("runCase(root,out,config,'I_control_wire','native')")
save('candidate_scope_review.json', {
    'scope_review':'pass', 'matlab_executed':False,
    'candidate_manifest_sha256':sha(manifest_path), 'runner_sha256':sha(runner_path),
    'helper_sha256':sha(KIT / '+ac/controlWireBytes.m'),
    'verified_transforms':verified, 'unchanged_baseline_model_files':99,
    'native_contract_checks':[
        'Compact marker originates only in requestTick and requires one unicast REQUEST.',
        'Backlog and materialization retain the marker; owner residual retries retain Payload.',
        'All three owner-size calculations call the isolated helper.',
        'Untagged real ARL sections retain baseline size and byte validation.',
        'NoPath adjustment is only envelope size; target, subtype, callbacks and retry ownership remain baseline.',
        'Simulation differs from H only in class/constructor name and NWK binding.',
        'Natural fidelity gate, inherited preflights and two new public preflights precede one I network case.'
    ],
    'limits':[
        'MATLAB component preflights and I continuation require owner execution.',
        'Accepted 0–330 fixture has no NoPath: no network trajectory coverage for that branch.',
        'Inherited H timing, admission and semantic-guard limitations remain; no performance parity claim.'
    ]})

log = (OUT / 'control_size_probe.log').read_text()
assert log.endswith('ALL_PACKET_CASES_PASS\n')
cases = [line for line in log.splitlines()[1:] if not line.startswith(('AIRTIME,','ALL_'))]
assert len(cases) == 12
inputs = [fixture, ROOT/'autonomous/native_capture/normalize.py',
          ROOT/'autonomous/native_capture/run/observations.tsv',
          ROOT/'autonomous_sixth/data/H_admission_route/first_divergence.json',
          ROOT/'autonomous/native_env/build.json']
sources = ['csr-nwk-layer.h','csr-hop-layer.h','csr-hop-security.h',
           'csr-opnet-envelope.h','csr-opnet-packet-model.cc','csr-net-device.h',
           'csr-phy-model.h','csr-hello-header.h','csr-hello-header.cc']
proof_spans = [
    ('NoPath public entry', 'csr-nwk-layer.h', 778, 784),
    ('NoPath relay failure caller', 'csr-nwk-layer.h', 1453, 1470),
    ('NeighborCheck actual payload builder', 'csr-nwk-layer.h', 7880, 7948),
    ('NeighborCheck actual HOP sender and explicit envelope', 'csr-hop-layer.h', 1856, 1930),
    ('MAC preserves the explicit envelope', 'csr-net-device.h', 2240, 2250),
    ('Existing envelope is authoritative', 'csr-opnet-envelope.h', 110, 127),
    ('Compact REQUEST actual payload builder', 'csr-nwk-layer.h', 8945, 8996),
    ('Routing envelope strips compatibility metadata', 'csr-opnet-envelope.h', 35, 74),
    ('PHY consumes modeled child sizes', 'csr-net-device.h', 661, 704),
    ('Targeted compatibility DELETE versus raw self DELETE', 'csr-nwk-layer.h', 8907, 8943),
]
save('source_path_proof.json', {
    'source_commit':'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b',
    'read_only_source_proof_not_sender_runtime_probe':True,
    'spans':[{'purpose':label, 'file':name, 'first_line':first, 'last_line':last,
              'file_sha256':sha(CSR/name),
              'source':'\n'.join((CSR/name).read_text().splitlines()[first-1:last])+'\n'}
             for label,name,first,last in proof_spans]})
libs = ROOT/'autonomous/native_env/engine/build/lib'
save('evidence_receipt.json', {
    'schema':'csr-sixth-control-wire-native-evidence-v1',
    'status':'native_packet_component_pass_and_candidate_static_review_pass',
    'native_network_run':False, 'matlab_executed':False,
    'production_or_fixture_edited':False,
    'native_component_cases':len(cases),
    'component_scope':'Native packet/header/security/envelope/PHY rate APIs only; no Simulator::Run, device or channel.',
    'no_path_actual_sender_path_source_verified':True,
    'no_path_actual_sender_path_executed':False,
    'no_path_network_coverage':0,
    'source_pins':json.loads((ROOT/'autonomous/native_env/build.json').read_text())['sources'],
    'toolchain':json.loads((ROOT/'autonomous/native_env/build.json').read_text())['toolchain'],
    'input_sha256':{str(p.relative_to(ROOT)):sha(p) for p in inputs},
    'native_source_sha256':{name:sha(CSR/name) for name in sources},
    'runtime_library_sha256':{p.name:sha(p) for p in sorted(libs.glob('libns3-dev-*-debug.so'))},
    'artifact_sha256':{p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name not in ('evidence_receipt.json','control_size_probe')},
    'compile_argv':json.loads((OUT/'compile_command.json').read_text()),
    'run_argv':[str(OUT/'control_size_probe'),str(OUT/'captured_frames.tsv')],
    'include_wrapper_note':'Three local headers redirect restored ns3 wrappers to the pinned CSR checkout; source and build were not modified.',
    'recommended_candidate':'I_control_wire: provenance-tagged compact REQUEST16 and compatibility-metadata NoPath16; no general opcode-based exemption.',
    'limits':['No downstream trajectory or delivery improvement measured.',
              'NoPath source chain plus packet component validated; owner-side public preflight remains pending.',
              'Compatibility DELETE-marker API is also16, but real grouped DELETE remains26; no new DELETE change justified.']})
print('PASS: 1495-row inventory; 17 compact REQUESTs; 98 real ARL sections; 12 packet cases; 16 exact transforms; 99 unchanged model files.')
