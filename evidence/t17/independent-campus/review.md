# Independent T17 campus aggregate review

T17 exactly reproduces T10 campus application observations, protocol trace, PHY trace, and aggregate series. No default-real-PHY campus behavior improvement or regression is observed.

| Metric | T17 MATLAB | Pinned ns-3 | Archived OPNET |
|---|---:|---:|---:|
| Admitted applications | 12484 | 12417 | 12072 |
| Delivered applications | 11825 | 11769 | 11410 |
| Delivery fraction | 0.9472124319128484 | 0.9478134815172747 | 0.9451623591782637 |
| Mean delay, populated buckets equally weighted (s) | 98.09146890252902 | 103.18100582955141 | 112.74800745492433 |
| Mean delay, packets weighted (s) | 98.97012338799816 | 104.19477083093884 | 113.27494314367226 |

Packet-weighted OPNET mean is reconstructed from archived global Sink aggregate series, not raw packet data. All 100 time-axis bins exist. Delay samples are absent only in the first five bins (ends 60,120,180,240,300 s). OPNET received-count samples are also absent there, while received-rate samples are observed zeros. Do not replace absent delay means with zeros.

| Source → 1 | MATLAB delivered | ns-3 delivered | Delivery delta | MATLAB mean latency (s) | ns-3 mean latency (s) |
|---|---:|---:|---:|---:|---:|
| 2 | 411 | 410 | +0.24% | 487.330071 | 456.845567 |
| 3 | 8472 | 8535 | -0.74% | 10.328367 | 10.448459 |
| 4 | 348 | 419 | -16.95% | 299.153621 | 269.688918 |
| 5 | 1644 | 1369 | +20.09% | 53.463518 | 67.303448 |
| 7 | 533 | 574 | -7.14% | 784.556503 | 777.848315 |
| 8 | 417 | 462 | -9.74% | 653.139140 | 645.370060 |

Network delivery differs by only +56 applications (+0.4758%), but flow 5 contributes +275; flows 3, 4, 7, and 8 contribute −220 combined. Prioritize service/admission fairness across flows 4 and 5 under autonomous real-PHY contention. Separate shifted admitted load from delivery conditional on admission; retain flow 8 as secondary.

- OPNET packet-weighted delay is reconstructable from global Sink bucket-mean delays and corresponding global bucket-sum receive counts for all95 populated bins; report it as reconstructed from archived aggregates. Per-flow OPNET delivery and packet latency distributions are unavailable in the aggregate-only archive.
- Observed missing values at early bucket ends60,120,180,240,300 are not missing file coverage. All100 axis bins exist. No generation before300; endpoint semantics exclude t300 from the bin ending300.
- Per-flow MATLAB/ns3 figures here are single-seed descriptive comparisons, not event-equivalence or confidence intervals. Equal seed numbers do not imply matched PRNG draws.
- Suggested next bounded diagnosis is autonomous multi-hop service/admission fairness under saturated offered traffic, focusing on flows4 and5 and gateway-link service for local vs relay traffic, with flow8 as secondary. Trace first divergence and distinguish admitted-load shifts from conditional delivery failure before changing protocol. Do not repeat controlled ACK-boundary fixtures or adjust PHY/ECC to improve a single seed.

Source details, full precision, and identity hashes: aggregate-comparison.json; row-level flow metrics: per-flow-comparison.csv.
