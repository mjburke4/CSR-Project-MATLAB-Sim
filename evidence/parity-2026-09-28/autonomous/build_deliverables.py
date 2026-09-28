#!/usr/bin/env python3
"""Package the validated native evidence and the source-bound MATLAB runner."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'autonomous'
OUT = BASE / 'deliverables'
KIT = BASE / 'kit/autocase'

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()

def pack(target, paths, base):
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(paths):
            z.write(p, p.relative_to(base))
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
    return {'path': str(target), 'bytes': target.stat().st_size, 'sha256': sha(target), 'files': len(paths)}

def tree(p):
    return {x for x in p.rglob('*') if x.is_file() and '__pycache__' not in x.parts}

def main():
    OUT.mkdir(exist_ok=True)
    assert (KIT / 'run_autonomous_tests.m').is_file()
    assert (KIT / 'README.md').is_file()
    manifest = json.loads((KIT / 'FILES.json').read_text())
    for row in manifest['files']:
        assert sha(KIT / row['path']) == row['sha256'], row['path']
    syntax = json.loads((BASE / 'tooling/final_syntax/syntax_summary.json').read_text())
    # Exact schema of the syntax receipt is retained in the package and checked
    # by the caller. Its presence does not represent MATLAB execution.
    assert syntax['status'] == 'pass'
    assert syntax['source_unchanged_during_parse']
    assert syntax['file_sha256'] == {
        str(p.relative_to(KIT)): sha(p) for p in sorted(KIT.rglob('*.m'))
    }, 'Kit MATLAB source changed after syntax check'
    report = OUT / 'Autonomous_Network_Investigation_2026-09-25.md'
    shutil.copy2(BASE / report.name, report)
    kit_paths = tree(KIT)
    assert not any('out_auto_' in str(p.relative_to(KIT)) for p in kit_paths)
    owner = pack(OUT / 'autonomous-seed132-tests.zip', kit_paths, KIT.parent)
    with zipfile.ZipFile(owner['path']) as z:
        assert 'autocase/run_autonomous_tests.m' in z.namelist()

    readme = '''# Autonomous network investigation evidence — 25 September 2026

The findings are in `autonomous/Autonomous_Network_Investigation_2026-09-25.md`.
This archive is the analysis/reference record. For the user-run MATLAB batch,
use `autonomous-seed132-tests.zip`; its `autocase/README.md` gives the one command.

## Executed here

- Offline comparison of the original seed-132 traffic/admission/receiver traces.
- Pinned ns-3 environment restoration and an extended passive 0–330 s capture.
- Exact comparison of 48,919 canonical native rows and all 30 fields.
- Independent comparison of all 928 MAC samples with the earlier accepted capture.
- Source-transform reversal, syntax checks and static peer review of the new
  MATLAB diagnostic kit. These checks are not MATLAB runtime execution.

MATLAB's natural-prefix equivalence and coupled case remain pending an owner
run. A diagnostic stop does not itself prove a production bug. The 15% network
target remains separate and unmet.

## Contents and reproduction

`autonomous/traffic` and `autonomous/receiver` contain the offline audit scripts,
joined events, per-source counts, summaries, input hashes and reviews.
Their input manifests identify the original 6,000 s files. The large original
MATLAB return and original full native trace are retained separately:
`out_6000_20260924_152302.zip` and `t25up.zip`. Restore the former under
`return6000/data/` and the latter's seed132 trace under
`next_feedback/native_archive/evidence/tranche-25-ns3-reference/s132/` if rerunning
the full raw audits. The accepted native application ledger is included under
`return6000/kit/csr6000/reference/s132/`.

`autonomous/native_capture` contains the native driver, passive overlay
generators, compile/run recipes, exact prefix reference, raw new observations,
normalizers, random/TX/state fixtures and provenance receipts. The compiled
binary and engine libraries are excluded. Its README describes the precise
observation scope. `autonomous/native_env/build.json` records the restored
environment; the included `restore_native.py --root autonomous/native_env`
script can recreate the pinned repositories/build before rerunning the
native build/capture recipes. Those operations are for the analyst, not a task
Mike needs to perform.

`autonomous/design` and `autonomous/capture_design` contain instrumentation,
design and independent review. `autonomous/kit` contains the exact source-bound
MATLAB kit. `autonomous/tooling/final_syntax` records the syntax-only check,
parser version, output and source hashes. No installed parser package is
bundled. The original 99-file MATLAB model is included solely as a reference
for the reversible source-transform audit; it is not a new production release.

From the extracted archive root, the already captured native data can be
renormalized without running a simulator:

```sh
python3 autonomous/native_capture/normalize.py
python3 autonomous/capture_design/check_final_transform.py
```

The manifest `autonomous/EVIDENCE_CONTENT_SHA256.json` lists all archive members
except itself. It preserves exact captured and reviewed files, including
historical workspace paths inside provenance records.
'''
    (BASE / 'EVIDENCE_README.md').write_text(readme)
    paths = {BASE / 'EVIDENCE_README.md', BASE / report.name, BASE / 'build_deliverables.py'}
    for sub in ['traffic', 'receiver', 'capture_design', 'design', 'build', 'kit']:
        paths |= tree(BASE / sub)
    for p in tree(BASE / 'native_capture'):
        if p.name == 'autonomous-capture':
            continue
        paths.add(p)
    for p in (BASE / 'native_env').iterdir():
        # Only environment receipts at the root; no repository-backed files,
        # binaries, tool packages or restored checkout contents.
        if p.is_file() and p.suffix == '.json':
            paths.add(p)
    paths.add(ROOT / 'next_feedback/short_kit/two_case_next/maintenance/restore_native.py')
    paths |= tree(BASE / 'tooling/final_syntax')
    paths.add(BASE / 'tooling/check_matlab_syntax.py')
    paths |= tree(ROOT / 'return6000/kit/csr6000/model')
    paths.add(ROOT / 'return6000/kit/csr6000/reference/s132/applications.csv')
    # Offline receiver/traffic audits refer to this earlier exact native prefix
    # and native MAC fixture. Preserve only their required small inputs.
    paths.add(ROOT / 'next_feedback/short_kit/two_case_next/schema_review/native_s132_prefix_0_330.csv.gz')
    paths |= tree(ROOT / 'next_feedback/prior_coverage/out_short_20260924_083651/replays/source5_mac/staging')
    inventory = [{'path': str(p.relative_to(ROOT)), 'size_bytes': p.stat().st_size,
                  'sha256': sha(p)} for p in sorted(paths)]
    index = BASE / 'EVIDENCE_CONTENT_SHA256.json'
    index.write_text(json.dumps(inventory, indent=2) + '\n')
    paths.add(index)
    evidence = pack(OUT / 'autonomous-seed132-evidence.zip', paths, ROOT)
    receipt = {'report': str(report), 'owner_kit': owner, 'evidence': evidence,
               'matlab_execution_performed': False}
    (OUT / 'package_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
