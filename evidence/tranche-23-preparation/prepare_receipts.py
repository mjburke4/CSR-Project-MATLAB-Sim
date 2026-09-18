"""Record local static/checker gates, explicitly without MATLAB execution."""
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
W=Path(__file__).resolve().parents[1];R=W/'csr23';O=R/'evidence/tranche-23-preparation'
O.mkdir(exist_ok=True)
env=os.environ.copy();env['PYTHONPATH']=str(W/'t22-work/tooling')
commands=[('matlab-static.log',[sys.executable,'-m','miss_hit_core.mh_style','--no-style',str(R/'run_tranche23_validation.m'),str(R/'+csr/+validation/receiverFeedbackContract.m'),str(R/'tests/TestReceiverFeedbackContract.m')],env),
 ('checker-tests.log',[sys.executable,'-m','unittest','discover','-s',str(R/'scripts/tests'),'-p','test_tranche23_return.py','-v'],None)]
receipts=[]
for name,cmd,e in commands:
 result=subprocess.run(cmd,cwd=W,env=e,text=True,capture_output=True)
 (O/name).write_text(result.stdout+result.stderr)
 receipts.append({'command':cmd,'exit_code':result.returncode,'log':name})
 print(name,result.returncode,(result.stdout+result.stderr)[-300:])
 assert result.returncode==0,name
for name in ['freeze_candidate.py','package_update.py','prepare_receipts.py']:
 shutil.copyfile(W/'t23-work'/name,O/name)
shutil.copyfile(W/'t23-work/matlab-specialist.json',O/'matlab-specialist.json')
shutil.copyfile(W/'t23-work/review/implementation-review.json',O/'implementation-review.json')
(O/'static-checks.json').write_text(json.dumps({'schema':'csr-tranche23-preparation-static-v1',
 'passed':True,'MATLABExecuted':False,'commands':receipts,
 'note':'Python tests may use explicitly synthetic rows; no MATLAB results are asserted.'},indent=2)+'\n')
