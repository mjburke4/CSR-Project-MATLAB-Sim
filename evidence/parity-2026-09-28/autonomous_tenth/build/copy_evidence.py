from pathlib import Path
import shutil

base = Path(__file__).resolve().parents[1]
root = base / 'kit/autocase'
target = root / 'ref/membership'
target.mkdir(parents=True, exist_ok=True)
for name in [
    'REVIEW.md', 'membership_audit.json', 'source_path_proof.json',
    'evidence_receipt.json', 'candidate_scope_review.json',
]:
    shutil.copyfile(base / 'native' / name, target / name)
for name in ['snmp_node3_lifecycle.json', 'late_routes_node3.json']:
    shutil.copyfile(base / 'matlab' / name, target / name)
for name in ['watchdog_membership_audit.json', 'watchdog_history.csv',
             'node3_route7_updates.csv', 'membership_preflight_peer_review.json']:
    shutil.copyfile(base / 'receiver' / name, target / name)
shutil.copyfile(base / 'receiver/Discovery_Watchdog_Review_2026-09-28.md', target / 'receiver_review.md')
shutil.copyfile(base / 'review/discovery_membership_preflight_review.json', target / 'preflight_review.json')
(target / 'README.md').write_text('''# Discovery membership evidence

Run only `report = run_autonomous_tests` from the kit root. No native commands are required.

Native source and the actual L return show that the watchdog expires correctly. The discrepancy is the portable advancement routine importing current application routes into the discovery table. The isolated candidate removes only that import and preserves explicit population by local discovery completion and received DONE.

The new public checks establish retained routing and transit DATA behavior plus the legitimate population boundaries. Their MATLAB execution and the M network continuation remain pending owner execution. Existing unrelated DONE/wait semantics and all prior limitations remain unchanged. The native ten-node bound applies to an individual completion report, not the total discovery table.
''')
print('Copied final membership source/capture/preflight evidence.')
