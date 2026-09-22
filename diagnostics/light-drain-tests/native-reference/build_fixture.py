#!/usr/bin/env python3
"""Build a fixture-only runner with a strict generator cutoff; models unchanged."""
from pathlib import Path
import hashlib,json,subprocess,difflib,time
ROOT=Path(__file__).resolve().parent
WORK=ROOT.parent
SOURCE=WORK/'ns3-repo/csr-opnet-scenario-runner.cc'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 baseline=json.loads((WORK/'native-latency/build-receipt.json').read_text())
 original=SOURCE.read_text(); text=original
 # A default-zero override only changes arguments for opt-in fixture runs.
 text=text.replace('  double stopSeconds = 0.0;','  double stopSeconds = 0.0;\n  double trafficStopSeconds = 0.0;')
 needle='  command.AddValue ("stop", "Stop time in seconds (0 uses imported duration)", stopSeconds);'
 assert needle in text
 text=text.replace(needle,needle+'\n  command.AddValue ("trafficStop", "Fixture-only exclusive application generation cutoff (0 uses simulation stop)", trafficStopSeconds);')
 needle='  // br_app schedules its next generator interrupt before applying these'
 assert needle in text
 text=text.replace(needle,'  // Fixture cutoff: attempt interval is half-open [start, generation stop).\n  if (Simulator::Now ().GetSeconds () >= stopSeconds)\n    {\n      return;\n    }\n\n'+needle)
 needle='  std::vector<std::shared_ptr<FlowRuntimeState>> flowStates;'
 assert needle in text
 text=text.replace(needle,'  NS_ABORT_MSG_IF (!std::isfinite (trafficStopSeconds) || trafficStopSeconds < 0.0 ||\n                   trafficStopSeconds > stopSeconds, "invalid fixture traffic cutoff");\n  const double generationStopSeconds = trafficStopSeconds > 0.0 ? trafficStopSeconds : stopSeconds;\n\n'+needle)
 needle='                           nodes.at (flow.source).network,\n                           flow,\n                           flowIndex,\n                           stopSeconds,'
 assert needle in text
 text=text.replace(needle,needle.replace('stopSeconds,','generationStopSeconds,'))
 target=ROOT/'drain-scenario-runner.cc';target.write_text(text)
 (ROOT/'fixture.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='a/csr-opnet-scenario-runner.cc',tofile='b/drain-scenario-runner.cc')))
 cmd=list(baseline['runner_compile']['argv']);cmd[cmd.index(str(SOURCE))]=str(target);cmd[-1]=str(ROOT/'drain-scenario-runner')
 t=time.monotonic()
 with (ROOT/'build.log').open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
 assert r.returncode==0
 receipt={'schema':'light-drain-native-fixture-v1','status':'built-inert-check-pending','production_source_unchanged':sha(SOURCE)==baseline['inputs'][str(SOURCE)],'source_commit':baseline['source_commit'],'baseline_build_receipt_sha256':sha(WORK/'native-latency/build-receipt.json'),'baseline_runner_sha256':baseline['runner_sha256'],'fixture_source_sha256':sha(target),'runner_sha256':sha(ROOT/'drain-scenario-runner'),'patch_sha256':sha(ROOT/'fixture.patch'),'argv':cmd,'exit_code':r.returncode,'wall_seconds':time.monotonic()-t,'libraries':baseline['libraries']}
 assert receipt['production_source_unchanged']
 (ROOT/'fixture-build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print('built',receipt['wall_seconds'])
if __name__=='__main__':main()
