from pathlib import Path
import sys,json,hashlib
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/'node8_1200/build/python'))
from tree_sitter import Language, Parser
import tree_sitter_matlab
parser=Parser(Language(tree_sitter_matlab.language()))
kit=root/'relay_custody/kit/node8case'
files=['+ac/RelayCustodyProbe.m','+ac/relayCustodyPreflight.m']
rows=[]
for rel in files:
 data=(kit/rel).read_bytes(); tree=parser.parse(data)
 rows.append({'path':rel,'sha256':hashlib.sha256(data).hexdigest(),'parse_has_error':tree.root_node.has_error})
r={'schema':'csr-relay-custody-test-static-v1','passed':not any(x['parse_has_error'] for x in rows),
'files':rows,'groups':22,'implementation_pairs':['csr.nwk.Layer / csr.hop.Layer','ac.DiscoveryMembershipNwk / ac.TerminalHop'],
'matlab_execution':False,'dependencies':['csr.sim.EventScheduler','csr.sim.RandomStreams','csr.hop.Frames','csr.nwk.Layer','csr.hop.Layer','ac.DiscoveryMembershipNwk','ac.TerminalHop','ac.writeJson'],
'new_files':files,'limitations':'Static syntax only. Public component behavior must execute on MATLAB; no claim of runtime pass.'}
(root/'relay_custody/test_review/static_tests.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2)); assert r['passed']
