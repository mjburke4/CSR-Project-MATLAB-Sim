from pathlib import Path
import shutil

base = Path(__file__).resolve().parents[1]
root = base / 'kit/autocase'
target = root / 'ref/lifecycle'
target.mkdir(parents=True, exist_ok=True)
for name in [
    'REVIEW.md', 'lifecycle_audit.json', 'source_path_proof.json',
    'evidence_receipt.json', 'candidate_scope_review.json',
]:
    shutil.copyfile(base / 'native' / name, target / name)
for name in ['key_update_order_audit.json', 'key_update_masking_cases.csv', 'lifecycle_preflight_peer_review.json']:
    shutil.copyfile(base / 'receiver' / name, target / name)
shutil.copyfile(base / 'receiver/KEY_UPDATE_Order_Review_2026-09-28.md', target / 'receiver_review.md')
for name in ['snmp_node5_lifecycle.json', 'key_update_node4_boundary.json']:
    shutil.copyfile(base / 'matlab' / name, target / name)
shutil.copyfile(base / 'review/discovery_lifecycle_preflight_review.json', target / 'preflight_review.json')
(target / 'README.md').write_text('''# Discovery lifecycle evidence

Run only `report = run_autonomous_tests` from the kit root. No native build or commands are needed.

The native source/capture audit and actual MATLAB ordered events identify independent SNMP requester ownership and KEY_UPDATE admission-order defects. The candidate is restricted to those two boundaries. It preserves K receiver timers, strict comparison guards, actual native input fixtures and all original model files.

The MATLAB public component preflight and L network continuation remain pending owner execution. Capacity fallback checks establish retained portable ownership safety; native saturated resend behavior differs and is not claimed equivalent. The native capture does not exercise unrelated DONE wait-policy differences or the ten-requester capacity boundary; those policies remain unchanged.
''')
print('Copied final lifecycle, ordered-boundary and source/preflight evidence.')
