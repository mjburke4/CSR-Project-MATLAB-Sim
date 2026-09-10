# Tranche 5 performance diagnostics

`[row, applications] = csr.analysis.performanceSummary(result)` analyzes a
completed network-stack result without changing it. `row` is a scalar struct
suitable for `struct2table(row)`; `applications` is a table with one row per
unique generated application, in generation order. This layer retains every
field and structural gate from `csr.analysis.researchSummary` and adds the
`csr-performance-summary-v1` diagnostic contract.

## Traffic and latency

| Field | Definition |
| --- | --- |
| `GeneratedApplicationBytes` | Sum of application payload bytes in `app_generate` records; excludes protocol overhead and retransmissions. |
| `FirstGenerationSeconds`, `LastGenerationSeconds` | First and last actual generation timestamps. Missing (`NaN`) when no applications were generated. |
| `GenerationSpanSeconds` | Last minus first actual generation time. One application has span zero. |
| `TrafficObservationSeconds` | Simulation stop minus first actual generation, including the drain interval. |
| `ObservationMeanOfferedLoadBitsPerSecond` | Generated application bits divided by `TrafficObservationSeconds`; missing if that interval is zero or no applications were generated. It is an observation-window mean, not the configured active flow rate. |
| `ScheduledFlowRateSumBitsPerSecond` | Sum of `8 * ApplicationPayloadBytes / IntervalSeconds` across configured nonempty flows. Includes flows scheduled beyond the finite stop. This nominal sum is not a measured peak and does not imply that every flow overlaps. |
| `PlannedLastGenerationSeconds` | Latest configured `StartSeconds + (PacketCount-1) * IntervalSeconds` across nonempty flows, including generations after the stop. |
| `PlannedDrainSeconds` | Simulation stop minus planned last generation. Negative means the configured traffic extends beyond the stop; missing means no nonempty flows. |
| `MaxLatencySeconds` | Maximum delivered-application latency. Missing when no applications were delivered. |
| `LatencyP50Seconds`, `LatencyP95Seconds`, `LatencyP99Seconds` | Inherited nearest-rank empirical quantiles: sorted latency at index `max(1,ceil(p*n))`. No interpolation or Statistics Toolbox. |
| `GoodputBitsPerSecond` | Inherited received application bits divided by the entire simulation duration, including warmup and drain. |

The application table columns are `PacketId` (`uint64`), `SourceId`,
`DestinationId`, `ApplicationBytes`, `Dscp`, `GeneratedSeconds`,
`LastEventSeconds`, `ReceivedSeconds`, `LatencySeconds`, `Outcome`, and
`DropReason`. Outcome is `pending`, `dropped`, or `delivered` at the finite stop.
`LastEventSeconds` is the last recorded application state event (generation,
relay acceptance, drop, or delivery), not the last MAC/HOP action. Pending and
dropped applications have missing receive time and latency; this does not
convert them into zero-latency observations.

Event reconstruction preserves the simulator's late recovery semantics:
`app_drop` can be followed by `app_receive` (late delivery) or `relay_accept`
(restored pending custody). A later delivery wins over earlier drop records.
Unknown identities, changed payloads, changed delivered DSCP, and reconstructed
outcome totals that disagree with final counters fail the diagnostic gate.
Recovered applications do not retain an obsolete final drop reason.

## Transmission units

| Field | Source and unit |
| --- | --- |
| `PhysicalTransmissions` | Existing OTA transmission count. A concatenated aggregate counts once. |
| `PhysicalAttempts` | Existing receiver-observation count. One OTA transmission is observed at each non-self receiver, whether intended or overhearing. |
| `PhysicalReceived`, `PhysicalDropped`, `PhysicalPending` | Receiver outcomes, not unique application outcomes or transmitter counts. |
| `MacMemberTransmissions` | Sum of MAC `SegmentsTransmitted`; counts every transmitted member within each OTA envelope. Retries and repeated feedback count again. |
| `DataMemberTransmissions` | Existing simulation `DataTransmissions`: DATA members, including retransmission attempts and relays. |
| `ControlMemberTransmissions` | Existing simulation `ControlTransmissions`: all non-DATA members, including network controls, ACK and DACK. |
| `NetworkControlMemberTransmissions` | Sum of HOP `ControlTransmitted`: CONTROL members, including discovery/admission and routing. A grouped control is one member, regardless of target count. |
| `AckFeedbackMemberTransmissions` | Sum of MAC `AckTransmissions`: ACK and DACK feedback members, including repeated feedback and feedback packed in aggregates. It does not separate ACK from DACK. |
| `ConcatenatedTransmissions` | Number of OTA envelopes with more than one member, from the MAC counter. |

