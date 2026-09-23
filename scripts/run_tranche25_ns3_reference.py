#!/usr/bin/env python3
"""Run untouched pinned full-campus native seeds 131/132 after a seed-129 control.

The recovered source/engine trees and rebuilt pristine executable are verified
before any run. The control must reproduce the accepted T20 complete trace,
admission diagnostics, aggregate values, and unique-application metrics exactly.
Only the canonical run.seed changes in the new reference scenarios.
"""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,shutil,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import run_tranche7_ns3_reference as T7
import run_tranche8_ns3_diagnostics as T8
import run_tranche20_ns3_reference as T20
import tranche20_native_metrics as metrics

PIN='486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
ENGINE='6b5cd24ea80713ce16d88575869aedd6f432bdae'
CASE_FILES=('app-admission-diagnostics.csv','execution-stages.json','native-applications.json',
            'ns3-aggregate.log','ns3-aggregates.csv','ns3-aggregates.provenance.json',
            'ns3-benchmark.provenance.json','ns3-run.log','ns3-trace.csv.gz',
            'scenario.csv','seed-recipe.json')

def require(value,message):
    if not value:raise ValueError(message)
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def load(path):return json.loads(Path(path).read_text())
def case_files(directory):
    actual={p.name for p in directory.iterdir() if p.is_file() and not p.name.startswith('.') and p.name!='manifest.json'}
    require(actual==set(CASE_FILES),'Native case must contain exactly its canonical completed artifacts')
    return [{'path':name,'sha256':digest(directory/name),'bytes':(directory/name).stat().st_size} for name in CASE_FILES]
