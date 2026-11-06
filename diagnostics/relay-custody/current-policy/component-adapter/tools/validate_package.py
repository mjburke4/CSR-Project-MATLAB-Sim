#!/usr/bin/env python3
"""Static integrity/sanitization checks only. Does not execute MATLAB."""
from pathlib import Path,PurePosixPath
import hashlib,json,re,sys
root=Path(__file__).resolve().parents[1]
checks=0
def check(ok,message):
 global checks
 checks+=1
 if not ok:raise AssertionError(message)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def safe(rel):
 p=PurePosixPath(rel)
 return bool(re.fullmatch(r'[A-Za-z0-9_+./-]+',rel)) and not p.is_absolute() and all(x not in ('','..','.') for x in rel.split('/'))
m=load(root/'PACKAGE_MANIFEST.json')
check(m['schema']=='csr-component-package-v1','manifest schema')
paths=[x['path'] for x in m['files']]
check(len(paths)==len(set(paths)),'unique files')
actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}
check(actual==set(paths)|{'PACKAGE_MANIFEST.json'},'file census')
for item in m['files']:
 rel=item['path'];check(safe(rel),'unsafe path '+rel);p=root/rel
 check(not p.is_symlink() and all(not x.is_symlink() for x in p.parents if x!=root.parent),'symlink '+rel)
 check(p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],'bytes '+rel)
 text=p.read_text(encoding='utf-8')
 check(rel=='tools/validate_package.py' or not re.search(r'(?:(?<![A-Za-z])[A-Za-z]:[\\/]|/Users/|/home/|/workspace/|libfile_|sediment://|BEGIN [A-Z ]*PRIVATE KEY)',text),'private path/identifier '+rel)
s=load(root/'SOURCE_MANIFEST.json')
check(s['schema']=='csr-component-sources-v1','source schema')
for item in s['immutable_sources']:
 check(safe(item['path']) and sha(root/item['path'])==item['sha256'],'immutable '+item['path'])
for item in s['effective_symbols']:
 check(safe(item['path']) and sha(root/item['path'])==item['sha256'],'resolution '+item['symbol'])
for name in ('TerminalHop','DiscoveryMembershipNwk'):
 item=next(x for x in s['effective_symbols'] if x['symbol']=='ac.'+name)
 check(item['path']=='observer/+ac/'+name+'.m','observer precedence')
for forbidden in ('configure_case.m','qualify_opnet_compact6000.m','run_opnet_compact6000.m','run_exclusive_prefix.m','run_6000_batch.m'):
 check(not any(Path(p).name==forbidden for p in paths),'stale/full runner included')
check(not (root/'config').exists(),'configuration must remain external')
check(not any(x.startswith('config/') for x in paths),'configuration listed in manifest')
a=(root/'adapter/run_current_policy_adapter.m').read_text()
check('clear classes' not in a and 'restoredefaultpath' not in a,'unsafe session reset')
check('batchStartupOptionUsed()' in a and "~usejava('desktop')" in a,'fresh batch guard')
check("'engine_creation_independently_verified',false" in a,'ownership qualification')
check(not re.search(r'\b(?:CIM|Get-CimInstance|System\.Diagnostics\.Process)\b',a),'new protected/independent process query')
check('run_congestion_candidate(configPath,componentPath)' in a and '.run(' not in a,'bounded entrypoint only')
check('preflight_current_policy(config,preflightRoot,@check)' in a,'preflight wired')
check('System.IO.FileMode.CreateNew' in a,'create-new output')
check("'scientific_configuration_path'" in a,'external configuration plan field')
check("configPath=char(System.IO.Path.GetFullPath(plan.scientific_configuration_path))" in a,'external configuration resolved')
check("'adapter:ConfigurationChanged'" in a and "'adapter:ConfigurationHash'" in a,'configuration checks before and after')
check("'configuration_contents_exported',false" in a,'no configuration export claim')
check("'scientific_configuration_sha256',plan.scientific_configuration_sha256" not in a,'private hash excluded from result')
check("'config/scientific_configuration.json'" not in a,'no packaged configuration path')
result={'static_pass':True,'checks':checks,'matlab_executed':False,'package_manifest_sha256':sha(root/'PACKAGE_MANIFEST.json'),'source_manifest_sha256':sha(root/'SOURCE_MANIFEST.json')}
print(json.dumps(result,indent=2))