The diagnostic gate checks OTA counts against MAC counters and `tx_start`
records. It also checks that DATA plus non-DATA equals all transmitted members,
and that network CONTROL plus ACK/DACK feedback equals non-DATA members. The
protocol trace's `FrameKind=AGGREGATE` does not expose individual members, so
member counts come from source-owned counters, not guessed trace expansion.
No radio-loss ratio is interpreted as application delivery probability.

## Reliability, routing and queue observations

| Field | Source |
| --- | --- |
| `HopDataRetransmissions`, `HopControlRetransmissions` | HOP `Retransmissions` and `ControlRetransmissions`; retry actions, separate from total transmitted members. |
| `HopControlFailures`, `HopControlTargetFailures` | HOP `ControlFailed` and `ControlTargetFailures`; preserve the transaction/target distinction. |
| `ControlFailures`, `ControlResidualRetries` | NWK counters of those names; do not sum them with HOP failures to infer unique lost messages. |
| `NeighborActivations`, `NeighborDeactivations`, `RouteChanges`, `SnapshotTimeouts` | Summed NWK counters. These report events, not unique peers, routes, or causes. |
| `QueueAdmissionRejections`, `ControlQueueRejections` | NWK admission refusal counters; repeated refusal attempts can count more than once. |
| `HopMacAdmissionRejections` | HOP `MacAdmissionRejected`; preserve separately from the MAC counter of the same refusal path. |
| `MacDataQueueRejections`, `MacFeedbackQueueRejections` | MAC `DataQueueDrops` and `AckQueueDrops`; queue admission refusals, not final application losses. |
| `HopFeedbackQueueDrops` | HOP feedback queue refusal counter; may overlap the MAC feedback rejection observation. |

These fields are descriptive. They do not establish why a packet was slow or
lost, statistical confidence, or equivalence to ns-3 protocol behavior.

## Finite-stop ownership and runtime

`ApplicationsDrained` means zero pending applications. Inherited `DataDrained`
also requires zero HOP pending DATA, resend entries and DACK holds, plus zero
NWK custody. `ControlsDrained` requires zero HOP control transactions and target
ownership plus zero NWK pending control messages/backlog.
`OwnershipDrained = DataDrained && ControlsDrained` is limited to those exported
counters. `ControlDrainScope` explicitly states that current MAC feedback queue
depth is unavailable. Neither flag certifies empty MAC queues, all receiver
observations completed, or an empty scheduler. `PhysicalPending` and
`PendingSchedulerEvents` remain separate; periodic protocol timers can remain
scheduled even after ownership drains.

`RuntimeSeconds` is inherited elapsed wall time. `PendingSchedulerEvents` is the
scheduler's remaining count at stop. `ProtocolTraceRecords` and
`PhyTraceRecords` count exported rows, not executed callbacks.

The unchanged network result does not export sender durations, current MAC
queue depths, CPU time, or executed scheduler callback count. MAC callback
duration details are discarded during trace serialization, and PHY end records
include early receiver failures. Therefore `AirtimeAvailable`,
`CpuTimeAvailable`, and `ExecutedEventsAvailable` are false; all corresponding
airtime, CPU-time and executed-event measurements are `NaN`. No receiver-signal
interval is substituted for transmitter airtime and no event-count rate is
invented. DATA/control/feedback airtime allocation would also need an explicit
shared-preamble rule for mixed aggregates.

## Validation evidence

A read-only Python audit applied the transmission equalities and application
reconstruction rules to all **11 accepted Tranche 4 research/shared cases** in
`evidence/tranche-4-r2025a-accepted/tranche4_evidence.zip`:

- All 11 passed MAC/OTA, total-member, network-control/feedback-member, and
  `tx_start` count checks.
- All 11 passed application identity, time, payload, delivered-DSCP, and final
  delivered/dropped/pending reconstruction checks.
- None of those 11 contained a late drop-to-delivery or drop-to-relay transition.
  Dedicated synthetic MATLAB tests cover both transitions.

The new MATLAB test class also covers metric units, denominators, finite-stop
pending work, empty/singleton tables, control-drain scope, distinct retry and
failure counters, invalid evidence, and an actual short network result. Static
lint passes for the new analysis and test files. MATLAB execution of these new
tests remains a separate acceptance gate; the Python audit is not MATLAB
runtime validation.
