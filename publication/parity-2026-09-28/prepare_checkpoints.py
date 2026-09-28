#!/usr/bin/env python3
"""Read historical work; stage standalone checkpoints without repository edits."""
from pathlib import Path
import collections
import csv
import difflib
import hashlib
import json
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
STAGE=ROOT/'publication_sep28/stage'
REPO=ROOT/'publication_sep28/repo'
STAGES=['autonomous','autonomous_return','autonomous_third','autonomous_fourth',
        'autonomous_fifth','autonomous_sixth','autonomous_seventh','autonomous_eighth',
        'autonomous_ninth','autonomous_tenth']

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def jsonread(p): return json.loads(p.read_text())
def write(name,value): (OUT/name).write_text(json.dumps(value,indent=2)+'\n')
def gitid(p):
    raw=p.read_bytes()
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

raw=subprocess.check_output(['git','-C',str(REPO),'ls-tree','-r','HEAD'],text=True)
objects={};byhash=collections.defaultdict(list)
for line in raw.splitlines():
    left,path=line.split('\t',1);oid=left.split()[2]
    objects[path]=oid;byhash[oid].append(path)
base=subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip()
assert base=='6bfbb3ceaa39c3a7457027384a4bf6498313194e'

definitions=[('macfix','next_feedback/mac_kit/macfix','diagnostics/mac-batch'),
             ('two_case_next','next_feedback/short_kit/two_case_next','diagnostics/two-case-short/two_case_next'),
             ('csr6000','return6000/kit/csr6000','diagnostics/campus6000/csr6000')]
