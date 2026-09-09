# Tranche 3 integration review

Review updated: 2026-09-09. Pinned ns-3 reference:
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.
MATLAB base: merged PR #2, `88e56a83c2e9baa295be89f63b873bbe1fa1aa5f`.

The portable R2025a functional gate is now accepted at `ff7859a`.
The earlier review of recovered candidate `602ddd3` missed several observable
protocol differences; those conclusions are superseded by this correction pass.
Astra performed the routing and integration closeout at the owner's request.
No MATLAB or Octave test execution occurred in this workspace.
The final owner run passed all 289 methods and all eight T3/nine T2 scenario
exports. Source hashes, candidate manifest and test CSV linkage were verified.
Astra independently reviewed the final scenario/accounting gate. See the
[acceptance record](tranche-3-portable-acceptance.md) and
[historical repairs](tranche-3-r2025a-repair.md).

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

The candidate manifest records source hashes and the static-lint outcome and
now points to the acceptance record. The owner run establishes 289/289 passing
tests, independently of syntax checks. Its original manifest is preserved as
`evidence/tranche-3-validated-candidate.json` for runtime hash verification.
MISS_HIT 0.9.44 uses its supported MATLAB 2022a parser profile; this checks syntax
without establishing R2025a/R2026a numerical or scheduling behavior.

Twelve preserved ns-3 workflow binaries re-executed successfully. Their original
source/build/binary/log manifest is retained. The current environment has no
CMake, so neither a fresh build nor five proposed extra security/wire workflows
was completed. Do not reinterpret these checks as MATLAB differential evidence.

## Remaining validation work

- R2025a is accepted: all portable methods and scenario exports passed, with
  zero control/backlog rejection and fully drained ownership in the final rows.
- The supplied release/version, raw file hashes, test CSV and scenario summaries
  are preserved. Raw per-layer traces/config/MAT exports were not supplied;
  preserve those on the owner machine for later differential analysis.
- Repeat portable validation on R2026a; six native clock/packet tests remain
  separate, including full routed portable-versus-native-clock equality.
- Equivalent MATLAB/ns-3 network scenarios and OPNET aggregate comparison remain
  unexecuted. Portable functional acceptance does not establish numerical parity.

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
