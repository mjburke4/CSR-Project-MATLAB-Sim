#!/usr/bin/env python3
"""Build bounded, controlled HOP action contracts; no simulator model arithmetic."""
import argparse,csv,gzip,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DEFAULT_SOURCE=Path(__file__).resolve().parents[1] if Path(__file__).parent.name=='scripts' else ROOT/'csr22'
parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,default=DEFAULT_SOURCE);opts=parser.parse_args()
SOURCE=opts.source_root.resolve(); OUT=SOURCE/'scenarios/t22'
A=[]; C=[]; M=[]; case=''
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def begin(name,scope):
 global case
 case=name;C.append(dict(case_id=name,resend_seconds=2,max_resends=2,dack_seconds=20,tic_seconds=1/36e6,pending_threshold=16,flow_threshold_max=16,policy='actual-tx',scope=scope))
def row(t,action,packet='',peer=8,acks='',dacks='',note=''):
 r=dict(case_id=case,step=1+sum(x['case_id']==case for x in A),time_s=format(t,'.12g'),action=action,packet=packet,peer=peer,ack_packets=acks,dack_packets=dacks,note=note);A.append(r);return r
def check(r,reason,**want):M.append(dict(case_id=r['case_id'],step=r['step'],rationale=reason,equals=want))
def send(t,p,peer=8):return row(t,'SEND',p,peer)
def tx(t,p,peer=8):return row(t,'TX',p,peer)
def ack(t,p):return row(t,'FEEDBACK',acks=p)
def clean(n,start=0,period=.01,prefix='w'):
 for i in range(n):
  t=start+i*period;p=f'{prefix}{i+1}';send(t,p);tx(t,p);r=ack(t+.002,p)
 return r
