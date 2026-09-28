#!/usr/bin/env python3
"""Audit existing F routing lineage without executing a network simulation."""
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
F = ROOT / 'autonomous_fifth/data/F_message_flag'
NATIVE = ROOT / 'autonomous/native_capture'
T = 14.400468077

def decode_section(values):
    data = bytes(values)
    result = {'hex': data.hex(), 'routing_sequence': int.from_bytes(data[:4], 'big'),
              'section': data[4], 'total_sections': data[5], 'records': []}
    assert result['section'] == 0 and result['total_sections'] == 1
    i = 6
    info_names = ['MinSpeedKbps','MaxSpeedKbps','MinPowerDbmX10','MaxPowerDbmX10',
                  'LinkMarginDbX10','LowPowerDbmX10','TempLowCx10','TempHighCx10']
    def take(n, signed=False):
        nonlocal i
        assert i+n <= len(data)
        value = int.from_bytes(data[i:i+n], 'big', signed=signed)
        i += n
        return value
    while i < len(data):
        op = take(1)
        if op == 0:
            record = {'operation':'FLUSH'}
        elif op == 1:
            record = {'operation':'DELETE','destination':take(3)}
        elif op == 2:
            record = {'operation':'UPDATE','destination':take(3),'capability':take(1),
                      'hops':take(2),'cost':take(4)}
            record['path'] = [take(3) for _ in range(record['hops'])]
        elif op == 3:
            record = {'operation':'REQUEST'}
        elif op == 4:
            record = {'operation':'INFO','info':{name:take(2, j > 1) for j,name in enumerate(info_names)}}
        else:
            raise AssertionError(f'Unknown operation {op}')
        result['records'].append(record)
    assert i == len(data)
    return result

def write_json(name, data):
    (OUT/name).write_text(json.dumps(data, indent=2) + '\n')

