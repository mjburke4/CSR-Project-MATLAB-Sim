# Tranche 17 portable acceptance

**Accepted: all 660 portable MATLAB tests and the unchanged 6,000-second campus structural gate passed.** No MATLAB rerun or reviewer repair is needed. This establishes a validated portable baseline while retaining measured numerical differences.

The owner ran MATLAB R2025a, version 25.1.0.2943329, on 15 September 2026. The full gate took **66 minutes 58 seconds**, including about 61.6 minutes for the campus simulation call. This review did not execute MATLAB or rerun ns-3/OPNET.

## Integrity and structural result

The issued checker and independent review verified the exact candidate, all **313 source files (160 MATLAB)**, **520 references**, all **304 prior T16 source bindings (155 MATLAB)** unchanged, both completed stage receipts, every test identity and all transported artifact hashes. The one declared local MAT snapshot is optional and was not needed for return review.

At 6,000 seconds, application accounting closes exactly:

| Outcome | Count |
| --- | ---: |
| Admitted/generated | 12,484 |
| Delivered | 11,825 |
| Retry-exhaustion drops | 402 |
| Pending at the finite stop | 257 |

All six traffic sources made progress. There were 1,710,000 scheduled generation attempts, of which 1,697,516 were blocked by the pre-generation NSDP gate. These blocked attempts are not generated-and-dropped applications. Complete admission counters are retained; the declared trace contains its first 100,000 records and explicitly omits 1,610,000 later records.

All **605,198 protocol** and **749,282 PHY** records are present, with no omissions. The run made 47,145 physical transmissions and 282,870 receiver attempts: 80,083 received, 202,775 dropped and 12 pending. Overheard receiver outcomes are not equivalent to addressed application outcomes.

Pending application custody, resend entries and DACK holds remain legitimate finite-stop observations. No draining period was added. HOP and NWK control ownership are zero; the current MAC feedback queue depth is not exported, so this is not proof that every MAC control queue is empty.

## Parity result

MATLAB delivered **11,825 packets versus 11,769 in ns-3 (+0.476%)**. The six-flow sum of absolute delivery differences is **496 packets**; the net difference of 56 packets conceals redistribution.

| Source → gateway | MATLAB delivered | ns-3 delivered | Difference |
| --- | ---: | ---: | ---: |
| 2 → 1 | 411 | 410 | +0.24% |
| 3 → 1 | 8,472 | 8,535 | -0.74% |
| 4 → 1 | 348 | 419 | -16.95% |
| 5 → 1 | 1,644 | 1,369 | +20.09% |
| 7 → 1 | 533 | 574 | -7.14% |
| 8 → 1 | 417 | 462 | -9.74% |
| Total | 11,825 | 11,769 | +0.48% |

The archived OPNET comparison remains an aggregate comparison:

| Metric over the original window | MATLAB | ns-3 | OPNET |
| --- | ---: | ---: | ---: |
| Receive rate, packets/s | 1.970833 | 1.961500 | 1.901667 |
| Mean of populated delay-bucket means, seconds | 98.091469 | 103.181006 | 112.748007 |

MATLAB receive rate is +3.637% relative to OPNET. Its mean of populated delay-bucket means is −4.933% relative to ns-3 and −12.999% relative to OPNET. These delay values are unweighted means over 95 populated 60-second bins, not per-packet means. MATLAB's directly measured packet-weighted mean latency is 98.970123 seconds, with a 704.503811-second 95th percentile. The first five delay bins are missing for every source and remain missing. OPNET's corresponding packet-count bins are also missing while its receive-rate bins are observed zeros; they are not silently interchanged.

Same numeric seeds do not establish common random streams. A single campus seed does not establish statistical equivalence. OPNET supplies archived aggregates, not packet/path/PHY event truth.

## Regression against T10

All campus Statistics fields match accepted T10 exactly. All **11 retained raw CSV files** match byte for byte, including the full protocol and PHY traces. Scenario, application-outcome and aggregate CSVs also match byte for byte. The two summary CSVs differ only in RuntimeSeconds.

Thus T11–T16 diagnostic and optional-timing additions caused no observed campus regression with default continuous timing. T17 demonstrates no campus parity improvement over T10. The earlier controlled timing benefit does not justify changing the production default.

## Recommended Tranche 18

Investigate **real-PHY local-versus-relayed service at node 5, together with feedback and retry behavior on 4 → 5**. Node 5 delivers 20.09% more locally generated traffic than ns-3 while source 4 delivers 16.95% less. Independently reconstructed MATLAB events place **309 of 402 terminal drops (76.9%)** at node 4 on 4 → 5, with 1,692 of the run's 4,346 DATA retries on that link. These observations locate the next investigation; they do not establish an implementation defect relative to ns-3.

Use bounded real-PHY workloads and several seeds to distinguish local/relay admission and service allocation from stochastic variation. Compare actual native and MATLAB service, feedback and retry observations before selecting a policy correction. Preserve PHY/ECC and continuous timing. There is no need to repeat the completed controlled ACK-boundary experiments to accept T17.

## Provenance and reproduction

- Candidate SHA256: `6210329add45cd50c8173e2e1390f2aa157a154c6977a10bee5917ee01a1052c`
- Owner ZIP SHA256: `19921afa83c57db2779e4302e5b39afef5120afb129a87fddb1f6d1bdbec2bd1`
- Source snapshot SHA256: `5ba7ff4b26a12192496d98cc36ccbcffe77199255da1cbda1025f83a14618891`
- Reference snapshot SHA256: `6cce3c1bcfc836fb369890ffeae76aab499eb8732036ba81ff3777d91f92601c`
- Upstream ns-3 pin: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`

`SourceCommit` identifies upstream ns-3; the candidate and source hashes identify the MATLAB implementation. The unchanged original owner archive is included as `owner/t17.zip`. `return/review.json` preserves the automatic checker result; it intentionally leaves acceptance decisions unset. `acceptance.json` records the scoped engineering disposition after review. Aggregate CSVs and independent audits are included. No public repository mutation is part of this review.

To reproduce the automatic review using the exact frozen T17 installation, choose a fresh output directory:

```text
python scripts/analyze_tranche17_return.py --evidence PATH_TO_owner_t17.zip --source-root PATH_TO_FROZEN_T17 --output NEW_REVIEW_DIRECTORY
```

Original absolute temporary paths in the automatic comparison records identify where its inputs were read. Those temporary paths need not survive; hashes bind the MATLAB files inside the owner ZIP and the native/OPNET files in the frozen installation.