begin('clean_growth_boundary','Three clean ACKs grow the per-peer window; threshold+1 admission boundary.')
check(row(0,'PROBE'),'Fresh DATA flow has one available slot.',threshold=0,ack_count=0,outstanding=0,global_pending=0,can_send=1)
send(.001,'p1');tx(.001,'p1');check(send(.002,'blocked'),'Threshold zero permits one outstanding DATA.',accepted=0,outstanding=1,can_send=0)
ack(.003,'p1');send(.004,'p2');tx(.004,'p2');ack(.005,'p2');send(.006,'p3');tx(.006,'p3')
check(ack(.007,'p3'),'The third ACK raises threshold from zero to one.',threshold=1,ack_count=0,outstanding=0,ack_total=3)
send(.008,'a');tx(.008,'a');check(send(.009,'b'),'Threshold one permits two DATA entries.',accepted=1,outstanding=2,can_send=0);tx(.009,'b')
check(send(.010,'blocked2'),'The third concurrent DATA is blocked.',accepted=0,outstanding=2)
check(ack(.011,'a;b'),'Both admitted entries release exactly once.',global_pending=0,resend=0,ack_total=5,ack_count=2)
begin('retried_third_ack','A retried third ACK grows the window before resetting the accumulator.')
clean(2);send(.1,'retry');tx(.1,'retry');check(row(2.099,'PROBE'),'Retry has not yet become due.',retry_total=0)
check(row(2.101,'PROBE'),'The natural retry timer enqueues one retry.',retry_total=1,resend=1)
tx(2.11,'retry');check(ack(2.12,'retry'),'Increment/test precedes reset after a retried third ACK.',threshold=1,ack_count=0,ack_total=3,retry_total=1)
clean(1,2.2,prefix='after');check(row(2.21,'PROBE'),'The following clean ACK begins a fresh accumulator.',threshold=1,ack_count=1)
begin('retried_second_ack','A retried second ACK resets partial progress without growing the window.')
clean(1);send(.1,'retry');tx(.1,'retry');tx(2.11,'retry')
check(ack(2.12,'retry'),'A retried second ACK cannot grow the window.',threshold=0,ack_count=0,ack_total=2,retry_total=1)
clean(2,2.2,prefix='after');check(row(2.22,'PROBE'),'Two subsequent clean ACKs are insufficient after reset.',threshold=0,ack_count=2)
clean(1,2.23,prefix='third');check(row(2.24,'PROBE'),'Three new clean ACKs restore growth.',threshold=1,ack_count=0)
begin('dack_hold_20','DACK releases NSDP immediately, retaining HOP capacity for the ordinary 20-second hold.')
clean(5);send(.2,'held');tx(.2,'held')
check(row(.21,'FEEDBACK',dacks='held'),'DACK completes ownership but retains one HOP capacity slot.',threshold=1,ack_count=0,outstanding=1,global_pending=1,dack_holds=1,resend=0,dack_total=1,nsdp_release_total=6)
send(.22,'other');tx(.22,'other');check(send(.221,'blocked'),'DACK-held capacity participates in admission.',accepted=0,outstanding=2)
ack(.23,'other');check(row(20.209,'PROBE'),'Capacity remains occupied immediately before hold expiry.',global_pending=1,dack_holds=1,nsdp_release_total=7)
check(row(20.211,'PROBE'),'Hold expiry releases capacity without another NSDP release.',global_pending=0,dack_holds=0,dack_expired_total=1,nsdp_release_total=7,threshold=1,ack_count=1)
begin('dack_hold_40','A DACK after the maximum two retries holds capacity for 40 seconds.')
clean(2);send(.1,'held');tx(.1,'held');tx(2.11,'held');tx(4.12,'held')
check(row(4.13,'FEEDBACK',dacks='held'),'At the retry limit, DACK still releases NSDP immediately.',threshold=0,ack_count=0,dack_holds=1,global_pending=1,resend=0,retry_total=2,nsdp_release_total=3)
check(row(24.131,'PROBE'),'The ordinary 20-second deadline is insufficient at maximum retry.',dack_holds=1,dack_expired_total=0)
check(row(44.129,'PROBE'),'Capacity persists until the doubled deadline.',dack_holds=1,global_pending=1)
check(row(44.131,'PROBE'),'The doubled hold releases capacity once.',dack_holds=0,global_pending=0,dack_expired_total=1,nsdp_release_total=3)
begin('final_failure_floor','Natural final retry expiration lowers threshold once and never below zero.')
clean(3);send(.1,'fail1');tx(.1,'fail1');tx(2.11,'fail1');tx(4.12,'fail1')
check(row(8.119,'PROBE'),'Final attempt retains capacity for twice the retry interval.',fail_total=0,outstanding=1)
check(row(8.121,'PROBE'),'Final DATA failure lowers threshold and releases ownership.',threshold=0,ack_count=0,fail_total=1,global_pending=0,nsdp_release_total=4)
send(9,'fail2');tx(9,'fail2');tx(11.01,'fail2');tx(13.02,'fail2')
check(row(17.021,'PROBE'),'A second failure cannot make threshold negative.',threshold=0,fail_total=2,global_pending=0,nsdp_release_total=5)
check(send(17.1,'next'),'Failure capacity release admits the next packet.',accepted=1,outstanding=1,global_pending=1)
begin('ceiling_global_capacity','Window ceiling and global capacity remain separate from per-peer capacity.')
check(clean(51,period=.003),'Fifty-one clean ACKs exercise one growth cycle beyond the ceiling.',threshold=16,ack_count=0,ack_total=51)
for i in range(17):send(.2+i*.001,f'full{i+1}');tx(.2+i*.001,f'full{i+1}')
check(send(.22,'blocked'),'Threshold sixteen allows seventeen outstanding, then blocks.',accepted=0,threshold=16,outstanding=17,global_pending=17,can_send=0)
check(row(.221,'PROBE',peer=9),'Global capacity blocks a fresh peer with its own available slot.',threshold=0,outstanding=0,global_pending=17,can_send=0)
ack(.23,'full1');check(send(.24,'peer9',peer=9),'One global release permits a fresh peer.',accepted=1,threshold=0,outstanding=1,global_pending=17);tx(.24,'peer9',peer=9)
check(send(.25,'globalblocked'),'The original peer has spare neighbor capacity but global capacity is full.',accepted=0,threshold=16,outstanding=16,global_pending=17,can_send=0)
ack(.26,';'.join(f'full{i}' for i in range(2,18)))
check(row(.27,'PROBE',peer=9),'An occupied fresh peer remains blocked despite abundant global space.',global_pending=1,outstanding=1,threshold=0,can_send=0)
check(row(.28,'FEEDBACK',peer=9,acks='peer9'),'All capacity is released exactly once.',global_pending=0,resend=0,nsdp_release_total=69)
begin('grouped_feedback_order','Cumulative newest-first ACK/DACK processing, overlap precedence and duplicate idempotence.')
clean(5);send(.2,'a');tx(.2,'a');send(.21,'b');tx(.21,'b')
check(row(.22,'FEEDBACK',acks='a;b',dacks='b'),'An overlapping ACK wins, so both complete as positive ACKs.',threshold=2,ack_count=1,ack_total=7,dack_total=0,dack_holds=0)
send(.23,'c');tx(.23,'c');send(.24,'d');tx(.24,'d')
check(row(.25,'FEEDBACK',acks='c',dacks='d'),'Newer DACK resets before older ACK begins new progress.',threshold=2,ack_count=1,ack_total=8,dack_total=1,dack_holds=1,nsdp_release_total=9)
check(row(.26,'FEEDBACK',acks='c',dacks='d'),'Repeated bitmap feedback cannot release an identity twice.',ack_total=8,dack_total=1,dack_holds=1,nsdp_release_total=9)
check(row(.27,'FEEDBACK',acks='d'),'An ACK cannot complete an already DACK-completed resend entry.',ack_total=8,dack_total=1,dack_holds=1,nsdp_release_total=9)
check(row(20.251,'PROBE'),'The retained DACK capacity still expires normally.',global_pending=0,dack_holds=0,dack_expired_total=1)
begin('seed130_feedback_motif','Reduced ordered feedback motif from native seed 130 startup; times and surrounding traffic are controlled.')
clean(6,prefix='prefix');send(.1,'old_retry');tx(.1,'old_retry');clean(1,.2,prefix='clean7');clean(1,.3,prefix='clean8')
tx(2.11,'old_retry');send(2.12,'clean9');tx(2.12,'clean9')
check(row(2.13,'FEEDBACK',acks='clean9;old_retry'),'Observed newer clean ninth ACK grows to three, then older retried ACK resets progress.',threshold=3,ack_count=0,ack_total=10,retry_total=1,global_pending=0,nsdp_release_total=10)
OUT.mkdir(parents=True,exist_ok=True)
for name,rows in [('cases.csv',C),('actions.csv',A)]:
 with (OUT/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
for c in C:
 rr=[r for r in A if r['case_id']==c['case_id']];assert all(float(rr[i]['time_s'])<=float(rr[i+1]['time_s']) for i in range(len(rr)-1));assert [r['step'] for r in rr]==list(range(1,len(rr)+1))
trace=SOURCE/'evidence/tranche-20-ns3-reference/s130/ns3-trace.csv.gz';captured=[]
with gzip.open(trace,'rt') as f:
 for r in csv.DictReader(f):
  if float(r['time_s'])>307.139:break
  if float(r['time_s'])>=300 and r['node']=='7' and r['peer']=='8' and r['event'] in ('hop_admission','hop_completion'):
   captured.append({k:v for k,v in r.items() if v})
prov={'schema':'csr-tranche22-seed130-motif-provenance-v1','input_path':trace.relative_to(SOURCE).as_posix(),'input_gzip_sha256':sha(trace),'accepted_candidate_sha256':sha(SOURCE/'evidence/tranche-20-candidate.json'),'source_pin':'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b','selection':'Node 7, peer 8, HOP admission/completion events from 300 through 307.139 seconds.','events':captured,'motif':{'clean_completion_application_sequences':[958,964,970,976,982,994,1000,1006,1018],'old_retried_application_sequence':988,'ordered_group_event_indices':[31560,31563],'observed_time_s':307.138292442,'clean_completion_threshold_after':3,'retried_completion_threshold_after':3},'transformation':['Original application and HOP sequence numbers are replaced with local aliases; fresh harness HOP allocator starts normally.','The first six clean completions form a rapid warm-up; the old retry is admitted before the final three clean completions.','The final newer clean ACK and older retried ACK share one controlled cumulative ACK bitmap, matching observed completion order.','Explicit TX times and reduced delays isolate the adaptive-window contract; MAC, PHY, NWK, contention and original startup timing are not replayed.','This is an observed feedback motif, not a full campus trace replay or proof of the cause of numerical differences.']}
(OUT/'seed130-provenance.json').write_text(json.dumps(prov,indent=2)+'\n')
state='case_id step time_s action packet peer accepted threshold ack_count outstanding global_pending dack_holds resend can_send ack_total dack_total fail_total nsdp_release_total retry_total tx_total dack_expired_total'.split()
contract={'schema':'csr-tranche22-controlled-hop-contract-v1','case_count':len(C),'action_count':len(A),'action_columns':list(A[0]),'state_columns':state,'configuration_columns':list(C[0]),'paths':{'cases':'scenarios/t22/cases.csv','actions':'scenarios/t22/actions.csv','seed130_provenance':'scenarios/t22/seed130-provenance.json'},'input_hashes':{x:sha(OUT/x) for x in ['cases.csv','actions.csv','seed130-provenance.json']},'execution':['Every case creates fresh real production HOP and scheduler objects; no threshold or ACK accumulator state is assigned.','Advance scheduler through time_s before each row, then execute action; equal-time rows execute in CSV order. No action is placed on a natural timer boundary.','SEND first checks the actual public admission gate, then invokes the real DATA send method if permitted. Rejected aliases receive no frame or sequence.','TX confirms the latest queued original/retry copy using the real HOP sent-notification method. No PHY or MAC transmission occurs; the MAC enqueue/cancel boundary is a controlled adapter.','FEEDBACK constructs one cumulative DATA feedback frame using the highest listed sequence and semicolon-separated alias bitmaps. ACK wins overlapping bits. It calls the real production receive method once.','PROBE mutates no model state. Every action produces a post-action state row.','Rows use node 7 and original source 7, final destination 1, with peer 8 unless explicitly peer 9.','Default actual-tx remains unchanged. Explicit retry transmissions avoid leaving queued retries unconfirmed across later retry scans.'], 'state_semantics':{'accepted':'-1 except SEND, where 0/1 indicates public admission outcome.','threshold':'Adaptive threshold for current row peer; effective neighbor window is threshold+1.','ack_count':'Current row peer ACK accumulator.','outstanding':'Current row peer capacity, including DACK holds.','global_pending':'Global DATA capacity, including DACK holds.','dack_holds':'Global delayed DACK capacity owners.','resend':'Global active reliable DATA resend entries.','nsdp_release_total':'One notification for ACK, DACK or final failure; no extra notification at DACK capacity expiry.','retry_total':'Natural retry enqueue count, not manually constructed retransmissions.','tx_total':'Actual sent-notification count across original and retry copies.','dack_expired_total':'DACK capacity release count.'},'milestones':M,'structural_invariants':['Global pending equals resend entries plus DACK holds in these DATA-only cases.','Cumulative accepted SEND equals ACK total plus DACK total plus failure total plus resend depth.','NSDP releases equal ACK total plus DACK total plus failure total.','Threshold remains between 0 and 16; ACK accumulator between 0 and 2.','One native and one MATLAB state row must correspond to every exact action row; integer states match exactly.'],'comparison':{'integer_tolerance':0,'time_absolute_tolerance_seconds':1e-9,'campus_percent_target_applies':False},'limitations':['Controlled HOP unit contract with real production methods; no PHY, radio contention, NWK routing or whole-network numerical parity test.','MATLAB execution remains pending until owner return; native reference execution is recorded separately.','Historical motif is transformed and reduced; independently selected synthetic cases cover timer and counter edge conditions.']}
(OUT/'contract.json').write_text(json.dumps(contract,indent=2)+'\n')
plan={'schema':'csr-tranche22-adaptive-window-plan-v1','tranche':22,'source_commit':'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b','engine_commit':'6b5cd24ea80713ce16d88575869aedd6f432bdae','cases_file':'scenarios/t22/cases.csv','actions_file':'scenarios/t22/actions.csv','contract_file':'scenarios/t22/contract.json','cases_sha256':sha(OUT/'cases.csv'),'actions_sha256':sha(OUT/'actions.csv'),'contract_sha256':sha(OUT/'contract.json'),'native_reference':'evidence/t22/native','case_count':len(C),'action_count':len(A),'checkpoint_count':len(A),'milestone_count':len(M),'case_order':[c['case_id'] for c in C],'state_columns':state,'action_columns':list(A[0]),'configuration_columns':list(C[0]),'default_configuration':{k:v for k,v in C[0].items() if k not in ('case_id','scope')},'comparison':contract['comparison'],'input_files':[{'path':'scenarios/t22/'+x,'sha256':sha(OUT/x)} for x in ['contract.json','cases.csv','actions.csv','seed130-provenance.json']],'semantics':contract['execution'],'timing_policy':'continuous','default_policy':'actual-tx','production_source_changed':False,'phy_ecc_changed':False,'full_campus_run':False,'working_campus_band_percent':10}
(OUT/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
print(json.dumps({'cases':len(C),'actions':len(A),'milestones':len(M),'contract_sha256':sha(OUT/'contract.json')}))
