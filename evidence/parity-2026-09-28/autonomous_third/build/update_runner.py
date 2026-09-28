from pathlib import Path
root=Path(__file__).resolve().parents[1]/'kit'/'autocase'
p=root/'run_autonomous_tests.m'
s=p.read_text()
def edit(old,new):
 global s
 assert s.count(old)==1,(old[:100],s.count(old))
 s=s.replace(old,new)
edit('%RUN_AUTONOMOUS_TESTS One short natural capture plus fully coupled draw replay.',
 '%RUN_AUTONOMOUS_TESTS Accepted natural gate plus two coupled diagnostic cases.')
edit("fprintf('All seven nodes warm up from time zero. No receiver state or feedback is replayed.\\n');", 
 "fprintf('All seven nodes warm up from time zero. No receiver state or feedback is replayed.\\n');\nfprintf('C tests receiver callback timing; D adds only synchronous no-ACK KEY_REQUEST admission.\\n');")
edit("    resolved=bindSource(root,manifest.files);", "    resolved=bindSource(root,manifest.files);\n    report.case_design=struct('A_natural','Accepted natural run reused if exact gates match; otherwise fresh natural run', ...\n        'C_timing','Native random inputs with existing nanosecond receiver callback option', ...\n        'D_inline_key','Same timing option plus isolated fresh no-ACK KEY_REQUEST admission candidate');\n    report.previous_common_case=jsondecode(fileread(fullfile(root,'ref','history','history.json')));\n    ac.writeJson(fullfile(out,'previous_case_history.json'),report.previous_common_case);")
edit("        'source_transform',jsondecode(fileread(fullfile(root,'source_transform.json')))));", 
 "        'source_transform',jsondecode(fileread(fullfile(root,'source_transform.json'))), ...\n        'candidate_transform',jsondecode(fileread(fullfile(root,'candidate_transform.json')))));" )
edit("    if first.completed && first.natural_prefix_passed\n        second=runCase(root,out,config,'B_common','native');\n        report.cases(end+1)=second;\n    else\n        fprintf('\\nCase B skipped: natural source-fidelity gate did not pass. Return this ZIP.\\n');\n    end\n    verifyFiles(root,manifest.files);\n    report.completed=numel(report.cases)==2 && all([report.cases.completed]);",
 "    if first.completed && first.natural_prefix_passed\n        fprintf('Checking isolated KEY_REQUEST admission, replacement, capacity and callback ownership.\\n');\n        report.key_request_preflight=ac.keyRequestPreflight(config,fullfile(out,'key_preflight'));\n        second=runCase(root,out,config,'C_timing','native');\n        report.cases(end+1)=second;\n        % A diagnostic stop in C must not suppress the independent candidate.\n        third=runCase(root,out,config,'D_inline_key','native');\n        report.cases(end+1)=third;\n    else\n        fprintf('\\nCases C and D skipped: natural source-fidelity gate did not pass. Return this ZIP.\\n');\n    end\n    verifyFiles(root,manifest.files);\n    report.completed=numel(report.cases)==3 && all([report.cases.completed]);")
edit("fprintf('\\n%s starting. A divergence in B is a diagnostic result, not a parity pass.\\n',name);\ntry\n    simulation=csr.sim.NetworkSimulation(config,observer,[],options);",
 "timing=[];\nfprintf('\\n%s starting. A semantic divergence is a diagnostic result, not a parity pass.\\n',name);\ntry\n    if strcmp(mode,'native'), timing=csr.sim.TransportTiming('nanoseconds',200000); end\n    if strcmp(name,'D_inline_key')\n        simulation=ac.InlineKeySimulation(config,observer,timing,options);\n    else\n        simulation=csr.sim.NetworkSimulation(config,observer,timing,options);\n    end")
edit("ac.Trace.close(); item.wall_seconds=toc(started);", "if ~isempty(timing)\n    try\n        timingStatus=timing.snapshot();\n        writetable(timingStatus.Records,fullfile(folder,'transport_timing.csv'));\n        ac.writeJson(fullfile(folder,'transport_timing_summary.json'),rmfield(timingStatus,'Records'));\n    catch caught\n        item.completed=false; item.diagnostic_status='unexpected_harness_error';\n        ac.writeJson(fullfile(folder,'transport_export_error.json'),struct('message',caught.message));\n    end\nend\nac.Trace.close(); item.wall_seconds=toc(started);")
p.write_text(s)
print('Runner C/D updated; natural case and prefix comparator unchanged.')
