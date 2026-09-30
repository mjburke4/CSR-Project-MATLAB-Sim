"""Focused static dependency and returned-gate review; no MATLAB execution."""
from pathlib import Path
import sys, json, re, hashlib, zipfile
BASE=Path(__file__).resolve().parents[2]
KIT=BASE/'node8_return/kit/node8case'
ACCEPTED=BASE/'recovered/short_v2/combinedcase'
RETURN=BASE/'upload/out_node8_20260930_072827.zip'
OUT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
with zipfile.ZipFile(RETURN) as z:
    assert z.testzip() is None
    report=json.loads(z.read('report.json'))
    natural=json.loads(z.read('A_natural/prefix_gate.json'))
    gates=[{'name':r['name'],'passed':r['passed'],'error_identifier':r['error_identifier']} for r in report['preflights']]
    case=report['cases']
    if isinstance(case,list):case=case[0]
    assert len(gates)==17 and [g['name'] for g in gates if not g['passed']]==['retry_policy']
    assert case['diagnostic_status']=='prerequisite_failed' and case['wall_seconds']==0 and not case['completed']
    assert case['import_preflight']['passed'] and natural['passed'] and all(g['passed'] for g in natural['checks'])
    assert not any(n.startswith('S132_1200/') and n.rsplit('/',1)[-1] in ('protocol_trace.csv','ordered_events.jsonl','random_summary.json') for n in z.namelist())
# Verify the sole restored root-level dependency against accepted source and its issued manifest.
test='TestQueuedRetryPolicy.m'
issued=json.loads((ACCEPTED/'FILES.json').read_text())
row=next(x for x in issued['files'] if x['path']==test)
assert (KIT/test).read_bytes()==(ACCEPTED/test).read_bytes()
assert sha(KIT/test)==row['sha256']=='603eef79184d92c5b217039b234c98815c1b68409321da8c18441a4e7c74ccee'
source=[]
for prefix in ('model','+ac'):
    for p in sorted((ACCEPTED/prefix).rglob('*')):
        if not p.is_file():continue
        rel=p.relative_to(ACCEPTED); q=KIT/rel
        assert q.exists() and q.read_bytes()==p.read_bytes(),str(rel)
        source.append({'path':str(rel),'sha256':sha(q)})
assert len(source)==167
old_runner=BASE/'node8_1200/kit/node8case/run_node8_tests.m'
assert (KIT/'run_node8_tests.m').read_bytes()==old_runner.read_bytes()
# Lexical overapproximation: follow all csr./ac. class/function references in each reached file,
# including callback bodies, local methods, class inheritance, and inactive optional-native branches.
files={}
for p in KIT.rglob('*.m'):
    parts=list(p.relative_to(KIT).parts)
    if parts[0]=='model':parts.pop(0)
    key='.'.join(x.lstrip('+') for x in parts)[:-2]
    files[key]=p
seen=set(); pending=['run_node8_tests','TestQueuedRetryPolicy']; unresolved={}
while pending:
    key=pending.pop()
    if key in seen:continue
    seen.add(key)
    for token in re.findall(r'\b(?:ac|csr)(?:\.[A-Za-z]\w*)+',files[key].read_text()):
        parts=token.split('.')
        target=next(('.'.join(parts[:i]) for i in range(len(parts),1,-1) if '.'.join(parts[:i]) in files),None)
        if target is None:unresolved.setdefault(token,[]).append(key)
        elif target not in seen:pending.append(target)
assert not unresolved,unresolved
# Focused scan for runtime-created function/file entry points. The one actual dynamic call is restored.
dynamic=[]
for key in sorted(seen):
    for line,text in enumerate(files[key].read_text().splitlines(),1):
        if re.search(r'\b(?:fromFile|fromFolder|runtests|str2func|feval|eval)\s*\(',text):
            dynamic.append({'source':str(files[key].relative_to(KIT)),'line':line,'text':text.strip()})
