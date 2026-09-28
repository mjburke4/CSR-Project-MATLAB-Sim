from pathlib import Path
import shutil,hashlib,json
base=Path(__file__).resolve().parents[1];root=base/'kit/autocase';target=root/'ref/control';target.mkdir(parents=True,exist_ok=True)
for name in ['control_size_probe.cc','control_size_probe.log','compile_command.json','captured_frames.tsv','evidence_receipt.json','candidate_scope_review.json','fixture_control_audit.json','source_path_proof.json','REVIEW.md']:
 shutil.copyfile(base/'native'/name,target/name)
for name in ['size_audit.json','routing_sizes.csv']:
 shutil.copyfile(base/'matlab'/name,target/name)
shutil.copyfile(base/'review/control_wire_preflight_review.json',target/'preflight_review.json')
receipt=json.loads((target/'candidate_scope_review.json').read_text())
for name,key in [('candidate_transform.json','candidate_manifest_sha256'),('run_autonomous_tests.m','runner_sha256'),('+ac/controlWireBytes.m','helper_sha256')]:
 assert hashlib.sha256((root/name).read_bytes()).hexdigest()==receipt[key],name
(target/'README.md').write_text('''# Control-wire evidence

These files document native packet/component experiments and static source review; they are not additional owner commands. Run only `report = run_autonomous_tests` from the kit root.

The native probe exercised 12 packet/header/envelope cases, including the captured63-byte transmission, compact REQUEST16 versus raw-section REQUEST23, metadata NoPath16 versus a real three-byte body19, and native PHY airtime arithmetic. It ran no full network. Native NoPath sender behavior is source verified; its live sender path was not executed, and the accepted network fixture contains no NoPath.

The compile command refers to the separate pinned native build environment; that environment is not required or bundled in this MATLAB kit. Source pins, fixture hashes and exact candidate review are in the JSON receipts. `routing_sizes.csv` and `size_audit.json` audit the native fixture against the supplied MATLAB return. The MATLAB component review is static; six REQUEST and three NoPath checks await owner runtime execution.
''')
print('Copied final source-reviewed control evidence; manifest/runner/helper review hashes agree.')
