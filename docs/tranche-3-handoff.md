# Tranche 3: autonomous network and routing candidate

Objective: connect application custody, autonomous ARL routing and admission to
the accepted CSR HOP/MAC/PHY foundation. The candidate is prepared for MATLAB
execution; portable Tranche 3 acceptance remains pending.

Tranche 2 is published in [PR #2](https://github.com/mjburke4/CSR-Project-MATLAB-Sim/pull/2).
This local tranche branches from its published head `5a4a96f`. The published
Tranche 2 checkpoints have exactly the original accepted file trees; GitHub API
commit creation changed their commit identifiers. No Tranche 3 push or merge
is part of this handoff.

## Implemented capabilities

- Per-node discovery, reciprocal key/check admission, neighbor freshness and
  explicit recovery discovery, with a behavioral security boundary.
- Self capabilities, INFO, UPDATE, DELETE, REQUEST, FLUSH and targeted NoPath; route candidates,
  sequence freshness, cost/hop selection, reverse learning, grouped changes,
  selected-route export and loss/readmission handling.
- Big-endian ARL record encoding, 700-byte sections and bounded atomic reassembly.
- Reliable grouped routing controls through the same HOP sequence/ACK windows,
  MAC queues and CSR PHY as DATA; partial ACK ownership and residual retry.
- Bounded application custody, route-dependent queue draining, DSCP, gateway
  selection, dynamic hop traversal and source-compatible admission boundaries.
- Link-cost driven rate/power selection, configurable fixed-rate experiments,
  per-layer counters, route/neighbor tables and MAT/CSV/JSON result export.

The protocol core uses base MATLAB classes, containers, structs and the existing
clock/RNG abstraction. No new R2026a-only dependency was added. R2025a portable is
the first execution target; R2026a portable and native remain separate gates.

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

Current ns-3 main was fetched and inspected before implementation. It remains
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

This runs 254 prepared portable regression and Tranche 3 test methods, then exports eight
network fixtures. Native tests remain separate. The runner records actual
MATLAB version/release, source file hashes, source pin, scenario seed/config and
test outcomes so the new evidence avoids the provenance gaps in older CSVs.
Return the console, `results/tranche3_validation/scenario_summary.csv`,
`results/tranche3_validation/regression/tests/test_results.csv` and the runner's validation
manifest. If a scenario fails, preserve its trace and per-node exports.

| Fixture | Structural purpose |
|---|---|
| `autonomous` | Gateway-led discovery and 3 → 2 → 1 delivery |
| `no_route_custody` | Early traffic waits for admission and routing |
| `control_loss` | Deliberate routing-control erasure and recovery |
| `route_recovery` | Neighbor loss, retained traffic, explicit discovery after restoration |
| `gateway` | Gateway destination selected from routing capability |
| `leaf_no_transit` | Explicitly disabled transit policy discards DATA after HOP receipt |
| `high_rate_500` | Autonomous network with configured 500 kbps radio |
| `high_rate_1000` | Autonomous network with configured 1 Mbps radio |

The line topology uses a named 150 m closure delegate with 100 m spacing.
It restricts physical visibility, without injecting routes. The complete CSR
acquisition/interference/BER/ECC pipeline still decides eligible receptions.
Recovery uses post-PHY RF erasure at 120–170 s and an explicit administrative
discovery request at 180 s. A scan at 110 s also exercises the blackout boundary. It does not imply that enqueuing DATA starts
discovery. Freshness monitoring is explicitly enabled only in that fixture.

## Evidence and remaining gate

Twelve unchanged native ns-3 workflows were built and executed: **12/12 passed**.
The [reference manifest](../evidence/tranche-3-ns3-workflows.json) records source,
binary, command, build and log provenance. Expected protocol failure events
are distinguished from failed test assertions. These are source-side results,
not MATLAB differential results.

No MATLAB or Octave execution occurred in this workspace. Static syntax/lint,
source-derived C++ calculations and independent review are recorded separately
in the candidate manifest. The accepted historical T2 owner result remains
145/145 methods and nine scenarios; it does not certify modified T3 code.

No new OPNET run or packet trace is available. Preserve current ns-3 semantics
where practical, record explicit simplifications in the parity ledger, and
defer aggregate OPNET comparison until equivalent network experiments run.

Known differences include retained-custody queue limits, transactional HOP
overload, the existing strict aggregate bound, bounded NWK control retries,
modeled security/control envelopes and diagnostic accounting. Cryptographic
key protection and full native wireless packet transport are not implemented.
The coordinator specification lists remaining control/watchdog/scan details.
No full-network numerical parity claim is made.

Recommended next step: execute this candidate on R2025a, repair any structural
failures as part of Tranche 3, then proceed to Tranche 4 reusable research
scenarios and MATLAB/ns-3 aggregate comparisons. Battery, supervision and BBN
remain outside the baseline.