assert len(dynamic)==1 and dynamic[0]['source']=='+ac/retryPolicyPreflight.m' and 'TestSuite.fromFile(testFile)' in dynamic[0]['text']
required=['FILES.json','TestQueuedRetryPolicy.m','inputs/s132.csv','model/data/ber_tables.json',
'review/validated_short_v2/return_audit.json','review/validated_short_v2/issued_FILES.json','review/accepted400_tx_starts.csv',
'ref/native/random_draws.csv','ref/native/tx_signatures.csv',
'ref/native132_1200/random_draws.csv','ref/native132_1200/tx_signatures.csv','ref/native132_1200/receipt.json',
'ref/native132_400/tx_signatures.csv','ref/history/I_control_wire/first_divergence.json',
'ref/history/M_discovery_membership/first_divergence.json','ref/receiver_order/native_receiver_order.json',
'ref/receiver_timers/phy_component_fixture.csv','ref/receiver_timers/acquisition_schedule_fixture.csv',
'ref/receiver_timers/native_TX_finish_arithmetic.csv']
required+=['ref/accepted/'+x for x in ['reuse_proof.json','configuration.json','case_summary.json','prefix_gate.json','protocol_trace.csv','phy_trace.csv','application_admission_trace.csv','observer_status.json','random_summary.json']]
required+=['ref/matlab/'+x for x in ['protocol_trace.csv','phy_trace.csv','application_admission_trace.csv']]
proof=json.loads((KIT/'ref/accepted/reuse_proof.json').read_text())
required += ['ref/accepted/'+r['path'] for r in proof['accepted_files']]
required += [r['path'] for r in proof['unchanged_natural_source_files']]
required=sorted(set(required))
for rel in required: assert (KIT/rel).is_file(),rel
# The failing test's 16 methods use local helpers; every named non-MATLAB implementation is bundled.
test_method_text=(KIT/test).read_text().split('methods (Test)',1)[1].split('\nfunction ',1)[0]
methods=re.findall(r'^\s*function\s+(\w+)\(test\)',test_method_text,re.M)
assert len(methods)==16,methods
sys.path.insert(0,str(BASE/'node8_1200/build/python'))
from tree_sitter import Language,Parser
import tree_sitter_matlab
parser=Parser(Language(tree_sitter_matlab.language()))
syntax=[]
for p in sorted(KIT.rglob('*.m')):
    tree=parser.parse(p.read_bytes())
    assert not tree.root_node.has_error,str(p)
    syntax.append({'path':str(p.relative_to(KIT)),'sha256':sha(p)})
assert len(syntax)==166,len(syntax)
result={'schema':'csr-node8-return-dependency-review-v1','status':'pass','matlab_execution_performed':False,
'review_scope':'Package correction and actual entry-point dependencies; no protocol changes and no new network results.',
'failed_return_sha256':sha(RETURN),'failed_return_runtime':report['runtime'],'failed_return_wall_seconds':report['wall_seconds'],
'returned_top_level_preflights':gates,'returned_native1200_import_passed':case['import_preflight']['passed'],
'returned_natural_prefix_checks':natural['checks'],'network_started':False,'new_parity_result_available':False,
'restored_dependency':{'path':test,'sha256':sha(KIT/test),'accepted_source_identical':True,'historical_test_methods':methods},
'unchanged_model_and_candidate_files':len(source),'runner_sha256':sha(KIT/'run_node8_tests.m'),'runner_unchanged':True,
'resolved_lexical_source_closure_files':len(seen),'lexical_source_closure':sorted(seen),'unresolved_csr_ac_symbols':unresolved,
'dynamic_entrypoint_scan':dynamic,'required_file_count':len(required),'required_files':[{'path':x,'sha256':sha(KIT/x)} for x in required if x!='FILES.json'],
'static_matlab_files_parsed':len(syntax),'static_parser':'tree-sitter-matlab','static_parse_errors':[],
'limits':['Source-level closure and static parsing are not MATLAB execution.','Optional native wnet branch is bundled but remains unused by the portable configuration.','This repair adds the exact omitted historical test; it does not rerun or bypass failed gates.'],
'source_files':source,'matlab_files':syntax}
(OUT/'dependency_review.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','network_started','new_parity_result_available','unchanged_model_and_candidate_files','runner_unchanged','resolved_lexical_source_closure_files','required_file_count','static_matlab_files_parsed']}))
