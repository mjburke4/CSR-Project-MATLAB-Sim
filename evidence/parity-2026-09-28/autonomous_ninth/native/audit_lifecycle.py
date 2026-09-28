#!/usr/bin/env python3
"""Read-only lifecycle audit of the accepted native capture and actual K return."""
import collections,csv,hashlib,json,re
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
CSR=ROOT/'autonomous/native_env/csr/model'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,data):(OUT/name).write_text(json.dumps(data,indent=2)+'\n')
fixture=ROOT/'autonomous/native_capture/fixture/tx_signatures.csv'
runlog=ROOT/'autonomous/native_capture/run/run.log'
observations=ROOT/'autonomous/native_capture/run/observations.tsv'
returned=ROOT/'autonomous_ninth/data/K_receiver_timers/first_divergence.json'
rows=list(csv.DictReader(fixture.open()));snmp=[r for r in rows if r['kind']=='7'];keys=[r for r in rows if r['kind']=='9']
assert len(rows)==1495 and len(snmp)==36 and len(keys)==14
for r in snmp:
    assert r['hop_sequence']=='0' and r['ackable']=='0' and r['dscp']=='0' and r['wire_bytes']=='31'
    packet=bytes.fromhex(r['packet_hex']);payload=bytes.fromhex(r['payload_hex'])
    assert int.from_bytes(packet[:3],'big')==int(r['source'])
    assert int.from_bytes(packet[3:6],'big')==int(r['hop_destination'])
    assert int.from_bytes(payload[:3],'big')==int(r['snmp_source'])
    assert int.from_bytes(payload[3:6],'big')==int(r['snmp_destination'])
    assert payload[7]==int(r['snmp_command']) and len(payload)==13+3*payload[12]
assert len({r['frame_id']for r in keys})==14
for r in keys:assert r['ackable']=='1' and r['dscp']=='7' and r['wire_bytes']=='62'
stop=json.loads(returned.read_text());assert stop['fields']==['child3.hop_destination','child3.snmp_destination']
a=stop['actual']['children'][2];e=stop['expected'][2]
assert (a['hop_destination'],a['snmp_destination'])==(4,2)
assert (e['hop_destination'],e['snmp_destination'])==(1,1)

pending={};starts=[];dones=[];complete=[];append=[];handoff=[];keysend=[];keydone=[];selected=[]
all_lines=runlog.read_text().splitlines()
for line in all_lines:
    match=re.match(r'time_ns=(\d+) \[(NWK|HOP) (\d+)\] (.*)',line)
    if not match:continue
    t,layer,node,body=match.groups();t=int(t);node=int(node)
    item={'time_ns':t,'layer':layer,'node':node,'text':body}
    found=re.search(r'RX SNMP_START_DISCOVERY source=(\d+) hopSource=(\d+) delay=(-?\d+) state=(\d+)',body)
    if found:
        source,hop,delay,state=map(int,found.groups());starts.append({**item,'source':source,'hop_source':hop,'delay':delay,'state':state})
    found=re.search(r'RX SNMP_DISCOVERY_DONE source=(\d+)',body)
    if found:
        source=int(found[1]);dones.append({**item,'source':source,'prior_pending_target':pending.get(node),'matches_pending':source==pending.get(node)})
    found=re.search(r'SNMP discovery handoff target=(\d+)',body)
    if found:
        pending[node]=int(found[1]);handoff.append({**item,'target':int(found[1])})
    if 'SNMP discovery report watchdog expired' in body:pending[node]=None
    found=re.search(r'Legacy discovery lifecycle complete initiator=(\d+) knownNodes=(\d+) completionReports=(\d+)',body)
    if found:
        initiator,known,reports=map(int,found.groups());complete.append({**item,'initiator':initiator,'known_nodes':known,'completion_reports':reports})
    found=re.search(r'Discovery table append node=(\d+) needed=(\d+) position=(\d+)',body)
    if found:
        dest,needed,position=map(int,found.groups());append.append({**item,'destination':dest,'needed':needed,'position':position})
    found=re.search(r'TX reliable KeyUpdate neighbor=(\d+) hopSeq=(\d+)',body)
    if found:keysend.append({**item,'destination':int(found[1]),'sequence':int(found[2])})
    found=re.search(r'KeyUpdate send completion neighbor=(\d+) acknowledged=(\d+) sentKey=(\d+)',body)
    if found:keydone.append({**item,'destination':int(found[1]),'acknowledged':int(found[2]),'sent_key':int(found[3])})
    if node==5 and any(s in body for s in ('RX SNMP','Discovery table append','Legacy discovery lifecycle complete','SNMP discovery handoff','Ignore duplicate SNMP')):
        selected.append(item)
