#!/usr/bin/env python3
"""Read-only discovery-membership audit of accepted native capture and L return."""
import collections,csv,hashlib,json,re
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1]
CSR=ROOT/'autonomous/native_env/csr/model'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,data):(OUT/name).write_text(json.dumps(data,indent=2)+'\n')
fixture=ROOT/'autonomous/native_capture/fixture/tx_signatures.csv'
runlog=ROOT/'autonomous/native_capture/run/run.log'
ret=ROOT/'autonomous_tenth/data/L_discovery_lifecycle'
stop=json.loads((ret/'first_divergence.json').read_text())
summary=json.loads((ret/'random_summary.json').read_text())
rows=list(csv.DictReader(fixture.open()));snmp=[r for r in rows if r['kind']=='7']
assert len(rows)==1495 and len(snmp)==36
assert stop['node']==3 and stop['ordinal']==86
a=stop['actual']['children'][0];e=stop['expected']
assert (a['kind'],a['snmp_source'],a['snmp_destination'],a['hop_destination'])==(7,3,7,5)
assert e['kind']==0 and e['time_ns']==300365000000 and e['source_tx_ordinal']==86
events=[]
for line_number,line in enumerate(runlog.read_text().splitlines(),1):
    m=re.match(r'time_ns=(\d+) \[NWK (\d+)\] (.*)',line)
    if m:
        t,node,body=m.groups();events.append({'time_ns':int(t),'node':int(node),'log_line':line_number,'text':body})
tables=collections.defaultdict(dict);appends=[];handoffs=[];watchdogs=[];starts=[];dones=[];completions=[];node3=[];pending={}
for item in events:
    t,node,body=item['time_ns'],item['node'],item['text'];table=tables[node]
    found=re.search(r'RX SNMP_START_DISCOVERY source=(\d+) hopSource=(\d+) delay=(-?\d+) state=(\d+)',body)
    if found:
        source,hop,delay,state=map(int,found.groups());starts.append({**item,'source':source,'state':state})
        if state==0 and source in table:table[source]=False
    found=re.search(r'RX SNMP_DISCOVERY_DONE source=(\d+)',body)
    if found:
        source=int(found[1]);dones.append({**item,'source':source,'pending_target':pending.get(node),'matches_pending':source==pending.get(node)})
    found=re.search(r'Discovery table append node=(\d+) needed=(\d+) position=(\d+)',body)
    if found:
        target,needed,position=map(int,found.groups());assert target not in table and position==len(table)
        table[target]=bool(needed);appends.append({**item,'destination':target,'needed':needed,'position':position})
    found=re.search(r'Legacy discovery lifecycle complete initiator=(\d+) knownNodes=(\d+) completionReports=(\d+)',body)
    if found:
        initiator,known,reports=map(int,found.groups());completions.append({**item,'initiator':initiator,'known_nodes':known,'completion_reports':reports})
    if 'SNMP discovery report watchdog expired' in body:
        watchdogs.append({**item,'prior_target':pending.get(node),'existing_pending_entries':[n for n,needed in table.items()if needed]})
        pending[node]=None
    found=re.search(r'SNMP discovery handoff target=(\d+)',body)
    if found:
        target=int(found[1]);needed=[n for n,flag in table.items()if flag]
        assert needed and target==needed[0],(item,needed)
        table[target]=False;pending[node]=target
        handoffs.append({**item,'target':target,'registered_pending_order_before_send':needed})
    if node==3 and any(s in body for s in ('RX SNMP','Discovery table append','Legacy discovery lifecycle complete','SNMP discovery handoff','SNMP discovery report watchdog expired')):
        node3.append({**item,'source_reconstructed_table':[{'destination':n,'needed':f}for n,f in table.items()]})
assert len(appends)==34 and len(handoffs)==28 and len(completions)==8 and len(starts)==8 and len(dones)==7
assert all(d['matches_pending']for d in dones)
assert [(x['destination'],x['needed'])for x in appends if x['node']==3]==[(1,0),(5,1),(4,1)]
w=next(x for x in watchdogs if x['node']==3 and x['time_ns']==116340299163)
assert w['prior_target']==4 and not w['existing_pending_entries']
assert list(tables[3])==[1,5,4] and not any(tables[3].values())
late=[x for x in events if x['node']==3 and re.search(r'Added route candidate dst=(2|8|7)\b',x['text']) and x['time_ns']<116340299163]
assert any(x['time_ns']==96268879163 and 'dst=7' in x['text']for x in late)
# Register each append to the source-backed input boundary at its exact node/time.
boundary={}
for x in starts:
    if x['state']==0:boundary.setdefault((x['node'],x['time_ns']),[]).append('idle_start_requester')
