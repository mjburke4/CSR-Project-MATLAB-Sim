#!/usr/bin/env python3
"""Package this offline investigation and the inputs needed to reuse acceptance."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'next_feedback'
OUT = BASE / 'deliverables'

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

readme = '''# Seed-132 receiver-feedback evidence — 25 September 2026

Read `next_feedback/deliverables/Seed132_Feedback_Investigation_2026-09-25.md` first.
Native means ns-3. This package contains offline analysis and previously executed
MATLAB evidence. It is not a new MATLAB test kit. No simulation is required to
read the findings, and no new production model change is included.

## Main results

- MATLAB 139 ACK + 993 DACK decisions account for all 1,132 accepted 8→2 packets;
  native 300 ACK + 945 DACK account for all 1,245. All audited first receptions
  follow the same per-flow custody threshold, and completion classes agree.
- Source-7 arrival-weighted custody is 75.91 versus 25.16; its time average over
  300–6000 seconds is 72.96 versus 25.30. The source mix also differs.
- Native node 8 sends 34 feedback transmissions before its first DATA at
  316.719 seconds. The actual September 23 MATLAB return already reproduces
  this sequence under the same inputs. A repeat conditional MAC test is redundant.
- Autonomous network histories remain different. This audit does not explain
  all long-run latency or establish the ±15% network target.

## Included evidence

`next_feedback/matlab_receiver`, `native_receiver`, and `delivery` contain
receiver-state reconstruction, per-application outcome joins, physical-feedback
reconstruction, and the early scheduling investigation. `comparison` contains
the combined custody and service tables and plotting code.

`prior_coverage` contains capture provenance, byte-comparison results and the
native 0–330-second MAC fixture. `prior_acceptance` contains independent checks
against the actual earlier MATLAB outputs. The earlier owner's outputs, its
160 runtime-bound files, the four reused adapter files, and the current 99-file
MATLAB model snapshot are included so the acceptance-reuse checks can be rerun.
These model files are reference snapshots, not files the user needs to install.

The draft repeat replay kit and its superseded static assessment are excluded.
`CONTENT_SHA256.json` inventories every included file except itself.
`INPUTS.json` identifies original archives and records hashes of the external
large inputs. Those original long-run traces are not duplicated here.

## Reproduce the acceptance-reuse finding without a simulator

Extract this ZIP into a new directory and run from its root:

```sh
python3 next_feedback/prior_coverage/compare_prior_acceptance.py
python3 next_feedback/prior_acceptance/check_prior_actual_service.py
```

These scripts check existing actual MATLAB results against native references;
they do not run MATLAB or ns-3. Expected results are `pass: true`, 160 bound
files verified, 4,075 matched MAC input events, 192 matched full frames,
208 matched TX records and 241 matched random draws in the two-node prefix.
The second script checks the three specific service assertions.

The combined tables and figure can be regenerated entirely from included
derived data (Python 3; matplotlib is required only for the plot):

```sh
python3 next_feedback/comparison/compare_receiver_histories.py
python3 next_feedback/comparison/plot_receiver_pressure.py
```

## Reproduce the full raw-trace audit

The original source archives are separately retained in the project files.
Check their hashes against `INPUTS.json` before extraction. Extract
`out_6000_20260924_152302.zip` into `return6000/data/`, preserving its member
paths. Extract `evidence/tranche-25-ns3-reference/s132/` from `t25up.zip` into
`next_feedback/native_archive/`, preserving that path. Then run:

```sh
python3 next_feedback/matlab_receiver/audit_receiver.py
python3 next_feedback/delivery/audit_feedback.py
python3 next_feedback/native_receiver/analyze.py
python3 next_feedback/native_receiver/derive_service.py
python3 next_feedback/delivery/early_service/analyze_early.py
python3 next_feedback/comparison/compare_receiver_histories.py
python3 next_feedback/comparison/plot_receiver_pressure.py
```

The native audit streams about 1.17 GB of decompressed trace. It may take time;
all its resulting CSVs and summaries are already included. No new network run
is necessary. Individual audit reviews describe inference and capture limits.

For the auxiliary short-return archive/provenance check, place the original
`out_short_20260924_083651.zip` and `out_next_20260924_100916.zip` under
`next_feedback/recovered/NS3 to MATLAB Network Simulation/`, then run
`python3 next_feedback/prior_coverage/audit_coverage.py`. That script extracts
its inputs locally. This is optional for inspecting the already included
acceptance-reuse proof.
'''
(BASE / 'README.md').write_text(readme)

archives = [
    ('upload/out_6000_20260924_152302.zip', 'libfile_9e1d90ca16148191989b7cc45f6a35db', 'MATLAB 6000-second corrected return', False),
    ('next_feedback/recovered/NS3 to MATLAB Network Simulation/t25up.zip', 'libfile_559456f84fa481918cbc96a7f01a7671', 'Original native seed-132 trace', False),
    ('next_feedback/recovered/NS3 to MATLAB Network Simulation/out_short_20260924_083651.zip', 'libfile_51267f9bcfb48191862470821c98a716', 'Earlier short return with native MAC fixture', False),
    ('next_feedback/recovered/NS3 to MATLAB Network Simulation/out_next_20260924_100916.zip', 'libfile_12a87dd32a488191b876b266681ef7eb', 'Integration return provenance', False),
    ('next_feedback/recovered/NS3 to MATLAB Network Simulation/out_mh_20260923_121427.zip', 'libfile_c5e2372eabe48191be05e678c27921e8', 'Previously executed MATLAB MAC acceptance', True),
    ('next_feedback/recovered/mac-history-fix.zip', 'libfile_b8cb0859bad48191805f976977120c9e', 'Issued prior MAC kit; runtime-bound subset included', False),
    ('next_feedback/recovered/NS3 to MATLAB Network Simulation/csr-short-tests-ready-v3.zip', 'libfile_6a5551901bc88191b81b03984e894280', 'Issued later short kit; reused MAC adapter included', False),
]
inputs = {'schema': 'csr-feedback-inputs-v1', 'archives': [], 'external_raw_inputs': []}
for rel, library_id, purpose, included in archives:
    p = ROOT / rel
    inputs['archives'].append(dict(filename=p.name, original_workspace_path=rel,
        library_file_id=library_id, purpose=purpose, sha256=digest(p),
        size_bytes=p.stat().st_size, archive_included=included))
raw_paths = [
    'return6000/data/s132/attempt_001/raw/protocol_trace.csv',
    'return6000/data/s132/attempt_001/raw/phy_trace.csv',
    'return6000/data/s132/attempt_001/raw/hop_nodes.csv',
    'return6000/data/s132/attempt_001/raw/nwk_nodes.csv',
    'return6000/data/s132/attempt_001/analysis/applications.csv',
    'next_feedback/native_archive/evidence/tranche-25-ns3-reference/s132/ns3-trace.csv.gz',
]
for rel in raw_paths:
    p = ROOT / rel
    inputs['external_raw_inputs'].append(dict(path=rel, sha256=digest(p), size_bytes=p.stat().st_size))
(BASE / 'INPUTS.json').write_text(json.dumps(inputs, indent=2) + '\n')

files = set()
def add_tree(path):
    files.update(p for p in path.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
for sub in ['matlab_receiver', 'native_receiver', 'delivery', 'comparison', 'prior_acceptance', 'mac_owner']:
    add_tree(BASE / sub)
for p in (BASE / 'prior_coverage').iterdir():
    if p.is_file() and p.name not in {'review_adapter.py', 'adapter_static_review.json'}:
        files.add(p)
add_tree(BASE / 'prior_coverage/out_short_20260924_083651/replays/source5_mac/staging')
add_tree(BASE / 'short_kit/two_case_next/source5_replay/mac_adapter')
add_tree(ROOT / 'return6000/kit/csr6000/model')
binding = json.loads((BASE / 'mac_owner/runtime_binding.json').read_text())
files.update(BASE / 'mac_kit/macfix' / row['path'] for row in binding['files'])
files.add(BASE / 'recovered/NS3 to MATLAB Network Simulation/out_mh_20260923_121427.zip')
files.update(BASE / n for n in ['README.md', 'INPUTS.json', 'build_evidence_package.py'])
files.update(p for p in OUT.iterdir() if p.suffix in {'.md', '.png', '.svg'})
inventory = [{'path': str(p.relative_to(ROOT)), 'size_bytes': p.stat().st_size,
              'sha256': digest(p)} for p in sorted(files)]
(BASE / 'CONTENT_SHA256.json').write_text(json.dumps(inventory, indent=2) + '\n')
files.add(BASE / 'CONTENT_SHA256.json')
target = OUT / 'seed132-feedback-evidence.zip'
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for p in sorted(files):
        z.write(p, p.relative_to(ROOT))
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
print(json.dumps({'archive': str(target), 'files': len(files),
    'size_bytes': target.stat().st_size, 'sha256': digest(target)}, indent=2))
