from pathlib import Path
import json,hashlib,shutil
root=Path(__file__).resolve().parents[1]/'kit/autocase'
p=root/'run_autonomous_tests.m';s=(Path(__file__).resolve().parents[2]/'autonomous_fifth/kit/autocase/run_autonomous_tests.m').read_text()
def edit(a,b):
 global s
 assert s.count(a)==1,(a[:120],s.count(a));s=s.replace(a,b)
edit('%RUN_AUTONOMOUS_TESTS Accepted natural gate plus two coupled diagnostic cases.','%RUN_AUTONOMOUS_TESTS Accepted natural gate plus control-wire diagnostic.')
edit("fprintf('G tests MAC population publication; H also separates route admission from direct observation.\\n');", "fprintf('I retains H and tests native REQUEST and NoPath wire representation.\\n');")
edit("        'G_population','Prior F plus event-owned MAC population publication', ...\n        'H_admission_route','G plus route admission without inventing an unobserved direct candidate');", "        'I_control_wire','Prior H plus compact REQUEST and metadata-only NoPath target sizing');")
edit("        second=runCase(root,out,config,'G_population','native');\n        report.cases(end+1)=second;\n        % A diagnostic stop in G must not suppress independent case H.\n        third=runCase(root,out,config,'H_admission_route','native');\n        report.cases(end+1)=third;", "        fprintf('Checking generated compact REQUEST ownership, retries and unchanged raw ARL sizing.\\n');\n        report.request_wire_preflight=ac.requestWirePreflight(config,fullfile(out,'request_preflight'));\n        report.no_path_wire_preflight=ac.noPathWirePreflight(config,fullfile(out,'no_path_preflight'));\n        second=runCase(root,out,config,'I_control_wire','native');\n        report.cases(end+1)=second;")
edit('Cases G and H skipped: natural source-fidelity gate did not pass.','Case I skipped: natural source-fidelity gate did not pass.')
edit('report.completed=numel(report.cases)==3 && all([report.cases.completed]);','report.completed=numel(report.cases)==2 && all([report.cases.completed]);')
edit("    if strcmp(name,'G_population')\n        simulation=ac.PopulationSimulation(config,observer,timing,options);\n    elseif strcmp(name,'H_admission_route')\n        simulation=ac.AdmissionSimulation(config,observer,timing,options);", "    if strcmp(name,'I_control_wire')\n        simulation=ac.ControlWireSimulation(config,observer,timing,options);")
p.write_text(s)
for name in ['G_population','H_admission_route']:
 shutil.copytree(root.parents[1]/'data'/name,root/'ref/history'/name,dirs_exist_ok=True)
prior=json.loads((Path(__file__).resolve().parents[2]/'autonomous_fifth/kit/autocase/ref/history/history.json').read_text())
history=dict(schema='csr-prior-common-case-history-v4',new_execution=False,actual_owner_matlab_execution=True,prior_history=prior,
 cases=[json.loads((root/'ref/history'/name/'case_summary.json').read_text()) for name in ['G_population','H_admission_route']],
 successful_prior_preflights=['Native CSV import','Accepted natural A reuse','All7 KEY_REQUEST checks','All8 neighbor-condition checks','All6 population checks','All8 route-admission checks'],
 diagnosis='G cleared the earlier MAC population guard and exposed the predicted extra DELETE at14.534. H removed that extra control and reached25.298, where two compatibility-header REQUESTs were charged23bytes each instead of native16; ordered payload semantics matched.',
 source_issued_manifest_sha256=hashlib.sha256(Path('autonomous_fifth/kit/autocase/FILES.json').read_bytes()).hexdigest(),
 evidence_folders=['ref/history/G_population','ref/history/H_admission_route'],new_cases=['I_control_wire'])
(root/'ref/history/history.json').write_text(json.dumps(history,indent=2)+'\n')
print('Runner set to A gate + preflights + I; G/H actual results retained as history.')
