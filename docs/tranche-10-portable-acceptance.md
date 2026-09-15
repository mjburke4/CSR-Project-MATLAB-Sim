# Tranche 10 portable acceptance

Tranche 10's repaired build is **accepted for its portable R2025a structural and functional gate**. All required execution phases completed. Numerical parity remains open: the campus total is close to ns-3, but individual flow differences increased overall, and the smaller contention outlier persists.

The accepted build is the existing **`csr10r.zip`**. This review requires no simulator changes or MATLAB rerun. The full returned evidence is included as `tranche10_evidence.zip`; all other material in this bundle documents its verification and interpretation.

## Actual MATLAB execution

The owner ran MATLAB **25.1.0.2943329 (R2025a)** using the portable backend on September 14, 2026, from **13:29:36.361 to 15:16:53.531 UTC**. Total wall time was **1 hour 47 minutes 17 seconds**. The 6,000-second campus case took **73 minutes 3 seconds**.

| Acceptance check | Result |
| --- | --- |
| MATLAB unit tests | **550/550 passed**, no failures or incomplete tests; all named tests match the executed source |
| Prescribed subsystem contracts | **534/534 checkpoints**: 279 MAC, 154 receiver, 101 ACK; exact agreement with pinned native values |
| Retained scenarios | **29/29 completed** |
| Research sweeps | **18/18 completed** |
| Small diagnostics | **6/6 completed** |
| Passive tracing controls | **2/2 passed**; 24 CSV file pairs byte-identical, configuration and statistics exact |
| Campus benchmark | **6,000 simulated seconds**, seed 128; all six application sources made progress |
| Executed source verification | **225 files**, including all **124 MATLAB files**, match immutable `csr10r.zip` |
| Reference verification | **332 file hash/size checks** passed |
| Returned artifact verification | **854 outer bindings**, plus **858 bindings in 63 nested manifests**; ZIP CRC and path checks passed |

These **550 tests executed in MATLAB on the owner's laptop**. Python was used here to inspect the returned files, verify hashes, reconstruct application outcomes and compare the simulators. It did not substitute for MATLAB execution. No new MATLAB, ns-3, OPNET or native MATLAB-backend execution occurred in the review workspace.

The full retained mesh run also reproduced the earlier focused mesh result: configuration and statistics are exact, and all 11 compared raw CSV files are byte-identical. The original event limit remained in force. This closes the previously observed mesh execution gap after the retry-deadline repair. The original failure log lacked the clock and callback details needed to prove that defect caused that specific failed run.

## Campus results against ns-3

| Measure | Accepted T7 MATLAB | T10 MATLAB | Pinned ns-3 |
| --- | ---: | ---: | ---: |
| Admitted/generated applications | 12,382 | 12,484 | 12,417 |
| Delivered applications | 11,727 | **11,825** | **11,769** |
| Pooled delivered-packet mean latency, seconds | 103.963 | 98.970 | 104.195 |

T10 delivered **56 more packets than ns-3 (+0.476%)** and 98 more than T7. Its absolute total discrepancy nevertheless grew slightly: T7 was 42 packets below ns-3. The lower observed latency involves different delivered packet populations and is not evidence of a paired per-packet improvement.

| Source → gateway 1 | T7 delivered | T10 delivered | ns-3 delivered | T10 difference from ns-3 |
| --- | ---: | ---: | ---: | ---: |
| 2 → 1 | 395 | 411 | 410 | +0.24% |
| 3 → 1 | 8,593 | 8,472 | 8,535 | −0.74% |
| 4 → 1 | 454 | 348 | 419 | **−16.95%** |
| 5 → 1 | 1,285 | 1,644 | 1,369 | **+20.09%** |
| 7 → 1 | 617 | 533 | 574 | −7.14% |
| 8 → 1 | 383 | 417 | 462 | **−9.74%** |

Node 8 improved from the earlier **−17.10%** delivery deficit. Nodes 4 and 5 moved farther from the reference. Summed absolute per-flow delivery differences increased **314 → 496 packets**. The largest absolute flow deviation in this particular campus run is now 20.09%; this is not a bound across scenarios or seeds.

MATLAB accounting closes exactly: **12,484 generated = 11,825 delivered + 402 dropped + 257 pending** at the finite stop. The native trace has 648 admitted applications without an observed delivery; this evidence does not classify them as drops or pending work.

