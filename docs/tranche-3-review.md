# Tranche 3 integration review

Review date: 2026-09-08. Reference source:
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` in
`mjburke4/CSR-Project-NS3-part2`.

The bounded code review found no additional known structural blocker after
the fixes below. This is a source inspection and static validation result.
Tranche 3 has not received MATLAB runtime acceptance; the previously accepted
Tranche 2 results do not certify this modified tree.

## Scope and actual checks

Reviewed the HOP-to-NWK callbacks, grouped control ownership, simulator
transmit/receive dispatch, application custody accounting, routing snapshots,
scenario normalization, discovery/link events, and result exports. The review
also revisited changes to existing HOP DATA completion and frame aggregation
for possible Tranche 2 regressions.

MISS_HIT 0.9.44, using its latest supported MATLAB language setting `2022a`,
reported all 16 selected implementation/test files clean: HOP `Layer` and
`Frames`; NWK `Layer`, `Routes`, `Neighbors`, `defaults` and `validateConfig`;
scenario `validate` and `routedNetwork`; `NetworkSimulation`, `runScenario`,
`exportResults`; and `TestNetworkConfig`, `TestHopLayer`, `TestHopFrames`,
`TestHopControls`. The final configuration-test edits were linted again with
no findings. `git diff --check` reported no whitespace errors.

No MATLAB or Octave runtime was available to this reviewer. No test methods
were executed, and no simulator output was inferred from the lint result.
The integration lead records the complete repository lint and hash audit
separately.

## Findings addressed

| Finding | Resolution inspected |
|---|---|
| Empty scalar `App` structs erased control identities in traces; aggregate TX records could inherit a member's application ID and control kind. | Aggregate traces retain the unique OTA `frame.Id` and `AGGREGATE` kind. DATA selects its application ID only when present. Control events select `Control.Id`. PHY trace identity remains the OTA identity. |
| Partial control ACK traces reported the original primary destination even when a secondary peer ACKed. | Protocol tracing reads `details.PeerId` with a fallback to the HOP callback's `details.Peer`. |
| Local INFO configuration accepted unsupported rate endpoints and inverted rate/power ranges, allowing failure only after measured traffic reached adaptive link calculation. | NWK scenario normalization now rejects unsupported rate endpoints, `MinSpeedKbps > MaxSpeedKbps`, and `MinPowerDbmX10 > MaxPowerDbmX10` before scheduling work. |
| Treating source capability zero as a general prohibition on transit changed ordinary source routing behavior. | Transit policy is an explicit `Nodes.TransitForwardingEnabled` Boolean, default true. Capability zero remains valid independently. The configured leaf fixture disables transit explicitly. |
| Returning an inactive-peer policy rejection to HOP after final ACK admission would raise `LocalCustodyRefused`. | The simulator translates inactive/disabled-transit policy rejection into protocol receipt plus an explicit application drop. Actual custody-queue refusal remains a false delivery result. The proposed pre-ACK neighbor gate was removed to preserve source ordering. |

The INFO and node-policy configuration contracts are covered by the eight
methods in `TestNetworkConfig`. The file also exercises partial nested
defaults, absent explicit paths, invalid capabilities, unknown nested options,
link/discovery event IDs and times, Boolean fields, control-type fault filters,
legacy wildcard normalization, supported high-rate settings, and minimal
network-stack dispatch. These are prepared runtime tests, not passing evidence.

## Integration conclusions

Grouped controls occupy one HOP resend record, preserve original target and
sequence lists through partial ACKs, and cancel their original MAC copy only
on whole-group completion or expiration. Per-peer control sequences share the
DATA receive/ACK window without changing DATA pending/window/NSDP counters.
NWK retains fresh residual-control retry ownership and waits for a scheduler
event before resubmission. The original 22 control tests remain present.

Successful PHY aggregates reach all intended control recipients through
explicit member addressing. Overheard decoded traffic updates measured peer
state but cannot complete another node's HOP transaction. OTA transmission
identifiers are allocated centrally and are separate from application and
per-node control identities.

Application accounting follows current custody ownership. An older sender's
ACK exhaustion cannot turn an already forwarded or delivered application into
a drop. Source no-route suppression followed by a duplicate ACK is exposed as
unretained application loss; a later actual custody acceptance or delivery can
reverse that provisional accounting. These accounting paths need particular
attention in the MATLAB scenario gate because static review cannot establish
their timing outcomes.

## Source limits and remaining gate

- The source inactive-peer gate resides in NWK `ReceiveFromHop` after HOP
  sequence handling and local ACK admission. The retained simulator wrapper
  preserves this ordering and distinguishes protocol receipt from application
  retention.
- Transactional queue admission, waiting for actual retry transmission, and
  suppression of duplicate partial-ACK result callbacks remain explicitly
  documented portable policies. They are not source-exact overload/timer
  certification.
- Behavioral key/admission state and modeled security byte counts do not
  implement cryptographic authentication, encryption or replay protection.
- Routed fixtures use a declared 150 m closure delegate to constrain line
  topology. The CSR signal engine still carries the admitted-link traffic.
  Link blackout and control-loss fixtures are deliberate receive erasures,
  not measured RF outage models or physical topology changes.
- Routing, discovery and recovery acceptance requires running the complete
  MATLAB suite and scenario runner on the delivered tree, retaining MATLAB
  release/version, pass/fail records and exported scenario evidence. The gate
  must include the existing Tranche 2 regressions plus autonomous forwarding,
  control loss, no-route custody, recovery, gateway policy, explicit transit
  refusal and both high-rate cases.

An unavailable OPNET packet/event trace is not a blocker for this functional
tranche. Full cross-simulator numerical parity and cryptographic security are
not claimed by this review.

## Lead final checks

The complete repository passed MISS_HIT on all 72 MATLAB files. The final tree
contains 254 prepared portable test methods and five separately gated native
methods. The lead added a ninth configuration test for integer storage of
fractional time/power units, extended the leaf fixture to verify targeted
NoPath transmission, and checked the source NoPath rule with the routing
specialist. These follow-up checks are static/source evidence only. All twelve
reference workflows and their source, binary, log, runner and CMake hashes
were audited successfully.
