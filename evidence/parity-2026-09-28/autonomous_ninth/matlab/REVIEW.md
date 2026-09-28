# Discovery lifecycle review of the ninth owner return

The actual K return passed all 53 component checks and reused accepted natural A through its unchanged gates. It matched 1,450 random requests and 243 physical transmission signatures before stopping at 71.942 seconds, node 5 transmission 68. The third child was SNMP_START: MATLAB addressed final node 2 through HOP peer 4; native addressed final node 1 through peer 1. The other two children, total 166 bytes, rate, power and reservation context matched. This is a behavioral destination difference and remains a strict comparison failure.

Two independent control-lifecycle mismatches are supported by the existing evidence. L batches them in one network continuation. It retains K's receiver timers, all prior protocol candidates and all comparison guards.

## Active SNMP requester ownership

At 40.900359163, node 5 receives SNMP_START from node 3 and starts its local discovery. At 41.202171086, it receives another START from node 1 while that scan is active. Both requesters must receive a DONE report when the scan finishes. Native marks the requester as already scanned only when that requester initiates a new local session; an active duplicate is merely retained for the completion report.

The portable implementation adds the requester to `ScanRequested` after the new-session branch, so it marks both 3 and 1 complete. This state difference occurs before the later MAC timing difference. At 55.900359163, both implementations send DONE to 3 and 1, then start discovery at node 4. When node 4's DONE arrives at 71.827352444, node 1 should remain ahead of newly learned node 2 in the pending scan list. MATLAB skips node 1 and sends START for node 2 through node 4. Native sends START for node 1 directly.

The isolated NWK copy moves only the requester-completed update inside the new-session branch, before starting discovery. It retains active duplicate requesters, their DONE replies, insertion order, routing lookup, watchdog and receiver address filtering. The captured native audit contains eight START receives with one active duplicate, and seven delivered DONE messages all from the currently expected handoff target. Requester capacity never exceeds two. Native/MATLAB differences for unrelated DONE arrival policy and requester capacity are not changed or claimed resolved.

## Reliable KEY_UPDATE admission timing

The first nontrivial random-request time difference occurs earlier than the destination stop, at node 4's MAC draw 25. Native requests it at 62.870833632; MATLAB requests the same value and semantic context at 62.881, 10.166368 ms later. The returned ordered trace identifies the cause without another simulation.

Node 4 receives a KEY_REQUEST from node 2 while PHY/MAC are tracking. NWK creates the reliable KEY_UPDATE owner but schedules the ordinary same-time pump. PHY then returns Track to Search while the MAC queue is empty. The pump subsequently enqueues the 62-byte KEY_UPDATE, after that receiver transition has passed. MAC preparation waits for the next slot. The matching native path calls HOP synchronously during reception, so the response is already queued when Track ends. Its next actual transmission is at 62.985, versus MATLAB 62.998, a 13 ms shift.

L extends the existing targeted inline KEY_REQUEST path to fresh reliable KEY_UPDATE only. It registers the owner before calling HOP, applies the current `CanSendControl` guard, preserves radio selection and reliability, and re-finds the owner after any synchronous completion. It does not pump unrelated controls or application traffic and does not change MAC scheduling. A blocked or refused submission retains the portable deferred retry path. Native source installs resend ownership before MAC enqueue; its ACK timer starts on the sent callback. The captured native population contains 14 unique KEY_UPDATE packets, all 62 bytes, reliable and DSCP 7, with no observed retries or saturated queues.

The portable reliable-capacity gate is intentionally retained. Native's saturated resend behavior differs, so the new capacity/fallback component checks establish preserved portable ownership safety, not saturated native parity.

## Isolation and evidence limits

`DiscoveryLifecycleNwk` is a source-bound copy of K's `ControlWireNwk` with these two control-boundary changes. `DiscoveryLifecycleSimulation` is a copy of K's simulation with only its NWK class binding changed. All 99 original model files, K timer classes, prior providers, packet comparisons and random-input fixtures remain unchanged. Every candidate transform is reversible to its exact source bytes.

The runner keeps all 53 prior component checks and adds public lifecycle tests before one new `L_discovery_lifecycle` network case. Actual K results remain historical evidence and are not rerun. A reuse still requires exact source, runtime, configuration, returned-file hashes and the three original CSV-prefix comparisons.

No MATLAB runtime is available here. New component tests and L remain pending owner execution. Matching per-request contexts does not imply identical timing; the earlier timing difference is explicitly retained in the diagnosis. Neither this local repair nor the current prefix establishes the ±15% full-network accounting and latency milestone.
