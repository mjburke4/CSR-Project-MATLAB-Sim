# Tranche 3 integration review

Review updated: 2026-09-09. Pinned ns-3 reference:
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.
MATLAB base: merged PR #2, `88e56a83c2e9baa295be89f63b873bbe1fa1aa5f`.

This is a corrected implementation candidate, not runtime acceptance.
The earlier review of recovered candidate `602ddd3` missed several observable
protocol differences; those conclusions are superseded by this correction pass.
Astra performed the routing and integration closeout at the owner's request.
No MATLAB or Octave test execution occurred in this workspace.
The latest owner R2025a run reported 287 passed, two failed and two incomplete;
all ten integrated network-scenario methods passed. The
[runtime repair record](tranche-3-r2025a-repair.md) documents the two remaining
test-fixture errors, their correction and the complete runner's pending rerun.

## Architecture retained

The candidate cleanly transplants because its old base and merged main have
identical trees. Keep the existing pure MATLAB scheduler, independent per-node
NWK objects and separate `NetworkSimulation`. The scheduler still orders
`(double time, uint64 insertion ID)`. No native framework dependency, global
priority redesign, or simulator-plumbing refactor is needed for this tranche.

## Source-critical corrections

| Contract | Correction and regression boundary |
|---|---|
| DATA versus control replay | Shared outbound per-peer sequences; independent receive windows. Control feedback is exact/non-windowed; DATA retains its cumulative bitmap. |
| Malformed ROUTING | NWK validation callback runs before HOP replay/ACK bookkeeping. Section-envelope failures do not consume the sequence; complete record validation remains atomic at reassembly. |
| Reliable group ownership | Completion/failure callbacks run while the original HOP owner exists. Failure metadata retains original targets; NWK owns its residual list. |
| DATA feedback wake | NWK custody removal is non-scheduling; HOP owns the +TIC pump. Direct/no-ACK terminal paths still release normally. The same correction applies to fixed-path integration. |
| Ordinary snapshot capability | INFO+FLUSH without a reporter self record clears an earlier gateway/routable capability while retaining the direct physical route. |
| Snapshot transport | Each peer gets an independent sequence and forward section order. Reverse groups/sections apply only to grouped incremental changes. |
| Snapshot lifecycle | Per-peer section ACK tracking suppresses repeated REQUESTs until completion or generation-safe watchdog expiry. Late old ACKs cannot complete replacement streams; pending and same-time processed changes remain excluded. |
| Backlog pressure | Failed semantic admission restores route dirty flags and pending snapshot work. Bounded capacity delays convergence rather than silently dropping changes. |
| Request retry | Sequence-keyed reassembly is preserved. Neighbor invalidation still discards peer-owned incomplete streams. |
| Admission/discovery | Conditional remote-active REQUEST is ordered after route processing. Scan completion refreshes active links and requests route repair. |
| SNMP | Best effort, sequence 0, DSCP 0, minimum local rate/maximum local power; separate final and one-hop destinations; no forwarding or NWK neighbor refresh. DONE expands known-node scan state; idle START opens a new epoch. |
| Profile sizes | Routed scenarios require production-behavioral Pairwise16 sizing. Control byte counts are explicit and not added again by HOP. |
| Security-count reset | Key/discovery proof clears without erasing retained key-send ownership, retry event, generation or backoff histories. |

Two initially suspected MAC defects are frozen source behaviors, not fixes:
a large control at an 8-kbps multi-entry concatenation head can remain packing
blocked, and a standalone grouped control checks only its primary destination
for preamble freshness. Focused tests retain both behaviors, with a separate
128-kbps multi-section progress test. These are limits to consider before
large-table scenario certification.

## Evidence

The candidate manifest records current source hashes, prepared test counts and
the final static-lint outcome. Those counts are definitions, not passed tests.
MISS_HIT 0.9.44 uses its supported MATLAB 2022a parser profile; this checks syntax
without establishing R2025a/R2026a numerical or scheduling behavior.

Twelve preserved ns-3 workflow binaries re-executed successfully. Their original
source/build/binary/log manifest is retained. The current environment has no
CMake, so neither a fresh build nor five proposed extra security/wire workflows
was completed. Do not reinterpret these checks as MATLAB differential evidence.

## Remaining acceptance gates

- Run `run_tranche3_validation` on R2025a with every portable test passing,
  zero failed/incomplete, all nine T2 scenarios and all eight T3 scenarios.
- Preserve actual release/version, raw file hashes, test CSV, scenario summary,
  per-layer exports and protocol traces. Standard JVM is required for hashing.
- Require zero control-queue/backlog rejection in acceptance scenarios.
- Repeat portable validation on R2026a; six native clock/packet tests remain
  separate, including full routed portable-versus-native-clock equality.
- Equivalent MATLAB/ns-3 network scenarios and OPNET aggregate comparison remain
  unexecuted. Historical accepted T0–T2 results do not certify modified T3 files.

Explicit differences remain: bounded custody/reassembly/control storage,
transactional overload handling, actual-transmission retry timing, bounded NWK
retry cycles, duplicate partial-ACK callback suppression, diagnostic accounting,
modeled rather than serialized security envelopes and behavioral rather than cryptographic admission.
Application profiles currently enforce names, legacy DSCP-zero and provenance;
they do not reproduce historical gateway generators, cached-gateway selection
or pre-allocation attempt gates. The gateway fixture is route-selection
coverage only. Recovery uses explicit administrative discovery after a
diagnostic receive-erasure blackout.

Battery, supervisory behavior, BBN routing, waveform/GUI/Simulink work and
integrated native CSR packet transport remain outside Tranche 3.
