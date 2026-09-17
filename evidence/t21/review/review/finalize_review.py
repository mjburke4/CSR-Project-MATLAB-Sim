"""Freeze the independently reviewed T21 offline diagnostic gate."""
import csv
import datetime
import json
import math
from pathlib import Path
from audit_inputs import digest, BASE, WORKSPACE

def read(path):return json.loads(path.read_text())

def main():
    reviewed = ['input-target-review.json','source4-review.json','matlab-review.json',
                'native-review.json','native-capacity-review.json','threshold-replay-review.json']
    for name in reviewed:
        assert read(BASE/'review'/name)['passed']
    # Confirm the final source tree and pinned reference bytes still equal T20.
    owner=WORKSPACE/'t20-return-review/owner'
    sources,refs=read(owner/'source.json'),read(owner/'references.json')
    for row in sources+refs:
        assert digest(WORKSPACE/'csr20'/row['path'])==row['sha256']
    summary=read(BASE/'diagnostic.json')
    assert summary['status']=='diagnostic_completed'
    assert summary['working_numerical_band_percent']==10
    assert summary['matlab_simulations_executed']==summary['native_simulations_executed']==0
    assert not summary['matlab_rerun_required'] and not summary['production_change_justified']
    for name,expected in summary['result_files'].items():
        assert digest(BASE/name)==expected
    target=read(BASE/'target/target-screen.json')
    assert summary['target_summary']==target['summaries']
    matlab=read(BASE/'matlab/matlab_node8.json')
    assert digest(BASE/'matlab/extract_matlab.py')==matlab['analysis_script_sha256']
    replay=read(BASE/'matlab/matlab_threshold_replay.json')
    assert digest(BASE/'matlab/replay_flow_threshold.py')==replay['analysis_script_sha256']
    assert digest(BASE/'matlab/extract_matlab.py')==replay['helper_sha256']
    semantic=read(BASE/'source-semantics.json')
    for row in semantic['files']:
        assert digest(WORKSPACE/'csr20'/row['path'])==row['sha256']
    native_source=semantic['fresh_native_source']
    assert digest(BASE/native_source['local_copy'])==native_source['sha256']=='0a826930bab43db429a2a3bd905672b370774274f7de826abf180f002156f10b'
    for comparison in summary['node8_comparison']:
        seed,source=comparison['seed'],comparison['source']
        m=next(c for s in matlab['results'] if s['seed']==seed for c in s['cohorts'] if c['node']==8 and c['source']==source)
        n=read(BASE/f'native/s{seed}.json')
        state=next(r for r in n['nsdp_state'] if r['node']==8 and r['source']==source)
        residence=next(r for r in n['residence'] if r['node']==8 and r['source']==source)
        assert comparison['matlab_mean_custody_apps']==m['mean_nwk_custody_traffic_window']
        assert comparison['ns3_mean_nsdp_apps']==state['time_weighted_mean_300_6000']
        assert comparison['matlab_completed_first_submit_mean_s']==m['completed_nwk_first_submit_wait']['mean_s']
        assert comparison['ns3_completed_first_admission_mean_s']==residence['nwk_queue_wait_s']['mean']
        assert comparison['matlab_pending_custody_apps_at_stop']==m['nwk_pending_at_stop']
        assert comparison['ns3_nsdp_apps_at_stop']==state['last']
    native130=read(BASE/'native/s130.json')
    events=native130['node_source_event_reasons']
    count=lambda ev,reason,source:next(r['count'] for r in events if (r['node'],r['source'],r['event'],r['reason'])==(8,source,ev,reason))
    assert count('nwk_enqueue','relay',7)==1361
    assert count('nwk_admission','admitted',7)==1043
    assert 1361-1043==318
    native129=read(BASE/'native/s129.json')
    assert sum(read(BASE/f'native/s{s}.json')['input']['rows']for s in (128,129,130))==11786557
    m130=next(r for r in replay['results']if r['seed']==130)
    assert sum(m130['threshold_at_admission_histogram'][str(x)]for x in (1,2))==654
    assert sum(m130['threshold_at_admission_histogram'].values())==787
    assert round(sum(m130['threshold_seconds_300_to_6000'][str(x)]for x in (1,2)))==5090
    script_paths=sorted(p for p in BASE.rglob('*.py') if '__pycache__' not in p.parts)
    result_paths=[BASE/'T21_Review.md',BASE/'diagnostic.json',BASE/'source-main-check.json',BASE/'source-semantics.json',BASE/native_source['local_copy']]
    for folder in ['target','matlab','native','source4']:
        result_paths.extend(p for p in (BASE/folder).iterdir() if p.is_file() and p.suffix in ('.json','.csv','.md') and p.name!='exploration.json')
    result_paths.extend(BASE/'review'/name for name in reviewed)
    output={
        'schema':'csr-tranche21-independent-final-review-v1',
        'reviewed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'passed':True,
        'remaining_blockers':[],
        'model_source_unchanged':True,
        'accepted_source_bindings_unchanged':len(sources),
        'accepted_reference_bindings_unchanged':len(refs),
        'matlab_source_files_unchanged':sum(r['path'].endswith('.m')for r in sources),
        'fresh_matlab_simulations':0,
        'fresh_native_simulations':0,
        'new_matlab_tests_executed':0,
        'accepted_matlab_tests_reused':716,
        'matlab_rerun_required':False,
        'working_descriptive_target_percent':10,
        'assessment':'T21 existing-trace diagnostic is complete and internally consistent. Numerical residuals remain descriptive exceptions; no model change or claim of statistical equivalence is warranted by these observations.',
        'review_scope':[
            'Independently verified all source/reference bindings, accepted T20 identity hashes, revised target arithmetic and summary denominators.',
            'Independently matched source-4 final outcomes and conserved admissions, deliveries and undelivered populations across all seeds.',
            'Independently swept MATLAB cohort intervals to verify time-integrated custody/capacity and censored population accounting.',
            'Reviewed native streaming parser; independently checked derived full-trace counts, NSDP/queue conservation, capacity/outcome identity joins and accepted gzip/provenance bindings. Did not redundantly reparse raw multi-gigabyte traces.',
            'Independently inspected unchanged MATLAB and freshly fetched pinned native threshold rules, plus reconstructed MATLAB callback transitions. Threshold replay is explicitly source-derived, not a new raw observation.',
            'Reviewed final root and specialist reports for matching units/endpoints, historical instrumentation gaps, no cross-engine identity joins, and no unsupported causal or execution claims.'
        ],
        'resolved_review_findings':[
            'Native DACK feedback/NSDP-release residence was renamed and actual delayed capacity-release joins added before cross-engine comparison.',
            'MATLAB table occupancy columns explicitly use applications, not elapsed seconds; empty saturation intervals are skipped.',
            'Native route-change timing of103.09 seconds is scoped to seed130; seed129 has a different pretraffic endpoint.',
        ],
        'reviewed_script_sha256':{p.relative_to(BASE).as_posix():digest(p)for p in script_paths},
        'reviewed_result_sha256':{p.relative_to(BASE).as_posix():digest(p)for p in sorted(set(result_paths))},
        'packaging_scope':'This gate freezes technical reports, scripts and results. A later archive/member verification is required to validate packaging; saving or publication is outside this technical review.'
    }
    (BASE/'review/final-review.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({k:v for k,v in output.items()if k not in ['reviewed_script_sha256','reviewed_result_sha256','review_scope','resolved_review_findings']},indent=2))

if __name__=='__main__':main()
