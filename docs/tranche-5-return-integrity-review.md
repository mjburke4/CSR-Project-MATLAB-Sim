# Tranche 5 returned-evidence integrity review

The submitted R2025a evidence passes the independent integrity audit against
candidate commit `536b288d765a7b18007ff7898eaf3f2e173d9e58`. This review checked the
original archive and committed Git objects, without changing the uploaded archive
or executing MATLAB locally.

| Check | Verified result |
| --- | --- |
| Original archive | 3,727,389 bytes; SHA-256 `824cf0f5cb6a735ee896ebc5431be5c72f69d9d95135c8e03311238bd0ca75c1` |
| Archive membership and contents | 551 unique files, identical to the extracted bytes; ZIP CRC checks passed |
| Top-level inventory | All 550 declared artifacts have matching hashes and byte counts; the remaining file is the intentionally self-excluded metadata |
| Local artifacts | 48 execution-machine artifacts are correctly absent from the submitted ZIP |
| Source snapshot | All 116 paths match the committed candidate: 88 MATLAB files, 12 Python files, five CSV files and 11 JSON files |
| Candidate manifest | SHA-256 `63f1442ac301d32d24891fc14437b30021f182fcb4cb6e4a532dee052c774e35` matches the committed Tranche 5 candidate |
| Portable tests | Exactly 367 distinct test names across 29 classes match the committed `methods (Test)` declarations; all passed, with zero failed or incomplete |
| Test CSV | SHA-256 `0bba05d281b6d499c0125508f9b40977c13e648b42006a2f1709c587ab2c2c60`; summed unit-test duration 151.264 seconds |
| Case manifests | All 29 manifests verified: 18 new sweep cases and 11 retained Tranche 4 cases |
| Nested verification | 33 complete source-snapshot checks, 1,165 artifact hash/size checks and 295 CSV row-count checks passed; repeated nested declarations are included in these counts |

The initial and final Tranche 5 source snapshots are identical. The retained
Tranche 4 source snapshot and Tranche 3 MATLAB-only snapshot also match the same
candidate, and all three metadata records agree on the test CSV and 367/367 result.
Every declared case-manifest hash matches its actual file.

Nine byte-count declarations across the inventories use JSON scientific notation.
Each decodes to a finite, nonnegative, mathematically integral value and matches
the actual raw byte length. Rejecting these solely because Python decodes them as
`float` is a consumer compatibility defect, not an evidence-integrity failure.

The retained Tranche 4 writer deliberately excludes its live `validation.log`
from its own inventory. The final closed log is present and correctly hashed in
the enclosing Tranche 5 inventory. MAT objects and nested ZIPs remain on the
execution machine under the documented archive policy.

This result verifies source provenance and the submitted portable R2025a
execution record. It does not establish native execution, R2026a acceptance,
6,000-second sweep completion, or numerical/full protocol parity. Acceptance of
the measured delivery, retry and recovery outcomes requires the separate results
analysis.

The detailed machine-readable record is
[`tranche-5-return-integrity.json`](../evidence/tranche-5-return-integrity.json).