def main():
    inputs = [F/'ordered_events.jsonl', F/'service_trace.csv', F/'first_divergence.json',
              NATIVE/'run/run.log', NATIVE/'run/observations.tsv',
              NATIVE/'fixture/tx_signatures.csv']
    controls = []
    with inputs[0].open() as f:
        for line in f:
            event = json.loads(line)
            detail = event.get('details', {})
            frame = detail.get('frame', {})
            if (event.get('node') == 1 and event['time_s'] == T and
                    detail.get('event') == 'mac_enqueue' and
                    frame.get('Control', {}).get('Type') == 'ROUTING'):
                controls.append({'observation_order':event['observation_order'], 'time_s':T,
                    'control_id':frame['Control']['Id'], 'hop_sequence':frame['Sequence'],
                    'targets':frame['DestinationIds'], 'hop_sequences':frame['HopSequences'],
                    'wire_bytes':frame['WirePayloadBytes'], 'queues':detail['details'],
                    'routing':decode_section(frame['Control']['Payload']['Bytes'])})
    assert len(controls) == 2
    assert controls[1]['routing']['hex'] == '00000004000101000003'
    assert controls[1]['targets'] == [3,5] and controls[1]['hop_sequences'] == [5,7]
    assert controls[1]['routing']['records'] == [{'operation':'DELETE','destination':3}]
    write_json('matlab_routing_controls.json', controls)

    with inputs[1].open() as f:
        timeline = [row for row in csv.DictReader(f) if row['NodeId'] == '1' and
                    row['PeerId'] == '3' and float(row['TimeSeconds']) <= T and
                    (row['Event'].startswith('hop_control') or row['Event'].startswith('neighbor_')
                     or row['Event'] == 'hop_sent')]
    fields = ['ObservationId','TimeSeconds','Event','PeerId','ControlType','Sequence',
              'Reason','FrameDestinationsJSON','HopSequencesJSON','DetailsJSON']
    with (OUT/'matlab_peer3_control_timeline.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fields, extrasaction='ignore')
        writer.writeheader(); writer.writerows(timeline)
    received = [r for r in timeline if r['Event'] == 'hop_control_receive']
    assert {r['ControlType'] for r in received} == {'KEY_REQUEST','KEY_UPDATE'}
    assert not any(r['ControlType'] in {'DISCOVER','NEIGHBOR_CHECK','ROUTING'} for r in received)

    native_lines = inputs[3].read_text().splitlines()
    at_admission = [{'line':i,'text':line} for i,line in enumerate(native_lines,1)
                    if line.startswith('time_ns=14400468077 ') and
                    any(v in line for v in ('[NWK 1]', '[HOP 1]', '[MAC] Enqueue'))]
    assert sum('[HOP 1] TX reliable RoutingControl' in r['text'] for r in at_admission) == 1
    assert any('changes count=0 infoChanged=0' in r['text'] for r in at_admission)
    additions = [{'line':i,'text':line} for i,line in enumerate(native_lines,1)
                 if '[NWK 1] Added route candidate dst=3 nextHop=3 ' in line]
    first_addition = additions[0]
    assert first_addition['text'].startswith('time_ns=18724108077 ')
    before_add = [{'line':i,'text':line} for i,line in enumerate(native_lines,1)
                  if line.startswith('time_ns=18724108077 ') and '[NWK 1]' in line]
    write_json('native_admission_and_first_route.json', {'at_admission':at_admission,
               'first_candidate_addition':first_addition,'first_candidate_context':before_add})

    with inputs[5].open() as f:
        native_snapshot = [r for r in csv.DictReader(f) if r['time_ns']=='14534000000' and
                           r['source']=='1' and r['hop_destination']=='3' and r['hop_sequence']=='4']
    assert len(native_snapshot) == 1
    row = native_snapshot[0]
    assert row['routing_section_hex'] == controls[0]['routing']['hex']
    write_json('native_matching_snapshot.json', {'native_tx':row,
        'decoded':decode_section(bytes.fromhex(row['routing_section_hex'])),
        'matlab_snapshot_byte_identical':True})

    with inputs[4].open() as f:
        native_observations = [r for r in csv.DictReader(f, delimiter='\t')
                               if r['node']=='1' and r['time_ns']=='14400468077']
    write_json('native_admission_observations.json', native_observations)
    divergence = json.loads(inputs[2].read_text())
    assert divergence['actual_time_s'] == 14.534
    summary = {'seed':132,'case':'F_message_flag','admission_time_s':T,
        'matlab_control_count':2,'native_control_count':1,
        'extra_control':controls[1], 'snapshot_byte_identical':True,
        'matlab_received_control_types_from_peer3_before_admission':sorted({r['ControlType'] for r in received}),
        'native_first_direct_candidate_3_time_ns':18724108077,
        'next_guard_failure':divergence,
        'conclusion':'ACK admission incorrectly creates a MATLAB direct route candidate; capability zero produces DELETE3',
        'evidence_boundary':'Decoded controls and native first-candidate log are observed; MATLAB private candidate birth is inferred from the traced callback and exact source path',
        'independent_issue':'Guarded MAC active-node count mismatch is a separate population-publication behavior',
        'new_network_simulation_executed':False,'matlab_runtime_executed':False}
    write_json('summary.json', summary)
    source_paths = [ROOT/'autonomous_fourth/kit/autocase/model/+csr/+nwk/Routes.m',
        ROOT/'autonomous_fourth/kit/autocase/model/+csr/+nwk/RoutingCodec.m',
        ROOT/'autonomous_fourth/kit/autocase/+ac/MessageFlagNwk.m',
        ROOT/'autonomous_fourth/kit/autocase/+ac/MessageFlagSimulation.m',
        ROOT/'autonomous/native_env/csr/model/csr-nwk-layer.h']
    write_json('input_hashes.json', [{'path':str(p.relative_to(ROOT)), 'bytes':p.stat().st_size,
                                    'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                                   for p in inputs+source_paths])
    print(json.dumps({'controls':len(controls), 'extra_delete_hex':controls[1]['routing']['hex'],
                      'snapshot_byte_identical':True,'native_first_direct_candidate_ns':18724108077}))

if __name__ == '__main__':
    main()
