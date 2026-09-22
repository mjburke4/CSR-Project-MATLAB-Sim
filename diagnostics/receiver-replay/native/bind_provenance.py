#!/usr/bin/env python3
"""Bind the built native fixture to pinned source and untouched engine libraries."""
import pathlib,json,hashlib,tarfile,subprocess
R=pathlib.Path(__file__).resolve().parents[2];N=R/'receiver_replay/native';E=R/'startup131/environment'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
for archive,root in [(E/'source.tar.gz',E/'csr'),(E/'engine.tar.gz',E/'engine')]:
 count=0
 with tarfile.open(archive) as t:
  for m in t:
   if not m.isfile():continue
   rel=pathlib.Path(*pathlib.Path(m.name).parts[1:]);p=root/rel;assert p.is_file() and hashlib.sha256(t.extractfile(m).read()).hexdigest()==sha(p),(archive,rel);count+=1
 checks.append(dict(archive=archive.name,archive_sha256=sha(archive),source_regular_files_checked=count,all_original_files_unchanged=True))
receipt=dict(source_repository='mjburke4/CSR-Project-NS3-part2',source_commit='486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b',engine_repository='nsnam/ns-3-dev-git',engine_commit='6b5cd24ea80713ce16d88575869aedd6f432bdae',archives=checks,compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0],shared_libraries={p.name:sha(p)for p in (E/'engine/build/lib').glob('libns3-*-debug.so')},binaries={p.name:sha(p)for p in [N/'capture-exe',N/'receiver-replay']},source_files={str(p.relative_to(N)):sha(p)for p in N.rglob('*')if p.is_file() and p.suffix in ['.h','.cc','.py']},original_trace_sha256=sha(R/'original_extracted/t25up/evidence/tranche-25-ns3-reference/s132/ns3-trace.csv.gz'),scenario_sha256=sha(R/'original_extracted/t25up/evidence/tranche-25-ns3-reference/s132/scenario.csv'),capture_trace_sha256=sha(N/'capture/ns3-trace.csv'),capture_receiver_input_sha256=sha(N/'capture/receiver-input.log'),source_logic_policy='production files unchanged; copied observation/input-injection seams only; no forced Track, successful packet injection, or prescribed receive outcomes')
(N/'native-provenance.json').write_text(json.dumps(receipt,indent=2)+'\n');print('verified',[(x['archive'],x['source_regular_files_checked'])for x in checks])