source_rows=[];staging=[]
for name,source_rel,publication in definitions:
    src=ROOT/source_rel;dest=STAGE/name;selected=set()
    allfiles=[p for p in src.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    required=[]
    if name=='macfix':
        required=jsonread(src/'RUN_FILES.json')['files']
        selected.update(src/row['path'] for row in required)
        # Preserve every actual source plus small documentation/receipts.
        selected.update(p for p in allfiles if p.suffix in {'.m','.py','.h','.cc','.md','.json'})
    else:
        selected.update(allfiles)
    for p in sorted(selected):
        rel=p.relative_to(src);target=dest/rel
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        assert sha(target)==sha(p)
    for row in required:
        assert sha(dest/row['path'])==row['sha256']
    included=[dict(path=p.relative_to(src).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(selected)]
    omitted=[dict(path=p.relative_to(src).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(allfiles) if p not in selected and not p.name.startswith('.')]
    evidence=dest/'publication_source_manifest.json'
    evidence.write_text(json.dumps(dict(schema='csr-sep28-checkpoint-publication-v1',source_workspace=source_rel,
        proposed_repository_path=publication,source_bytes_changed=False,matlab_executed_by_publication=False,
        runtime_manifest_entries_verified=len(required),files=included,omitted=omitted),indent=2)+'\n')
    staging.append(dict(name=name,source=source_rel,stage=dest.relative_to(ROOT).as_posix(),
        proposed_repository_path=publication,source_files=len(included),source_bytes=sum(r['bytes'] for r in included),
        matlab_files=sum(r['path'].endswith('.m') for r in included),omitted_files=len(omitted),
        omitted_bytes=sum(r['bytes'] for r in omitted),runtime_binding_verified=bool(required)))
    for p in allfiles:
        if p.suffix not in {'.m','.py','.h','.cc'}:continue
        oid=gitid(p);rel=p.relative_to(src).as_posix()
        source_rows.append(dict(checkpoint=name,path=rel,bytes=p.stat().st_size,sha256=sha(p),git_blob=oid,
            existing_main_paths=';'.join(byhash.get(oid,[])),content_already_in_main=oid in byhash))

with (OUT/'source_vs_main.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(source_rows[0]));w.writeheader();w.writerows(source_rows)

autonomous=[];unique=collections.defaultdict(list)
for name in STAGES:
    p=ROOT/name/'kit/autocase';manifest=jsonread(p/'FILES.json');rows=manifest['files']
    mfiles=[f for f in p.rglob('*.m') if f.is_file()]
    for f in mfiles:unique[sha(f)].append(f)
    history=[r for r in rows if r['path'].startswith('ref/history/')]
    autonomous.append(dict(stage=name,manifest_sha256=sha(p/'FILES.json'),bound_files=len(rows),matlab_files=len(mfiles),
        bound_bytes=sum(r['bytes'] for r in rows),history_files=len(history),history_bytes=sum(r['bytes'] for r in history)))
    legacy=STAGE/'legacy_autonomous_sources'/name
    legacy.mkdir(parents=True,exist_ok=True);shutil.copyfile(p/'FILES.json',legacy/'issued_FILES.json')
latest={sha(p) for p in (ROOT/'autonomous_tenth/kit/autocase').rglob('*.m')}
legacy_rows=[]
for digest,paths in unique.items():
    if digest in latest:continue
    p=paths[0];rel=p.relative_to(ROOT);parts=rel.parts;dest=STAGE/'legacy_autonomous_sources'/parts[0]/Path(*parts[3:])
    dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    legacy_rows.append(dict(sha256=digest,bytes=p.stat().st_size,original_paths=[str(x.relative_to(ROOT)) for x in paths],
        staged_path=str(dest.relative_to(STAGE))))
write('autonomous_stage_inventory.json',autonomous)
write('legacy_unique_source_versions.json',dict(unique_matlab_files_all_stages=len(unique),
    total_matlab_copies=sum(len(v) for v in unique.values()),unique_matlab_bytes=sum(v[0].stat().st_size for v in unique.values()),
    older_versions_not_in_latest=len(legacy_rows),older_version_bytes=sum(r['bytes'] for r in legacy_rows),files=legacy_rows))

old=ROOT/'next_feedback/mac_kit/macfix/core/+csr/+hop/Layer.m'
new=ROOT/'return6000/kit/csr6000/model/+csr/+hop/Layer.m'
assert objects['+csr/+hop/Layer.m']==gitid(old)
provenance=ROOT/'return6000/data/invocations/run_20260924_114424/provenance.json'
actual=jsonread(provenance)
for source_manifest in (actual['model_source_snapshot'],actual['plan']['source_manifest']):
    assert next(x for x in source_manifest if x['path']=='+csr/+hop/Layer.m')['sha256']==sha(new)
verification=ROOT/'return6000/review/provenance/verification.json';check=jsonread(verification)
assert check['status']=='pass' and all(x['complete'] and x['source_files_verified']==99 for x in check['cases'])
diff=''.join(difflib.unified_diff(old.read_text().splitlines(True),new.read_text().splitlines(True),
    fromfile='main/+csr/+hop/Layer.m',tofile='corrected/+csr/+hop/Layer.m'))
(OUT/'grouped_routing_cleanup.diff').write_text(diff)
production=[]
for p in sorted((ROOT/'return6000/kit/csr6000/model').rglob('*')):
    if p.is_file():
        rel=p.relative_to(ROOT/'return6000/kit/csr6000/model').as_posix()
        production.append(dict(path=rel,same_as_main=objects.get(rel)==gitid(p),sha256=sha(p)))
assert [r['path'] for r in production if not r['same_as_main']]==['+csr/+hop/Layer.m']
write('production_hop_proof.json',dict(schema='csr-existing-validated-hop-cleanup-publication-proof-v1',
    main_commit=base,changed_production_file='+csr/+hop/Layer.m',old_sha256=sha(old),new_sha256=sha(new),
    scope='Exact ACK removes HOP resend owner but preserves queued structured ROUTING retry; other control cancellation unchanged.',
    source_model_files=len(production),otherwise_byte_identical_to_main=True,model_file_comparison=production,
    owner_archive=check['input_archive'],owner_archive_sha256=check['input_archive_sha256'],
    issued_kit_sha256=check['issued_kit_sha256'],runtime=actual['identity']['runtime'],
    actual_completed_6000_second_seeds=[c['seed'] for c in check['cases']],
    actual_source_snapshot_path=str(provenance.relative_to(ROOT)),actual_source_snapshot_sha256=sha(provenance),
    independent_verification_path=str(verification.relative_to(ROOT)),independent_verification_sha256=sha(verification),
    network_15_percent_parity_established=False,new_simulation_executed=False,
    source_shortkit_same=sha(ROOT/'next_feedback/short_kit/two_case_next/candidate/+csr/+hop/Layer.m')==sha(new)))
write('staging_receipt.json',dict(schema='csr-sep28-checkpoint-staging-v1',main_commit=base,repository_modified=False,
    checkpoints=staging,legacy_unique_source_versions=len(legacy_rows),original_publication_source_bytes_preserved=True))
print(json.dumps(staging,indent=2))
