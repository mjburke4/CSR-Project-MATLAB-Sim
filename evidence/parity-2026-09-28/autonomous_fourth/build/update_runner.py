from pathlib import Path
import json,hashlib,shutil
root=Path(__file__).resolve().parents[1]/'kit'/'autocase'
p=root/'run_autonomous_tests.m';s=p.read_text()
def edit(a,b):
 global s
 assert s.count(a)==1,(a[:100],s.count(a));s=s.replace(a,b)
edit("fprintf('C tests receiver callback timing; D adds only synchronous no-ACK KEY_REQUEST admission.\\n');",
 "fprintf('E tests Overheard eligibility; F also tests Message-only admission-proof flag ownership.\\n');")
edit("        'C_timing','Native random inputs with existing nanosecond receiver callback option', ...\n        'D_inline_key','Same timing option plus isolated fresh no-ACK KEY_REQUEST admission candidate');",
 "        'E_check_gate','Prior D plus deadline-only Overheard eligibility', ...\n        'F_message_flag','E plus set the Message-active flag only for Message subtype');")
edit("        second=runCase(root,out,config,'C_timing','native');\n        report.cases(end+1)=second;\n        % A diagnostic stop in C must not suppress the independent candidate.\n        third=runCase(root,out,config,'D_inline_key','native');\n        report.cases(end+1)=third;",
 "        fprintf('Checking independent discovery, Overheard and Message proof conditions.\\n');\n        report.check_gate_preflight=ac.checkGatePreflight(config,fullfile(out,'check_preflight'));\n        second=runCase(root,out,config,'E_check_gate','native');\n        report.cases(end+1)=second;\n        % A diagnostic stop in E must not suppress independent case F.\n        third=runCase(root,out,config,'F_message_flag','native');\n        report.cases(end+1)=third;")
edit("Cases C and D skipped: natural source-fidelity gate did not pass.","Cases E and F skipped: natural source-fidelity gate did not pass.")
edit("    if strcmp(name,'D_inline_key')\n        simulation=ac.InlineKeySimulation(config,observer,timing,options);\n    else",
 "    if strcmp(name,'E_check_gate')\n        simulation=ac.CheckGateSimulation(config,observer,timing,options);\n    elseif strcmp(name,'F_message_flag')\n        simulation=ac.MessageFlagSimulation(config,observer,timing,options);\n    else")
p.write_text(s)
for name in ['C_timing','D_inline_key']:
 source=root.parents[1]/'data'/name
 shutil.copytree(source,root/'ref/history'/name,dirs_exist_ok=True)
prior=json.loads((root/'ref/history/history.json').read_text())
history=dict(schema='csr-prior-common-case-history-v2',new_execution=False,
 actual_owner_matlab_execution=True,prior_B=prior,
 cases=[json.loads((root/'ref/history'/name/'case_summary.json').read_text()) for name in ['C_timing','D_inline_key']],
 successful_prior_preflights=['Native CSV import','Accepted natural A reuse','All 7 KEY_REQUEST checks'],
 diagnosis='Both C and D stopped at12.402 seconds with node5 TX3 containing ACK1, ACK3 and discovery-check3 (66 bytes), missing native Overheard-check4 (16 bytes). D removed the earlier KEY_REQUEST request-time mismatch. These are historical actual owner cases, not rerun by this kit.',
 source_issued_manifest_sha256=hashlib.sha256(Path('autonomous_third/kit/autocase/FILES.json').read_bytes()).hexdigest(),
 evidence_folders=['ref/history/C_timing','ref/history/D_inline_key'],new_cases=['E_check_gate','F_message_flag'])
(root/'ref/history/history.json').write_text(json.dumps(history,indent=2)+'\n')
print('Runner executes A gate, preflights, independent E/F; historical C/D are retained.')
