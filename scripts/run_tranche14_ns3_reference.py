#!/usr/bin/env python3
"""Run the fixed T14 DATA/ACK boundary fixture on a fresh verified native build.

The T12 overlay is copied unchanged. All prior source files remain immutable.
Clean/disabled control runs demonstrate the empty hooks preserve native behavior.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
from build_tranche12_overlay import build as build_overlay
from run_tranche4_ns3_reference import MODULES, PIN, check_source, compile_runner
ENGINE='6b5cd24ea80713ce16d88575869aedd6f432bdae'
PLAN_SHA256='7e7ec33e946cb1fb315b0990813a2102d18c64b6f966b46cee021f8f273b61b9'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    with p.open(newline='') as f:
        reader=csv.DictReader(f); fields=reader.fieldnames
        if not fields or len(fields)!=len(set(fields)): raise ValueError('Missing/duplicate CSV header')
        rows=list(reader)
        if any(None in r or any(v is None for v in r.values()) for r in rows): raise ValueError('Invalid CSV width')
        return rows
def write(p,fields,rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)
def execute(argv,log,timeout=180):
    begin=time.monotonic();r=subprocess.run([str(x) for x in argv],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=timeout);log.write_bytes(r.stdout)
    if r.returncode: raise RuntimeError(f'Command failed ({r.returncode}): {log}')
    return {'argv':[str(x) for x in argv],'exit_code':r.returncode,'wall_seconds':time.monotonic()-begin,'log_sha256':sha(log)}
def validate_inputs(p):
    if sha(p/'plan.json')!=PLAN_SHA256: raise ValueError('Unsupported edge plan hash')
    plan=json.loads((p/'plan.json').read_text());names=['tie_early','tie_late','before','after','continuous','quantized']
    if plan['cases']!=names or plan['source_pin']!=PIN or plan['engine_pin']!=ENGINE: raise ValueError('Unsupported source/engine/cases')
    cases=[{'case':n,'mode':'continuous' if n=='continuous' else 'local_ns' if n=='quantized' else 'target','offset_ns':str(-1 if n=='before' else 1 if n=='after' else 0),'late_insertion':str(int(n=='tie_late'))} for n in names]
    if read(p/'cases.csv')!=cases: raise ValueError('Changed boundary mode/order/offset')
    draws=[{'case':n,'node':str(node),'ordinal':str(i),'min':'0','max':'31','draw':'0'} for n in names for node in (1,4,5) for i in range(1,65)]
    if read(p/'draws.csv')!=draws: raise ValueError('Changed full raw tape')
    return plan
def canonical_draws(folder,plan):
    native=read(folder/'native.csv'); purposes={}
    for r in native:
        if r['event']=='reservation_advertise': purpose='advertise'
        elif r['event']=='reservation_prepare' and r['reason']=='new': purpose='prepare'
        else: continue
        t=str(int((Decimal(r['time_s'])*1000000000).to_integral_value()))
        purposes.setdefault((r['node'],t),[]).append((purpose,r['reservation_slot']))
    out=[]
    for r in read(folder/'raw.csv'):
        key=(r['node'],r['time_ns'])
        if not purposes.get(key): raise ValueError('Raw draw missing native purpose')
        purpose,resolved=purposes[key].pop(0)
        if resolved!=r['resolved']: raise ValueError('Raw resolution differs from native trace')
        out.append({k:r[k] for k in plan['draws_output_schema'] if k!='purpose'}|{'purpose':purpose})
    if any(purposes.values()): raise ValueError('Unmatched native reservation purpose')
    return out

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for n in ('source','build','work','output'):parser.add_argument('--'+n,type=Path,required=True)
    parser.add_argument('--compiler',default='/usr/bin/g++');a=parser.parse_args();source,build,work,output=[getattr(a,n).resolve() for n in ('source','build','work','output')]
    root=Path(__file__).resolve().parent.parent;inputs=root/'scenarios/edge';plan=validate_inputs(inputs);check_source(source,build)
    native_build=root/'evidence/tranche-14-native-build.json';baseline=json.loads(native_build.read_text())
    if baseline['source_commit']!=PIN or baseline['engine_commit']!=ENGINE or baseline['status'] not in ('built-controls-pending','passed'):raise ValueError('Unverified native build source')
    actual_engine=subprocess.check_output(['git','-C',str(build.parent),'rev-parse','HEAD'],text=True).strip()
    if actual_engine!=ENGINE:raise ValueError('Engine checkout mismatch')
    if subprocess.check_output(['git','-C',str(build.parent),'status','--porcelain','--untracked-files=no'],text=True).strip():raise ValueError('Tracked engine changed')
    libraries={n:sha(build/'lib'/f'libns3-dev-{n}-debug.so') for n in MODULES}
    if libraries!={Path(r['path']).name.removeprefix('libns3-dev-').removesuffix('-debug.so'):r['sha256'] for r in baseline['libraries']}:raise ValueError('Native build libraries changed')
    models={p.name:sha(p) for p in (source/'model').glob('csr-*') if p.is_file()}
    for p in (work,output):
        if p.exists() and any(p.iterdir()):raise ValueError(f'Use empty directory {p}')
        p.mkdir(parents=True,exist_ok=True)
    overlay=work/'overlay';overlay_info=build_overlay(source,overlay);controls=output/'controls';controls.mkdir();records=[]
    def compile_one(task):
        label,filename,use_overlay=task;cmd=compile_runner(source,build,work/label,a.compiler);cmd[cmd.index(str(source/'csr-opnet-scenario-runner.cc'))]=str(root/'scripts/ns3'/filename)
        # Link every declared module: spectrum references building type metadata.
        # This changes dependency retention only, never model source or callbacks.
        cmd.remove('-Wl,--as-needed')
        if use_overlay:cmd.insert(1,'-I'+str(overlay))
        rec=execute(cmd,controls/(label+'-build.log'),300);rec['binary_sha256']=sha(work/label);return rec
    tasks=[('ack-clean','tranche9_ack_contract.cc',False),('ack-off','tranche9_ack_contract.cc',True),('receiver-clean','tranche10_receiver_contract.cc',False),('receiver-off','tranche10_receiver_contract.cc',True),('clock-clean','tranche12_clock.cc',False),('clock-off','tranche12_clock.cc',True),('edge','tranche14_edge.cc',True)]
    with ThreadPoolExecutor(max_workers=2) as pool:records.extend(pool.map(compile_one,tasks))
    control_results={}
    for label,count in [('ack',101),('receiver',154),('clock',72)]:
        for mode in ('clean','off'):
            p=controls/(label+'-'+mode)
            if label=='clock':p.mkdir();arg=p
            else:arg=p.with_suffix('.csv')
            records.append(execute([work/(label+'-'+mode),arg],controls/(label+'-'+mode+'.log')))
        if label=='clock':
            clean=controls/'clock-clean/checks.csv';off=controls/'clock-off/checks.csv';same=(controls/'clock-clean/events.csv').read_bytes()==(controls/'clock-off/events.csv').read_bytes()
        else:clean=controls/(label+'-clean.csv');off=controls/(label+'-off.csv');same=True
        rows=read(clean)
        if len(rows)!=count or any(r['pass']!='1' for r in rows) or clean.read_bytes()!=off.read_bytes() or not same:raise ValueError('Disabled overlay changed '+label+' controls')
        control_results[label]={'checks':count,'passed':True,'clean_and_disabled_byte_equal':True,'sha256':sha(clean)}
    records.append(execute([work/'edge','--self-test'],controls/'self-test.log'))
    if (controls/'self-test.log').read_text().strip()!='EDGE_SELF_TEST checks=14 failed=0':raise ValueError('Missing edge self-tests')
    records.append(execute([work/'edge',inputs/'cases.csv',inputs/'draws.csv',output/'raw'],output/'run.log'))
    all_events=[];all_boundaries=[];all_checks=[];all_draws=[];all_usage=[];results=[]
    for name in plan['cases']:
        folder=output/'raw'/name;events=read(folder/'events.csv');boundary=read(folder/'boundary.csv');checks=read(folder/'checks.csv');usage=read(folder/'usage.csv');draws=canonical_draws(folder,plan)
        for rows,schema in [(events,plan['events_schema']),(boundary,plan['boundary_schema']),(checks,plan['checks_schema']),(draws,plan['draws_output_schema']),(usage,plan['usage_schema'])]:
            if not rows or list(rows[0])!=schema:raise ValueError('Native schema mismatch')
        if len(boundary)!=1 or len(checks)!=37 or any(r['pass']!='1' for r in checks):raise ValueError('Native checks incomplete')
        ids=[r['app_id'] for r in events if r['phase']=='deliver'];acks=[r for r in events if r['phase']=='ack_tx'];expected_first='3' if name in ('tie_late','after') else '7'
        if ids!=['1','2','3'] or acks[0]['ack_bits']!=expected_first or acks[-1]['ack_bits']!='7':raise ValueError('Native delivery/feedback structural mismatch')
        if any(int(r['consumed'])+int(r['unused'])!=64 for r in usage) or sum(int(r['consumed']) for r in usage)!=len(draws):raise ValueError('Draw usage mismatch')
        all_events+=events;all_boundaries+=boundary;all_checks+=checks;all_draws+=draws;all_usage+=usage;results.append({'case':name,'events':len(events),'checks':len(checks),'draws':len(draws),'delivered':len(ids),'gateway_ack_transmissions':len(acks),'first_ack_sequence':int(acks[0]['hop_seq']),'first_ack_bits':acks[0]['ack_bits'],'last_ack_bits':acks[-1]['ack_bits'],'ingress_event_id':boundary[0]['ingress_event_id'],'structural_passed':True})
    for filename,schema,rows in [('events.csv',plan['events_schema'],all_events),('boundary.csv',plan['boundary_schema'],all_boundaries),('checks.csv',plan['checks_schema'],all_checks),('draws.csv',plan['draws_output_schema'],all_draws),('usage.csv',plan['usage_schema'],all_usage)]:write(output/filename,schema,rows)
    check_source(source,build)
    if libraries!={n:sha(build/'lib'/f'libns3-dev-{n}-debug.so') for n in MODULES} or models!={p.name:sha(p) for p in (source/'model').glob('csr-*') if p.is_file()}:raise ValueError('Native source/build changed during run')
    baseline['status']='passed';baseline['controls']={k:v for k,v in control_results.items()};baseline['control_artifact_location']='evidence/tranche-14-edge-reference/controls';baseline['native_control_checks']=sum(r['checks'] for r in control_results.values());native_build.write_text(json.dumps(baseline,indent=2)+'\n')
    for n in ('seams.patch','overlay.json'):shutil.copy2(overlay/n,output/n)
    fixtures=[Path(__file__).resolve(),root/'scripts/run_tranche4_ns3_reference.py',root/'scripts/build_tranche12_overlay.py',*[root/'scripts/ns3'/n for n in ('tranche14_edge.cc','tranche12-relay-hooks.h','tranche9_ack_contract.cc','tranche10_receiver_contract.cc','tranche12_clock.cc')]]
    summary={'schema':'csr-tranche14-edge-native-v1','status':'passed','generated_utc':datetime.now(timezone.utc).isoformat(),'source_pin':PIN,'engine_pin':ENGINE,'case_count':6,'event_count':len(all_events),'checkpoint_count':len(all_checks),'draw_count':len(all_draws),'boundary_count':len(all_boundaries),'failed_count':0,'cases':results,'controls':control_results,'self_tests':{'checks':14,'failed':0},'native_build_manifest':'evidence/tranche-14-native-build.json','native_build_manifest_sha256':sha(native_build),'shared_libraries':libraries,'model_sources':models,'fixture_sources':{str(p.relative_to(root)):sha(p) for p in fixtures},'input_bindings':{str(p.relative_to(root)):sha(p) for p in sorted(inputs.iterdir()) if p.is_file()},'overlay':overlay_info,'commands':records,'native_executed':True,'matlab_executed':False,'production_source_unchanged':True,'engine_source_unchanged':True,'global_scheduler_changed':False,'native_current_callback_ids':'zero means unavailable; boundary ingress_event_id is actual EventId.GetUid','native_time_resolution':'integer nanoseconds','scope':plan['scope'],'numerical_parity_established':False,'full_network_acceptance_established':False}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');manifest={'schema':'csr-tranche14-edge-reference-files-v1','files':{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file() and p.name!='manifest.json'}};(output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'status':'passed','checks':len(all_checks),'events':len(all_events),'draws':len(all_draws),'control_checks':baseline['native_control_checks'],'manifest_sha256':sha(output/'manifest.json')}))
if __name__=='__main__':main()