assert len(starts)==8 and len([x for x in starts if x['state']!=0])==1
assert [(x['node'],x['source'],x['time_ns'])for x in starts if x['state']!=0]==[(5,1,41202171086)]
assert len(dones)==7 and all(x['matches_pending']for x in dones)
assert max(x['completion_reports']for x in complete)==2
assert len(keysend)==len(keydone)==14 and all(x['acknowledged']==1 for x in keydone)
assert not any('Resend entry rejected: OPNET queue limit reached' in x for x in all_lines)
assert [(x['destination'],x['needed'],x['position'])for x in append if x['node']==5]==[(3,0,0),(4,1,1),(1,1,2),(2,1,3)]
target_handoff=next(x for x in handoff if x['node']==5 and x['time_ns']==71827352444)
assert target_handoff['target']==1
native_transition=[]
with observations.open() as stream:
    for r in csv.DictReader(stream,delimiter='\t'):
        if r['node']=='4' and int(r['time_ns'])==62870833632:native_transition.append(r)
assert any(r['event']=='mac_draw' and json.loads(r['detail_json'])['draw_ordinal']=='25' for r in native_transition)
save('lifecycle_audit.json',{
 'status':'source_and_existing_capture_consistent','native_network_or_component_run':False,
 'returned_stop':{'time_s':stop['actual_time_s'],'node':stop['node'],'tx_ordinal':stop['ordinal'],
     'actual_hop_destination':a['hop_destination'],'actual_final_destination':a['snmp_destination'],
     'native_hop_destination':e['hop_destination'],'native_final_destination':e['snmp_destination'],
     'native_packet_hex':e['packet_hex']},
 'snmp_packet_inventory':{'all':36,'start':sum(r['snmp_command']=='1'for r in snmp),
     'done':sum(r['snmp_command']=='2'for r in snmp),'hop_differs_from_final':sum(r['hop_destination']!=r['snmp_destination']for r in snmp)},
 'native_snmp_packets':[{k:r[k]for k in ('time_ns','source','frame_id','hop_destination','snmp_destination','snmp_command','snmp_nodes','packet_hex')}for r in snmp],
 'native_start_receives':starts,'native_done_receives':dones,
 'native_discovery_completions':complete,'native_table_appends':append,'native_handoffs':handoff,
 'node5_observed_lifecycle':selected,
 'source_reconstructed_node5_at71827352444':{'native_pending_order':[1,2],'matlab_pending_order':[2],
     'reason':'MATLAB marks source1 requested during active duplicate START at41.202171086; native does not.',
     'is_runtime_private_state_dump':False},
 'native_key_update_sends':keysend,'native_key_update_completions':keydone,
 'native_key_update_packets':[{k:r[k]for k in ('time_ns','source','frame_id','hop_destination','hop_sequence','wire_bytes','ackable','dscp','rate_kbps','tx_power_dbm')}for r in keys],
 'native_node4_key_response_boundary':native_transition,
 'sibling_limits':['All7 delivered DONEs matched the pending handoff; broader DONE interruption policy not exercised.',
     'Requester list peaks at2, so native cap10 versus unbounded MATLAB is unexercised.',
     'Native resend overflow forwards untracked control; retained MATLAB admission gate differs in saturation, absent here.',
     'No full timing-prefix claim: an earlier node4 MAC request-time drift occurs at62.870833632 versus62.881.'],
 'input_sha256':{str(p.relative_to(ROOT)):sha(p)for p in (fixture,runlog,observations,returned)}})

spans=[
 ('Native SNMP route/final address separation','csr-nwk-layer.h',8164,8240),
 ('Native START idle-only marking and active requester retention','csr-nwk-layer.h',8241,8318),
 ('Native DONE handling','csr-nwk-layer.h',8319,8339),
 ('Native discovery table insertion and marking','csr-nwk-layer.h',7951,8001),
 ('Native ordered completion and handoff','csr-nwk-layer.h',8390,8477),
 ('Native one-hop SNMP receive contract','csr-hop-layer.h',2682,2735),
 ('Native synchronous NWK KEY_UPDATE ownership','csr-nwk-layer.h',3902,3936),
 ('Native key request and reciprocal update callbacks','csr-nwk-layer.h',4306,4356),
 ('Native KEY_UPDATE HOP sequence/radio/resend/MAC order','csr-hop-layer.h',1977,2031),
 ('Native queue-overflow boundary retained as limitation','csr-hop-layer.h',4349,4408),
 ('Native ACK clock starts at sent confirmation','csr-hop-layer.h',585,637),
]
save('source_path_proof.json',{'source_commit':'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b',
 'spans':[{'purpose':purpose,'file':name,'first_line':first,'last_line':last,'file_sha256':sha(CSR/name),
 'source':'\n'.join((CSR/name).read_text().splitlines()[first-1:last])+'\n'}for purpose,name,first,last in spans]})
print('PASS:36 raw SNMP packets,8 START receives/1active duplicate,7 DONE receives all matching,14 reliable KEY_UPDATE sends/TXs/completions; source boundary evidence retained.')
