# Tranche 7 portable campus benchmark acceptance

The **portable R2025a campus benchmark milestone is accepted**, with the
numerical differences and finite-stop backlog below. This accepts the
repeatable benchmark, its bounded historical profiles, complete accounting,
and retained regression behavior. It does not establish full protocol or
statistical equivalence with ns-3 or OPNET.

The executed candidate is `28ed878f5673e308047cbea7878b933697d932f3` on
`agent/tranche-7-campus-benchmarks`, based on T6 acceptance `b53653ed`.
The owner returned MATLAB **25.1.0.2943329 (R2025a)** evidence on
2026-09-10. Execution ran from **14:25:45.905 to 15:53:49.092 UTC**:
**88 minutes 3.187 seconds** overall. Reported simulation runtimes were
71 minutes 37.452 seconds for campus, 2 minutes 50.460 seconds for two
nodes, and 40.251 seconds for contention. The total also includes regression
execution, analysis, export and orchestration work; these are observations
from this laptop, not a runtime guarantee for another machine.

## Verification

- **467/467 portable tests passed**, with no failed or incomplete tests;
  these include all 87 new T7 test methods.
- **18/18 sweeps and all 28 retained scenarios completed.** Their reported
  non-runtime outcome fields match accepted T6. The nested T6/T5/T4 schema
  names identify reused harnesses executing the T7 source snapshot.
- All **five retained strict ns-3 shared comparisons pass**, covering 15/15
  applications. This is application equality; their protocol timing remains
  distinct and the 500/1,000 kbps fixtures remain labeled extensions.
- All **155 bound source/input hashes**, including **103 MATLAB files**,
  match the executed candidate. All **50 reference/input files** match the
  pinned reference tree; both start/end snapshots are stable.
- The original ZIP has **692 files**. All **691 declared outer artifact
  byte/hash checks** pass, along with ZIP CRC, nested manifests, test
  membership, scenario identity, admission partitions and application,
  physical receiver and node ownership accounting.
- All three benchmark comparisons align the eight common series on their
  prescribed 100-bucket grids. MATLAB aggregates were reconstructed from
  the complete returned application records. All **nine source flows**
  across the three cases admit and deliver traffic.

The fresh ns-3 references remain pinned to
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. Their production records bind
the freshly compiled standalone runner to verified preserved engine
libraries; they do not claim a full engine rebuild. OPNET observations are
from the archived original campus vector output, not a new OPNET execution.

## Application outcomes

All runs use seed 128. Relative differences below use ns-3 as denominator.
Admitted packets are the application traffic-sent population; an attempted
generation blocked by the admission gate is not a packet drop.

| Case | Attempts | MATLAB admitted | ns-3 admitted | MATLAB delivered | ns-3 delivered | Delivery difference |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Campus, 6,000 s | 1,710,000 | 12,382 | 12,417 | 11,727 | 11,769 | −0.357% |
| Two nodes, 1,200 s | 45,000 | 11,395 | 11,380 | 11,385 | 11,364 | +0.185% |
| Three-node contention, 360 s | 60,000 | 954 | 946 | 928 | 914 | +1.532% |

Campus MATLAB admission differs by −0.282%; its delivery ratio among
admitted applications is 94.710%. Of 12,382 admitted applications, 11,727
were delivered, **401 exhausted retries**, and **254 remained pending** at
6,000 seconds. The two smaller cases have no terminal application drops and
retain **10 and 26 pending applications**, respectively. Generation continues
almost to each observation horizon. Eventual delivery or drain is unobserved.

All pre-creation blocks are attributed to the local NSDP admission cap:
1,697,618 campus, 33,605 two-node and 59,046 contention attempts. The campus
admission diagnostic trace retains its first 100,000 rows and explicitly
omits 1,610,000 rows. Full per-flow counters and admitted application records
remain complete. **Protocol and PHY traces have no omissions.**

The ns-3 trace has 648, 16 and 32 admitted applications without an observed
final delivery. These are unmatched sends; the available reference does
not establish their global terminal-drop versus pending classification.

### Campus flows

Aggregate agreement does not imply per-flow equality. The gateway is node 1;
each source makes 285,000 attempts.

| Source | MATLAB admitted | ns-3 admitted | MATLAB delivered | ns-3 delivered | Delivery difference |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2 | 506 | 547 | 395 | 410 | −3.66% |
| 3 | 8,608 | 8,551 | 8,593 | 8,535 | +0.68% |
| 4 | 566 | 498 | 454 | 419 | +8.35% |
| 5 | 1,309 | 1,397 | 1,285 | 1,369 | −6.14% |
| 7 | 832 | 803 | 617 | 574 | +7.49% |
| 8 | 561 | 621 | 383 | 462 | −17.10% |

