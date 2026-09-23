#!/usr/bin/env python3
import pathlib,subprocess,json,os,time,csv,gzip,itertools,hashlib
R=pathlib.Path(__file__).resolve().parents[2];N=R/'receiver_replay/native';B=R/'startup131/environment/engine/build';O=N/'overlay';D=N/'capture';D.mkdir(exist_ok=True)
cmd=['g++','-std=c++23','-O0','-g','-DNS3_ASSERT_ENABLE','-DNS3_BUILD_PROFILE_DEBUG','-DNS3_LOG_ENABLE','-DSTACKTRACE_LIBRARY_IS_LINKED=1','-D__LINUX__','-I'+str(O),'-I'+str(B/'include'),str(N/'capture.cc'),'-L'+str(B/'lib'),'-Wl,-rpath,'+str(B/'lib'),'-Wl,--no-as-needed','-lns3-dev-csr-debug','-Wl,--as-needed']+['-lns3-dev-'+n+'-debug' for n in ['spectrum','buildings','propagation','mobility','antenna','network','stats','core']]+['-lstdc++exp','-o',str(N/'capture-exe')]
with (D/'compile.log').open('w') as f:p=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
assert p.returncode==0,(D/'compile.log').read_text()[-12000:]
A=R/'original_extracted/t25up/evidence/tranche-25-ns3-reference/s132';cmd=[str(N/'capture-exe'),'--scenario='+str(A/'scenario.csv'),'--trace='+str(D/'ns3-trace.csv'),'--appDiagnostics='+str(D/'app-admission.csv'),'--stop=675','--flowLimit=0','--dutyCycling=1','--opnetAlignedDutyCycle=1','--gatewayDiscovery=1','--opnetAppGating=1','--aggregateTraceOnly=0','--admissionTrace=1','--quietModelLogs=0','--stochasticSyncThreshold=1']
env=dict(os.environ,CSR_REPLAY_CAPTURE=str(D/'receiver-input.log'));start=time.monotonic()
with (D/'run.log').open('w') as f:p=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
assert p.returncode==0
with gzip.open(A/'ns3-trace.csv.gz','rt') as f,(D/'ns3-trace.csv').open() as g:
 rr=csv.DictReader(f);ar=csv.DictReader(g);assert rr.fieldnames==ar.fieldnames;count=0
 for x,y in itertools.zip_longest(itertools.takewhile(lambda r:float(r['time_s'])<675,rr),itertools.takewhile(lambda r:float(r['time_s'])<675,ar)):
  assert x==y,(count,x,y);count+=1
receipt=dict(exact_prefix=True,rows=count,fields=rr.fieldnames,seconds=time.monotonic()-start,command=cmd)
(D/'prefix-equality.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt)
