#!/usr/bin/env python3
"""Independent static completeness checks; does not execute MATLAB."""
from pathlib import Path
import csv,json,hashlib,difflib
R=Path(__file__).resolve().parent
B=R.parent/'short_kit/two_case_next/source5_replay/mac_adapter'
S=R/'out_short_20260924_083651/replays/source5_mac/staging'
M=R.parents[1]/'return6000/kit/csr6000/model'
def rows(p):return list(csv.DictReader(p.open()))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
binding=json.loads((B/'binding.json').read_text())
files={'adapter_mac_layer_sha256':B/'matlab/+mac_replay/MacLayer.m','adapter_scheduler_sha256':B/'matlab/+mac_replay/Scheduler.m','run_mac_history_sha256':B/'matlab/run_mac_history.m','production_mac_sha256':M/'+csr/+mac/Layer.m'}
assert all(sha(p)==binding[k] for k,p in files.items())
ins=rows(S/'inputs/inputs.csv');fr=rows(S/'inputs/frames.csv');draw=rows(S/'inputs/draws.csv');tx=rows(S/'reference/tx.csv')
checks=[]
for node in ['2','8']:
 ni=[r for r in ins if r['node']==node];nf=[r for r in fr if r['node']==node];nd=[r for r in draw if r['node']==node];nt=[r for r in tx if r['node']==node]
 ids={r['frame_id'] for r in nf};enq={r['frame_id'] for r in ni if r['kind']=='enqueue'};txids={p for r in nt for p in r['frame_ids'].split(';')}
 assertions={'zero_time_idle_input':ni[0]['time_ns']=='0' and ni[0]['kind']=='receiver_state' and ni[0]['value']=='idle','all_enqueue_ids_bound':enq<=ids,'all_tx_ids_bound_and_enqueued':txids<=ids and txids<=enq,'unique_frame_ids':len(ids)==len(nf),'unique_input_orders':len({r['event_order'] for r in ni})==len(ni),'draw_ordinals_contiguous':list(map(lambda r:int(r['ordinal']),nd))==list(range(1,len(nd)+1)),'supported_input_kinds':{r['kind'] for r in ni}<=set(['enqueue','receiver_state','sync','received','active','reported','cancel_ack','cancel_type']),'explicit_frame_link_control':all(r['has_link_control']=='1' for r in nf),'valid_mac_rate_power':all(r['rate'] in ['8','16','32','64','128','500','1000'] and float(r['tx_power_dbm'])==33 for r in nf),'integer_exact_times':all(int(r['time_ns'])<2**53 for r in ni),'all_draws_before_stop':all(int(r['time_ns'])<330000000000 for r in nd)}
 assert all(assertions.values()),(node,assertions)
 checks.append({'node':int(node),'inputs':len(ni),'frames':len(nf),'draws':len(nd),'warmup_txs':len(nt),'target_txs':sum(int(r['time_ns'])>=300000000000 for r in nt),'assertions':assertions})
prod=(M/'+csr/+mac/Layer.m').read_text().splitlines(keepends=True);adapt=(B/'matlab/+mac_replay/MacLayer.m').read_text().splitlines(keepends=True)
(R/'adapter_vs_production.diff').write_text(''.join(difflib.unified_diff(prod,adapt,fromfile='production/+csr/+mac/Layer.m',tofile='adapter/+mac_replay/MacLayer.m')))
report={'scope':'Static fixture and source audit only; no MATLAB execution performed.','existing_adapter_binding_all_hashes_match':True,'node_checks':checks,'diff_interpretation':['class/constructor rename','suppress periodic native wake in favor of supplied receiver state','suppress post-TX Search-to-Idle in favor of supplied receiver state','suppress Track-to-Search sleep timer in favor of supplied receiver state','additional reservation tick observation','native bitmap cancellation boundary translation to production per-sequence cancel; protected structured-destination frames and collision assertion'],'no_queue_packing_reservation_backoff_algorithm_edit':True,'genuine_limits':['All exogenous inputs are scheduled before runtime-generated callbacks; a mismatch involving an equal timestamp requires boundary-order diagnosis before calling it a production mismatch.','Receiver availability, queue admission and feedback cancellations are inputs, so a pass cannot validate discovery, ACK generation, HOP custody, or autonomous duty-cycle behavior.','Existing fidelity manifest nodes list node5 because only node5 was replayed earlier; new nodes must be described as pending MATLAB comparison.','Original binding origin mentions older nodes2/4/8 acceptance, but those original results were not inspected in this audit.']}
(R/'adapter_static_review.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
