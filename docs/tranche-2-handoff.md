# Tranche 2 MAC/HOP integration handoff

**Status: implementation candidate ready for owner-run MATLAB validation.**
This tranche adds reliable packet exchange and fixed-path relays over the
existing CSR PHY. Static/source review is complete; MATLAB runtime acceptance
is pending. Nothing in this handoff claims executed Tranche 2 MATLAB results.

## Objective and capabilities

Connect application traffic → forwarding custody → HOP → MAC → CSR PHY as a
cohesive portable simulation. The implementation includes:

- MAC DATA/ACK queues, stable DSCP priority, pseudo carrier sense, source slot
  and reservation behavior, duty cycling, generic wake, access holdoff,
  overhearing, long/short preambles and rate-dependent concatenation.
- MAC-owned ACK repetition/coalescing and HOP-owned DATA retransmission.
  Retry timing begins at actual MAC transmission. Cumulative ACK/DACK windows,
  sequence wrap, duplicate handling, neighbor admission and deferred capacity
  release preserve the current source's ownership boundaries.
- Fixed-path multi-hop custody with NSDP-based ACK/DACK selection. Missing
  feedback does not undo application delivery or move relay custody backward.
  Late in-flight reception can correct provisional timeout loss.
- Integrated 8 kbps and 500 kbps / 1 Mbps scenarios using the Tranche 1 signal,
  interference, BER and ECC engine. Per-node MAC/HOP counters, bounded traces,
  reproducible streams and MAT/CSV/JSON exports support diagnosis.

## Baseline and architecture

The working branch is `tranche/2-mac-hop-reliability`, based on merged MATLAB
PR #1 at `8b185ff586a0cfb0562194c2948c5271826a0e9d`.
The authoritative ns-3 main was rechecked at
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, including PR #50 acquisition and
third-ACK growth ordering. Source-specific behavior uses MATLAB records,
callbacks and the existing scheduler; ns-3 object/packet/event boilerplate
was not translated literally.

| Area | Main files / responsibility |
|---|---|
| MAC | `+csr/+mac/Layer.m`: access, queues, reservations, wake/sleep and packing |
| HOP | `+csr/+hop/Layer.m`: DATA custody, admission, ACK/DACK and retries |
| Frames/configuration | `+csr/+hop/Frames.m`, `validateConfig.m`: logical frames, modeled layouts and defaults |
| PHY coupling | `+csr/+phy/SignalEngine.m`: state callbacks and admitted SYNC presence; decoded members precede MAC Search preparation |
| Integration | `+csr/+sim/MacHopSimulation.m`: node composition, paths, custody ledger, metrics and diagnostic erasures |
| Scenarios/export | `+csr/+scenario/macHopNetwork.m`, scenario validation, `+csr/runScenario.m`, `+csr/+analysis/exportResults.m` |
| Verification | Six new portable test classes, `run_tranche2_validation.m`, original ns-3 reference runner and evidence |

The original controlled and PHY-only runners remain available. Portable
protocol classes acquire no R2026a-only superclass or toolbox dependency.
The existing optional native clock adapter is unchanged in scope: full native
CSR packet transport remains unintegrated and native execution unvalidated.

## Tests and versions

| Evidence | Result / limit |
|---|---|
| Actual original ns-3 execution | **17/17 focused workflows passed** in Debug/assertions/logging, source pin above; engine `6b5cd24ea80713ce16d88575869aedd6f432bdae` |
| Static MATLAB lint | **54 files passed**, MISS_HIT 0.9.44, MATLAB 2022a syntax profile |
| Independent review | No remaining structural blocker found by static/source review; [review record](tranche-2-review.md) |
| Prepared portable MATLAB suite | **145 test methods**, including all 72 previous portable tests, plus nine exported MAC/HOP scenarios |
| Tranche 2 MATLAB R2025a | **Not executed**; intended first owner runtime gate |
| Tranche 2 MATLAB R2026a | **Not executed**; test separately after portable R2025a |
| Native adapter tests | Five separate methods; not executed; `validate_native` |
| Historical T1 acceptance | Owner-reported R2025a 25.1.0.2943329: 72/72 tests and nine PHY scenarios passed for the accepted revision |

