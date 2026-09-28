"""Package offline evidence without duplicating the large owner-return archive."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'deliverables'
NAME='csr-6000-corrected-review-evidence.zip'
REC='return6000/recovered/NS3 to MATLAB Network Simulation/'
README='''# Corrected 6,000-second review evidence — 25 September 2026

Scope: MATLAB seeds 131/132, ±15% per-source target; no simulator is launched by
these analysis tools. Native means the pinned ns-3 reference.

Start with `deliverables/CSR_6000s_Corrected_Run_Review_2026-09-25.md`.
The same folder contains the latency figure as PNG and editable SVG.

Included:
- Complete new accounting, phase, queue/capacity, native-rule and provenance
  audit outputs and Python source under `return6000/review/`.
- Returned application/summary tables and small raw node/admission counters.
- Exact original issued kit and historical evidence ZIPs. Their source/model
  provenance and historical native ledgers are preserved in those archives.
- A per-file SHA-256 manifest, input archive identities, and restoration helper.

The original 30 MB owner ZIP is preserved separately and is NOT duplicated here:
`out_6000_20260924_152302.zip` (SHA-256 in INPUTS.json).
Full raw-trace and sealed-case verification requires that ZIP. This package alone
reproduces numerical accounting, the archived native capacity-rule comparison,
and the figure from preserved phase results. It does not independently replace
the original raw trace evidence.

## Reproduce without another simulation

Extract this package into an empty directory and run commands from that directory.
Python 3.10+ suffices for audits; only the figure requires matplotlib.

```
python3 restore_inputs.py
python3 return6000/review/accounting/recompute.py
python3 return6000/review/phase132/check_native_capacity_rules.py
python3 return6000/review/presentation/plot_phases.py
```

The restoration helper validates archive hashes and expands the bundled kit and
history into the exact paths expected by the scripts. It performs no network access.

For full raw-trace regeneration, supply your original returned ZIP:

```
python3 restore_inputs.py --owner-zip /path/to/out_6000_20260924_152302.zip
python3 return6000/review/provenance/verify_return.py
python3 return6000/review/phase131/analyze.py
python3 return6000/review/phase132/analyze_current.py
python3 return6000/review/phase132/queue_capacity_audit.py
python3 return6000/review/phase132/check_native_capacity_rules.py
python3 return6000/review/presentation/plot_phases.py
python3 return6000/review/presentation/build_report.py
```

The helper verifies the owner ZIP hash, copies it into `upload/`, and expands it
into `return6000/data/`. Existing evidence with the same path must match exactly;
the helper refuses to replace different bytes. Audits regenerate their derived
output files. The figure uses saved phase results until full phase reconstruction
has been rerun.

Key semantics:
- Attempts rejected before admission are not persistent admitted applications.
- Deduplicate native deliveries; four repeated events exist in seed 132.
- Native undelivered fate is unresolved, not assumed live or terminally dropped.
- Delivered-only means exclude drops/pending; ages never substitute for latency.
- Native source/seed weighting is descriptive and excludes zero-native cells.
- Pending-copy and queue-state reconstruction is complete for current seed 132.
- The native-rule check translates capacity arithmetic; it does not execute
  MATLAB callbacks or reproduce receiver ACK selection and bitmap processing.
- Equal seed values do not imply matching random streams or application IDs.

Peer review: accounting/figure values and queue/capacity conclusions were checked
independently. The report distinguishes observed cohort changes from isolated
causal effects of the cleanup fix.
'''
RESTORE='''"""Restore hash-verified local evidence. No simulation or network access."""
from pathlib import Path, PurePosixPath
import argparse, hashlib, shutil, zipfile
ROOT=Path(__file__).resolve().parent
REC=ROOT/'return6000/recovered/NS3 to MATLAB Network Simulation'
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def extract(archive,destination,expected):
    if digest(archive)!=expected: raise ValueError(f'Archive hash mismatch: {archive}')
    destination.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        bad=z.testzip()
        if bad: raise ValueError(f'ZIP CRC failed: {bad}')
        for m in z.infolist():
            p=PurePosixPath(m.filename)
            if p.is_absolute() or '..' in p.parts or '\\\\' in m.filename:
                raise ValueError(f'Unsafe member: {m.filename}')
            target=destination.joinpath(*p.parts)
            if m.is_dir(): target.mkdir(parents=True,exist_ok=True); continue
            blob=z.read(m)
            if target.exists():
                if target.read_bytes()!=blob: raise ValueError(f'Different existing bytes: {target}')
            else: target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(blob)
    print(f'Verified and restored {archive.name}')
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-zip',type=Path)
    args=parser.parse_args()
    extract(REC/'csr-6000-batch.zip',ROOT/'return6000/kit','fc3e8acff9b1fda90693a7ba299c0d201b7ad7d4edcd1dddf85d706ca92683bf')
    extract(REC/'csr-6000s-accounting-evidence.zip',ROOT/'return6000/history','5326c8050c2d00f6dca0ea06482c0a7c66ac865921dfb0b6b8820bad7a3abfd9')
    if args.owner_zip:
        src=args.owner_zip.resolve();expected='a3f7fd6fc09a5b0505c6a759a5c025390151bef484e7e15c9818e51a3f4f1484'
        if digest(src)!=expected: raise ValueError('Owner ZIP hash mismatch')
        dest=ROOT/'upload/out_6000_20260924_152302.zip';dest.parent.mkdir(exist_ok=True)
        if dest.exists() and digest(dest)!=expected: raise ValueError('Different existing owner ZIP')
        if not dest.exists(): shutil.copyfile(src,dest)
        extract(dest,ROOT/'return6000/data',expected)
if __name__=='__main__': main()
'''

def main():
    members={}
    def add(path): members[path.relative_to(ROOT).as_posix()]=path.read_bytes()
    for p in (ROOT/'return6000/review').rglob('*'):
        if p.is_file() and p.suffix in {'.py','.md','.csv','.json','.log'} and '__pycache__' not in p.parts:
            add(p)
    for p in (ROOT/'return6000/data').rglob('*'):
        if not p.is_file():continue
        if p.name in {'protocol_trace.csv','trace.csv','phy_trace.csv','application_admission_trace.csv'}:continue
        if p.suffix in {'.csv','.json','.log'}:add(p)
    for name in ['csr-6000-batch.zip','csr-6000s-accounting-evidence.zip']:add(ROOT/REC/name)
    for p in OUT.glob('CSR_6000s_*_2026-09-25.*'):add(p)
    members['README.md']=README.encode()
    members['restore_inputs.py']=RESTORE.encode()
    inputs=[dict(name='out_6000_20260924_152302.zip',included=False,sha256='a3f7fd6fc09a5b0505c6a759a5c025390151bef484e7e15c9818e51a3f4f1484',library_file_id='libfile_9e1d90ca16148191989b7cc45f6a35db'),
            dict(name='csr-6000-batch.zip',included=True,sha256='fc3e8acff9b1fda90693a7ba299c0d201b7ad7d4edcd1dddf85d706ca92683bf',library_file_id='libfile_750bd67cf8a081919197738aea2fe890'),
            dict(name='csr-6000s-accounting-evidence.zip',included=True,sha256='5326c8050c2d00f6dca0ea06482c0a7c66ac865921dfb0b6b8820bad7a3abfd9',library_file_id='libfile_d64d4f8d672c8191909a85f2625f5070')]
    members['INPUTS.json']=(json.dumps(inputs,indent=2)+'\n').encode()
    manifest=[dict(path=name,bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest()) for name,blob in sorted(members.items())]
    members['FILES.sha256.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    output=OUT/NAME
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,blob in sorted(members.items()):
            z.writestr(name,blob,compress_type=zipfile.ZIP_STORED if name.endswith('.zip') else zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        for m in manifest: assert hashlib.sha256(z.read(m['path'])).hexdigest()==m['sha256']
    print(json.dumps(dict(package=str(output),files=len(members),bytes=output.stat().st_size,sha256=hashlib.sha256(output.read_bytes()).hexdigest(),member_hashes_verified=True),indent=2))
if __name__=='__main__':main()
