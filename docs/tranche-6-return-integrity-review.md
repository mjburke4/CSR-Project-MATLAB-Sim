# Tranche 6 independent integrity review

Status: **PASSED**.

Candidate: `21c0a3f024c9efffdbd11c8059f1540a67c19b1a`. Pinned ns-3 source: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.

Returned archive: `tranche6_evidence.zip`, 3,893,666 bytes, SHA-256 `5c8ec2997ae8c248625240c3fd084aaaca85d5221ec7a347a0aaad2dabeb1e17`.

| Check | Result |
| --- | --- |
| ZIP CRC and extraction | 552 members; no CRC, duplicate-path, extraction-byte, or membership failures |
| Archived artifact hashes and sizes | 551 unique files; 1716 outer/nested assertions |
| Manifest CSV row counts | 295 verified |
| Source provenance | 127 unique source files, including 90 MATLAB files, match git and the candidate ZIP |
| All runtime source snapshots | 35 snapshots; 4408 hash assertions verified |
| MATLAB tests | 380/380 passed; 0 failed; 0 incomplete; 13 outage recovery tests |
| Runtime | MATLAB R2025a, 25.1.0.2943329, portable |
| Cases | 18 sweep cases plus 28 regression summary cases present; all 46 application-accounting identities hold |
| Stop-time control boundary | Three 300-second cases have DataDrained=false from one pending control resend each; all application/DATA custody counters are zero |
| Shared comparisons | Main reviewer reports 5/5 application matches; result records inspected without duplicate execution |
| Native/long-run execution | Not requested |

The uploaded archive and extracted evidence were not changed. Review scripts wrote only in this independent-review directory.

## Boundaries

- The 48 unique MAT result/test objects are intentionally excluded by the declared archive policy; their recorded hashes and sizes agree across nested inventories, but their bytes cannot be independently checked from this ZIP.
- The execution host has no available git HEAD metadata. Candidate identity is independently established by comparing all 127 source-snapshot hashes, including all 90 MATLAB files, against git commit 21c0a3f and the delivered candidate ZIP.
- Nested metadata retains Tranche 3/4/5 schema labels and historical base commits because those regression runners are reused; every checked source snapshot matches the Tranche 6 candidate. These labels do not indicate older code execution.
- The nested Tranche 4 inventory deliberately omits its own live validation.log per the candidate runner. Its closed final bytes are independently covered by both enclosing Tranche 5 and Tranche 6 inventories.
- The sweep plan retains planned-not-executed because it is the immutable pre-execution plan; separate case manifests, summaries, and outer metadata establish completed execution.
- Three 300-second freshness cases report DataDrained=false because that conservative field includes the shared resend queue. Each has zero pending applications, HOP DATA, DACK hold, NWK custody, and route wait, with one pending reliable CONTROL owner. Trace inspection shows ROUTING 2->3 and DISCOVER controls admitted at exactly the 900-second stop. This is a finite-stop control-residual boundary, not an archive-integrity failure.
- Native wireless simulator execution and long-run cases were not requested. This is portable R2025a evidence; no new MATLAB or ns-3 execution was performed by this integrity review.
- This integrity review verifies provenance and supplied accounting. The main reviewer owns measured Tranche 5/6 outcome analysis and the five MATLAB/ns-3 shared application comparisons.
