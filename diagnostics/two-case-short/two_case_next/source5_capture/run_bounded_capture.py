#!/usr/bin/env python3
"""Run seed 132 from time zero through 330 s, then validate native fidelity.

Requires the source-bound ns-3/CSR checkout and built Debug ns-3 modules on
the owner's machine. Never modifies source checkout or original reference.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from prepare_overlay import prepare, HERE

ORIGINAL_SCENARIO_SHA = 'fa45217f8631f34d203580842d8a1a12cb18c53a3efbe0b702b2e17aaeb30d48'
ORIGINAL_TRACE_SHA = '3da17e3397756f8890964d571932a44f7c94573b4d38eac9387342588883a4ef'
COMPACT_PREFIX_SHA = '6819889725eb891112b57dbc9f8e63c35af7e87fcf64f77c6dbe3f490d3c63a8'
DRIVER_SHA = 'b859a78a9e260e87689126569aeb6693861ffb78f28da2d296ff9eaa4287cc4d'
SOURCE_COMMIT = '486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
ENGINE_COMMIT = '6b5cd24ea80713ce16d88575869aedd6f432bdae'
STOP_NS = 330_000_000_000
START_NS = 300_000_000_000


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def run_command(cmd, log: Path, env=None):
    with log.open('w') as f:
        p = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env,
                           check=False)
    if p.returncode:
        raise RuntimeError(f'command failed ({p.returncode}): {cmd!r}; see {log}')


def prefix_rows(original: Path, observed: Path):
    with gzip.open(original, 'rt', newline='') as baseline, observed.open(newline='') as current:
        a, b = csv.DictReader(baseline), csv.DictReader(current)
        assert a.fieldnames == b.fieldnames and len(a.fieldnames) == 30
        def bounded(reader):
            for row in reader:
                if float(row['time_s']) >= STOP_NS/1e9:
                    return
                yield row
        n = 0
        for left, right in itertools.zip_longest(bounded(a), bounded(b)):
            if left != right:
                raise AssertionError(f'canonical native prefix mismatch at row {n}: {left!r} != {right!r}')
            n += 1
    assert n > 40_000, ('implausibly small native prefix', n)
    return n, a.fieldnames


def read_csv(path: Path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def copy_compact_reference(original: Path, destination: Path):
    if sha(original) == COMPACT_PREFIX_SHA:
        shutil.copy2(original, destination)
        return
    with gzip.open(original,'rt',newline='') as source, destination.open('wb') as sink:
        reader = csv.DictReader(source)
        with gzip.GzipFile(fileobj=sink, mode='wb', filename='', mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding='utf-8', newline='') as output:
                writer=csv.DictWriter(output, fieldnames=reader.fieldnames)
                writer.writeheader()
                for row in reader:
                    if float(row['time_s']) >= STOP_NS/1e9:
                        break
                    writer.writerow(row)


def verify_checkout(directory: Path, expected: str, label: str):
    # A repository checkout has stronger ancestry than standalone file hashes.
    # If source was supplied as an archive, exact header hashes + complete
    # canonical trace fidelity still enforce the runtime behavioral boundary.
    result = subprocess.run(['git','-C',str(directory),'rev-parse','HEAD'],
                            capture_output=True,text=True,check=False)
    if result.returncode:
        return 'archive: no git metadata; source headers and canonical prefix bound'
    head = result.stdout.strip()
    assert head == expected, f'{label} checkout is {head}, expected {expected}'
    dirty = subprocess.run(['git','-C',str(directory),'status','--porcelain',
                            '--untracked-files=no'],
                           capture_output=True,text=True,check=True)
    assert not dirty.stdout.strip(), f'{label} checkout has local modifications'
    return head


def execute(ns3build: Path, stock: Path, scenario: Path, original: Path,
            output: Path):
    driver = HERE/'vendor/capture.cc'
    assert sha(scenario) == ORIGINAL_SCENARIO_SHA, 'scenario hash differs from accepted seed132'
    assert sha(original) in {ORIGINAL_TRACE_SHA, COMPACT_PREFIX_SHA}, 'native reference trace hash differs'
    assert sha(driver) == DRIVER_SHA, 'native driver source differs from accepted fixture'
    source_commit = verify_checkout(stock.parent, SOURCE_COMMIT, 'CSR source')
    engine_commit = verify_checkout(ns3build.parent, ENGINE_COMMIT, 'ns-3 engine')
    assert (ns3build/'include/ns3').is_dir(), 'missing Debug ns-3 build/include/ns3'
    assert (ns3build/'lib').is_dir(), 'missing Debug ns-3 build/lib'
    assert not output.exists(), f'output already exists (fresh run required): {output}'
    output.mkdir(parents=True)
    overlay = output/'overlay/ns3'
    prepare(stock, overlay)
    capture_dir = output/'capture'
    captures = output/'inputs'
    accepted = output/'reference'
    for p in [capture_dir, captures, accepted]:
        p.mkdir(parents=True, exist_ok=True)
    executable = output/'source5-native-capture'
    libs = ['csr','spectrum','buildings','propagation','mobility','antenna',
            'network','stats','core']
    cmd = ['g++','-std=c++23','-O0','-g',
           '-DNS3_ASSERT_ENABLE','-DNS3_BUILD_PROFILE_DEBUG','-DNS3_LOG_ENABLE',
           '-DSTACKTRACE_LIBRARY_IS_LINKED=1','-D__LINUX__',
           '-I'+str(output/'overlay'), '-I'+str(ns3build/'include'), str(driver),
           '-L'+str(ns3build/'lib'), '-Wl,-rpath,'+str(ns3build/'lib'),
           '-Wl,--no-as-needed', '-lns3-dev-csr-debug', '-Wl,--as-needed']
    cmd += [f'-lns3-dev-{name}-debug' for name in libs[1:]]
    cmd += ['-lstdc++exp', '-o', str(executable)]
    run_command(cmd, capture_dir/'compile.log')
    command = [str(executable), '--scenario='+str(scenario),
               '--trace='+str(capture_dir/'ns3-trace.csv'),
               '--appDiagnostics='+str(capture_dir/'app-admission.csv'),
               '--stop=330','--flowLimit=0', '--dutyCycling=1',
               '--opnetAlignedDutyCycle=1','--gatewayDiscovery=1',
               '--opnetAppGating=1','--aggregateTraceOnly=0',
               '--admissionTrace=1','--quietModelLogs=0',
               '--stochasticSyncThreshold=1']
    env = dict(os.environ)
    env['CSR_MAC_CAPTURE'] = str(capture_dir/'mac-input.log')
    env['CSR_SOURCE5_CAPTURE'] = str(capture_dir/'source5_native.tsv')
    run_command(command, capture_dir/'run.log', env)
    # The gate precedes conversion and any pass/fidelity claim. `event_index`
    # and all 30 native fields are compared byte-for-byte as CSV values.
    n, fields = prefix_rows(original, capture_dir/'ns3-trace.csv')
    run_command([sys.executable, str(HERE/'vendor/convert_capture.py'),
                 str(capture_dir/'mac-input.log'), str(captures)],
                capture_dir/'convert.log')
    tx = read_csv(captures/'tx.csv')
    draws = read_csv(captures/'draws.csv')
    children = read_csv(captures/'tx_frames.csv')
    framed = read_csv(captures/'frames.csv')
    inputs = read_csv(captures/'inputs.csv')
    required = {'rx_signal_arrival','rx_sync_gate','rx_acquire','rx_phy_decision',
                'rx_sync_draw','rx_binomial_draw','node4_ack_rx','node4_ack_drop',
                'node5_nwk_submit','node5_relay_rx','node5_nwk_scan',
                'node5_nwk_gate','node5_hop_admit','node5_hop_feedback',
                'node5_mac_service','node5_mac_tx','mac_tx_child',
                'boundary_state','rx_error_interval','rx_child'}
    with (capture_dir/'source5_native.tsv').open(newline='') as f:
        observed = list(csv.DictReader(f, delimiter='\t'))
    names = collections.Counter(r['event'] for r in observed)
    missing = required - set(names)
    assert not missing, ('missing required observer events', sorted(missing))
    assert all(START_NS <= int(r['time_ns']) < STOP_NS for r in observed)
    assert [int(r['event_order']) for r in observed] == list(range(1,len(observed)+1))
    boundary = [r for r in observed if r['event']=='boundary_state' and r['node']=='4']
    assert len(boundary) == 1 and int(boundary[0]['time_ns']) == START_NS, (
        'node4 must provide exactly one t=300s receiver-state snapshot', boundary)
    boundary_details = json.loads(boundary[0]['detail_json'])
    assert boundary[0]['state_before'] in ('idle','search'), ('node4 receiver not clean',boundary[0])
    for field in ('rx_signal_count','tracked_id','acquisition_pending',
                  'done_rx_pending','signal_wake_pending','sync_present'):
        assert boundary_details.get(field) == '0', (
            'node4 receiver boundary cannot initialize the bounded replay',field,boundary_details)
    assert boundary_details.get('rx_signal_ids') == '', ('node4 active signals at t300',boundary_details)
    # Bind the target cases to canonical native pair outcomes, not only the
    # presence of generic events elsewhere in the interval.
    for event, node, peer, kind, expected in [
            ('node4_ack_rx','4','5',None,6),
            ('node4_ack_drop','4','5',None,4),
            ('rx_child','5','3','0',32)]:
        subset = [r for r in observed if r['event']==event and r['node']==node
                  and r['peer']==peer and (kind is None or r['kind']==kind)]
        # The reference counts accepted/dropped physical aggregates, while
        # one such aggregate can carry several child packets.
        distinct_signals = {r['tx_id'] for r in subset}
        assert '' not in distinct_signals and len(distinct_signals)==expected, (
            'target physical receiver/relay outcome count differs from canonical reference',
            event,node,peer,expected,len(distinct_signals),len(subset))
    node4_intervals = {}
    node4_sync_draws = [r for r in observed if r['node']=='4' and r['event']=='rx_sync_draw']
    node4_binomial_draws = [r for r in observed if r['node']=='4' and r['event']=='rx_binomial_draw']
    assert node4_sync_draws and node4_binomial_draws, 'node4 target receiver draw tape is empty'
    for r in observed:
        if r['node']!='4' or r['event']!='rx_error_interval':
            continue
        details=json.loads(r['detail_json'])
        key=(r['tx_id'],details['interval_ordinal'])
        assert r['tx_id'] and key not in node4_intervals, ('ambiguous node4 BER interval',key)
        node4_intervals[key]=details
    for r in node4_binomial_draws:
        details=json.loads(r['detail_json'])
        key=(r['tx_id'],details['interval_ordinal'])
        assert key in node4_intervals, ('node4 receiver draw missing BER interval',key)
        assert details['component'] in ('header','payload') and details['rng_consumed']=='1'
        assert (int(details['interval_start_ns'])<=int(details['component_start_ns'])<=
                int(details['component_end_ns'])<=int(details['interval_end_ns']))
        assert int(details['bits'])>0 and 0<float(details['probability'])<1
        assert 0<=float(details['draw'])<=1
    for filename in ['tx.csv','draws.csv']:
        shutil.copy2(captures/filename, accepted/filename)
    profile = {
        'schema': 'csr-mac-history-replay-v1',
        'nodes': [5], 'replay_start_ns': 0, 'replay_stop_ns': STOP_NS,
        'comparison_start_ns': START_NS, 'comparison_stop_ns': STOP_NS,
        'slot_profile': 'hist-2014-next-tslot-modulo-probe',
        'initial_active_nodes': 1, 'initial_reported_nodes': 0,
        'initial_native_mac_state': 'search',
        'external_state_initialization': 'receiver_state inputs from time zero',
        'duty_cycle_enabled': True,
        'receiver_lifecycle': 'external recorded receiver_state and sync inputs',
        'same_time_order': 'captured (time_ns,event_order); strict native prefix verified',
        'rate_key': 8, 'rate_bps': 4/.00051,
    }
    (captures/'profile.json').write_text(json.dumps(profile,indent=2)+'\n')
    selected_tx = [r for r in tx if r['node']=='5']
    selected_draws = [r for r in draws if r['node']=='5']
    assert selected_tx and selected_draws
    fidelity = {
        'schema': 'csr-source5-native-capture-v1',
        'all_passed': True,
        'scope': 'Full 0–330 s native warmup and bounded 300–330 s source-5 receiver/service capture; no MATLAB replay verdict',
        'source_capture': {'exact_prefix':True, 'rows':n,'fields':fields,
                           'start_ns':0,'stop_ns':STOP_NS,
                           'scenario_sha256':sha(scenario),
                           'original_full_trace_sha256':ORIGINAL_TRACE_SHA,
                           'comparison_trace_sha256':sha(original)},
        'nodes': [{'node':5,'full_warmup_tx':len(selected_tx),
                   'target_window_tx':sum(START_NS<=int(r['time_ns'])<STOP_NS for r in selected_tx),
                   'raw_draws':len(selected_draws), 'unused_draws':'pending replay'}],
        'reference_sha256': {name:sha(accepted/name) for name in ['tx.csv','draws.csv']},
        'input_sha256': {p.name:sha(p) for p in captures.glob('*.csv')},
        'observer_sha256': sha(capture_dir/'source5_native.tsv'),
        'source_commit_gate': source_commit,
        'engine_commit_gate': engine_commit,
        'observer_events': dict(names),
        'coverage': {'aggregate_children':'observed','receiver_state':'observed',
                     'competing_signals':'observed','mac_integer_draws':'observed',
                     'phy_random_tape': 'observed' if node4_sync_draws and node4_binomial_draws else 'unavailable',
                     'nwk_hop_capacity': 'observed' if names['node5_hop_gate'] and names['node5_nwk_gate'] else 'unavailable'},
        'command': command,
    }
    provenance = output/'provenance'
    provenance.mkdir(exist_ok=True)
    required_sources = {
        'scenario': scenario,
        'native_capture_source': driver,
        'instrumentation_generator': HERE/'prepare_overlay.py',
    }
    copied={}
    for role, source in required_sources.items():
        p=provenance/source.name
        shutil.copy2(source,p)
        copied[role]=p
    compact=provenance/'native_s132_prefix_0_330.csv.gz'
    copy_compact_reference(original,compact)
    copied['native_reference']=compact
    for name in ('csr-net-device.h','csr-mac-core.h','csr-phy-model.h',
                 'csr-hop-layer.h','csr-nwk-layer.h','source5-observer.h',
                 'mac-replay-hooks.h'):
        copied['native_overlay' if name=='csr-net-device.h' else 'overlay_'+name]=overlay/name
    manifest={
        'schema':'csr-two-case-capture-v1','case_id':'source5_132',
        'seed':132,'window_ns':[START_NS,STOP_NS],
        'source_files':[
            {'role':role,'path':str(p.relative_to(output)),'sha256':sha(p)}
            for role,p in sorted(copied.items())],
        'reference_lineage':{'original_full_trace_sha256':ORIGINAL_TRACE_SHA,
                             'strict_stop_ns':STOP_NS,'rows':n,
                             'extractor':'run_bounded_capture.py:copy_compact_reference'},
        'capture':{'status':'verified','prefix_fidelity':'passed',
                   'prefix_end_ns':STOP_NS,'prefix_rows':n,
                   'trace_path':'capture/ns3-trace.csv',
                   'observations_path':'capture/source5_native.tsv',
                   'mac_tape_paths':{k:f'inputs/{k}.csv'
                       for k in ('inputs','frames','draws','tx','tx_frames')}},
        'coverage':{'counts':{'mac_inputs':len(inputs),'mac_draws':len(draws),
                              'tx':len(tx),'tx_children':len(children),
                              'observer_events':len(observed)},
                    'event_counts':dict(names),
                    'observability':fidelity['coverage']},
        'replay':{'status':'replay_pending'},
        'claims':{'full_network_parity':False},
    }
    manifest_path=output/'source5_132.manifest.json'
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    validator=HERE.parent/'schema_review/validate_two_case.py'
    assert validator.is_file(), f'missing shared schema validator: {validator}'
    run_command([sys.executable,str(validator),str(manifest_path)],
                capture_dir/'schema-validation.log')
    (accepted/'fidelity.json').write_text(json.dumps(fidelity,indent=2)+'\n')
    print(json.dumps({'prefix_rows':n,'observer_events':sum(names.values()),
                      'tx':len(tx),'draws':len(draws),'frames':len(framed),
                      'mac_inputs':len(inputs),'tx_children':len(children),
                      'native_fidelity':'passed', 'replay':'pending'},indent=2))


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--engine-build',type=Path,required=True,
                    help='matching ns-3 Debug engine/build directory')
    ap.add_argument('--source-model',type=Path,required=True,
                    help='matching native CSR model/*.h source directory')
    ap.add_argument('--reference',type=Path,
                    help='optional source-bound t25/s132 directory containing scenario.csv and ns3-trace.csv.gz')
    ap.add_argument('--scenario',type=Path,
                    help='direct hash-bound seed132 scenario.csv, e.g. portable schema_review/scenario_s132.csv')
    ap.add_argument('--reference-trace',type=Path,
                    help='optional 0–330 s compact exact prefix, SHA bound to original full trace')
    ap.add_argument('--out',type=Path,required=True,
                    help='new isolated output directory')
    args=ap.parse_args()
    if not args.reference and not (args.scenario and args.reference_trace):
        ap.error('--reference or both --scenario and --reference-trace are required')
    scenario = args.scenario or (args.reference/'scenario.csv')
    original = args.reference_trace or (args.reference/'ns3-trace.csv.gz')
    execute(args.engine_build.resolve(),args.source_model.resolve(),
            scenario.resolve(),original.resolve(),args.out.resolve())
