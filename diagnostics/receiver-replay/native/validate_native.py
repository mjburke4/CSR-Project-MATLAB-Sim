#!/usr/bin/env python3
"""Check observed native history against the physical-input receiver replay."""
import csv,hashlib,json,pathlib,collections,re,argparse,gzip
N=pathlib.Path(__file__).resolve().parent;P=N.parent
ap=argparse.ArgumentParser();ap.add_argument('--capture-dir',type=pathlib.Path,default=N/'capture');ap.add_argument('--replay-log',type=pathlib.Path,default=N/'replay-output.log');ap.add_argument('--reference-dir',type=pathlib.Path,default=P/'reference');a=ap.parse_args();a.reference_dir.mkdir(exist_ok=True)
def open_text(p):
 return p.open() if p.exists() else gzip.open(str(p)+'.gz','rt')
def load(p):
 out=collections.defaultdict(list)
 for line in open_text(p):
  v=line.rstrip('\n').split('|');out[v[0]].append(v[1:])
 return out
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
c=load(a.capture_dir/'receiver-input.log');r=load(a.replay_log)
columns='event_index time_ns signal_id stage source hop_sequence result reason state_before state_after'.split();states={'0':'Idle','1':'Search','2':'Track','3':'Tx'}
def events(raw):
 rows=[]
 for i,v in enumerate(raw):
  d=dict(zip(columns,v));d['event_index']=i;d['state_before']=states[d['state_before']];d['state_after']=states[d['state_after']];d['raw_reason']=d['reason'];rows.append(d)
 return rows
def write(path,rows):
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
actual=events(r['EVENT']);expected=events(c['EVENT']);write(a.reference_dir/'events.csv',actual);write(a.capture_dir/'events.csv',expected)
def window(rows):return [{k:v for k,v in d.items() if k!='event_index'}for d in rows if 657000000000<=int(d['time_ns'])<669000000000]
ae,ee=window(actual),window(expected);assert ae==ee,'receiver timeline differs from original capture'
ci={x[3]:x[1:]for x in c['INPUT'] if x[2]=='signal' and int(x[1])<669000000000};ri={x[3]:x[1:]for x in r['INPUT']};assert ci==ri,'RF frontend/physical input differs'
# Exact doubles and phase, bit counts, probabilities, sampled uniforms all bind.
def key(x):return (x[0],x[1],x[2],x[3])
cd={key(x):x for x in c['DRAW']};assert len(cd)==len(c['DRAW']),'duplicate semantic draw key'
for x in r['DRAW']:assert cd[key(x)]==x,('draw mismatch',x,cd.get(key(x)))
usage=[dict(zip('signal_id interval_start_s interval_end_s phase uniform bits probability'.split(),x)) for x in r['DRAW']]
write(a.reference_dir/'draw_usage.csv',usage)
cs=dict(c['SYNC']);assert all(cs[x[0]]==x[1] for x in r['SYNC'])
target=[d for d in ae if d['stage']=='signal_end' and d['source']=='8' and d['hop_sequence']=='174'];assert [(int(d['time_ns']),d['reason']) for d in target]==[(658408815346,'prior_stage'),(662126815346,'half_duplex'),(664505815346,'prior_stage')]
# Verify the listening-control setting against actual original observer output.
active_lines=[];wait_lines=[]
for line in open_text(a.capture_dir/'run.log'):
 m=re.match(r'time_ns=(\d+)',line)
 if not m:continue
 t=int(m[1])
 if '[MAC 2] active_nodes set' in line and t<669000000000:active_lines.append(line.strip())
 if '[MAC 2] post-TX WAIT_FOR_ACK' in line and 620000000000<=t<669000000000:wait_lines.append(line.strip())
assert 'active_nodes set to 3 ' in active_lines[-1]
assert wait_lines and all('POST_TX_WAIT=20 s' in x for x in wait_lines)
proof=dict(native_original_timeline_exact=True,comparison_start_ns=657000000000,comparison_end_ns=669000000000,ordered_events=len(ae),counts=dict(collections.Counter(d['stage']for d in ae)),target_drops=target,rf_inputs_recomputed_exact=len(ri),rf_verified_fields='all emitted fields: callback time, physical start/end, source, header, radio profile, power, noise, distance, preamble, rate, bytes and flags',sync_thresholds_replayed=len(r['SYNC']),uniform_draw_requests_exact=len(r['DRAW']),uniform_checks='semantic key, absolute doubles, phase, bits, probability and uniform exact; missing keys abort; no fallback draws',receiver_control=dict(active_nodes=3,last_observed_active_nodes_line=active_lines[-1],post_tx_wait_lines=wait_lines,prep_tx_and_cancel_wait='captured assignment/call timeline',queues_empty_at_tx_end='captured OnMacTxFinished input'),warmup=dict(start_ns=620000000000,initial_state='Idle',forced_track=False,forced_decode=False,production_duty_cycle=True,prehistory_preserved='all physical arrivals and own transmissions since620 plus recorded MAC listening controls'),input_hashes={p.name:sha(p)for p in (P/'inputs').glob('*')if p.is_file()},capture_log_sha256=sha(a.capture_dir/'receiver-input.log'),replay_log_sha256=sha(a.replay_log),prefix_receipt=json.loads((a.capture_dir/'prefix-equality.json').read_text()),matlab_executed=False,claim_scope='receiver decisions and addressed MAC-to-HOP boundary on a fixed schedule; no end-to-end/network parity claim')
(a.reference_dir/'native_fidelity.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({k:proof[k]for k in ['ordered_events','counts','rf_inputs_recomputed_exact','sync_thresholds_replayed','uniform_draw_requests_exact']},indent=2))
