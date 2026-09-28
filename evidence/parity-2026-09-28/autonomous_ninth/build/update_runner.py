from pathlib import Path
import hashlib
import json
import shutil

base = Path(__file__).resolve().parents[1]
root = base / 'kit/autocase'
previous = base.parent / 'autonomous_eighth/kit/autocase'
text = (previous / 'run_autonomous_tests.m').read_text()

def edit(old, new):
    global text
    assert text.count(old) == 1, (old[:110], text.count(old))
    text = text.replace(old, new)

edit('%RUN_AUTONOMOUS_TESTS Accepted natural gate plus native relative-timer diagnostic.',
     '%RUN_AUTONOMOUS_TESTS Accepted natural gate plus discovery-lifecycle diagnostic.')
edit("fprintf('K retains J and corrects native relative receiver timers plus paired TX completion.\\n');",
     "fprintf('L retains K and corrects active SNMP requester ownership plus inline KEY_UPDATE admission.\\n');")
edit("        'K_receiver_timers','Prior J with native integer-nanosecond acquisition/rejected-return and paired PHY/MAC TX completion targets');",
     "        'L_discovery_lifecycle','Prior K with idle-only SNMP requester completion and inline reliable KEY_UPDATE ownership');")
edit("        second=runCase(root,out,config,'K_receiver_timers','native');",
     "        fprintf('Checking discovery requester lifecycle and reliable key-update admission boundaries.\\n');\n"
     "        report.discovery_lifecycle_preflight=ac.discoveryLifecyclePreflight(config,fullfile(out,'lifecycle_preflight'));\n"
     "        second=runCase(root,out,config,'L_discovery_lifecycle','native');")
edit('Case K skipped: natural source-fidelity gate did not pass.',
     'Case L skipped: natural source-fidelity gate did not pass.')
edit('simulation=ac.ReceiverTimerSimulation(config,observer,timing,options);',
     'simulation=ac.DiscoveryLifecycleSimulation(config,observer,timing,options);')
assert text.count("strcmp(name,'K_receiver_timers')") == 3
text = text.replace("strcmp(name,'K_receiver_timers')", "strcmp(name,'L_discovery_lifecycle')")
(root / 'run_autonomous_tests.m').write_text(text)
shutil.copytree(base / 'data/K_receiver_timers', root / 'ref/history/K_receiver_timers', dirs_exist_ok=True)
prior = json.loads((previous / 'ref/history/history.json').read_text())
history = dict(
    schema='csr-prior-common-case-history-v7', new_execution=False,
    actual_owner_matlab_execution=True, prior_history=prior,
    cases=[json.loads((base / 'data/K_receiver_timers/case_summary.json').read_text())],
    successful_prior_preflights=['Native CSV import', 'Accepted natural A reuse', 'All53 component checks including receiver timers'],
    diagnosis='K passed53 checks and stopped71.942 at node5TX68: SNMP_START hop/final destination4/2 versusnative1/1. Earlier node4MACdraw25 was10.166368ms late because KEY_UPDATE was deferred beyond Track exit. Both causes are source-confirmed; strict guards remain unchanged.',
    source_issued_manifest_sha256=hashlib.sha256((previous / 'FILES.json').read_bytes()).hexdigest(),
    evidence_folders=['ref/history/K_receiver_timers'], new_cases=['L_discovery_lifecycle'],
)
(root / 'ref/history/history.json').write_text(json.dumps(history, indent=2) + '\n')
print('Runner retains53checks and K timing exports; only new L is executed after accepted A.')
