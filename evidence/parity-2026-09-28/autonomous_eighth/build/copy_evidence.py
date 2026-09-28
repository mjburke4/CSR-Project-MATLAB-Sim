from pathlib import Path
import shutil

base = Path(__file__).resolve().parents[1]
root = base / 'kit/autocase'
target = root / 'ref/receiver_timers'
target.mkdir(parents=True, exist_ok=True)
for name in [
    'REVIEW.md', 'arithmetic_summary.json', 'source_path_proof.json',
    'evidence_receipt.json', 'candidate_scope_review.json',
    'acquisition_schedule_fixture.csv', 'phy_component_fixture.csv',
]:
    shutil.copyfile(base / 'native' / name, target / name)
for name in ['relative_timer_audit.json', 'native_TX_finish_arithmetic.csv']:
    shutil.copyfile(base / 'receiver' / name, target / name)
shutil.copyfile(base / 'receiver/PHY_Relative_Timer_Review_2026-09-28.md', target / 'receiver_review.md')
shutil.copyfile(base / 'review/receiver_timer_preflight_review.json', target / 'preflight_review.json')
(target / 'README.md').write_text('''# Receiver timer evidence

Run only `report = run_autonomous_tests` from the kit root. No native build or commands are needed.

The native arithmetic probe and unchanged captured geometry establish the integer-nanosecond scheduling boundary. The MATLAB component preflight uses the unchanged public allocator and real receiver/MAC component callbacks; its execution remains pending until this kit is run. The accepted prior J result remains historical evidence, not a new execution.

K supplements the existing TransportTiming arrival/preamble/end policy with acquisition, the source-confirmed rejected-return 28 ns delay, and paired PHY/MAC transmission completion. It retains MATLAB's PHY-first callback decomposition and uses one deadline for PHY TxUntil and both completion callbacks. Generic MAC after(), raw physical geometry, bit truncation, BER and common-input guards remain unchanged.

Conversion uses integer nanoseconds divided by 1e9. Native GetSeconds differs by one binary64 ULP at 2 of 10,301 captured ticks; neither exception changes any of the 1,542 sampled component counts or 4,070 complete captured interval counts. The rejected-return path has no observed callback in this capture and is covered by source binding and a pure target calculation only.
''')
print('Copied final native, receiver, and preflight review evidence.')
