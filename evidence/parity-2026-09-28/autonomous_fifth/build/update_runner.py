from pathlib import Path
import json,hashlib,shutil
root=Path(__file__).resolve().parents[1]/'kit'/'autocase';p=root/'run_autonomous_tests.m';s=p.read_text()
def edit(a,b):
 global s
 assert s.count(a)==1,(a[:120],s.count(a));s=s.replace(a,b)
edit("fprintf('E tests Overheard eligibility; F also tests Message-only admission-proof flag ownership.\\n');", "fprintf('G tests MAC population publication; H also separates route admission from direct observation.\\n');")
edit("        'E_check_gate','Prior D plus deadline-only Overheard eligibility', ...\n        'F_message_flag','E plus set the Message-active flag only for Message subtype');", "        'G_population','Prior F plus event-owned MAC population publication', ...\n        'H_admission_route','G plus route admission without inventing an unobserved direct candidate');")
edit("        second=runCase(root,out,config,'E_check_gate','native');\n        report.cases(end+1)=second;\n        % A diagnostic stop in E must not suppress independent case F.\n        third=runCase(root,out,config,'F_message_flag','native');\n        report.cases(end+1)=third;", "        fprintf('Checking population publication and route-admission ownership.\\n');\n        report.population_preflight=ac.populationPreflight(config,fullfile(out,'population_preflight'));\n        report.route_admission_preflight=ac.routeAdmissionPreflight(config,fullfile(out,'route_preflight'));\n        second=runCase(root,out,config,'G_population','native');\n        report.cases(end+1)=second;\n        % A diagnostic stop in G must not suppress independent case H.\n        third=runCase(root,out,config,'H_admission_route','native');\n        report.cases(end+1)=third;")
edit('Cases E and F skipped: natural source-fidelity gate did not pass.','Cases G and H skipped: natural source-fidelity gate did not pass.')
edit("    if strcmp(name,'E_check_gate')\n        simulation=ac.CheckGateSimulation(config,observer,timing,options);\n    elseif strcmp(name,'F_message_flag')\n        simulation=ac.MessageFlagSimulation(config,observer,timing,options);", "    if strcmp(name,'G_population')\n        simulation=ac.PopulationSimulation(config,observer,timing,options);\n    elseif strcmp(name,'H_admission_route')\n        simulation=ac.AdmissionSimulation(config,observer,timing,options);")
p.write_text(s)
for name in ['E_check_gate','F_message_flag']:
 shutil.copytree(root.parents[1]/'data'/name,root/'ref/history'/name,dirs_exist_ok=True)
prior=json.loads((root/'ref/history/history.json').read_text())
history=dict(schema='csr-prior-common-case-history-v3',new_execution=False,actual_owner_matlab_execution=True,prior_history=prior,
 cases=[json.loads((root/'ref/history'/name/'case_summary.json').read_text()) for name in ['E_check_gate','F_message_flag']],
 successful_prior_preflights=['Native CSV import','Accepted natural A reuse','All7 KEY_REQUEST checks','All8 neighbor-condition checks'],
 diagnosis='Both E/F stopped at14.534 node1 MACdraw8: prematurely published local population3 versus native latch2. Current NWK count3 is correct. Same returned prefix also contains an extra grouped routing control after peer3 admission.',
 source_issued_manifest_sha256=hashlib.sha256(Path('autonomous_fourth/kit/autocase/FILES.json').read_bytes()).hexdigest(),
 evidence_folders=['ref/history/E_check_gate','ref/history/F_message_flag'],new_cases=['G_population','H_admission_route'])
(root/'ref/history/history.json').write_text(json.dumps(history,indent=2)+'\n')
print('Runner set to A gate + preflights + independent G/H; historical E/F retained.')