def suite_files(out):
    return [{'path':str(p.relative_to(out)),'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(out.rglob('*')) if p.is_file() and not any(part.startswith('.') for part in p.relative_to(out).parts) and p!=out/'manifest.json']
def source_verification(env,build):
    receipt=env/build['tracked_source_verification']
    require(digest(receipt)==build['tracked_source_verification_sha256'],'Tracked source receipt changed')
    tracked=load(receipt)
    for kind,folder in [('source',env/'csr'),('engine',env/'engine')]:
        require(tracked[kind]['all_archive_bytes_match'],'Incomplete archived source verification')
        for name,expected in tracked[kind]['file_sha256'].items():
            path=folder/name
            actual=hashlib.sha256(str(path.readlink()).encode()).hexdigest() if path.is_symlink() else digest(path)
            require(actual==expected,'Native tracked source changed: '+name)
    return {'source_files':tracked['source']['file_count'],'engine_files':tracked['engine']['file_count'],'all_tracked_files_verified':True}
def verify_environment(env):
    build=load(env/'build.json')
    require(build['schema']=='csr-tranche25-native-build-v1' and build['status']=='passed' and build['ns3_source_commit']==PIN and build['engine_commit']==ENGINE,'Incorrect or incomplete native build')
    require(build['observer_enabled'] is False and build['production_source_unchanged'] and build['engine_source_unchanged'],'Modified native source not allowed')
    require(build['source_tree']=='b611b233fb369569b98f0914ece24d029ccc2f42' and build['engine_tree']=='f30343185fb057e3a9cdd54f496cca0cef49ae23','Native tree pin mismatch')
    require(digest(env/'t25-pristine')==build['runner_sha256'],'Native binary changed')
    for name,rec in build['libraries'].items():
        require(digest(env/'engine/build/lib'/name)==rec['sha256'],'Native library changed: '+name)
    source_verification(env,build)
    require(digest(env/'csr/utils/aggregate-ns3-trace.py')==metrics.PINNED_HELPER_SHA256,'Native upstream aggregator changed')
    return build
def run_case(env,out,seed,build,build_path,workflow):
    directory=out/f's{seed}';directory.mkdir()
    scenario=directory/'scenario.csv'
    recipe=T20.seed_scenario(ROOT/'scenarios/benchmarks/campus_multihop_6000.csv',scenario,seed)
    write(directory/'seed-recipe.json',recipe)
    case={'case_id':f's{seed}','scenario':'blue_radio_campus-multihop','seed':seed,'duration_s':6000,'bucket_width_s':60,'profile_id':'hist-adb97c54-bare','source_kind':'archived_opnet_seed_override','scenario_sha256':digest(scenario)}
    parsed=workflow.load_scenario_run(scenario)
    require(parsed['seed']==seed and parsed['duration_s']==6000,'Scenario identity mismatch')
    command=T8.runner_command(env/'t25-pristine',scenario,case,directory)
    command[command.index('--aggregateTraceOnly=1')]='--aggregateTraceOnly=0'
    command.append('--admissionTrace=1')
    print(f'Running unchanged native full campus seed {seed}',flush=True)
    run=T7.run_stage(command,directory/'ns3-run.log',2400)
    write(directory/'execution-stages.json',{'run_ns3':run})
    require(run['exit_code']==0,'Native campus execution failed')
    command=[sys.executable,'-B','-I',str(env/'csr/utils/aggregate-ns3-trace.py'),str(directory/'ns3-trace.csv'),str(directory/'ns3-aggregates.csv'),'--scenario',case['scenario'],'--bucket-width','60','--stop-time','6000','--legacy-trace-size-exclusion-bits','0','--require-zero-size-mismatches','--provenance',str(directory/'ns3-aggregates.provenance.json')]
    aggregate=T7.run_stage(command,directory/'ns3-aggregate.log',2400)
    write(directory/'execution-stages.json',{'run_ns3':run,'aggregate_ns3':aggregate})
    require(aggregate['exit_code']==0,'Native upstream aggregation failed')
    admissions=workflow.validate_app_admission_diagnostics(directory/'app-admission-diagnostics.csv',case['scenario'],parsed['application_profile'],parsed['flows'])
    lineage=workflow._load_and_validate_ns3_provenance(directory/'ns3-aggregates.provenance.json',directory/'ns3-trace.csv',directory/'ns3-aggregates.csv',case['scenario'])
    T7.normalized_sidecar(case,directory,'ns3')
    compressed=T7.compress(directory/'ns3-trace.csv')
    applications=metrics.native_applications(directory)
    write(directory/'native-applications.json',applications)
    verified=source_verification(env,build)
    manifest={'schema':'csr-tranche25-native-reference-v1','status':'completed','case':case,'ns3_source_commit':PIN,'engine_commit':ENGINE,'runner_sha256':digest(env/'t25-pristine'),'build_sha256':digest(build_path),'observer_enabled':False,'stages':{'run_ns3':run,'aggregate_ns3':aggregate},'seed_recipe':recipe,'application_admission_totals':admissions,'exact_sequence_validation':lineage,'compressed_artifacts':[compressed],'source_verification_after_run':verified,'files':case_files(directory)}
    write(directory/'manifest.json',manifest)
    print(f'Completed seed {seed}: {applications["totals"]}',flush=True)
    return manifest
def control_equivalence(accepted,fresh):
    old,new=load(accepted/'ns3-aggregates.provenance.json'),load(fresh/'ns3-aggregates.provenance.json')
    require({k:v for k,v in old['input'].items() if k!='path'}=={k:v for k,v in new['input'].items() if k!='path'},'Seed129 full raw trace changed')
    require((accepted/'app-admission-diagnostics.csv').read_bytes()==(fresh/'app-admission-diagnostics.csv').read_bytes(),'Seed129 admission diagnostics changed')
    require(load(accepted/'native-applications.json')==load(fresh/'native-applications.json'),'Seed129 native unique application metrics changed')
    def aggregate_rows(path):
        with path.open(newline='') as f:return [{k:v for k,v in r.items() if k not in ('source_file','source_file_sha256')} for r in csv.DictReader(f)]
    require(aggregate_rows(accepted/'ns3-aggregates.csv')==aggregate_rows(fresh/'ns3-aggregates.csv'),'Seed129 aggregate statistics changed')
    return {'schema':'csr-tranche25-native-build-control-v1','status':'passed','seed':129,'duration_s':6000,'accepted_manifest_sha256':digest(accepted/'manifest.json'),'fresh_manifest_sha256':digest(fresh/'manifest.json'),'accepted_trace_sha256':digest(accepted/'ns3-trace.csv.gz'),'fresh_trace_sha256':digest(fresh/'ns3-trace.csv.gz'),'uncompressed_trace_identity':{k:v for k,v in new['input'].items() if k!='path'},'full_uncompressed_trace_identical':True,'admission_diagnostics_byte_identical':True,'unique_application_metrics_identical':True,'aggregate_values_identical':True,'scope':'Recovered native environment equivalence only. No new MATLAB seed129 run.'}
def finalize(env,out,control,accepted):
    """Seal only completed canonical files; never rerun a simulation here."""
    verify_environment(env)
    repairs=[]
    for directory in (control/'s129',out/'s131',out/'s132'):
        manifest=load(directory/'manifest.json')
        require(manifest['status']=='completed','Cannot finalize incomplete native case')
        prior={r['path']:r for r in manifest['files']}
        for name in CASE_FILES:
            p=directory/name;r=prior[name]
            require(digest(p)==r['sha256'] and p.stat().st_size==r['bytes'],'Completed native artifact changed: '+str(p))
        raw=directory/'ns3-trace.csv'
        if raw.exists():
            identity=load(directory/'ns3-aggregates.provenance.json')['input']
            require(raw.stat().st_size==identity['size_bytes'] and digest(raw)==identity['sha256'],'Uncompressed temporary trace changed')
            raw.unlink()
        for p in directory.iterdir():
            if p.is_file() and p.name.startswith('.'):
                try:
                    repairs.append({'case':directory.name,'temporary_file':p.name,'bytes':p.stat().st_size,'sha256':digest(p)})
                    p.unlink(missing_ok=True)
                except FileNotFoundError:
                    pass  # Runtime staging copies may already have been retired.
        manifest['files']=case_files(directory);write(directory/'manifest.json',manifest)
    for p in out.rglob('*'):
        if p.is_file() and p.name.startswith('.'):
            try:
                repairs.append({'path':str(p.relative_to(out)),'bytes':p.stat().st_size,'sha256':digest(p)});p.unlink(missing_ok=True)
            except FileNotFoundError:
                pass
    if repairs:
        write(out/'build-provenance/reference-packaging-repair.json',{'schema':'csr-tranche25-reference-packaging-repair-v1','status':'passed','removed_temporary_runtime_files':repairs,'canonical_artifact_hashes_unchanged':True,'new_simulations':0,'scope':'Temporary runtime staging copies excluded; complete canonical trace and metrics bytes unchanged.'})
    write(out/'control-seed129.json',control_equivalence(accepted,control/'s129'))
    shutil.copy2(control/'s129/manifest.json',out/'build-provenance/control-s129/manifest.json')
    write(out/'manifest.json',{'schema':'csr-tranche25-native-suite-v1','status':'completed','ns3_source_commit':PIN,'engine_commit':ENGINE,'seeds':[131,132],'control_seed':129,'control_sha256':digest(out/'control-seed129.json'),'observer_enabled':False,'production_source_unchanged':True,'engine_source_unchanged':True,'matlab_executed':False,'files':suite_files(out)})
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--environment',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--control-work',type=Path,required=True)
    ap.add_argument('--control-reference',type=Path,default=ROOT/'evidence/tranche-20-ns3-reference/s129')
    ap.add_argument('--finalize-only',action='store_true',help='Verify and seal already-completed cases without new simulation')
    args=ap.parse_args();env=args.environment.resolve();out=args.output.resolve();control=args.control_work.resolve()
    if args.finalize_only:
        finalize(env,out,control,args.control_reference.resolve());print('Completed native references verified and sealed; no simulation run',flush=True);return
    require(not out.exists(),'Output must be a new directory')
    require(not control.exists(),'Control workspace must be a new directory')
    build=verify_environment(env);out.mkdir(parents=True);control.mkdir(parents=True)
    shutil.copy2(env/'build.json',out/'build.json')
    shutil.copytree(env/'build-provenance',out/'build-provenance')
    for name in ('archive-verification.json','downloads.json','build_environment.py','tooling-install.log'):
        shutil.copy2(env/name,out/'build-provenance'/name)
    workflow=T7.load_module('t25_native_workflow',env/'csr/utils/run-opnet-aggregate-differential.py')
    run_case(env,control,129,build,out/'build.json',workflow)
    equivalence=control_equivalence(args.control_reference.resolve(),control/'s129')
    write(out/'control-seed129.json',equivalence)
    for name in ('manifest.json','execution-stages.json','ns3-run.log','ns3-aggregate.log','ns3-aggregates.provenance.json','native-applications.json','scenario.csv','seed-recipe.json'):
        target=out/'build-provenance/control-s129';target.mkdir(exist_ok=True);shutil.copy2(control/'s129'/name,target/name)
    for seed in (131,132):run_case(env,out,seed,build,out/'build.json',workflow)
    finalize(env,out,control,args.control_reference.resolve())
    print('T25 native references and rebuilt environment equivalence passed',flush=True)
if __name__=='__main__':main()