The original C++ workflows exercise queues, windows, DSCP retries, DACK hold,
sent-time ownership, concatenation, preambles, reservations, slots, contention,
overhearing, link control, no-route relay behavior, relay-holdoff metadata,
queue observation and OPNET modeled packet envelopes. Some are references for
deferred behavior; passing source tests is not evidence that MATLAB implements
every covered source feature. The manifest and hashed logs are in
`evidence/tranche-2-ns3-workflows.json` and its adjacent directory.

No equivalent full-network MATLAB↔ns-3 numerical comparison has run yet.
No new OPNET execution or aggregate comparison was performed. Existing source
evidence is used; unavailable OPNET event exports are not an acceptance blocker.

## Run the acceptance gate

Extract the package to a fresh folder, open MATLAB there, and run:

```matlab
run_tranche2_validation
```

The runner first requires all portable tests to pass. It then exports nine
MAC/HOP scenarios to `results/tranche2_validation/`: reliable, ACK loss, DATA
loss, DACK, contention, relay, queue pressure, 500 kbps and 1 Mbps.
The suite checks retry and feedback ownership, unique application delivery,
drained completed-scenario custody, deliberate loss recovery, queue pressure,
finite-horizon pending work, trace bounds and deterministic repeatability.

Return the complete console output and `scenario_summary.csv`. Per-scenario
`protocol_trace.csv`, `phy_trace.csv`, `mac_nodes.csv`, `hop_nodes.csv`,
configuration and metadata are available if a gate fails. Preserve the MATLAB
version/release and the candidate revision with those outputs. A structural
failure blocks acceptance; small numerical/stochastic differences are triaged
using the [validation strategy](tranche-2-validation.md).

## Known differences and deferred parity

- Paths are configured inputs. Neighbor discovery, autonomous ARL routes,
  admission, route maintenance/recovery and reliable routing controls belong
  to Tranche 3. Fixed-path delivery is not route convergence evidence.
- Adaptive HOP rate/power link control is not implemented. This is material
  for variable-link experiments and must be completed or explicitly controlled
  before claiming parity for those experiments. ACKs use the received rate
  and the transmitting node's configured power.
- Full MAC/resend admission rolls back transactionally; an explicitly refused
  relay receive remains retryable. These differ from source overload behavior
  that can retain bookkeeping or lose custody. A queued retry pauses its timer
  until actual transmission, avoiding the source's provisional stale scan.
- MAC enforces 16 total aggregate members, including ACKs, rather than the
  source's ACK-only packing quirk. The forwarding queue bounds all retained
  custody, including submitted rows; it is not the final source NWK queue policy.
- Frame helpers reproduce modeled layouts and envelope sizing. Cryptographic
  security and routing-control serialization are not implemented. NWK relay
  holdoff metadata is deferred; no unsupported extra MAC gate was invented.
- Loss fixtures erase successful PHY receptions before MAC/HOP handling.
  Raw PHY trace success is before erasure; physical receive/drop counters are
  after erasure. The DACK scenario deliberately uses NSDP threshold zero;
  ordinary configuration retains source threshold 16.
- `Transmitted` counts OTA aggregates, including control. ACK/DACK counters
  count completed HOP transactions, not raw repeated control copies. Collision
  observations do not automatically mean packet loss. Trace timeout events
  may be superseded by late reception; final statistics reflect that correction.
- Exact global timer-scan coalescing, minor packing/event ordering, full network
  numerical parity, native integration and OPNET aggregate agreement remain
  deferred or unvalidated. The [three-way ledger](parity-ledger.csv) records
  these boundaries without claiming unexecuted MATLAB matches.

## Recommended next tranche

After this portable gate passes, begin Tranche 3 as one integrated NWK/control
plane tranche: neighbors and admission, autonomous ARL route construction and
maintenance, reliable INFO/UPDATE/FLUSH, gateway behavior, no-route custody,
route loss and recovery. Replace the fixed-path route provider while retaining
the working MAC/HOP/PHY composition. Resolve adaptive link-control placement
with that integration before variable-link comparisons. Battery, supervisory
features and BBN routing remain excluded from the baseline.

Tranche 2 is recorded locally for validation. Remote push and PR creation need
separate owner authorization; no Tranche 2 publication is claimed here.
