#!/usr/bin/env python3
"""Execute the pinned native discovery controller at a controlled transport boundary.

Requires an already built Debug ns-3 engine at the frozen commit. The engine
build is independent of these fixtures; no production source is patched. GCC's
-fno-access-control grants this diagnostic translation unit access to private
read-only state and to the actual receive-SNMP entry point. A bare native MAC
(with no attached device) accepts queued frames and its existing null-device
check prevents physical transmission. No responses are synthesized except the
explicit input DONE events in the frozen plan.
"""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time

SOURCE_PIN='486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
ENGINE_PIN='6b5cd24ea80713ce16d88575869aedd6f432bdae'
SOURCE_TREE='b611b233fb369569b98f0914ece24d029ccc2f42'
ENGINE_TREE='f30343185fb057e3a9cdd54f496cca0cef49ae23'
CASE_IDS=['C0','C1','C2','C3_match','C3_timeout']
MODULES=['csr','spectrum','buildings','propagation','mobility','antenna','network','stats','core']

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def write(path,value):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def require(ok,message):
    if not ok:raise ValueError(message)

def tracked(expected,source,engine):
    for kind,folder in [('source',source),('engine',engine)]:
        for name,want in expected[kind]['file_sha256'].items():
            p=folder/name
            got=hashlib.sha256(str(p.readlink()).encode()).hexdigest() if p.is_symlink() else sha(p)
            require(got==want,'Pinned tracked file changed: '+kind+'/'+name)
    return {k:{'file_count':len(expected[k]['file_sha256']),'all_tracked_files_verified':True} for k in ('source','engine')}

def generate_header(plan,path):
    rows=['// Generated exactly from evidence/tranche-27-plan.json.','const std::vector<CaseConfig> kCases = {']
    require([c['id'] for c in plan['cases']]==CASE_IDS,'Wrong case IDs')
    for c in plan['cases']:
        row='{'+json.dumps(c['id'])+',{'+','.join(map(str,c['initial_peers']))+'},'
        row+=','.join(str(c[k] or 0) for k in ('done_source','late_peer','done_time_s','late_peer_time_s','local_duration_s','stop_s'))
        row+=',{'+','.join(map(repr,c['checkpoints_s']))+'}},'
        rows.append(row)
    rows.append('};')
    path.write_text('\n'.join(rows)+'\n')

def execute(argv,path):
    start=time.monotonic()
    with path.open('wb') as f:result=subprocess.run(list(map(str,argv)),stdout=f,stderr=subprocess.STDOUT)
    record={'argv':list(map(str,argv)),'exit_code':result.returncode,'wall_seconds':time.monotonic()-start,'log':path.name,'log_sha256':sha(path)}
    require(result.returncode==0,'Native command failed: '+str(path))
    return record