Node 3 dominates delivered traffic in both simulators. The other flows
also progress, but the node-8 difference and flow imbalance remain material
follow-up observations.

## Delay and archived OPNET comparison

For cross-simulator delay comparison, this table uses the **arithmetic mean
of populated bucket means**, not a global packet-weighted mean. Bucket widths
are 60, 12 and 3.6 seconds. Empty means remain missing.

| Case | MATLAB delay (s) | ns-3 delay (s) | Difference |
| --- | ---: | ---: | ---: |
| Campus | 102.941880 | 103.181006 | −0.232% |
| Two nodes | 0.942589 | 0.947511 | −0.519% |
| Three-node contention | 1.727025 | 1.914475 | −9.791% |

The MATLAB campus packet-weighted mean latency is separately **103.963442 s**,
with median 10.310808 s, p95 749.106811 s and p99 878.036811 s. The long tail
and pending population matter even though aggregate means are close.
The reconstructed ns-3 packet-weighted campus mean is 104.194771 s. For
contention, the corresponding packet-weighted means are 1.640671 s MATLAB
and 1.694846 s ns-3 (−3.20%); the −9.791% value above specifically compares
populated bucket means and gives each observed bucket equal weight.
Ninety-four of 100 campus receive-rate buckets differ from ns-3; the largest
difference is 24 deliveries in one 60-second bucket. All 95 populated delay
buckets differ; the largest difference between bucket delay means is
140.467924 s. No numerical tolerance was imposed after seeing the results.

| Campus metric | MATLAB | ns-3 | Archived OPNET | MATLAB vs OPNET |
| --- | ---: | ---: | ---: | ---: |
| Admitted traffic, packets/s over 6,000 s | 2.063667 | 2.069500 | 2.012000 | +2.568% |
| Received traffic, packets/s over 6,000 s | 1.954500 | 1.961500 | 1.901667 | +2.778% |
| Mean of populated delay bucket means, s | 102.941880 | 103.181006 | 112.748007 | −8.697% |

The OPNET traffic rates correspond to 12,072 sent and 11,410 received
observations over the full window. Its authoritative missing values remain
preserved, including the first five sink count/bit-sum buckets. Rate series
and matched bucket populations avoid comparing count means with unequal
denominators. Common measured campus size is 192 bytes (185-byte payload
plus seven NWK bytes); payload-only goodput is a different metric.

There is no claimed OPNET counterpart for the two synthetic diagnostics.
The exact historical latency/visible-node tests and the 60,000-second
hidden-node workload remain separate deferred experiments.

## Disposition and next milestone

Acceptance is bounded to the measured seed-128 portable benchmark and the
retained regression gate. It does not certify multiseed statistical parity,
packet/event equality with OPNET, complete end-of-run drain, R2026a/native
execution, or resolved outage recovery. HOP/NWK control ownership reports
drained for the three benchmarks; current MAC feedback queue depth is not
exported, so this is not a claim that every internal queue is empty.

Keep PHY/ECC, T6 freshness and retry behavior unchanged for this acceptance.
Known reverse ACK rate/power control and peer-S0/HOP-failure feedback
differences remain in the parity ledger. These results alone do not prove
which difference causes a residual.

The next bounded milestone should repeat the smaller admission/contention
diagnostics across multiple seeds and instrument reverse-link ACK rate/power
decisions. Then use matched source decisions and campus per-flow results to
choose any protocol correction. Preserve this seed-128 campus run as the
baseline; do not tune PHY parameters to fit aggregate OPNET numbers.
Long-run progress reporting is also a useful execution improvement: this
runner announces cases but has no periodic simulation heartbeat.

## Preserved evidence and source identity

The original 23,627,006-byte `tranche7_evidence.zip` has SHA-256
`ea39b86ef68f91a551e4e22d176e2e96dc5305f33673741eee0adc6039599655`.
Its source snapshot SHA-256 is
`b2139677d30438b0e9479566a7508ea29465aeb94a0ff532f9d1a1ace4ac14d6`.
The complete archive, byte-identical selected results, comparison reports and
independent reviews are retained under
`evidence/tranche-7-r2025a-accepted/`. The
[structured acceptance](../evidence/tranche-7-portable-acceptance.json)
records their identities and the exact qualification.

The reviewer required no Python repair. This return review modifies no MATLAB
or candidate Python source; all 103 MATLAB files, all 50 reference files and the original
candidate preparation record remain unchanged. The acceptance pointer in
`evidence/source-baseline.json` is updated after verifying the executed
snapshot. Reproduce that exact snapshot from commit `28ed878`, as described
in the [review reproduction notes](../evidence/tranche-7-r2025a-accepted/review/README.md).
The earlier 158/158 Python tests and 103-file MATLAB static check are candidate
preparation evidence, distinct from this owner's actual MATLAB execution.
No remote publication or merge was performed by this review.
