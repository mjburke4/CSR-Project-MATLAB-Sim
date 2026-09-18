#!/usr/bin/env python3
"""Generate a fixed, short receiver-pressure diagnostic; no model execution."""
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION_COLUMNS = ['case_id','step','time_s','observe_s','action','packet','sequence','nwk_source','destination','ack_packets','dack_packets','note']
CASE_COLUMNS = ['case_id','resend_seconds','max_resends','dack_seconds','tic_seconds','pending_threshold','flow_threshold_max','policy','scope']
STATE_COLUMNS = ['case_id','step','time_s','action','packet','accepted','nsdp_relay','nsdp_local','nwk_waiting','nwk_owned','hop_pending','hop_outstanding','hop_resend','hop_holds','rx_highest','rx_ack_hex','rx_dack_hex','ack_generated','dack_generated','rx_received','rx_delivered','rx_duplicates','nsdp_releases','ack_completed','dack_completed','dack_expired','data_tx']
FEEDBACK_COLUMNS = ['case_id','step','time_s','kind','sequence','ack_hex','dack_hex','relay_nsdp','local_nsdp','nwk_owned']
CASES = [
 ('relay_boundary','Unique relay DATA crosses pre-enqueue NSDP fifteen and sixteen.'),
 ('local_relay_independence','Local sixteen-owner quota remains separate from relay pressure.'),
 ('ack_duplicate','ACK-marked replay retains one custody owner.'),
 ('dack_duplicate_pressure','DACK-marked replay under pressure exposes native and MATLAB custody semantics.'),
 ('dack_reassessment_after_release','Three downstream ACKs reduce pressure before a DACK-marked replay.'),
 ('release_idempotence','Repeated downstream ACK and DACK cannot release the same owner twice.'),
 ('local_delivery_bypass','Locally addressed DATA remains ACK eligible while relay pressure is high.')]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_csv(path, columns, rows):
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)

