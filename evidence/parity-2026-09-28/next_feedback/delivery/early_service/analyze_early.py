#!/usr/bin/env python3
"""Attribute first source-8 DATA service using existing native fixture only."""
from pathlib import Path
import csv,json,hashlib
from collections import Counter
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
BASE=ROOT/'next_feedback/prior_coverage/out_short_20260924_083651/replays/source5_mac/staging'
def read(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def write(name,rows):
    with (OUT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
inputs=read(BASE/'inputs/inputs.csv');frames=read(BASE/'inputs/frames.csv');fmap={r['frame_id']:r for r in frames}
tx=read(BASE/'reference/tx.csv');draws=read(BASE/'inputs/draws.csv')
lo=300_000_000_000;first_tx=316_719_000_000
selected_inputs=[r for r in inputs if r['node']=='8' and lo<=int(r['time_ns'])<=first_tx]
selected_tx=[r for r in tx if r['node']=='8' and lo<=int(r['time_ns'])<=first_tx]
write('native_node8_mac_inputs_300_first_data.csv',selected_inputs)
write('native_node8_draws_300_first_data.csv',[r for r in draws if r['node']=='8' and lo<=int(r['time_ns'])<=first_tx])
write('native_node8_tx_300_first_data.csv',selected_tx)
events=[(int(r['time_ns']),0,r) for r in selected_inputs if r['kind']=='enqueue']+[(int(r['time_ns']),1,r) for r in selected_tx]
queue=None;ledger=[];generations=[];own=None
for stamp,typ,r in sorted(events,key=lambda x:(x[0],x[1])):
    if not typ:
        f=fmap[r['frame_id']]
        if f['is_ack']=='1':
            assert f['destination']=='7' and f['has_ack_window']=='1' and f['wirebytes']=='41'
            previous=queue['frame_id'] if queue else ''
            remaining=5-queue['transmissions'] if queue else 0
            queue={'frame_id':r['frame_id'],'sequence':f['sequence'],'kind':'DACK' if f['is_dack']=='1' else 'ACK',
                   'admit_ns':stamp,'transmissions':0}
            generations.append(queue)
            ledger.append({'time_ns':stamp,'event':'feedback_replace' if previous else 'feedback_enqueue',
                'frame_id':r['frame_id'],'sequence':f['sequence'],'previous_frame_id':previous,
                'previous_repeats_remaining':remaining,'feedback_repeats_after':5,
                'DATA_frame444_queued':bool(own)})
        else:
            assert r['frame_id']=='444' and own is None
            assert f['sequence']=='14' and f['wirebytes']=='217' and f['rate']=='8'
            own=f
            ledger.append({'time_ns':stamp,'event':'DATA_enqueue','frame_id':'444','sequence':'14','DATA_frame444_queued':True})
    else:
        ids=r['frame_ids'].split(';');assert len(ids)==1
        if queue:
            assert ids==[queue['frame_id']] and r['wirebytes']=='41'
            queue['transmissions']+=1
            ledger.append({'time_ns':stamp,'event':'feedback_tx','frame_id':queue['frame_id'],'sequence':queue['sequence'],
                'feedback_repeats_after':5-queue['transmissions'],'DATA_frame444_queued':bool(own)})
            if queue['transmissions']==5:queue=None
        else:
            assert ids==['444'] and stamp==first_tx and own
            ledger.append({'time_ns':stamp,'event':'DATA_first_tx','frame_id':'444','sequence':'14','feedback_repeats_after':0,'DATA_frame444_queued':False})
            own=None
assert len(selected_tx)==35 and sum(x['transmissions'] for x in generations)==34
assert len(generations)==20
write('native_node8_ack_queue_ledger.csv',ledger);write('native_node8_feedback_generations.csv',generations)
write('native_node8_early_frames.csv',[fmap[k] for k in ['444']+[g['frame_id'] for g in generations]])

native=read(ROOT/'next_feedback/native_receiver/filtered_native_events.csv')
native_first=[r for r in native if (r['event']=='hop_admission' and r['node']=='8' and r['sequence']=='884') or
    (r['node']=='2' and r['peer']=='8' and ((r['event']=='hop_feedback' and r['sequence']=='884') or(r['event']=='rx_accept' and r['sequence']=='14' and r['packet_type']=='data'))) or
    (r['event']=='tx_start' and r['node']=='8' and r['sequence']=='14' and r['packet_type']=='data')]
write('native_first_data_chain.csv',native_first)
mat=read(ROOT/'return6000/data/s132/attempt_001/raw/protocol_trace.csv')
mat_first=[r for r in mat if (r['PacketId']=='6' and r['Event'] in ('app_generate','mac_enqueue','hop_admit','hop_sent','hop_ack','hop_receive')) or
    (r['Event']=='tx_start' and r['NodeId']=='8' and r['Sequence']=='13')]
write('matlab_first_data_chain.csv',mat_first)
mat_first_arrival=next(r for r in mat if r['Event']=='hop_receive' and r['NodeId']=='8' and r['PeerId']=='7')
native_first_arrival=next(r for r in inputs if r['kind']=='enqueue' and r['node']=='8' and r['frame_id']=='445')
summary={'native_first_application':884,'native_hop_sequence':14,'native_MAC_frame_id':444,
 'native_MAC_enqueue_s':300.000000028,'native_first_DATA_tx_s':316.719,'native_first_DATA_rx_s':316.963815346,
 'native_first_DATA_prior_transmissions':0,'native_first_DATA_tx_received':True,
 'native_pre_DATA_feedback_transmissions':34,'native_feedback_queue_generations':20,
 'native_feedback_queue_replacements':sum(r['event']=='feedback_replace' for r in ledger),
 'native_feedback_generations_without_transmission':sum(g['transmissions']==0 for g in generations),
 'native_first_source7_receipt_at8_s':int(native_first_arrival['time_ns'])/1e9,
 'native_first_source7_DATA_tx_s':300.092,
 'native_last_feedback_generation':generations[-1],
 'native_final_feedback_tx_s':316.472,
 'native_initial_draws_at300_001':{r['node']:r['draw'] for r in draws if r['node'] in ('7','8') and int(r['time_ns'])==300_001_000_000},
 'matlab_first_application':6,'matlab_first_hop_sequence':13,'matlab_MAC_enqueue_s':300,
 'matlab_first_DATA_tx_s':300.144,'matlab_first_DATA_rx_s':301.381275345563,
 'matlab_first_source7_receipt_at8_s':float(mat_first_arrival['TimeSeconds']),
 'same_input_wire_bytes':{'cumulative_feedback':41,'DATA':217,'sum':258,'8kbps_concat_limit':256,'fits':False},
 'native_first_DATA_access_wait_s':316.719-300.000000028,
 'matlab_first_DATA_access_wait_s':.144,
 'first_receipt_difference_s':316.963815346-301.381275345563,
 'claim':'Different autonomous traffic and MAC availability histories; no same-input production MAC mismatch demonstrated.',
 'existing_replay_verification':{'node':8,'owner_return':'out_mh_20260923_121427',
    'owner_trace':'next_feedback/mac_owner/history/node8/tx.csv',
    'old_to_new_frame_id':{'172':'444'},'new_execution_needed':False,
    'warmup_start_ns':0,'verification_start_ns':lo,'verification_stop_ns':330_000_000_000,
    'required_assertions':['All warmup and target transmissions match native frame IDs, time_ns, wirebytes, preamble and slots.',
    'Exact 34 feedback transmissions to node7 precede first DATA frame444.',
    'First DATA frame444 transmits316719000000ns.',
    'All supplied slot draws and receiver/input records consumed without mismatch.']}}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
