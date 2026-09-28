"""Create a hash-bound repository continuation without changing MATLAB code."""
from pathlib import Path
import hashlib
import json
import shutil

stage = Path(__file__).resolve().parent
workspace = stage.parents[1]
source = workspace / 'autonomous_tenth/kit/autocase'
target = stage / 'autocase'

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

issued_bytes = (source / 'FILES.json').read_bytes()
issued_sha = sha(issued_bytes)
assert issued_sha == 'dbe65dd9feb20d7d1d6aae90caa07e9490a1c46188c71cd38469d93b2d455b88'
issued = json.loads(issued_bytes)
assert len(issued['files']) == 424
assert not target.exists(), 'Build into an absent staging directory; do not overwrite a review.'
target.mkdir()
retained = []
omitted = []
for row in issued['files']:
    relative = row['path']
    raw = (source / relative).read_bytes()
    assert sha(raw) == row['sha256'] and len(raw) == row['bytes'], relative
    if relative.startswith('ref/history/') and Path(relative).suffix in ('.csv', '.jsonl'):
        omitted.append(row)
        continue
    path = target / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / relative, path)
    retained.append(row)

provenance = target / 'ref/issued'
provenance.mkdir()
(provenance / 'M_FILES.json').write_bytes(issued_bytes)
(provenance / 'M_README.md').write_bytes((source / 'README.md').read_bytes())

readme = (target / 'README.md').read_text()
readme = readme.replace(
    '# Seed-132 discovery membership test — 0–330 seconds\n',
    '# Seed-132 discovery membership test — 0–330 seconds\n\n'
    'This is the lean repository continuation of the issued M owner kit. '
    'All 151 MATLAB files, all 99 original model artifacts, native inputs and '
    'natural-reuse gates are byte-identical to that kit. Only historical raw '
    'CSV/JSONL captures are omitted; their hashes remain in the preserved issued '
    'manifest. See `PUBLICATION.md` for the exact packaging distinction.\n',
)
readme = readme.replace(
    '`ref/history/L_discovery_lifecycle` stores the prior actual run and `DIAGNOSIS.md` explains the precise cause and limits.',
    '`ref/history/L_discovery_lifecycle` stores its actual summary and divergence metadata. '
    'Historical raw captures are excluded from this repository copy; `DIAGNOSIS.md` explains the precise cause and limits.',
)
(target / 'README.md').write_text(readme)

(target / 'PUBLICATION.md').write_text('''# Repository continuation provenance

This directory is a self-contained, lean publication of the issued **M_discovery_membership** owner kit. Run it with the same command from this folder:

```matlab
report = run_autonomous_tests;
```

Restart MATLAB before switching between CSR copies. The runner verifies this directory's exact `FILES.json` inventory, runtime bindings, required native inputs and accepted natural-reuse gates before running any network case.

All 151 MATLAB files, all 99 original model artifacts, all 54 `+ac` MATLAB classes/helpers, input scenario, native fixtures, source transforms and accepted natural evidence retain their issued bytes. The source code, physical model and strict comparisons have not been changed for publication.

The original M kit manifest is preserved verbatim at `ref/issued/M_FILES.json`, with its original README at `ref/issued/M_README.md`. Its SHA-256 is `dbe65dd9feb20d7d1d6aae90caa07e9490a1c46188c71cd38469d93b2d455b88`. The preserved manifest describes the full owner kit, including raw historical captures that are intentionally absent here. It is provenance; the current runner validates the lean `FILES.json` at this directory's root.

Only raw `.csv` and `.jsonl` files beneath `ref/history` are omitted. All historical summary/divergence JSON is retained, including the runtime-required `I_control_wire/first_divergence.json` and `history.json`. Required accepted/reference CSVs and receiver-timer component fixtures are retained. `PUBLICATION.json` lists every omitted original file, original digest and size, and binds the unchanged executable inventory. There is no hash cycle: the current manifest includes the publication record and preserved issued manifest, while neither claims the current manifest's own digest.

The actual L owner return passed 61 prior component checks. The five new membership checks and the M common-input network continuation remain **pending owner MATLAB execution**. Preparing this repository copy is not a new MATLAB run, production-model promotion or a full-network parity result. The ±15% accounting and latency target remains unestablished.
''')