for x in dones:boundary.setdefault((x['node'],x['time_ns']),[]).append('received_done')
for x in completions:boundary.setdefault((x['node'],x['time_ns']),[]).append('local_completion')
for x in appends:
    x['matching_registration_boundaries']=boundary.get((x['node'],x['time_ns']),[])
    assert x['matching_registration_boundaries'],x
source=(CSR/'csr-nwk-layer.h').read_text();lines=source.splitlines()
names=['EnsureDiscoveryEntry','MarkDiscoveryNotNeeded','CollectKnownDiscoveryNodes','CheckDiscoveryTable','NoteDestinationCreated']
inventory={name:[{'line':i,'source':s.strip()}for i,s in enumerate(lines,1)if name in s]for name in names}
assert [x['line']for x in inventory['EnsureDiscoveryEntry']]==[3404,7951,7996,8332,8398]
assert [x['line']for x in inventory['CollectKnownDiscoveryNodes']]==[387,3414,8135,8394]
assert [x['line']for x in inventory['CheckDiscoveryTable']]==[3402,8335,8421,8425,8476]
assert 'static constexpr uint8_t MAX_NODES = 10;' in (CSR/'csr-common.h').read_text()
save('membership_audit.json',{
 'status':'source_and_existing_capture_consistent','new_native_network_or_component_run':False,
 'returned_stop':{'time_s':stop['actual_time_s'],'node':3,'source_tx_ordinal':86,'actual_kind':'SNMP_START','actual_hop_destination':5,'actual_final_destination':7,'actual_wire_bytes':31,'native_next_kind':'DATA','native_next_time_ns':e['time_ns'],'native_next_hop_destination':e['hop_destination'],'native_next_wire_bytes':e['wire_bytes']},
 'first_time_difference':summary['first_time_difference'],
 'interpretation':'Extra scan traffic consumes a future per-node MAC/TX ordinal; the observed watchdog boundary is shared. This is not evidence of a 183.651-second watchdog timing error.',
 'native_inventory':{'snmp_tx':36,'start_tx':sum(r['snmp_command']=='1'for r in snmp),'done_tx':sum(r['snmp_command']=='2'for r in snmp),'start_nwk_receive':8,'done_nwk_receive':7,'local_completions':8,'table_appends':34,'handoffs':28,'watchdog_callbacks':len(watchdogs)},
 'all_registration_boundaries_accounted':True,'all_handoffs_use_first_existing_needed_entry':True,
 'native_table_appends':appends,'native_handoffs':handoffs,'native_watchdogs':watchdogs,
 'native_start_receives':starts,'native_done_receives':dones,'native_local_completions':completions,
 'native_final_tables_source_reconstruction':{str(node):[{'destination':n,'needed':f}for n,f in table.items()]for node,table in sorted(tables.items())},
 'node3_lifecycle':node3,'node3_late_route_additions':late,
 'node3_at_stop':{'native_registered_order':[1,5,4],'all_registered_complete':True,'route7_first_added_ns':96268879163,'watchdog_ns':116340299163,'route7_never_registered_in_full_native_capture':True},
 'table_reconstruction_method':'Replay logged append/hand-off operations and source-defined idle START marking; not a private runtime state dump.',
 'limits':['All7 native delivered DONEs match pending targets; broader DONE interruption gates are not exercised here.','Native requester cap10 is not reached (maximum2); completion known-node snapshot maximum6, so truncation is source-proven but not exercised.','No new native or MATLAB simulation; continuation remains owner-side.','Per-node draw and TX ordinal matching does not establish global callback order or 15-percent network parity.'],
 'input_sha256':{str(p.relative_to(ROOT)):sha(p)for p in (fixture,runlog,ret/'first_divergence.json',ret/'random_summary.json')}})
spans=[('Discovery table insert/mark and separate route-destination ordering','csr-nwk-layer.h',7951,8021),('Completion snapshot selection and bounded order','csr-nwk-layer.h',8135,8160),('Idle START and received DONE registration','csr-nwk-layer.h',8265,8338),('Local completion and existing-table-only advancement','csr-nwk-layer.h',8391,8477),('Known-node limit','csr-common.h',692,700)]
save('source_path_proof.json',{'source_commit':'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b','complete_function_name_inventory':inventory,'absence_proof':'EnsureDiscoveryEntry has exactly three executable caller sites: MarkDiscoveryNotNeeded, received DONE and CompleteDiscoveryLifecycle. Route mutations only call NoteDestinationCreated, which changes a separate destination-order list.','spans':[{'purpose':purpose,'file':name,'first_line':first,'last_line':last,'file_sha256':sha(CSR/name),'source':'\n'.join((CSR/name).read_text().splitlines()[first-1:last])+'\n'}for purpose,name,first,last in spans]})
print(f'PASS:34 registrations linked to allowed boundaries;28 handoffs match existing-table order;{len(watchdogs)} watchdogs audited; node3 exhausted at116.340299163.')
