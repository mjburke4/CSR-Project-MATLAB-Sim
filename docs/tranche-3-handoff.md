# Tranche 3: accepted portable autonomous network and routing

Objective: connect application custody, autonomous ARL routing and admission to
the accepted CSR HOP/MAC/PHY foundation. Portable Tranche 3 is accepted on
MATLAB R2025a at code commit `ff7859af3900f1ab8c25263dbd2b5bc580e8488d`.

The final owner run passed 289/289 tests, all eight T3 scenarios and nine retained
T2 scenarios. All 74 source hashes and the test CSV hash match the validated
package; every T3 queue drained and control/backlog rejections are zero.
See [portable acceptance](tranche-3-portable-acceptance.md) and the
[historical repair record](tranche-3-r2025a-repair.md). This acceptance update
changes documentation and evidence only.

Tranche 2 is merged through [PR #2](https://github.com/mjburke4/CSR-Project-MATLAB-Sim/pull/2)
at `88e56a83c2e9baa295be89f63b873bbe1fa1aa5f`. This tranche is on
`agent/tranche-3-routing-admission`. The recovered candidate was transplanted
onto that merge: its former base `5a4a96f` and the merge have identical trees.
Publication and merge status are tracked in the
[repository pull requests](https://github.com/mjburke4/CSR-Project-MATLAB-Sim/pulls).

## Implemented capabilities

- Per-node discovery, reciprocal key/check admission, neighbor freshness and
  explicit recovery discovery, with a behavioral security boundary.
- Self capabilities, INFO, UPDATE, DELETE, REQUEST, FLUSH and targeted NoPath; route candidates,
  sequence freshness, cost/hop selection, reverse learning, grouped changes,
  selected-route export and loss/readmission handling.
- Big-endian ARL record encoding, 700-byte sections and bounded atomic reassembly.
- Reliable grouped routing controls through shared HOP transmit allocation,
  separate DATA/control receive windows, exact control ACKs, MAC queues and
  CSR PHY; partial ACK ownership and residual retry.
- Bounded application custody, route-dependent queue draining, DSCP, gateway
  selection, dynamic hop traversal and source-compatible admission boundaries.
- Link-cost driven rate/power selection, configurable fixed-rate experiments,
  per-layer counters, route/neighbor tables and MAT/CSV/JSON result export.

The protocol core uses base MATLAB classes, containers, structs and the existing
clock/RNG abstraction. No new R2026a-only dependency was added. R2025a portable
passed; R2026a portable and native remain separate gates.

## Architecture and source

| File/package | Responsibility |
|---|---|
| `+csr/+nwk/Layer.m` | Network custody and control ownership/coordinator |
| `Neighbors.m` | Discovery, admission and freshness |
| `Routes.m`, `linkCost.m` | Independent route state and link calculation |
| `RoutingCodec.m`, `Reassembly.m` | ARL byte stream and sections |
| `defaults.m`, `validateConfig.m` | Scenario-facing protocol configuration |
| `+csr/+hop/Layer.m`, `Frames.m` | Group control transport alongside DATA |
| `+csr/+sim/NetworkSimulation.m` | Per-node full-stack integration and accounting |
| `+csr/+scenario/routedNetwork.m` | Autonomous fixtures without configured paths |

The inspected and pinned ns-3 reference is
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, tree
`b611b233fb369569b98f0914ece24d029ccc2f42`. Principal contracts come from
`model/csr-nwk-layer.h`, the ARL codec and the associated discovery, admission,
grouped-control, residual-retry, self-capability and integration smoke workflows.
The ns-3 event engine, TypeId/attributes, packet tags and NetDevice plumbing are
represented by small MATLAB contracts instead of translated framework classes.

See the [routing](tranche-3-routing.md), [neighbor](tranche-3-neighbors.md),
[codec](tranche-3-control-codec.md), [HOP controls](tranche-3-hop-controls.md) and
[coordinator](tranche-3-nwk-layer.md) specifications for precise boundaries.

## Run and return evidence

Extract the complete candidate into a fresh directory, open MATLAB in its
repository root and run:

```matlab
run_tranche3_validation
```

This discovers the complete portable regression suite, retains all nine Tranche 2
scenarios, then exports eight network fixtures. The candidate manifest records the
current prepared test count; it is not a passing count. Native tests remain separate.
The runner records actual
MATLAB version/release, source file hashes, source pin, scenario seed/config and
test outcomes so the new evidence avoids the provenance gaps in older CSVs.
Return the console, `results/tranche3_validation/scenario_summary.csv`,
`results/tranche3_validation/regression/tests/test_results.csv` and the runner's validation
manifest. If a scenario fails, preserve its trace and per-node exports.

Use a normal MATLAB session with the JVM enabled for SHA-256 provenance. R2025a
requires only the portable backend here, even if an older wireless add-on is
installed. Run the same portable gate on R2026a separately. Raw source hashes
may differ with LF/CRLF checkouts; compare commit identity and semantic results.
On R2026a with the native prerequisites installed, `validate_native` separately
runs six prepared tests, including full routed portable-versus-native-clock
equality. This does not integrate native packet transport into CSR.

| Fixture | Structural purpose |
|---|---|
| `autonomous` | Gateway-led discovery and 3 → 2 → 1 delivery |
| `no_route_custody` | Early traffic waits for admission and routing |
| `control_loss` | Deliberate routing-control erasure and recovery |
| `route_recovery` | Neighbor loss, retained traffic, explicit discovery after restoration |
| `gateway` | Gateway destination selected from routing capability; not full application-generator parity |
| `leaf_no_transit` | Explicitly disabled transit policy discards DATA after HOP receipt |
| `high_rate_500` | Autonomous network with configured 500 kbps radio |
| `high_rate_1000` | Autonomous network with configured 1 Mbps radio |

The line topology uses a named 150 m closure delegate with 100 m spacing.
It restricts physical visibility, without injecting routes. The complete CSR
acquisition/interference/BER/ECC pipeline still decides eligible receptions.
Recovery uses post-PHY RF erasure at 120–170 s and an explicit administrative
discovery request at 180 s. A scan at 110 s also exercises the blackout boundary. It does not imply that enqueuing DATA starts
discovery. Freshness monitoring is explicitly enabled only in that fixture.

## Evidence and remaining gates

Twelve unchanged native ns-3 workflows were previously built and executed and
their preserved binaries were re-executed during preparation: **12/12 passed**.
The [reference manifest](../evidence/tranche-3-ns3-workflows.json) records source,
binary, command, build and log provenance. Expected protocol failure events
are distinguished from failed test assertions. These are source-side results,
not MATLAB differential results.

The current workspace lacks CMake, so a fresh build and the proposed five extra
security/wire-format workflows could not run. The existing build evidence is
preserved rather than relabeled as a fresh compilation.

No MATLAB or Octave execution occurred in this workspace. Static syntax/lint,
source-derived C++ calculations and independent review are recorded separately
in the candidate manifest. The final owner R2025a evidence now certifies the
portable T3 functional gate at `ff7859a`: 289/289 methods and all eight network
scenarios, including the retained T2 regression suite and exports.

No new OPNET run or packet trace is available. Preserve current ns-3 semantics
where practical, record explicit simplifications in the parity ledger, and
defer aggregate OPNET comparison until equivalent network experiments run.

The correction pass adds fail-closed profile compatibility, independent snapshot
streams, ordinary-capability clearing on omitted self records, preserved
reassembly on request retry, per-peer snapshot ACK/watchdog ownership,
source control ACK/replay separation, HOP-owned
post-feedback wakes, and legacy SNMP addressing/scan behavior. Source quirks in
oversized 8-kbps concatenation and standalone grouped-control preambles are
preserved and tested explicitly. Acceptance scenarios additionally require
zero control/backlog rejections and DATA submission only while the next-hop
neighbor is admitted.

Known differences include retained-custody queue limits, transactional HOP
overload, the existing strict aggregate bound, bounded NWK control retries,
modeled security/control envelopes and diagnostic accounting. Cryptographic
key protection and full native wireless packet transport are not implemented.
Application profile labels enforce DSCP/provenance separation only: historical
gateway generation, first-gateway caching and attempt-before-allocation gates
remain deferred. Do not certify historical profile equivalence from these labels.
The coordinator specification lists remaining control/watchdog/scan details.
No full-network numerical parity claim is made.

Recommended next step: publish the accepted portable tranche through a PR when
authorized, then proceed to Tranche 4 reusable research scenarios and MATLAB/ns-3
comparisons. R2026a compatibility remains a separate gate. Battery, supervision
and BBN remain outside the baseline.
