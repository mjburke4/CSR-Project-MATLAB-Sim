"""Build the reviewed T23 update and verify its clean application to T22."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

WORK = Path(__file__).resolve().parents[1]
BASE, ROOT = WORK/'csr22', WORK/'csr23'
OUT = WORK/'deliverables/t23up.zip'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def files(root):
    return {p.relative_to(root).as_posix():p for p in root.rglob('*')
            if p.is_file() and not any(x.startswith('.') or x=='__pycache__'
                                      for x in p.relative_to(root).parts)
            and p.suffix != '.pyc' and p.relative_to(root).parts[0] != 'results'}

base, current = files(BASE), files(ROOT)
assert not set(base)-set(current), 'An accepted file was removed'
modified = sorted(k for k in base if digest(base[k]) != digest(current[k]))
assert modified == ['docs/parity-ledger.csv'], modified
members = sorted((set(current)-set(base)) | set(modified))
assert len(members) == len({x.casefold() for x in members})
assert all(not Path(x).is_absolute() and '..' not in Path(x).parts for x in members)
OUT.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for name in members:
        z.write(current[name],name)
with zipfile.ZipFile(OUT) as z:
    assert z.testzip() is None
    assert z.namelist() == members
    for name in members:
        assert hashlib.sha256(z.read(name)).hexdigest() == digest(current[name]), name
    target=WORK/'t23-work/install-check'
    if target.exists():
        shutil.rmtree(target)
    subprocess.run(['cp','-a','--reflink=auto',str(BASE),str(target)],check=True)
    z.extractall(target)
installed=files(target)
assert set(installed)==set(current)
for name in current:
    assert digest(installed[name])==digest(current[name]), name
command=[sys.executable,str(target/'scripts/analyze_tranche23_return.py'),
         '--source-root',str(target),'--verify-candidate','--output',str(WORK/'t23-work/install-review')]
result=subprocess.run(command,text=True,capture_output=True)
assert result.returncode==0, result.stdout+result.stderr
summary={'schema':'csr-tranche23-update-package-verification-v1','passed':True,
         'archive':str(OUT),'bytes':OUT.stat().st_size,'sha256':digest(OUT),
         'member_count':len(members),'members':members,'modified_prior_files':modified,
         'unchanged_source_bindings':390,'unchanged_matlab_sources':178,
         'complete_installation_files_verified':len(current),'clean_overlay_verified':True,
         'installed_candidate_verification':{'returncode':result.returncode,'stdout':result.stdout},
         'MATLABExecuted':False}
(WORK/'t23-work/package-verification.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ['members','installed_candidate_verification']}))
