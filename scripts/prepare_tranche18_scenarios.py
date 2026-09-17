#!/usr/bin/env python3
"""Derive bounded real-PHY relay diagnostics from the immutable campus input.

These are synthetic diagnostics, not new OPNET-equivalent benchmarks. Radio
parameters and retained node positions are copied exactly. No loss schedule,
fixed route, PHY adjustment or receiver timing policy is injected.
"""
from pathlib import Path
import csv
import hashlib
import io
import json

ROOT = Path(__file__).resolve().parents[1]
PIN = '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
PARENT = 'scenarios/benchmarks/campus_multihop_6000.csv'
PARENT_SHA = '90b143d93c13c6c2761bc5f2875ccc3fff98f85af6f2550370e435df2aaabcfc'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')

def prepare(root=ROOT):
    parent = root/PARENT
    assert digest(parent) == PARENT_SHA, 'The accepted campus input changed'
    with parent.open(newline='') as stream:
        reader = csv.DictReader(stream)
        fields, original = reader.fieldnames, list(reader)
    assert len(original) == 14
    cases = []
    specs = [(key+str(seed), condition, seed, 600, [1,4,5], sources)
             for seed in (128,129,130)
             for key, condition, sources in [('r','relay_only',[4]),('l','local_only',[5]),('m','mixed',[4,5])]]
    specs.append(('p128','campus_prefix',128,900,[1,2,3,4,5,7,8],[2,3,4,5,7,8]))
    for key, condition, seed, duration, nodes, sources in specs:
        scenario = 'csr_t18_'+key
        rows = []
        for before in original:
            row = dict(before)
            if row['record'] == 'run':
                row.update(scenario=scenario, duration_s=str(float(duration)), seed=str(seed))
            elif row['record'] == 'node' and int(row['node_id']) not in nodes:
                continue
            elif row['record'] == 'flow' and int(row['flow_src']) not in sources:
                continue
            rows.append(row)
        relative = f'scenarios/t18/inputs/{key}.csv'
        path = root/relative; path.parent.mkdir(parents=True,exist_ok=True)
        stream=io.StringIO(newline=''); writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n')
        writer.writeheader();writer.writerows(rows);path.write_text(stream.getvalue(),encoding='utf-8',newline='')
        recipe_relative = f'scenarios/t18/inputs/{key}.recipe.json'
        recipe = {'schema':'csr-tranche18-scenario-derivation-v1', 'case_id':key,
            'parent_scenario':PARENT,'parent_scenario_sha256':PARENT_SHA,
            'scenario_file':relative,'scenario_sha256':digest(path),
            'run_overrides':{'scenario':scenario,'duration_s':duration,'seed':seed},
            'retained_node_ids':nodes,'retained_flow_sources':sources,
            'retained_rows_otherwise_byte_value_equal':True,
            'application_start_s':300,'application_interval_s':0.02,
            'retained_geometry_radio_phy_ecc_and_profiles_unchanged':True,
            'routes':'autonomous','forced_loss':False,'fixed_routes':False,
            'opnet_equivalence_claimed':False,
            'limitations':['Reduced cases remove upstream nodes and interferers.',
                'The prefix case retains every original node/flow but stops at 900 seconds.',
                'Matching seed labels do not align MATLAB and ns-3 random streams.']}
        write_json(root/recipe_relative,recipe)
        prefix = condition=='campus_prefix'
        cases.append({'case_id':key,'storage_key':key,'condition':condition,'scenario':scenario,
            'scenario_file':relative,'scenario_sha256':digest(path),
            'recipe_file':recipe_relative,'recipe_sha256':digest(root/recipe_relative),
            'profile_id':'hist-adb97c54-bare','seed':seed,'duration_s':duration,
            'bucket_width_s':60,'reference_directory':'evidence/tranche-18-ns3-reference/'+key,
            'observer_enabled':True,'observer_max_records':400000 if prefix else 100000,
            'service_window_seconds':[0,duration+1],
            'trace_limits':{'protocol':1500000 if prefix else 300000,
                'phy':1500000 if prefix else 500000,'admission':300000 if prefix else 50000},
            'max_events':12000000,'flow_limit':0,'node_ids':nodes,'flow_sources':sources,
            'source_kind':'campus_prefix_diagnostic' if prefix else 'synthetic_relay_service_diagnostic',
            'parent_kind':'unchanged_campus_rows_with_explicit_derivation','opnet_available':False,
            'expected_admission_attempts':len(sources)*int((duration-300)/0.02)})
    order = [case['case_id'] for case in cases]
    execution = order[:3]+['m128_off']+order[3:]
    plan = {'schema':'csr-tranche18-relay-service-plan-v1','tranche':18,
        'ns3_source_commit':PIN,'engine_commit':'6b5cd24ea80713ce16d88575869aedd6f432bdae',
        'parent_scenario':PARENT,'parent_scenario_sha256':PARENT_SHA,
        'seeds':[128,129,130],'case_count':10,'observed_case_count':10,'execution_count':11,
        'case_order':order,'execution_order':execution,'planned_simulated_seconds':6900,
        'conditions':['relay_only','local_only','mixed','campus_prefix'],
        'control':{'case_id':'m128_off','base_case_id':'m128','observer_enabled':False,
            'duration_s':600,'configuration_must_match_exactly':True,
            'core_statistics_and_raw_csvs_must_match':True},
        'timing_policy':'continuous','phy_ecc_changed':False,'production_source_changed':False,
        'default_policy_changed':False,
        'full_portable_regression':False,'full_campus_acceptance':False,'native_tests_included':False,
        'post_horizon_drain':False,'native_reference_reused':False,'opnet_available':False,
        'all_protocol_phy_admission_and_observer_traces_complete_required':True,
        'finite_stop_pending_is_failure':False,'dack_required_in_every_case':False,
        'numerical_parity_required':False,'common_random_numbers_claimed':False,
        'known_policy_difference':'MATLAB queued DATA retry waits for actual MAC transmission before its next timeout; native can time out a provisionally queued retry. Accepted prior distinction remains unchanged.',
        'observer':'Existing csr.sim.AckServiceDiagnostics; no added HOP/NWK state polling or scheduled work. Existing six public MAC scalar reads per cancellation snapshot are retained.',
        'observation_semantics':'Callback order and directly supplied snapshots; reconstructed lifecycle is not hidden instantaneous queue state.',
        'prefix_comparison':'Compare p128 pre-stop protocol/PHY and common captured admission prefix against the exact T17 owner return; added admission capacity records the remainder.',
        'cases':cases}
    write_json(root/'scenarios/t18/plan.json',plan)
    return plan

if __name__=='__main__':
    plan=prepare()
    print(json.dumps({'cases':plan['case_count'],'executions':plan['execution_count'],
        'simulated_seconds':plan['planned_simulated_seconds'],'case_order':plan['case_order']},indent=2))
