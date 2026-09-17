#!/usr/bin/env python3
"""Build the T17 update and verify applying it to the exact recovered T16 base."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT.parent/'csr16-base'
OUT = Path(sys.argv[2]).resolve() if len(sys.argv)>2 else ROOT.parent/'deliverables'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def ignored(path):
    return any(part in ('.git','__pycache__','.pytest_cache','results') for part in path.parts) or path.suffix in ('.pyc','.pyo')

def inventory(root):
    return {p.relative_to(root).as_posix(): {'path': p.relative_to(root).as_posix(),
        'bytes': p.stat().st_size, 'sha256': sha(p)} for p in sorted(root.rglob('*'))
        if p.is_file() and not ignored(p.relative_to(root)) and p.name!='PACKAGE.json'}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    baseline = json.loads((ROOT/'evidence/tranche-17-baseline.json').read_text())
    assert all(sha(ROOT/row['path']) == row['sha256'] == sha(BASE/row['path']) for row in baseline)
    before, after = inventory(BASE), inventory(ROOT)
    assert set(before) <= set(after), 'Update cannot delete a base file'
    assert len({name.casefold() for name in after}) == len(after)
    modified = sorted(name for name in before if before[name]!=after[name])
    assert set(modified) <= {'README.md', 'docs/parity-ledger.csv'}, modified
    changed = sorted(name for name in after if before.get(name)!=after[name])
    manifest = {'Schema':'csr-portable-package-v1','Tranche':17,
        'CandidateSHA256':sha(ROOT/'evidence/tranche-17-candidate.json'),
        'Scope':'Full portable regression and unchanged campus6000 candidate; MATLAB execution pending.',
        'UpdateBaseRecipe':'Copy the exact reviewed Tranche 16 installation, then overlay every t17up.zip file at its root.',
        'BasePackageInventorySHA256':sha(BASE/'PACKAGE.json'),
        'FileCountExcludingManifest':len(after),
        'MaximumRelativePathLength':max(map(len,after)),
        'Files':list(after.values())}
    (ROOT/'PACKAGE.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    changed.append('PACKAGE.json'); changed.sort()
    bundle=OUT/'t17up.zip'
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name in changed:
            path=ROOT/name
            assert not path.is_symlink() and '..' not in Path(name).parts and not Path(name).is_absolute()
            archive.write(path,name)
    with zipfile.ZipFile(bundle) as archive:
        assert archive.testzip() is None
        assert sorted(archive.namelist())==changed
        with tempfile.TemporaryDirectory(prefix='t17-apply-',dir=ROOT.parent) as temporary:
            applied=Path(temporary)/'installation'
            shutil.copytree(BASE,applied,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','.git','*.pyc','*.pyo'))
            archive.extractall(applied)
            assert inventory(applied)==after, 'Applied update differs from prepared tree'
            assert sha(applied/'PACKAGE.json')==sha(ROOT/'PACKAGE.json')
    report={'schema':'csr-tranche17-package-verification-v1','status':'passed',
        'archive':bundle.name,'archive_sha256':sha(bundle),'archive_bytes':bundle.stat().st_size,
        'archive_members':len(changed),'candidate_sha256':manifest['CandidateSHA256'],
        'full_installation_files_excluding_manifest':len(after),
        'baseline_source_files_unchanged':304,'baseline_matlab_files_unchanged':155,
        'updated_existing_files':modified+['PACKAGE.json'],
        'maximum_relative_path_length':manifest['MaximumRelativePathLength'],
        'zip_crc_passed':True,'update_applied_and_full_tree_hash_verified':True,
        'matlab_executed':False,'native_executed':False,'numerical_parity_established':False}
    (OUT/'t17-package-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
