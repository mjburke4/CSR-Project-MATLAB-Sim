from pathlib import Path
import json,hashlib,shutil
base=Path(__file__).resolve().parents[1];root=base/'kit/autocase';target=root/'ref/identity';target.mkdir(parents=True,exist_ok=True)
for name in ['REVIEW.md','sequence_audit.json','source_path_proof.json','evidence_receipt.json','candidate_scope_review.json']:
 shutil.copyfile(base/'native'/name,target/name)
for name in ['discovery_sequence_audit.json','native_discovery_allocation.csv']:
 shutil.copyfile(base/'matlab'/name,target/name)
shutil.copyfile(base/'review/discovery_identity_preflight_review.json',target/'preflight_review.json')
(target/'README.md').write_text('''# DISCOVER identity evidence

These files document read-only native source/capture audits and static candidate review. Run only `report = run_autonomous_tests` from the kit root; no native commands are required.

The audit distinguishes native's process-wide outer DISCOVER label from source-local bookkeeping and payload discovery-session sequence. The exception is restricted to the captured protected, non-ACK broadcast subtype. Both raw outer values remain in each eligible child record. Native fixtures, protocol behavior and all other comparisons remain unchanged.

Native and MATLAB source review found no behavioral consumer of this outer identifier for the eligible path. No native or MATLAB network was rerun to create this proof. The new seven-check public comparator preflight and J network continuation await owner MATLAB execution.
''')
print('Copied final discovery identity audit and static preflight/candidate review.')
