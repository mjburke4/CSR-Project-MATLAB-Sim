"""Static release audit for the two occurrence-aware NWK implementations."""
from pathlib import Path
import difflib, hashlib, json, re, sys
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
CURRENT=ROOT/'relay_custody/kit/node8case'
BASE=ROOT/'node8_return/kit/node8case'
FILES=['model/+csr/+nwk/Layer.m','+ac/DiscoveryMembershipNwk.m']
sys.path.insert(0,str(ROOT/'node8_1200/build/python'))
from tree_sitter import Language, Parser
import tree_sitter_matlab
parser=Parser(Language(tree_sitter_matlab.language()))
methods=['receiveData','enqueueApplication','pendingPosition','custodyCount','release','releaseFromHop','terminal','pump','deliverLocal']
def extract(text, name):
    pattern=r'^        function [^\n]*\b'+re.escape(name)+r'\([^\n]*\n'
    found=re.search(pattern,text,re.M)
    assert found,name
    end=re.search(r'^        function |^    end\n',text[found.end():],re.M)
    assert end,name
    return text[found.start():found.end()+end.start()]
texts=[(CURRENT/f).read_text() for f in FILES]
checks={f'{method}_identical':extract(texts[0],method)==extract(texts[1],method) for method in methods}
rows=[]
for file,text in zip(FILES,texts):
    raw=(CURRENT/file).read_bytes(); old=(BASE/file).read_bytes()
    syntax_clean=not parser.parse(raw).root_node.has_error
    checks[file+'_syntax_clean']=syntax_clean
    rows.append({'path':file,'baseline_sha256':hashlib.sha256(old).hexdigest(),'candidate_sha256':hashlib.sha256(raw).hexdigest(),'syntax_clean':syntax_clean})
    (OUT/(Path(file).stem+'_occurrences.patch')).write_text(''.join(difflib.unified_diff(old.decode().splitlines(True),text.splitlines(True),fromfile='baseline/'+file,tofile='candidate/'+file)))
report={'schema':'csr-relay-custody-core-static-review-v1','passed':all(checks.values()),'checks':checks,'files':rows,'runtime_execution':False,'limitations':'Static parser and source-method parity only. Focused MATLAB preflight and common-input replay must run on the user runtime.'}
(OUT/'core_static_review.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
assert report['passed']
