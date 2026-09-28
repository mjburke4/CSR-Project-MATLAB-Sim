from pathlib import Path
import csv,json,hashlib,collections
base=Path(__file__).resolve().parents[1];project=base.parent
fixture=project/'autonomous_sixth/kit/autocase/ref/native/tx_signatures.csv'
rows=[r for r in csv.DictReader(fixture.open()) if r['kind']=='4']
by_frame={r['frame_id']:r for r in rows};created=[]
for r in csv.DictReader((project/'autonomous/native_capture/run/observations.tsv').open(),delimiter='\t'):
 if r['event']!='discovery_plaintext':continue
 child=by_frame[r['frame_id']];detail=json.loads(r['detail_json'])
 created.append(dict(native_create_ns=int(r['time_ns']),native_tx_ns=int(child['time_ns']),source=int(r['node']),native_outer_sequence=int(child['hop_sequence']),payload_session_sequence=int(detail['discovery_sequence']),subtype=child['discover_subtype'],source_tx_ordinal=int(child['source_tx_ordinal'])))
assert len(created)==24
assert [r['native_outer_sequence'] for r in created]==list(range(1,25))
portable=[]
for r in csv.DictReader((base/'data/I_control_wire/protocol_trace.csv').open()):
 if r['Event']=='hop_control_admit' and r['ControlType']=='DISCOVER':
  portable.append(dict(time_s=float(r['TimeSeconds']),source=int(r['NodeId']),destination=int(r['PeerId']),outer_sequence=int(r['Sequence'])))
status=json.loads((base/'data/I_control_wire/random_summary.json').read_text())
summary={k:v for k,v in status.items() if k not in ['first_context_mismatch','counts']}
proof=dict(schema='csr-discovery-outer-identity-audit-v1',matlab_executed_here=False,fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
 native_discover_count=24,native_creation_sequences_contiguous_1_to_24=True,subtypes=dict(collections.Counter(r['subtype'] for r in created)),
 native_first_four=created[:4],portable_admitted_discover=portable,returned_status=summary,
 observed_comparison_scope='Broadcast non-ACK DISCOVER only. Payload discovery-session sequence is semantic and remains strict.',
 sibling_allocators={'DISCOVER_broadcast_and_chirp':'Native function-static process counter; MATLAB per-object broadcast destination map. Only broadcast subtype is captured and normalized.',
 'KEY_REQUEST_KEY_UPDATE_NEIGHBOR_CHECK_ROUTING_DATA':'Per-source, per-destination uint16 transmit stream shared by kinds; reliable receive ACK ownership remains strict.',
 'SNMP':'Constant zero, no reliable sequence allocation in both.',
 'HELLO_and_authenticated_routing_broadcast':'Native independent process-static counters; no portable HELLO control type and no captured HELLO. No comparator exception.',
 'ApplicationPacketId':'Engine-local application identity; existing source flow/attempt semantic guards unchanged.',
 'NWK_routing_and_discovery_session_sequences':'Independent payload sequences; remain strict.'})
(base/'matlab/discovery_sequence_audit.json').write_text(json.dumps(proof,indent=2)+'\n')
with (base/'matlab/native_discovery_allocation.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(created[0]));w.writeheader();w.writerows(created)
print(json.dumps({'native_discovery':24,'portable_discovery':len(portable),'draws':status['draw_count'],'transmissions_checked':status['native_transmissions_checked'],'first_time_difference':status['first_time_difference']},indent=2))