def generate(root=ROOT):
    directory=root/'scenarios/t23'; directory.mkdir(parents=True,exist_ok=True)
    actions=[]; cases=[]; common=[]; native=[]
    for name,scope in CASES:
        case=dict(zip(CASE_COLUMNS,[name,2,2,20,'2.7777777777777778e-08',16,16,'actual-tx',scope]))
        cases.append(case); sequence=[]
        def add(action,packet='',number=0,source=0,destination=1,acks='',dacks='',note='',time=None):
            step=len(sequence)+1
            when=Decimal('0.1')+Decimal('0.01')*(step-1) if time is None else Decimal(time)
            sequence.append(dict(zip(ACTION_COLUMNS,[name,step,str(when),str(when+Decimal('0.000001')),action,packet,number,source,destination,acks,dacks,note])))
        def relay(count=17):
            for index in range(1,count+1): add('RX',f'r{index:02}',index,7)
        def milestone(step,**values): common.append({'case_id':name,'step':step,'equals':values})
        if name=='relay_boundary':
            relay(); milestone(15,nsdp_relay=15,nsdp_local=0,nwk_owned=15,ack_generated=15,dack_generated=0)
            milestone(16,nsdp_relay=16,nwk_owned=16,ack_generated=16,dack_generated=0)
            milestone(17,nsdp_relay=17,nwk_owned=17,ack_generated=16,dack_generated=1)
        elif name=='local_relay_independence':
            for index in range(1,18): add('LOCAL',f'l{index:02}',0,8)
            milestone(16,accepted=1,nsdp_local=16,nsdp_relay=0,nwk_owned=16)
            milestone(17,accepted=0,nsdp_local=16,nsdp_relay=0,nwk_owned=16)
            relay(); milestone(33,nsdp_local=16,nsdp_relay=16,nwk_owned=32,ack_generated=16,dack_generated=0)
            milestone(34,nsdp_local=16,nsdp_relay=17,nwk_owned=33,ack_generated=16,dack_generated=1)
        elif name=='ack_duplicate':
            relay(1); add('RX','r01',1,7,note='Same application and incoming HOP sequence.')
            milestone(2,nsdp_relay=1,nwk_owned=1,ack_generated=2,dack_generated=0,rx_delivered=1)
        elif name=='dack_duplicate_pressure':
            relay(); add('RX','r17',17,7,note='DACK-marked replay is reassessed; do not normalize duplicate custody.')
            milestone(17,nsdp_relay=17,nwk_owned=17,ack_generated=16,dack_generated=1)
            milestone(18,ack_generated=16,dack_generated=2,rx_delivered=18)
            native.append({'case_id':name,'step':18,'equals':{'nsdp_relay':18,'nwk_owned':18}})
        elif name=='dack_reassessment_after_release':
            relay()
            for number in (1,2,3):
                add('TX',number=number); add('FEEDBACK',acks=str(number))
            milestone(23,nsdp_relay=14,nwk_owned=14,nsdp_releases=3,ack_completed=3)
            add('RX','r17',17,7,note='Replay after pressure drains uses pre-enqueue count fourteen.')
            milestone(24,ack_generated=17,dack_generated=1,rx_delivered=18,nsdp_releases=3)
            native.append({'case_id':name,'step':24,'equals':{'nsdp_relay':15,'nwk_owned':15}})
        elif name=='release_idempotence':
            add('LOCAL','l01',source=8); add('LOCAL','l02',source=8)
            add('TX',number=1); add('FEEDBACK',acks='1'); add('FEEDBACK',acks='1')
            milestone(4,nsdp_local=1,nwk_owned=1,nsdp_releases=1,ack_completed=1,hop_holds=0)
            milestone(5,nsdp_local=1,nwk_owned=1,nsdp_releases=1,ack_completed=1,hop_holds=0)
            add('TX',number=2); add('FEEDBACK',dacks='2'); add('FEEDBACK',dacks='2')
            milestone(8,nsdp_local=0,nwk_owned=0,nsdp_releases=2,ack_completed=1,dack_completed=1,hop_holds=1)
            add('PROBE',time='20.17',note='Observe after ordinary delayed DACK capacity release.')
            milestone(9,nsdp_local=0,nwk_owned=0,nsdp_releases=2,hop_pending=0,hop_holds=0,dack_expired=1)
        elif name=='local_delivery_bypass':
            relay(); add('RX','to8',18,7,8); add('RX','to8',18,7,8)
            milestone(18,nsdp_relay=17,nwk_owned=17,ack_generated=17,dack_generated=1)
            milestone(19,nsdp_relay=17,nwk_owned=17,ack_generated=18,dack_generated=1)
        actions.extend(sequence)
    write_csv(directory/'actions.csv',ACTION_COLUMNS,actions)
    write_csv(directory/'cases.csv',CASE_COLUMNS,cases)
    contract={'schema':'csr-tranche23-receiver-feedback-contract-v1','case_count':len(cases),'action_count':len(actions),'action_columns':ACTION_COLUMNS,'configuration_columns':CASE_COLUMNS,'state_columns':STATE_COLUMNS,'feedback_columns':FEEDBACK_COLUMNS,'comparison':{'integer_tolerance':0,'time_absolute_tolerance_seconds':'1e-9','campus_percent_target_applies':False},'milestones':common,'native_milestones':native,'input_hashes':{name:digest(directory/name) for name in ['actions.csv','cases.csv']},'semantics':{'observation':'Action at time_s; drain callbacks through observe_s one microsecond later; checkpoint time_s is observe_s. No same-tick wake-order parity claim.','feedback':'Capture actual MAC-enqueued ACK/DACK frames; bitmaps are exact uppercase sixteen-digit hexadecimal strings.','duplicates':'Reused RX alias means the same application identity and incoming HOP sequence. Never normalize custody differences.','completion':'Intact diagnostic differences are review-required, not cross-engine acceptance. Source, membership, invariant or test failures remain blocking.'}}
    (directory/'contract.json').write_text(json.dumps(contract,indent=2)+'\n')
    plan={'schema':'csr-tranche23-receiver-feedback-plan-v1','tranche':23,'source_commit':'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b','engine_commit':'6b5cd24ea80713ce16d88575869aedd6f432bdae','case_order':[x[0] for x in CASES],'case_count':len(cases),'action_count':len(actions),'checkpoint_count':len(actions),'milestone_count':len(common),'native_milestone_count':len(native),'timing_policy':'continuous','default_policy':'actual-tx','working_campus_band_percent':10,'production_source_changed':False,'phy_ecc_changed':False,'full_campus_run':False,'native_reference':'evidence/t23/native','action_columns':ACTION_COLUMNS,'configuration_columns':CASE_COLUMNS,'state_columns':STATE_COLUMNS,'feedback_columns':FEEDBACK_COLUMNS,'comparison':contract['comparison'],'input_files':[]}
    for stem in ['cases','actions','contract']:
        name=stem+('.json' if stem=='contract' else '.csv'); rel='scenarios/t23/'+name
        plan[stem+'_file']=rel;plan[stem+'_sha256']=digest(directory/name)
        plan['input_files'].append({'path':rel,'sha256':digest(directory/name)})
    (directory/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps({'cases':len(cases),'actions':len(actions),'common_milestones':len(common),'common_assertions':sum(len(x['equals']) for x in common),'native_milestones':len(native)}))

if __name__=='__main__': generate()
