#!/usr/bin/env python3
"""Read accepted native evidence and the E/F return; no simulation or mutations."""
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sources=[]

def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2)+'\n')

log=ROOT/'autonomous/native_capture/run/run.log'
sources.append(log)
lines=log.read_text().splitlines()
publish=[]
for n,line in enumerate(lines,1):
    m=re.search(r'time_ns=(\d+) \[NWK 1\] active_nodes=(\d+) pushed to MAC',line)
    if m:
        publish.append({'line':n,'time_ns':int(m[1]),'count':int(m[2])})
assert not any('routesClearTable parity reset' in line for line in lines)
last_before=max((r for r in publish if r['time_ns']<=14534000000),key=lambda r:r['time_ns'])
first_three=next(r for r in publish if r['count']==3)
assert last_before['count']==2
assert first_three['time_ns']==18724108077
selected=[]
for n,line in enumerate(lines,1):
    m=re.match(r'time_ns=(\d+) ',line)
    if not m:continue
    t=int(m[1])
    if ('[NWK 1]' in line or '[MAC 1]' in line or '[HOP 1]' in line or 'TX from node 1' in line) and (
            t in (13266211086,14400468077,14534000000,16715760000,18724108077)):
        selected.append({'line':n,'text':line})
(OUT/'native_population_excerpt.txt').write_text('\n'.join(f"{r['line']}: {r['text']}" for r in selected)+'\n')

fixture=ROOT/'autonomous/native_capture/fixture/tx_signatures.csv'
sources.append(fixture)
tx=[r for r in csv.DictReader(fixture.open()) if r['time_ns']=='14534000000' and r['source']=='1']
assert len(tx)==7
routing=next(r for r in tx if r['kind']=='6')
assert routing['routing_active_nodes']=='3'
save('native_tx_population_proof.json',routing)

cases={}
for name in ('E_check_gate','F_message_flag'):
    folder=ROOT/'autonomous_fifth/data'/name
    ordered=folder/'ordered_events.jsonl'
    sources.extend([ordered,folder/'random_summary.json',folder/'first_divergence.json'])
    events=[json.loads(line) for line in ordered.open()]
    transitions=[]
    last=None
    for e in events:
        if e['node']==1 and e['kind']=='mac_boundary' and e['details']['ActiveNodes']!=last:
            last=e['details']['ActiveNodes']
            transitions.append(e)
    assert transitions[-1]['time_s']==14.400468077
    assert transitions[-1]['details']['ActiveNodes']==3
    selected=[e for e in events if e['node']==1 and 14.400468076<=e['time_s']<=14.400468078 and
              (e['kind']=='protocol' or e in transitions)]
    (OUT/f'{name}_causal_excerpt.jsonl').write_text('\n'.join(json.dumps(e,separators=(',',':')) for e in selected)+'\n')
    divergence=json.loads((folder/'first_divergence.json').read_text())
    assert divergence['fields']==['active_nodes']
    assert divergence['actual']['active_nodes']==3 and divergence['expected']['active_nodes']==2
    assert divergence['actual']['low']==divergence['expected']['low']==0
    assert divergence['actual']['high']==divergence['expected']['high']==31
    summary=json.loads((folder/'random_summary.json').read_text())
    cases[name]={'population_transitions':transitions,'first_divergence':divergence,
                 'matched_random_requests':sum(x['consumed'] for x in summary['counts']),
                 'native_transmissions_checked':summary['native_transmissions_checked'],
                 'routing_admissions_at_14_400468077':[
                    e for e in selected if e['kind']=='protocol' and e['details']['event']=='hop_control_admit']}
save('returned_population_summary.json',cases)

ranges={
 'autonomous/native_env/csr/model/csr-nwk-layer.h':[(842,854),(958,992),(1074,1089),(4397,4423),(4534,4587),(7779,7805)],
 'autonomous/native_env/csr/model/csr-net-device.h':[(469,495),(523,542),(1060,1076),(2129,2139),(2716,2727),(2892,2902)],
 'autonomous/native_env/csr/model/csr-mac-core.h':[(239,264),(350,408)],
 'autonomous_fourth/kit/autocase/model/+csr/+sim/NetworkSimulation.m':[(513,520),(576,604)],
 'autonomous_fourth/kit/autocase/model/+csr/+nwk/Layer.m':[(365,385)],
 'autonomous_fourth/kit/autocase/model/+csr/+nwk/Neighbors.m':[(155,168)],
 'autonomous_fourth/kit/autocase/model/+csr/+mac/Layer.m':[(48,58),(651,670)],
}
with (OUT/'source_excerpts.txt').open('w') as f:
    for relative,sections in ranges.items():
        path=ROOT/relative;sources.append(path);code=path.read_text().splitlines()
        f.write(f'\nFILE {relative}\nSHA256 {sha(path)}\n')
        for first,last in sections:
            f.write(f'LINES {first}-{last}\n')
            f.writelines(f'{n}: {code[n-1]}\n' for n in range(first,last+1))

probe=OUT/'population_route_probe.log'
component={}
if probe.exists():
    probe_text=probe.read_text()
    assert 'ALL_COMPONENT_CASES_PASS' in probe_text
    required=[
      'POPULATION absent_candidate current=3 published=2',
      'ROUTE_ADMISSION absent_candidate grouped_operations=0 selectable=0',
      'LATER_HELLO absent_candidate published=3 selectable=1 grouped_operation=Delete',
      'ROUTE_ADMISSION observed_capability_zero grouped_operations=1 selectable=1 operation=Delete',
      'ROUTE_ADMISSION observed_capability_one grouped_operations=1 selectable=1 operation=Update']
    assert all(line in probe_text for line in required)
    component={'status':'three_cases_passed','checkpoints':required,
      'network_or_phy_created':False,'private_state_access':False,
      'event_execution':'Only same-time NWK/HOP callbacks, bounded by 1 ns per drain; 3 or 4 ns total per component case.',
      'compile_command':json.loads((OUT/'compile_command.json').read_text())}
    sources.extend([probe,OUT/'population_route_probe.cc',ROOT/'autonomous/native_env/build.json'])
save('population_receipt.json',{
    'status':'source_and_capture_confirmed_publication_boundary_mismatch',
    'native_csr_pin':'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b',
    'network_run':False,'component_run':bool(component),'production_or_fixture_edit':False,
    'public_api_component_probe':component,
    'native_last_publication_before_stop':last_before,
    'native_first_publication_three':first_three,
    'ack_success_last_heard_refresh_ns':14400468077,
    'native_nwk_routing_payload_population_at_stop':3,
    'native_mac_published_population_at_stop':2,
    'matlab_mac_population_at_stop':3,
    'native_clear_routes_calls_in_capture':0,
    'same_draw_integer_bounds':[0,31],
    'native_next_post_tx_wait_start_ns':16715760000,
    'native_captured_wait_seconds':18.5,
    'counterfactual_wait_seconds_if_population_three':20.0,
    'counterfactual_limit':'Formula sensitivity only, not an executed continuation or realized delivery/latency difference.',
    'sources':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in sources],
})
print('Confirmed native NWK population3 / published MAC2 versus MATLAB eager MAC3; E/F96matched requests,16checked TXs.')
