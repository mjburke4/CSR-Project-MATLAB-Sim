#!/usr/bin/env python3
"""Audit existing native evidence and source only. No simulation or mutation."""
import collections
import csv
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
CSR=ROOT/'autonomous/native_env/csr/model'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(name,data): (OUT/name).write_text(json.dumps(data,indent=2)+'\n')

fixture=ROOT/'autonomous/native_capture/fixture/tx_signatures.csv'
observations=ROOT/'autonomous/native_capture/run/observations.tsv'
returned=ROOT/'autonomous_seventh/data/I_control_wire/first_divergence.json'
rows=list(csv.DictReader(fixture.open()))
discovery=[r for r in rows if r['kind']=='4']
assert len(rows)==1495 and len(discovery)==24
generated=[]
with observations.open() as stream:
    for row in csv.DictReader(stream,delimiter='\t'):
        if row['event']=='discovery_plaintext': generated.append(row)
assert len(generated)==24
by_frame={(r['source'],r['frame_id']):r for r in discovery}
local=collections.Counter()
joined=[]
for ordinal,g in enumerate(generated,1):
    row=by_frame[(g['node'],g['frame_id'])]
    details=json.loads(g['detail_json'])
    local[g['node']]+=1
    assert int(row['hop_sequence'])==ordinal
    assert row['discover_sequence']==details['discovery_sequence']
    assert row['ackable']=='0' and row['hop_destination']=='16777215'
    assert row['wire_bytes']=='19' and row['discover_subtype']=='broadcast'
    joined.append({
        'generation_time_ns':int(g['time_ns']),
        'generation_event_order':int(g['event_order']),
        'global_discovery_send_ordinal':ordinal,
        'source_discovery_send_ordinal':local[g['node']],
        'source':int(row['source']), 'frame_id':int(row['frame_id']),
        'tx_time_ns':int(row['time_ns']), 'tx_id':int(row['tx_id']),
        'source_tx_ordinal':int(row['source_tx_ordinal']),
        'outer_hop_sequence':int(row['hop_sequence']),
        'payload_discovery_sequence':int(row['discover_sequence']),
        'native_group_key_id':int.from_bytes(bytes.fromhex(row['payload_hex'])[:3],'big')>>12,
        'native_security_group_sequence':int.from_bytes(bytes.fromhex(row['payload_hex'])[:3],'big')&4095,
    })
assert sum(r['outer_hop_sequence']!=r['source_discovery_send_ordinal'] for r in joined)==21
stop=json.loads(returned.read_text())
assert stop['fields']==['child3.hop_sequence']
assert stop['actual']['children'][2]['hop_sequence']==1
assert stop['expected'][2]['hop_sequence']==4
assert stop['actual']['children'][2]['discover_sequence']==stop['expected'][2]['discover_sequence']==1
assert stop['actual']['total_wire_bytes']==stop['expected'][2]['total_wire_bytes']==109
assert [r['outer_hop_sequence']for r in sorted(joined,key=lambda r:r['tx_time_ns'])][14:16]==[16,15]
snmp=[r for r in rows if r['kind']=='7']
key_requests=[r for r in rows if r['kind']=='8']
assert len(snmp)==36 and all(r['hop_sequence']=='0' and r['ackable']=='0' for r in snmp)
assert len(key_requests)==15 and all(r['ackable']=='0' and r['hop_destination']!='16777215' for r in key_requests)
assert not any(r['kind'] in ('3','10') for r in rows)
save('sequence_audit.json',{
    'status':'pass_existing_evidence_source_audit',
    'fixture_rows':len(rows),'discovery_controls':joined,
    'global_send_ordinals_exact':True,
    'outer_sequence_differs_from_source_local_send_ordinal':21,
    'generation_order_is_not_transmission_order':True,
    'first_stop_only_mismatch':'child3.hop_sequence: MATLAB1 versus native4',
    'non_ack_control_inventory':{
        'DISCOVER':{'count':24,'allocator':'process-wide function-static 16-bit counter; increment before MAC enqueue'},
        'SNMP':{'count':36,'allocator':'constant zero; no per-peer allocation'},
        'KEY_REQUEST':{'count':15,'allocator':'sender-local per-destination shared reliable/data/control stream; increments despite nonACK'},
        'ACK':{'count':1104,'allocator':'echoes acknowledged sequence/base, not a fresh sender sequence'},
        'bare_HOP_HELLO':{'count':0,'allocator':'separate process-wide function-static counter'},
        'authenticated_HOP_HELLO':{'count':0,'allocator':'separate process-wide function-static counter'},
        'APP_NEIGHBORCAST':{'count':0,'allocator':'separate process-wide function-static counter'},
        'MAC_internal_HELLO':{'count':0,'allocator':'per-MAC-object m_helloSeq member'},
    },
    'key_request_identities':[{k:r[k] for k in ('time_ns','source','hop_destination','hop_sequence','frame_id')} for r in key_requests],
    'no_production_fixture_or_guard_edit':True, 'network_or_component_run':False,
    'limits':['Complete observed family inventory; zero-count siblings have source proof only.',
              'No counter wrap or queue-failure case appears in this accepted DISCOVER population.',
              'No cryptographic equivalence claim for MATLAB behavioral security.']})

