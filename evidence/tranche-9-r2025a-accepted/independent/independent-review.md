# Independent Tranche 9 owner-return gate

Recommendation: accept this portable R2025a execution and the reporting-only
repair. No MATLAB structural blocker was found. The completed review does not
establish numerical parity or a performance improvement.

The uploaded `tranche9_evidence.zip` has SHA256
`ddcede0a83b5ff906a7736f63406fc4cecb11e841795e39e93237364e0e11edf`.
The executed candidate remains
`99fff0381fe9621ccd76fbdce41eac9aba5a9469`, checked from the independent frozen
worktree `t9r/src`; the repaired Python reviewer is not substituted into the
owner's executed source snapshot.

The independent `independent_qa.py` uses only Python's standard library and
does not import the production return reviewer. It reads the original ZIP,
verifies CRCs, checks path safety and unique membership, rehashes all listed
artifacts, and compares returned source and reference hashes directly with
committed Git blobs. Its reproducible receipt is `receipt.json`.

| Check | Independent result |
| --- | --- |
| Archive | 10,194,267 bytes; 177 files; 154,809,567 expanded bytes |
| Declared artifact hash and size checks | 438 passed: 176 outer and 262 nested |
| Executed source snapshot | All 206 files match committed candidate, including 115 MATLAB files |
| Referenced source/evidence inputs | All 294 files match committed candidate |
| Actual owner runtime | MATLAB 25.1.0.2943329 (R2025a), portable backend |
| Execution interval | 2026-09-11 18:01:56.345–18:25:37.630 UTC: 23m41.285s |
| Full portable test membership | All 514 methods present exactly once; 514 passed, zero failed/incomplete; test-class diary entries present |
| Deterministic contracts | 101/101 rows match the native reference; maximum numerical difference zero |
| Diagnostic cases | All six planned cases completed |
| Tracing controls | Both completed; 24 CSV pairs byte-identical and statistics/configuration exactly equal |
| Service observations | 120,835 rows reconciled with original protocol/admission observations |
| Admission logical fields | All six logical fields checked across all 101,000 in-window attempts |

The six contract cases cover ACK wait, SYNC freezing, Track resumption, DATA
cancellation, control cancellation, and HOP release order. These are prescribed
subsystem conditions; they do not establish equivalent RF delivery or random
streams.

All service rows are within `300 <= t < 320`, have monotonic times and contiguous
observation identities, and satisfy their original callback/admission coverage
and omission counters. Cancellation before/after pairs preserve reservation
state and reconcile removed entries against data queue depth. The five
contention cases each remove one queued entry in this observation window;
the admission control removes none. Six scalar reads are accounted for per
cancellation snapshot, with no observer event scheduling or random draws.

Two Python reviewer defects were independently confirmed and reviewed:

1. MATLAB retains logical values as JSON `true`/`false`, while its admission
   CSV renders the same fields as `1`/`0`. The frozen reviewer incorrectly
   passed all admission fields to its strict numeric parser. The repair
   supports these representations only for six declared logical fields;
   numeric identities still reject booleans.
2. The accepted Tranche 8 and returned Tranche 9 configurations differ only
   in the installation prefix of `SharedScenario.SourcePath`. Both paths
   identify the exact planned relative input and its SHA256. The repair
   checks that binding, reports both paths, and compares all remaining
   configuration fields exactly.

`repair_gate.py` and `repair-receipt.json` bind the three repaired Python files,
independently verify that all 115 MATLAB files remain unchanged, and bind the
primary test and review logs. Ten new regressions cover these two concrete
issues. The primary full Python suite passed 254/254; the repaired complete
owner-return review exited zero using the frozen candidate as `--source-root`.
This independent reviewer inspected those logs rather than rerunning the
suite.

All six diagnostic application admission/delivery/drop/pending totals match
the accepted Tranche 8 totals. Five complete statistics objects are exactly
equal. For contention seed 131, latency sum increases by approximately
0.052 seconds and mean packet latency by approximately 0.000058101 seconds;
its delivery counts are unchanged. Some internal traces differ, so blanket
claims that all legacy observations are unchanged are inappropriate.

No MATLAB, ns-3, or OPNET execution was performed by this reviewer. The nine
declared local MAT artifacts remain on the owner's laptop and were not
available for independent rereading. No campus rerun, retained scenario/sweep
rerun, or native MATLAB R2026a validation is present in this archive. Recorded
source/reference stability is an owner-runner assertion supported by exact
returned snapshots, not an independently observed execution environment.

The two reporting defects do not require an unchanged MATLAB rerun. Accept
the portable evidence with the original executed candidate identity, preserve
the uploaded archive, and retain numerical/early-contention differences as
unresolved engineering work.
