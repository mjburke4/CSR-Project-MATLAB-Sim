from pathlib import Path
import subprocess,json,sys,time
R=Path(__file__).resolve().parent;K=R.parent/'latency-tests';S=R.parent/'ns3-repo';B=R/'engine/build'
results=[]
def run(args,name):
 start=time.monotonic()
 with (R/(name+'.log')).open('w') as f:r=subprocess.run(list(map(str,args)),stdout=f,stderr=subprocess.STDOUT)
 rec={'stage':name,'argv':list(map(str,args)),'exit_code':r.returncode,'seconds':time.monotonic()-start}
 results.append(rec);(R/'execution.json').write_text(json.dumps(results,indent=2)+'\n');print(name,r.returncode,round(rec['seconds'],2),flush=True)
 return r.returncode
for fixture in ['mac','replay']:
 run([sys.executable,K/fixture/'run_native.py','--ns3-source',S,'--ns3-build',B,'--output',R/('native-'+fixture)],fixture)
if (R/'native-mac/events.csv').exists():run([sys.executable,K/'mac/compare_mac.py',R/'matlab-fixtures/mac-events.csv',R/'native-mac/events.csv','--output',R/'mac-comparison.json'],'compare-mac')
if (R/'native-replay/hop.csv').exists():run([sys.executable,K/'replay/compare_hop_replay.py',R/'matlab-fixtures/hop.csv',R/'native-replay/hop.csv','--output',R/'hop-comparison.json'],'compare-hop')
run([sys.executable,K/'load/run_load_native.py','--runner',R/'csr-opnet-scenario-runner','--build-receipt',R/'build-receipt.json','--output',R/'native-load'],'load')