matlab_files = [r for r in retained if r['path'].endswith('.m')]
model_files = [r for r in retained if r['path'].startswith('model/')]
ac_files = [r for r in matlab_files if r['path'].startswith('+ac/')]
assert len(matlab_files) == 151 and len(model_files) == 99 and len(ac_files) == 54
for row in matlab_files + model_files:
    assert sha((target / row['path']).read_bytes()) == row['sha256']
required = [
    'ref/history/history.json', 'ref/history/I_control_wire/first_divergence.json',
    'ref/native/random_draws.csv', 'ref/native/tx_signatures.csv',
    'ref/accepted/reuse_proof.json', 'ref/receiver_timers/phy_component_fixture.csv',
    'ref/receiver_timers/acquisition_schedule_fixture.csv',
    'ref/receiver_timers/native_TX_finish_arithmetic.csv',
]
assert all((target / path).is_file() for path in required)
reuse = json.loads((target / 'ref/accepted/reuse_proof.json').read_text())
for row in reuse['accepted_files']:
    assert sha((target / 'ref/accepted' / row['path']).read_bytes()) == row['sha256']
for row in reuse['unchanged_natural_source_files']:
    assert sha((target / row['path']).read_bytes()) == row['sha256']
assert sha((target / '+ac/Streams.m').read_bytes()) == reuse['current_streams_sha256']

publication = dict(
    schema='csr-lean-repository-publication-v1', case='M_discovery_membership',
    source_issued_manifest='ref/issued/M_FILES.json', source_issued_manifest_sha256=issued_sha,
    source_issued_file_count=len(issued['files']),
    matlab_executed_for_publication=False, current_M_matlab_executed=False,
    previous_component_checks_actual_passed=61, new_component_checks_runtime_pending=5,
    production_model_changed=False, executable_code_changed=False, numeric_parity_established=False,
    preserved_matlab_file_count=len(matlab_files), preserved_model_artifact_count=len(model_files),
    preserved_ac_matlab_file_count=len(ac_files),
    code_and_model_files=sorted({r['path']:r for r in matlab_files+model_files}.values(), key=lambda r:r['path']),
    modified_original_files=['README.md'],
    omitted_files=omitted, omitted_bytes=sum(r['bytes'] for r in omitted),
    omission_scope='Only unused raw historical CSV/JSONL; required history JSON and all nonhistory runtime inputs retained',
    accepted_natural_file_hashes_verified=True, accepted_natural_source_hashes_verified=True,
    hash_cycle_policy='Root FILES.json binds this record; this record does not contain the root FILES.json digest',
)
(target / 'PUBLICATION.json').write_text(json.dumps(publication, indent=2) + '\n')

files = []
for path in sorted(target.rglob('*')):
    if not path.is_file():
        continue
    raw = path.read_bytes()
    files.append(dict(path=path.relative_to(target).as_posix(), sha256=sha(raw), bytes=len(raw)))
manifest = {key:value for key,value in issued.items() if key != 'files'}
manifest.update(
    schema='csr-autonomous-lean-repository-v1',
    packaging='Lean repository copy; executable bytes identical to issued M owner kit',
    issued_manifest_path='ref/issued/M_FILES.json', issued_manifest_sha256=issued_sha,
    publication_record='PUBLICATION.json', files=files,
)
(target / 'FILES.json').write_text(json.dumps(manifest, indent=2) + '\n')
receipt = dict(
    schema='csr-lean-stage-receipt-v1', root='publication_sep28/stage/autocase',
    source_manifest_sha256=issued_sha, published_manifest_sha256=sha((target / 'FILES.json').read_bytes()),
    bound_files=len(files), total_files=len(files)+1, bound_bytes=sum(r['bytes'] for r in files),
    total_bytes=sum(r['bytes'] for r in files)+(target/'FILES.json').stat().st_size,
    unchanged_matlab_files=len(matlab_files), unchanged_model_artifacts=len(model_files),
    unchanged_ac_matlab_files=len(ac_files), omitted_historical_files=len(omitted),
    omitted_historical_bytes=sum(r['bytes'] for r in omitted),
    prior_component_checks_passed=61, new_component_checks_pending=5,
    matlab_runtime_executed=False, current_M_runtime_pending=True,
)
(stage / 'lean_stage_receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt, indent=2))