def validate_cases(output,plan):
    # Native source-exact controller assertions. These do not assert MATLAB
    # equality; the return review reports any cross-engine differences.
    expected={'C0':[(.1,5),(60.1,3)],'C1':[(.1,3)],'C2':[(.1,4),(1.,5)],'C3_match':[(.1,4),(1.,5),(61.,3)],'C3_timeout':[(.1,4),(60.1,5)]}
    checks=[];cases={}
    for c in plan['cases']:
        name=c['id'];a=json.loads((output/(name+'.json')).read_text());b=json.loads((output/'observer-off'/(name+'.json')).read_text())
        require(a['controls']==b['controls'],'Observer altered native controls: '+name)
        ac=[s for s in a['states'] if s['event']=='checkpoint'];bc=[s for s in b['states'] if s['event']=='checkpoint']
        require(ac==bc,'Observer altered native checkpoint states: '+name)
        require(len(ac)==len(c['checkpoints_s']) and all(abs(s['time_s']-t)<1e-12 for s,t in zip(ac,c['checkpoints_s'])),'Checkpoint schedule mismatch: '+name)
        require([(x['time_s'],x['final_destination']) for x in a['controls']]==expected[name],'Native controller outcome differs: '+name)
        require(len(a['pre_send'])==len(a['controls']) and all(s['requested_before_send'] for s in a['pre_send']),'Target not marked before send: '+name)
        require(a['maximum_mac_queue']<512 and a['mac_data_queue_drops']==0,'Fixture transport capacity exceeded: '+name)
        for x in a['controls']:
            require(x['source']==1 and x['command']=='START' and x['sequence']==0 and x['dscp']==0 and x['ackable'] is False and x['send_result'] is True and x['next_hop']==x['final_destination'] and x['advertised_nodes']==[],'Unexpected native wire/control field: '+name)
        require(a['states'][-1]['time_s']==c['stop_s'],'Incorrect stop time: '+name)
        checks.append({'case_id':name,'observer_controls_identical':True,'observer_checkpoints_identical':True,'checkpoints_verified':len(ac),'controller_assertions_passed':True,'pre_send_marks_verified':len(a['pre_send']),'mac_queue_drops':0})
        control_path=output/'cases'/name/'controls.csv';control_path.parent.mkdir(parents=True,exist_ok=True)
        fields=['case_id','order','time_s','command','source','final_destination','next_hop','ackable','send_result','advertised_nodes']
        with control_path.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
            for order,x in enumerate(a['controls'],1):
                row={key:x[key] for key in fields if key in x}
                row.update(case_id=name,order=order,ackable=int(x['ackable']),send_result=int(x['send_result']),advertised_nodes=json.dumps(x['advertised_nodes'],separators=(',',':')))
                writer.writerow(row)
        cases[name]={'file':name+'.json','sha256':sha(output/(name+'.json')),'controls':len(a['controls']),'checkpoint_count':len(ac),'controls_csv':str(control_path.relative_to(output)),'controls_csv_sha256':sha(control_path)}
    return checks,cases

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True,help='Issued MATLAB candidate root')
    parser.add_argument('--native-source',type=Path,required=True,help='Pinned untouched CSR ns-3 source checkout')
    parser.add_argument('--engine-root',type=Path,required=True,help='Pinned ns-3 engine with Debug libraries already built')
    parser.add_argument('--build-dir',type=Path,required=True,help='Separate disposable fixture compilation directory')
    parser.add_argument('--output',type=Path,required=True,help='New closed native reference directory')
    parser.add_argument('--compiler',default='g++')
    args=parser.parse_args();root=args.source_root.resolve();source=args.native_source.resolve();engine=args.engine_root.resolve();build=args.build_dir.resolve();out=args.output.resolve()
    require(not out.exists() or not any(out.iterdir()),'Output must be new or empty')
    require(not build.exists() or not any(build.iterdir()),'Fixture build directory must be new or empty')
    build.mkdir(parents=True,exist_ok=True);out.mkdir(parents=True,exist_ok=True)
    pp=root/'evidence/tranche-27-plan.json';plan=json.loads(pp.read_text())
    require(plan['local_node']==1 and plan['local_role']=='gateway' and plan['peer_capability']==1,'Fixture setup differs from native harness contract')
    expected_path=root/'evidence/tranche-25-ns3-reference/build-provenance/tracked-source-verification.json';expected=json.loads(expected_path.read_text())
    before=tracked(expected,source,engine)
    # Verify the generated build include bindings lead to the pinned CSR input.
    headers={}
    for p in sorted((source/'model').glob('*')):
        if p.is_file():
            if p.suffix=='.h':
                binding=engine/'build/include/ns3'/p.name
                if sha(binding)!=sha(p):
                    # ns-3 CMake exports generated forwarding headers.
                    text=binding.read_text().strip()
                    require(text=='#include "'+str(p)+'"' or text=='#include "'+str(engine/'contrib/csr/model'/p.name)+'"','Build uses another CSR header: '+p.name)
                    require((engine/'contrib/csr/model'/p.name).resolve()==p.resolve(),'Incorrect CSR contrib binding')
            headers['model/'+p.name]=sha(p)
    harness=root/'scripts/ns3/tranche27_discovery_controller.cc';shutil.copy2(harness,build/'tranche27_discovery_controller.cc')
    generate_header(plan,build/'tranche27-plan.generated.h');shutil.copy2(pp,out/'plan.json');shutil.copy2(build/'tranche27-plan.generated.h',out/'plan.generated.h')
    compiler=Path(shutil.which(args.compiler) or args.compiler).resolve();library=engine/'build/lib';binary=build/'tranche27-native-controller'
    argv=[compiler,'-std=c++23','-g','-fno-access-control','-DNS3_ASSERT_ENABLE','-DNS3_BUILD_PROFILE_DEBUG','-DNS3_LOG_ENABLE','-DSTACKTRACE_LIBRARY_IS_LINKED=1','-D__LINUX__','-I'+str(engine/'build/include'),build/'tranche27_discovery_controller.cc','-L'+str(library),'-Wl,-rpath,'+str(library),'-Wl,--no-as-needed',*[f'-lns3-dev-{m}-debug' for m in MODULES],'-Wl,--as-needed','-lstdc++exp','-o',binary]
    compile_record=execute(argv,out/'compile.log')
    require(binary.read_bytes()[:4]==b'\x7fELF','Native fixture is not ELF')
    ldd=execute(['ldd','-r',binary],out/'ldd.log');require('not found' not in (out/'ldd.log').read_text() and 'undefined symbol' not in (out/'ldd.log').read_text(),'Unresolved native symbol')
    observed=execute([binary,out,'1'],out/'observed-run.log')
    (out/'observer-off').mkdir();unobserved=execute([binary,out/'observer-off','0'],out/'unobserved-run.log')
    checks,cases=validate_cases(out,plan);after=tracked(expected,source,engine);require(before==after,'Native source changed during execution')
    libs={}
    for m in MODULES:
        p=library/f'libns3-dev-{m}-debug.so';require(p.read_bytes()[:4]==b'\x7fELF','Invalid library: '+p.name)
        libs[p.name]={'bytes':p.stat().st_size,'sha256':sha(p)}
    verification={'schema':'csr-tranche27-native-tracked-verification-v1','before':before,'after':after,'original_tracked_manifest_sha256':sha(expected_path),'source_used_model_files_sha256':headers,'source_unchanged':True,'engine_unchanged':True}
    write(out/'tracked-verification.json',verification);write(out/'validation.json',{'schema':'csr-tranche27-native-validation-v1','status':'passed','checks':checks,'observer_on_off_identical':True})
    build_record={'schema':'csr-tranche27-native-build-v1','status':'passed','source_pin':SOURCE_PIN,'engine_pin':ENGINE_PIN,'source_tree':SOURCE_TREE,'engine_tree':ENGINE_TREE,'native_executed':True,'matlab_executed':False,'production_source_unchanged':True,'engine_source_unchanged':True,'new_compilation':True,'fresh_engine_build_claimed':False,'test_seam':{'compiler_flag':'-fno-access-control','source_edits':False,'private_input_entry':'ReceiveSnmpFromHop','private_state_reads':True,'transport':'Unmodified CsrNetLayer + CsrHopLayer + bare CsrMacCore; null device prevents physical transmission','control_send_result':'True means native NWK call completed and real SNMP frame retained in MAC queue; it is not delivery','native_pending_target':'Derived from last queued START while native report event remains pending','native_watchdog_generation':'Observed count of changed native report EventId UIDs','observations_do_not_schedule_events':True,'no_phy':True,'no_campus':True},'harness_sha256':sha(harness),'generated_plan_header_sha256':sha(out/'plan.generated.h'),'plan_sha256':sha(pp),'runner_sha256':sha(Path(__file__)),'binary_sha256':sha(binary),'compile':compile_record,'ldd':ldd,'runs':{'observed':observed,'unobserved':unobserved},'libraries':libs,'compiler':{'path':str(compiler),'sha256':sha(compiler),'version':subprocess.check_output([compiler,'--version'],text=True).strip()},'platform':platform.platform(),'tracked_verification':'tracked-verification.json','tracked_verification_sha256':sha(out/'tracked-verification.json'),'recorded_utc':datetime.now(timezone.utc).isoformat()}
    write(out/'build.json',build_record)
    summary={'schema':'csr-tranche27-native-reference-v1','status':'passed','source_pin':SOURCE_PIN,'engine_pin':ENGINE_PIN,'native_executed':True,'matlab_executed':False,'production_source_unchanged':True,'engine_source_unchanged':True,'observer_on_off_identical':True,'fixture_count':4,'execution_count':5,'case_ids':CASE_IDS,'plan_sha256':sha(pp),'build_manifest':'build.json','build_manifest_sha256':sha(out/'build.json'),'validation_file':'validation.json','validation_sha256':sha(out/'validation.json'),'cases':cases,'scope':'Deterministic controller characterization only; not seed-131 causality or campus parity.'}
    write(out/'summary.json',summary)
    write(out/'manifest.json',{'schema':'csr-tranche27-native-files-v1','files':{str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='manifest.json'}})
    print(json.dumps({'status':'passed','fixture_count':4,'execution_count':5,'observer_on_off_identical':True,'summary_sha256':sha(out/'summary.json')},indent=2))
if __name__=='__main__':main()
