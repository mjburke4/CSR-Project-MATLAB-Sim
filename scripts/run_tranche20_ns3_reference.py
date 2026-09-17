#!/usr/bin/env python3
"""Run full-campus seeds with unchanged pinned pristine ns-3 executable.

Only canonical run.seed changes. No observer or source changes are made.
Build inputs and binary are rebound to the preserved T18 build receipt.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import run_tranche7_ns3_reference as T7
import run_tranche8_ns3_diagnostics as T8
import tranche20_native_metrics as metrics


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2)+'\n')


def seed_scenario(parent, target, seed):
    data = parent.read_bytes()
    lines = data.splitlines(keepends=True)
    header = next(csv.reader([lines[0].decode()]))
    row = next(csv.reader([lines[1].decode()]))
    assert row[header.index('record')] == 'run' and row[header.index('seed')] == '128'
    # Exact byte substitution preserves every other field, including source lineage.
    original = b',6000.0,128,0,1000.0,'
    replacement = f',6000.0,{seed},0,1000.0,'.encode()
    assert lines[1].count(original) == 1
    lines[1] = lines[1].replace(original, replacement)
    target.write_bytes(b''.join(lines))
    before, after = T7.BASE.csv_rows(parent), T7.BASE.csv_rows(target)
    differences = [(i,k,a[k],b[k]) for i,(a,b) in enumerate(zip(before,after)) for k in a if a[k] != b[k]]
    assert len(before) == len(after)
    assert differences == ([(0,'seed','128',str(seed))] if seed != 128 else [])
    return {'parent_sha256':digest(parent),'scenario_sha256':digest(target),
            'field_changes':differences,'only_run_seed_changed':True,'seed':seed,
            'duration_s':6000,'scenario':'blue_radio_campus-multihop'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--environment',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--seeds',type=int,nargs='+',default=[129,130])
    args = ap.parse_args()
    env, out = args.environment.resolve(), args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    source = env/'csr'; runner = env/'runner-v3/t18-pristine'
    oldbuild = json.loads((env/'reference-v3/build.json').read_text())
    assert digest(runner) == oldbuild['pristine_runner_sha256']
    verified = {}
    for name, expected in oldbuild['input_sha256'].items():
        path=Path(name)
        # Actual compiled pristine input plus shared engine libraries/headers and tools.
        if str(path).startswith(str(source)) or str(path).startswith(str(env/'engine/build')):
            assert digest(path) == expected, f'Preserved native build input changed: {path}'
            verified[str(path)] = expected
    for repo, pin in ((source,oldbuild['ns3_source_commit']),(env/'engine',oldbuild['engine_commit'])):
        assert subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip() == pin
        assert not subprocess.check_output(['git','-C',str(repo),'diff','--name-only','HEAD'],text=True).strip()
    shutil.copy2(env/'reference-v3/build.json',out/'t18-build.json')
    shutil.copy2(env/'environment-build.json',out/'t18-environment-build.json')
    build={'schema':'csr-tranche20-native-build-v1','status':'verified-reused-pristine',
           'ns3_source_commit':oldbuild['ns3_source_commit'],'engine_commit':oldbuild['engine_commit'],
           'runner_sha256':digest(runner),'observer_enabled':False,'new_compilation':False,
           'verified_inputs':verified,'pristine_compile':oldbuild['compiles']['pristine'],
           't18_build_sha256':digest(out/'t18-build.json'),
           't18_environment_sha256':digest(out/'t18-environment-build.json')}
    write(out/'build.json',build)
    parent=ROOT/'scenarios/benchmarks/campus_multihop_6000.csv'
    workflow=T7.load_module('t20_native_workflow',source/'utils/run-opnet-aggregate-differential.py')
    for seed in args.seeds:
        directory=out/f's{seed}'; directory.mkdir()
        scenario=directory/'scenario.csv'
        recipe=seed_scenario(parent,scenario,seed); write(directory/'seed-recipe.json',recipe)
        case={'case_id':f's{seed}','scenario':'blue_radio_campus-multihop','seed':seed,
              'duration_s':6000,'bucket_width_s':60,'profile_id':'hist-adb97c54-bare',
              'source_kind':'archived_opnet_seed_override','scenario_sha256':digest(scenario)}
        parsed=workflow.load_scenario_run(scenario)
        assert parsed['seed'] == seed and parsed['duration_s'] == 6000
        command=T8.runner_command(runner,scenario,case,directory)
        command[command.index('--aggregateTraceOnly=1')]='--aggregateTraceOnly=0'
        command+=['--admissionTrace=1']
        print(f'Running native full campus seed {seed}',flush=True)
        run=T7.run_stage(command,directory/'ns3-run.log',1200)
        write(directory/'execution-stages.json',{'run_ns3':run})
        assert run['exit_code'] == 0
        command=[sys.executable,'-B','-I',str(source/'utils/aggregate-ns3-trace.py'),
                 str(directory/'ns3-trace.csv'),str(directory/'ns3-aggregates.csv'),
                 '--scenario',case['scenario'],'--bucket-width','60','--stop-time','6000',
                 '--legacy-trace-size-exclusion-bits','0','--require-zero-size-mismatches',
                 '--provenance',str(directory/'ns3-aggregates.provenance.json')]
        aggregate=T7.run_stage(command,directory/'ns3-aggregate.log',1200)
        write(directory/'execution-stages.json',{'run_ns3':run,'aggregate_ns3':aggregate})
        assert aggregate['exit_code'] == 0
        admissions=workflow.validate_app_admission_diagnostics(directory/'app-admission-diagnostics.csv',case['scenario'],parsed['application_profile'],parsed['flows'])
        lineage=workflow._load_and_validate_ns3_provenance(directory/'ns3-aggregates.provenance.json',directory/'ns3-trace.csv',directory/'ns3-aggregates.csv',case['scenario'])
        T7.normalized_sidecar(case,directory,'ns3')
        compressed=T7.compress(directory/'ns3-trace.csv')
        applications=metrics.native_applications(directory)
        write(directory/'native-applications.json',applications)
        manifest={'schema':'csr-tranche20-native-reference-v1','status':'completed','case':case,
                  'ns3_source_commit':build['ns3_source_commit'],'engine_commit':build['engine_commit'],
                  'runner_sha256':digest(runner),'build_sha256':digest(out/'build.json'),
                  'observer_enabled':False,'stages':{'run_ns3':run,'aggregate_ns3':aggregate},
                  'seed_recipe':recipe,'application_admission_totals':admissions,
                  'exact_sequence_validation':lineage,'compressed_artifacts':[compressed],
                  'files':[{'path':p.name,'sha256':digest(p),'bytes':p.stat().st_size} for p in sorted(directory.iterdir()) if p.is_file() and not p.name.startswith('.') and p.name != 'ns3-trace.csv']}
        write(directory/'manifest.json',manifest)
        print(f'Completed seed {seed}: {applications["totals"]}',flush=True)

if __name__ == '__main__': main()
