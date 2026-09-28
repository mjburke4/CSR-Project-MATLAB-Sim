from pathlib import Path
import json,hashlib,shutil
base=Path(__file__).resolve().parents[1];root=base/'kit/autocase';previous=base.parent/'autonomous_seventh/kit/autocase'
s=(previous/'run_autonomous_tests.m').read_text()
def edit(a,b):
 global s
 assert s.count(a)==1,(a[:110],s.count(a));s=s.replace(a,b)
edit('%RUN_AUTONOMOUS_TESTS Accepted natural gate plus DISCOVER identity diagnostic.','%RUN_AUTONOMOUS_TESTS Accepted natural gate plus native relative-timer diagnostic.')
edit("fprintf('J retains I behavior and distinguishes the trace-only outer DISCOVER identifier.\\n');", "fprintf('K retains J and corrects native relative receiver timers plus paired TX completion.\\n');")
edit("        'J_discovery_identity','Unchanged I protocol; eligible broadcast DISCOVER outer identity recorded separately');", "        'K_receiver_timers','Prior J with native integer-nanosecond acquisition/rejected-return and paired PHY/MAC TX completion targets');")
edit("        second=runCase(root,out,config,'J_discovery_identity','native');", "        fprintf('Checking relative timer targets, live callback boundaries and all native PHY arithmetic contexts.\\n');\n        report.receiver_timer_preflight=ac.receiverTimerPreflight(root,config,fullfile(out,'timer_preflight'));\n        second=runCase(root,out,config,'K_receiver_timers','native');")
edit('Case J skipped: natural source-fidelity gate did not pass.','Case K skipped: natural source-fidelity gate did not pass.')
edit("    if strcmp(name,'J_discovery_identity')\n        simulation=ac.DiscoveryIdentitySimulation(config,observer,timing,options);", "    if strcmp(name,'K_receiver_timers')\n        simulation=ac.ReceiverTimerSimulation(config,observer,timing,options);")
edit("    if strcmp(mode,'native')\n        randomStatus=simulation.autonomousRandomSummary();", "    if strcmp(name,'K_receiver_timers')\n        timerStatus=simulation.autonomousReceiverTimingSummary();\n        assert(timerStatus.Omitted==0,'autocase:Omitted','Relative timer evidence was truncated.');\n    end\n    if strcmp(mode,'native')\n        randomStatus=simulation.autonomousRandomSummary();")
edit("if ~isempty(timing)\n    try\n        timingStatus=timing.snapshot();", """if exist('simulation','var') && strcmp(name,'K_receiver_timers')
    try
        relativeStatus=simulation.autonomousReceiverTimingSummary();
        writetable(relativeStatus.Records,fullfile(folder,'receiver_timing.csv'));
        ac.writeJson(fullfile(folder,'receiver_timing_summary.json'),rmfield(relativeStatus,'Records'));
        assert(relativeStatus.Omitted==0,'autocase:Omitted','Relative timer evidence was truncated.');
    catch caught
        item.completed=false; item.diagnostic_status='unexpected_harness_error';
        ac.writeJson(fullfile(folder,'receiver_timing_export_error.json'),struct('message',caught.message));
    end
end
if ~isempty(timing)
    try
        timingStatus=timing.snapshot();""")
(root/'run_autonomous_tests.m').write_text(s)
shutil.copytree(base/'data/J_discovery_identity',root/'ref/history/J_discovery_identity',dirs_exist_ok=True)
prior=json.loads((previous/'ref/history/history.json').read_text())
history=dict(schema='csr-prior-common-case-history-v6',new_execution=False,actual_owner_matlab_execution=True,prior_history=prior,
 cases=[json.loads((base/'data/J_discovery_identity/case_summary.json').read_text())],
 successful_prior_preflights=['Native CSV import','Accepted natural A reuse','All45 component checks including discovery identity'],
 diagnosis='J passed45 component checks and reached45.662638077: node3PHY draw75 payload52bits versus native51. Acquisition callback double-addition endpoint was oneULP higher than native integer-nanosecond target despite identical rounded nanoseconds; payload geometry/truncation and BER match.',
 source_issued_manifest_sha256=hashlib.sha256((previous/'FILES.json').read_bytes()).hexdigest(),
 evidence_folders=['ref/history/J_discovery_identity'],new_cases=['K_receiver_timers'])
(root/'ref/history/history.json').write_text(json.dumps(history,indent=2)+'\n')
print('Runner set to A/old45checks/newtimerpreflight/K only; receiver timing exports survive diagnostic stop.')
