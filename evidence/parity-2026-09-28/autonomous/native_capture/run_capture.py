#!/usr/bin/env python3
"""Execute the passive 0--330 s capture and require exact native prefix."""
from pathlib import Path
import os,subprocess,sys,json,hashlib

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
RUN=HERE/'run'
def main():
    cmd=[str(RUN/'autonomous-capture'),
       '--scenario='+str(HERE/'fixture/scenario_s132.csv'),
       '--trace='+str(RUN/'ns3-trace.csv'),
       '--appDiagnostics='+str(RUN/'app-admission.csv'),
       '--stop=330','--flowLimit=0','--dutyCycling=1','--opnetAlignedDutyCycle=1',
       '--gatewayDiscovery=1','--opnetAppGating=1','--aggregateTraceOnly=0',
       '--admissionTrace=1','--quietModelLogs=0','--stochasticSyncThreshold=1']
    env=dict(os.environ,CSR_MAC_CAPTURE=str(RUN/'mac-input.log'),
             CSR_SOURCE5_CAPTURE=str(RUN/'observations.tsv'))
    (HERE/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
    with (RUN/'run.log').open('w') as f:
        subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
    subprocess.run([sys.executable,str(HERE/'normalize.py')],check=True)
    print('Full passive autonomous capture verified.')
if __name__=='__main__': main()
