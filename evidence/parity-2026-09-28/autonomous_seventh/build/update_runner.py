from pathlib import Path
import json,hashlib,shutil
base=Path(__file__).resolve().parents[1];root=base/'kit/autocase';previous=base.parent/'autonomous_sixth/kit/autocase'
s=(previous/'run_autonomous_tests.m').read_text()
def edit(a,b):
 global s
 assert s.count(a)==1,(a[:120],s.count(a));s=s.replace(a,b)
edit('%RUN_AUTONOMOUS_TESTS Accepted natural gate plus control-wire diagnostic.','%RUN_AUTONOMOUS_TESTS Accepted natural gate plus DISCOVER identity diagnostic.')
edit("fprintf('I retains H and tests native REQUEST and NoPath wire representation.\\n');", "fprintf('J retains I behavior and distinguishes the trace-only outer DISCOVER identifier.\\n');")
edit("        'I_control_wire','Prior H plus compact REQUEST and metadata-only NoPath target sizing');", "        'J_discovery_identity','Unchanged I protocol; eligible broadcast DISCOVER outer identity recorded separately');")
edit("        second=runCase(root,out,config,'I_control_wire','native');", "        fprintf('Checking the exact prior frame and strict comparator exclusion boundaries.\\n');\n        report.discovery_identity_preflight=ac.discoveryIdentityPreflight(root,fullfile(out,'identity_preflight'));\n        second=runCase(root,out,config,'J_discovery_identity','native');")
edit('Case I skipped: natural source-fidelity gate did not pass.','Case J skipped: natural source-fidelity gate did not pass.')
edit("    if strcmp(name,'I_control_wire')\n        simulation=ac.ControlWireSimulation(config,observer,timing,options);", "    if strcmp(name,'J_discovery_identity')\n        simulation=ac.DiscoveryIdentitySimulation(config,observer,timing,options);")
(root/'run_autonomous_tests.m').write_text(s)
shutil.copytree(base/'data/I_control_wire',root/'ref/history/I_control_wire',dirs_exist_ok=True)
prior=json.loads((previous/'ref/history/history.json').read_text())
history=dict(schema='csr-prior-common-case-history-v5',new_execution=False,actual_owner_matlab_execution=True,prior_history=prior,
 cases=[json.loads((base/'data/I_control_wire/case_summary.json').read_text())],
 successful_prior_preflights=['Native CSV import','Accepted natural A reuse','All7 KEY_REQUEST checks','All8 neighbor-condition checks','All6 population checks','All8 route-admission checks','All6 REQUEST wire checks','All3 NoPath wire checks'],
 diagnosis='I passed all38 component checks and the prior REQUEST wire boundary; at25.74 node3TX17, the sole mismatch is outer DISCOVER HOP identifier1 versus4. Native allocates this trace-only counter across the process; MATLAB uses a per-sender broadcast counter. Payload discovery-session sequence1 and all other aggregate fields match.',
 source_issued_manifest_sha256=hashlib.sha256((previous/'FILES.json').read_bytes()).hexdigest(),
 evidence_folders=['ref/history/I_control_wire'],new_cases=['J_discovery_identity'])
(root/'ref/history/history.json').write_text(json.dumps(history,indent=2)+'\n')
print('Runner retains A and all old component preflights; J new network case only. I actual history copied.')
