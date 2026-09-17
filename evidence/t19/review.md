**Tranche 19 return review — accepted experiment; retain the current default**

The portable regression and both full-campus structural checks pass. All 700 tests in 60 classes passed on MATLAB R2025a (25.1.0.2943329). Both seed-128 cases completed the original 6,000-second campus workload. All 358 source bindings, 170 MATLAB files, 60 references and carried evidence hashes verify. The issued checker needed no repair. No rerun is required.

The default actual-tx case reproduces all T17 statistics and the 12 original core CSV files byte-for-byte. The experimental native-provisional policy remains available for research, but is not promoted. Numerical parity across flows remains open.

| Whole-run measure | Default actual-tx | Experimental native-provisional |
| --- | ---: | ---: |
| Offered attempts | 1,710,000 | 1,710,000 |
| Admitted applications | 12,484 | 13,812 |
| Delivered applications | 11,825 | 11,889 |
| Final retry-exhaustion drops | 402 | 1,519 |
| Pending applications at stop | 257 | 404 |
| Delivery/admission ratio | 94.72% | 86.08% |
| Mean delivered latency, seconds | 98.97 | 113.16 |
| 95th percentile delivered latency, seconds | 704.50 | 860.14 |
| DATA retry requests | 4,346 | 5,583 |

The 1,328 additional admissions partition into only 64 more deliveries, 1,117 more final drops and 147 more pending applications. This is an aggregate accounting identity, not a match of individual packets across divergent policy runs. Total delivered count is +0.48% versus ns-3 for the default and +1.02% for the experiment; admission count is +0.54% and +11.23%, respectively.

| Source | ns-3 delivered | Default delivered | Default difference | Experimental delivered | Experimental difference |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 | 410 | 411 | +0.24% | 292 | -28.78% |
| 3 | 8,535 | 8,472 | -0.74% | 8,462 | -0.86% |
| 4 | 419 | 348 | -16.95% | 382 | -8.83% |
| 5 | 1,369 | 1,644 | +20.09% | 1,990 | +45.36% |
| 7 | 574 | 533 | -7.14% | 572 | -0.35% |
| 8 | 462 | 417 | -9.74% | 191 | -58.66% |

Only two of the six delivered-flow comparisons are inside the descriptive ±5% band in each policy. The experiment brings source 7 closer, but substantially worsens sources 2, 5 and 8. The close whole-network total therefore does not establish practical per-flow parity.

**Capacity and retry findings.** The 16 deterministic mechanism tests passed in MATLAB. In the campus trace, node 5 local HOP admissions rise from 1,657 to 2,376 while relay HOP admissions remain nearly unchanged (1,735 to 1,738). Mean node 5 capacity retention, including right-censored pending episodes, falls from 28.23 to 19.35 seconds. Its HOP failures rise from 23 to 672: much of the added turnover comes from abandoning work. Local-versus-relayed effects are observed here without introducing or proving an explicit local-priority rule.

| Link | Default HOP failure releases | Experimental HOP failure releases |
| --- | ---: | ---: |
| 2→4 | 28 | 41 |
| 3→1 | 1 | 443 |
| 4→5 | 310 | 334 |
| 5→1 | 23 | 672 |
| 7→8 | 10 | 8 |
| 8→2 | 31 | 21 |

On 4→5, retry requests rise from 1,692 to 1,717 and HOP failure releases from 310 to 334. Most added failure releases instead occur on 5→1 (+649) and 3→1 (+442). HOP failure releases are lifecycle events: the default has 403 such releases but 402 final dropped applications. The independent mechanism report preserves this distinction and the non-bijective relationship between queued retry requests and later sent callbacks.

Experimental NWK custody has 408 owners at stop across 407 unique applications: all 404 pending applications plus three already-delivered applications awaiting upstream retirement, with one pending application held at two nodes. These counts are reconciled; custody owners are not interchangeable with final pending applications.

Archived OPNET whole-run receive rate remains within the descriptive band: default +3.64%, experimental +4.20%. OPNET aggregate evidence cannot establish the same per-flow comparisons available from ns-3.

**Runtime.** The owner reports 3 h 44 min 15 s overall. Simulation-and-result-return time is about 57.5 minutes for the default and 161.4 minutes for the experiment, exceeding the earlier pair estimate. These are observed wall times from this machine/run, not an isolated CPU-cost benchmark.

**Recommended next milestone.** Keep actual-tx and quantify full-campus seed variation before changing another behavior. A small additional matched MATLAB/ns-3 seed set would test whether the residuals consistently affect the same flows and help define the practical ±5% goal. Reuse this completed seed-128 baseline; do not rerun T19 merely to repeat this result. This recommendation is not a new implementation or execution.

This package contains the original owner archive unchanged, the full checker output, acceptance decision, exact comparison table and independent audits. The reviewers executed Python analysis only; owner MATLAB evidence supplies runtime validation. To reproduce the official review against your exact issued T19 installation, run:

```text
python scripts/analyze_tranche19_return.py --evidence /path/to/owner.zip --source-root /path/to/csr19 --output /path/to/new-review-directory
```

Owner archive SHA-256: `525758669b8f84fa5dada46e293b8482980ef389efc5408ff056aac0e804ee30`. Candidate SHA-256: `37b87a253a217824b0160f14b23f2b498e9df7a99cdc46648f3d9785a2fda777`.
