from pathlib import Path
import hashlib
import json
import shutil

base = Path(__file__).resolve().parents[1]
root = base / 'kit/autocase'
previous = base.parent / 'autonomous_ninth/kit/autocase'
text = (previous / 'run_autonomous_tests.m').read_text()

def edit(old, new):
    global text
    assert text.count(old) == 1, (old[:110], text.count(old))
    text = text.replace(old, new)

edit('%RUN_AUTONOMOUS_TESTS Accepted natural gate plus discovery-lifecycle diagnostic.',
     '%RUN_AUTONOMOUS_TESTS Accepted natural gate plus discovery-membership diagnostic.')
edit("fprintf('L retains K and corrects active SNMP requester ownership plus inline KEY_UPDATE admission.\\n');",
     "fprintf('M retains L and keeps late routing knowledge separate from discovery membership.\\n');")
edit("        'L_discovery_lifecycle','Prior K with idle-only SNMP requester completion and inline reliable KEY_UPDATE ownership');",
     "        'M_discovery_membership','Prior L with discovery membership populated only at local completion or received DONE');")
edit("        second=runCase(root,out,config,'L_discovery_lifecycle','native');",
     "        fprintf('Checking late route usability and explicit discovery-membership boundaries.\\n');\n"
     "        report.discovery_membership_preflight=ac.discoveryMembershipPreflight(config,fullfile(out,'membership_preflight'));\n"
     "        second=runCase(root,out,config,'M_discovery_membership','native');")
edit('Case L skipped: natural source-fidelity gate did not pass.',
     'Case M skipped: natural source-fidelity gate did not pass.')
edit('simulation=ac.DiscoveryLifecycleSimulation(config,observer,timing,options);',
     'simulation=ac.DiscoveryMembershipSimulation(config,observer,timing,options);')
assert text.count("strcmp(name,'L_discovery_lifecycle')") == 3
text = text.replace("strcmp(name,'L_discovery_lifecycle')", "strcmp(name,'M_discovery_membership')")
(root / 'run_autonomous_tests.m').write_text(text)
shutil.copytree(base / 'data/L_discovery_lifecycle', root / 'ref/history/L_discovery_lifecycle', dirs_exist_ok=True)
prior = json.loads((previous / 'ref/history/history.json').read_text())
history = dict(
    schema='csr-prior-common-case-history-v8', new_execution=False,
    actual_owner_matlab_execution=True, prior_history=prior,
    cases=[json.loads((base / 'data/L_discovery_lifecycle/case_summary.json').read_text())],
    successful_prior_preflights=['Native CSV import', 'Accepted natural A reuse', 'All61 component checks including discovery lifecycle'],
    diagnosis='L passed61 checks and matched487TX and2729draws before node3watchdog116.340299163 manufactured a new discovery member from a late route. Its extra31byteSNMP_START final7 via5 failed at116.415; native next node3TX is application DATA at300.365. Watchdog expiry itself is correct.',
    source_issued_manifest_sha256=hashlib.sha256((previous / 'FILES.json').read_bytes()).hexdigest(),
    evidence_folders=['ref/history/L_discovery_lifecycle'], new_cases=['M_discovery_membership'],
)
(root / 'ref/history/history.json').write_text(json.dumps(history, indent=2) + '\n')
print('Runner retains61checks and K timing exports; only new M is executed after accepted A.')
