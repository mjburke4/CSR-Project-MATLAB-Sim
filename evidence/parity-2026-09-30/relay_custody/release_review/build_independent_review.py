from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'node8_return/kit/node8case'
KIT = ROOT / 'relay_custody/kit/node8case'
OUT = ROOT / 'relay_custody/release_review'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def sources(root):
    return {str(p.relative_to(root)): digest(p) for p in root.rglob('*')
            if p.is_file() and p.relative_to(root).parts[0] in ('model', '+ac')}

def method(path, name):
    source = path.read_text()
    matches = list(re.finditer(r'^        function [^\n]+', source, re.M))
    for i, found in enumerate(matches):
        if re.search(r'\b' + re.escape(name) + r'\(', found.group()):
            end = matches[i+1].start() if i+1 < len(matches) else source.index('\n    end\nend', found.end())
            return source[found.start():end].strip()
    raise ValueError(name)

expected_changed = sorted([
    '+ac/AccountingFixture.m', '+ac/DiscoveryMembershipNwk.m',
    '+ac/TerminalSimulation.m', '+ac/integratedAccountingPreflight.m',
    'model/+csr/+nwk/Layer.m', 'model/+csr/+sim/NetworkSimulation.m'])
expected_added = sorted(['+ac/RelayCustodyProbe.m', '+ac/relayCustodyPreflight.m'])
old, new = sources(BASE), sources(KIT)
changed = sorted(p for p in old.keys() & new.keys() if old[p] != new[p])
added, removed = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
checks = {'only_six_authorized_existing_source_files_changed': changed == expected_changed,
          'only_two_focused_test_source_files_added': added == expected_added,
          'no_source_files_removed': not removed}

for name in ['receiveData', 'enqueueApplication', 'pendingPosition', 'custodyCount',
             'pump', 'release', 'releaseFromHop', 'terminal', 'deliverLocal']:
    checks['production_candidate_nwk_' + name] = method(KIT/'model/+csr/+nwk/Layer.m', name) == method(KIT/'+ac/DiscoveryMembershipNwk.m', name)
for name in ['custodyAccepted', 'dropApplication', 'hasRetainedCustody', 'terminal', 'delivered', 'recoverDrop']:
    checks['production_candidate_accounting_' + name] = method(KIT/'model/+csr/+sim/NetworkSimulation.m', name) == method(KIT/'+ac/TerminalSimulation.m', name)

reference = []
for p in sorted((BASE/'ref/native132_1200').rglob('*')):
    if p.is_file():
        rel = p.relative_to(BASE)
        okay = (KIT/rel).is_file() and digest(p) == digest(KIT/rel)
        reference.append({'path':str(rel), 'sha256':digest(p), 'unchanged':okay})
checks['native_fixture_bytes_unchanged'] = bool(reference) and all(x['unchanged'] for x in reference)
checks['retry_policy_test_dependency_present_unchanged'] = digest(BASE/'TestQueuedRetryPolicy.m') == digest(KIT/'TestQueuedRetryPolicy.m')
checks['current_runner_has_exact_six_file_allowlist'] = all("'"+p+"'" in (KIT/'run_node8_tests.m').read_text() for p in expected_changed)
checks['old_natural_acceptance_explicitly_disabled'] = "'natural_result_reused_as_current_acceptance',false" in (KIT/'run_node8_tests.m').read_text()
checks['component_preflight_22_groups'] = 'report.completed=numel(checks)==22' in (KIT/'+ac/relayCustodyPreflight.m').read_text()
checks['accounting_preflight_four_groups'] = "for mode={'cutoff','final','relay','siblings'}" in (KIT/'+ac/integratedAccountingPreflight.m').read_text()
checks['probe_dropped_callback_correct'] = "'Dropped',@(app,reason)" in (KIT/'+ac/RelayCustodyProbe.m').read_text()
files = [dict(path=p, sha256=digest(KIT/p)) for p in expected_changed+expected_added+['run_node8_tests.m', 'README.md', 'TestQueuedRetryPolicy.m']]
report = {'schema':'csr-relay-custody-independent-review-v1', 'passed':all(checks.values()),
          'checks':checks, 'changed_files':changed, 'added_files':added,
          'unchanged_prior_model_candidate_files':sum(old[p] == new.get(p) for p in old),
          'reviewed_files':files, 'native_fixture':reference,
          'semantic_review':{
              'copy_identity':'Fresh receiver-local node and uint64 serial on every successful enqueue; original application identity preserved.',
              'exact_release':'No app-identity fallback. HOP release and following terminal target one occurrence; repeated or wrong-node callbacks cannot remove a sibling.',
              'queue_order':'Existing snapshot pump uses the stamped occurrence for pre/post callback lookup; same-app copies retain their individual FIFO positions.',
              'nsdp':'Existing source/destination counting sees every retained occurrence, including submitted HOP owners.',
              'application_accounting':'Read-only custody scan across all NWK nodes blocks provisional drop while any registered sibling remains. Equal-hop acceptance can recover a provisional drop. Unique final delivery, bytes and latency remain application keyed.',
              'scope':'No HOP, MAC, PHY, random-provider, wire-size, semantic comparator or native reference changes.',
              'focused_tests':'22 NWK/HOP groups across production and replay classes, including ACK, DACK hold, retry failure, stale/out-of-order releases, upstream tokens, final sink, queue-full retry, nested rejection and direct no-ACK completion.',
              'integration_tests':'Fourth real-Simulation case exercises same-node and lower-hop siblings, final registered-copy loss, same-hop recovery, unique sink latency and postdelivery copies.'},
          'matlab_execution_performed':False,
          'limitations':['Static source and packaging review only; MATLAB execution is pending.',
                         'Raw Dropped remains provisional when unregistered MAC copies may survive.',
                         'A completed bounded replay does not establish autonomous 6000-second or cross-seed parity.']}
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'independent_review.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':report['passed'],'checks':len(checks),'failed':[k for k,v in checks.items() if not v], 'unchanged':report['unchanged_prior_model_candidate_files']},indent=2))