spans=[
    ('Bare HOP HELLO allocator','csr-hop-layer.h',1194,1217),
    ('Group protection has no outer HOP header input','csr-hop-layer.h',1220,1240),
    ('DISCOVER allocator after protection','csr-hop-layer.h',1467,1499),
    ('Authenticated HELLO separate allocator','csr-hop-layer.h',1503,1536),
    ('SNMP constant zero','csr-hop-layer.h',1539,1573),
    ('Neighborcast separate allocator','csr-hop-layer.h',1816,1853),
    ('KEY_REQUEST shared destination stream','csr-hop-layer.h',1932,1972),
    ('Protected HELLO receiver does not consume outer sequence','csr-hop-layer.h',2204,2318),
    ('DISCOVER dispatch returns before reliable sequence window','csr-hop-layer.h',2764,2800),
    ('Security uses its own record sequence','csr-hop-security.cc',856,951),
    ('Replay key is group key and group sequence','csr-hop-security.cc',1114,1127),
    ('MAC direct HELLO uses object-local member','csr-net-device.h',575,596),
    ('Physical signal identity independent of sequence','csr-net-device.h',727,740),
    ('Outer sequence in receive signal metadata','csr-net-device.h',790,817),
    ('SYNC sequence is trace argument only','csr-net-device.h',1618,1635),
    ('NonACK MAC enqueue has no sequence rule','csr-net-device.h',2241,2311),
    ('MAC ACK cancellation excludes nonACK frames','csr-net-device.h',2315,2334),
    ('Sent callback uses sequence only for ACKable frames','csr-net-device.h',3210,3227),
    ('NWK uses payload discovery sequence','csr-nwk-layer.h',6986,7035),
]
save('source_path_proof.json',{
    'source_commit':'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b',
    'source_only_no_new_runtime_test':True,
    'spans':[{'purpose':purpose,'file':name,'first_line':first,'last_line':last,
              'file_sha256':sha(CSR/name),
              'source':'\n'.join((CSR/name).read_text().splitlines()[first-1:last])+'\n'}
             for purpose,name,first,last in spans]})
inputs=[fixture,observations,returned,
    ROOT/'autonomous_sixth/kit/autocase/model/+csr/+hop/Layer.m',
    ROOT/'autonomous_sixth/kit/autocase/model/+csr/+nwk/Neighbors.m',
    ROOT/'autonomous_sixth/kit/autocase/+ac/TxSignature.m']
save('evidence_receipt.json',{
    'schema':'csr-seventh-discovery-identity-audit-v1',
    'status':'source_and_existing_capture_consistent',
    'new_native_network_or_component_execution':False,
    'matlab_executed_here':False,
    'production_fixture_or_guard_edited':False,
    'input_sha256':{str(p.relative_to(ROOT)):sha(p)for p in inputs},
    'native_source_sha256':{n:sha(CSR/n)for n in sorted({s[1]for s in spans})},
    'artifact_sha256':{p.name:sha(p)for p in sorted(OUT.iterdir())if p.is_file() and p.name!='evidence_receipt.json'},
    'recommendation':'Treat only the observed broadcast subtype of protected DISCOVER outer sequence as nonbehavioral representation metadata, retaining both values and every semantic/frame/radio/lineage guard; no global allocator mutation is needed for network parity.',
    'limits':['Recommendation only: no checker edit performed.',
              'No new continuation or performance parity measured.',
              'Unobserved HELLO/neighborcast branches are not authorized as generic exceptions.']})
print('PASS: 24 generation-ordered DISCOVER identities, 21 differ from local ordinal; 36 SNMP zero; 15 KEY_REQUEST retained per-peer; original stop contains only outer sequence mismatch.')
