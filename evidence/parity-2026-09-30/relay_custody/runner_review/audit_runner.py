"""Static runner review; does not execute MATLAB or establish runtime parity."""
from pathlib import Path
import argparse, hashlib, json, re, sys

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KIT = ROOT / 'relay_custody/kit/node8case'
BASELINE = ROOT / 'node8_1200/kit/node8case/run_node8_tests.m'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def functions(text):
    matches = list(re.finditer(r'^function(?:\s+(?:\[[^]]+\]|\w+)\s*=\s*|\s+)(\w+)', text, re.M))
    return {match.group(1): text[match.start():matches[i+1].start() if i+1 < len(matches) else len(text)]
            for i, match in enumerate(matches)}


def audit(kit):
    current = kit / 'run_node8_tests.m'
    source = current.read_text()
    current_functions = functions(source)
    original_functions = functions(BASELINE.read_text())
    unchanged_functions = ('runNetwork', 'emptyCase', 'loadScenario', 'exportRaw', 'exportFinal',
                           'txTimingGate', 'compareTxTimes', 'txTimingPreflight', 'runPreflight',
                           'verifyFiles', 'hashFile', 'uniqueFolder', 'restore')
    rows = [{'name': name, 'unchanged': current_functions[name] == original_functions[name]}
            for name in unchanged_functions]
    sys.path.insert(0, str(ROOT / 'node8_1200/build/python'))
    from tree_sitter import Language, Parser
    import tree_sitter_matlab
    tree = Parser(Language(tree_sitter_matlab.language())).parse(current.read_bytes())
    names_match = re.search(r"    names=\{(.*?)\};\n    callbacks=", source, re.S)
    names = ['original_native_import'] + re.findall(r"'([^']+)'", names_match.group(1))
    checks = {
        'matlab_syntax_tree_has_no_error': not tree.root_node.has_error,
        'exactly_18_preflight_groups': len(names) == 18 and len(set(names)) == 18,
        'focused_custody_preflight_bound': "@()ac.relayCustodyPreflight(config,fullfile(out,'relay_custody_preflight'))" in source,
        'all_existing_runtime_and_export_functions_unchanged': all(row['unchanged'] for row in rows),
        'old_reuse_function_removed': 'reuseNatural' not in current_functions,
        'old_equivalence_function_removed': 'verifyAcceptedCandidate' not in current_functions,
        'no_current_natural_baseline_report': 'report.natural_baseline' not in source and 'report.accepted_natural_reuse' not in source,
        'historical_reference_explicit': "'natural_result_reused_as_current_acceptance',false" in source,
        'candidate_change_explicit': "'candidate_behavior_changed',true" in source,
        'current_target_20': "'target_percent',20" in source,
        'source_allowlist_6_existing': all(path in source for path in [
            '+ac/AccountingFixture.m', '+ac/DiscoveryMembershipNwk.m', '+ac/TerminalSimulation.m',
            '+ac/integratedAccountingPreflight.m',
            'model/+csr/+nwk/Layer.m', 'model/+csr/+sim/NetworkSimulation.m']),
        'added_candidate_test_allowlist_present': all(path in source for path in [
            '+ac/RelayCustodyProbe.m', '+ac/relayCustodyPreflight.m']),
        'archived_matlab_excluded_from_resolution': "active=startsWith(relative,'model/') || startsWith(relative,'+ac/') || ~contains(relative,'/');" in source,
    }
    return {
        'schema': 'csr-relay-custody-runner-static-v1',
        'status': 'pass' if all(checks.values()) else 'fail',
        'matlab_executed': False,
        'candidate_runner_sha256': sha(current),
        'baseline_runner_sha256': sha(BASELINE),
        'readme_sha256': sha(kit / 'README.md'),
        'checks': checks,
        'preflight_groups': names,
        'unchanged_functions': rows,
        'scope': 'Static syntax and preservation review only; current manifest and full dependency closure are separate release gates.',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--kit', type=Path, default=DEFAULT_KIT)
    parser.add_argument('--out', type=Path, default=Path(__file__).with_name('runner_static.json'))
    args = parser.parse_args()
    result = audit(args.kit)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    assert result['status'] == 'pass'