All six offered generators made 285,000 attempts each. MATLAB's complete counters record **1,710,000 attempts**, 12,484 admissions and 1,697,516 blocks at the admission-capacity gate. The per-attempt trace retains its first **100,000 rows** and explicitly omits **1,610,000** later rows. Aggregate accounting is complete; a full-run reconstruction of every admission decision is unavailable. Protocol/application observations support the delivered totals.

Archived OPNET campus aggregates were also compared, without an OPNET rerun. Average receive rate is **1.970833 packets/s** in MATLAB versus **1.901667 packets/s** in OPNET (**+3.64%**). The mean of populated 60-second delay-bucket means is **98.091 s** versus **112.748 s**. These bucket means differ from the pooled packet latency above. No OPNET packet-level equivalence is claimed.

## Small diagnostics and retained checks

All five contention seeds retain exactly their T9 generated, delivered, dropped and pending counts, including each source separately. Mean delivered count remains **916.4 MATLAB versus 891.0 ns-3 (+2.85%)**.

The compact outlier is unchanged: in contention seed 129, source 2 delivers **510 versus 353**. During the first 20 traffic seconds it delivers **152 versus 35**, accounting for **117 of the 157-packet gap**. Admission seed 129 delivers **11,357**, three more than T9 and 130 more than ns-3 (**+1.16%**). This does not establish a general improvement.

The 29 retained cases preserve all per-case application counts from accepted T7, totaling 149 generated, 122 delivered and 27 dropped. The 18 sweeps retain aggregate totals of 357 generated, 334 delivered and 23 dropped, with two offsetting case changes: offered-load ×4 at seed 129 gains one delivery; the 180-second recovery case at seed 128 loses one. Existing recovery limitations remain open.

## Scope and next investigation

The accepted changes address strict-future IdleRTS scheduling, the MAC slot clock's integer-nanosecond epoch and retry-deadline comparisons. The retry repair compares and schedules the same absolute deadline, avoiding a zero-delay retry loop caused by floating-point subtraction. Failure diagnostics expose scheduler context without changing event ordering. The matched receiver contracts provide bounded timing evidence, not general RF equivalence. This acceptance review changed no simulator or reporting source.

The next investigation should first replay **identical explicit contention choices** in a small matched experiment. Hold offered arrivals, initial conditions and prescribed receiver outcomes equivalent; compare the first divergence in DATA reception, ACK eligibility and transmission, HOP capacity release, and subsequent application admission. Matching numeric seeds alone does not match random streams. Existing forced-slot overrides require equivalent semantics before they can serve as this control.

Then isolate competing local and relayed traffic along **4 → 5 → 1**, recording service and admission by original source. The campus redistribution makes this a useful target, but does not prove a particular defect. Preserve PHY/ECC and radio policy; a production correction needs a demonstrated semantic mismatch, not a better-fitting aggregate count. No additional long campus run is needed to accept this return.

## Provenance and reproducibility

The executed repaired archive has no recorded Git commit. Its base candidate commit is `87d0d69ed7f23496f711816bb0f048548366ac7c`; that commit alone does not identify the repaired code. The exact build is identified by:

- `csr10r.zip` SHA256: `df3ad517708fccc9e4c85d8e38c3492b97aff8d2d5236b3f05249da3cd15b900`.
- Executed source-snapshot SHA256: `9be444b0fb1ffbfe818cab86502a287b19e3da83467d210ef426ec3b19e183da`.
- Returned `tranche10_evidence.zip` SHA256: `066c180f31c44412b617e1cc0f6197711ac50daaac9cbbbcbefbc6a59f1916f8`.
- Pinned ns-3 source: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.

`acceptance.json` is the final disposition. `canonical/review.json` deliberately retains its original `acceptance_established: false`: the analyzer completed the structural gate and left the final decision to review. It has not been rewritten. `integrity/` and `outcomes/` hold independent audits and their analysis scripts. `input-location-map.json` resolves original temporary input paths to immutable archive members with hashes. `manifest.json` binds all other bundle files.

To repeat the canonical review, extract the original `csr10r.zip` to a short directory such as `csr10`, keep this bundle in a short directory such as `t10a`, and run from the source directory:

```bash
python scripts/analyze_tranche10_return.py --evidence ../t10a/tranche10_evidence.zip --source-root . --output ../t10check
```

The independent scripts preserve the paths used for this review; their workspace constants must be adjusted for a different location. The primary reviewer above accepts explicit paths. The 92 MB source archive is preserved separately and is not duplicated in this review bundle. No GitHub push, pull request or merge was performed for this acceptance.
