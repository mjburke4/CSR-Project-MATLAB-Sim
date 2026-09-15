# Tranche 10 owner return: MAC and receiver timer audit

The supplied owner log does not establish which callback consumed the event limit. It establishes successful MAC (279), receiver (154), and ACK (101) contracts, completion of the unit-test phase, and completion of retained cases 1–26. The failure occurs in retained case 27, `research_mesh_6_seed_128`, with `MaxEvents=2,000,000` and duration 900 seconds. Campus has not begun.

I found no direct non-advancing callback cycle in the delivered MAC or receiver code. No MAC, PHY, or ECC behavior change is justified by this audit alone. Raising the limit would hide an unresolved structural failure.

## MAC timer findings

- `+csr/+mac/Layer.m` `scheduleSlotTick` (lines 291–324) requires `nextTime > Scheduler.Now` before using the new integer-nanosecond path. Otherwise it schedules the original `Now + SlotSeconds` path. The failed fixture uses `SlotSeconds=0.013`; neither branch can schedule the next tick at the present instant within a 900-second run.
- At 900 seconds, integer nanoseconds are at most `9e11`, far below the exact-double integer limit `2^53 ≈ 9e15`. The tick index and product remain exact integers. A Python IEEE-754 arithmetic probe through this horizon found a minimum consecutive tick gap of `0.012999999999919964` seconds.
- `slotTick` re-arms one timer first. `SlotEvent` holds the new event ID before receiver polling. An Idle transition cancels that ID. A subsequent Search transition resets the epoch only when `SlotEvent==0`. `receiverChanged` returns immediately for an unchanged state, and `setState` updates the MAC state before notifying the PHY. This does not create duplicate timer ownership through the normal bridge callbacks.
- `scheduleIdleRts` (lines 337–356) checks the computed boundary and advances one further slot if the first result is not strictly future. A Python probe of all 69,231 slot-grid positions through 900 seconds and the adjacent representable values (207,693 checks) found no non-future result. This is an arithmetic probe, not MATLAB execution.
- The remaining recurrent MAC timer, `periodicWake`, advances by a positive 0.988 seconds. Holdoff, sleep, packing retry, TX completion, and post-TX expiry are finite one-shot callbacks using positive fixture delays. TX completion can lead to more traffic, but does not directly re-arm itself at the same instant.
- Six continuously active MAC clocks would produce approximately 415,380 ticks over 900 seconds. Actual Idle periods cancel those clocks. This estimate alone does not bound all protocol events, but the new MAC timer does not inherently multiply the event load beyond two million.

## Receiver findings

- `SignalEngine.scheduleAcquisition` only arms when the receiver is Search and `AcquireEvent==0`. The delay is the positive 6.63 ms fixture setting. The callback clears its ID and changes to Track or returns; it does not re-arm itself in a loop.
- Each arrival creates finite preamble-end and signal-end events. `endSignal` retires the completed signal and decrements outstanding signal count before upper-layer callbacks and the rejected-packet 28 ns fallback.
- `returnRejectedToSearch` changes state once and only re-arms acquisition if another finite preamble remains. This is not a self-generating rejected-signal cycle.
- PHY transmission duration is validated positive. Receivers may see a zero-propagation arrival for colocated nodes, but one transmission still creates a finite set of signals and completion events. The failed mesh nodes are spatially separated.

## Historical comparison and causal limits

The accepted Tranche 7 archive contains this same 900-second fixture. It completed in 59.8014808 wall seconds, with 1,183 physical transmissions, 15/15 application deliveries, zero drops or pending applications, 85 route changes, and six pending scheduler events at normal stop. This supports treating the new event-limit exhaustion as a regression requiring diagnosis; it does not prove a specific root cause.

Tranche 10 changes the precise slot phase and can therefore expose an existing deadline bug elsewhere. A common mechanism is scheduling `deadline = sent + duration` but testing completion using `Now - sent >= duration`: at `Now == deadline`, subtraction can round just below `duration`, and retrying at `max(Now, deadline)` repeats forever. Root is auditing HOP/NWK owners of such deadlines. This mechanism remains a hypothesis for the owner failure until a matching timer is demonstrated or a runtime callback trace is obtained.

## Minimal diagnostic and verification suggestions

1. Preserve `MaxEvents`. Include `Now`, the next event time, the next callback identity, and consecutive callbacks at the same time in the event-limit failure record. Collecting those fields should not call protocol code or consume RNG.
2. Provide a short-path isolated run of `research_mesh_6_seed_128` before repeating contracts, all 29 cases, and campus. Include a source snapshot and its result or failure record so the diagnostic run cannot be confused with full acceptance.
3. If a deadline counterexample is found in HOP/NWK, add a deterministic unit regression that reaches the exact stored deadline and verifies removal, completion, or a strictly later event. Include just-before-deadline and multiple simultaneous ownership cases. Do not add global epsilon scheduling or quantize the PHY clock to hide a deadline-owner error.
4. Keep the already passing 279 MAC, 154 receiver, and 101 ACK checkpoint references unchanged unless a separate source-supported behavior change is demonstrated.

Audit is read-only for repository files. No MATLAB or Octave runtime was available or executed. The JSON companion records inspected file hashes and arithmetic-probe counts.

## Follow-up: demonstrated admission retry loop

The subsequent bounded HOP/NWK audit found a concrete zero-time loop in `+csr/+nwk/Neighbors.m`. This establishes a defect in the shipped source independently of the owner mesh run; the supplied owner log still does not prove that this exact path caused its event-limit failure.

All three admission backoff branches compare elapsed time using subtraction, then re-arm using an absolute deadline formed by addition:

| Backoff | Elapsed-time test | Re-arm expression |
|---|---|---|
| Key request | line 280: `now-KeyRequestWhen >= KeyRequestDelay` | line 283: `KeyRequestWhen+KeyRequestDelay-now` |
| Key send | line 291: `now-KeySendWhen >= KeySendDelay` | line 295: `KeySendWhen+KeySendDelay-now` |
| Overheard check | line 302: `now-OverheardWhen >= OverheardDelay` | line 308: `max(0,OverheardWhen+OverheardDelay-now)` |

Their common path is `scheduleRetry` line 367 → `retry` lines 370–372 → `evaluate` line 271. At a deadline where addition rounded downward, these two expressions disagree. With the ordinary five-second default backoff:

```text
When                       = 11.013
Delay                      = 5
scheduled Now = When+Delay = 16.012999999999998
Now-When                   = 4.9999999999999982 < Delay
When+Delay-Now              = 0
```

The callback takes the “not yet due” branch, schedules itself at the same `Now`, and does not change `When`, `Delay`, peer generation, or any gating state. Therefore every future iteration is identical and the scheduler eventually raises `csr:sim:EventLimitExceeded`. The ten-second backoff has the same result at this starting time: `Now=21.012999999999998`, elapsed `9.9999999999999982`, and remaining time zero.

Minimal reproduction recipes, using only existing public APIs, follow. They are proposed MATLAB reproductions, not claimed MATLAB executions. Empty `Callbacks` is a valid constructor input; it represents rejected control admission and produces the first two paths without accessing private fields.

```matlab
% Key-request deadline: expected old-code failure at 16.012999999999998.
s = csr.sim.EventScheduler(20);
s.run(11.013);
n = csr.nwk.Neighbors(1,s,struct(),struct());
n.receiveControl('DISCOVER',2,struct('Subtype','broadcast','Sequence',1));
s.run(20);
```

```matlab
% Key-send deadline: received key, own update rejected, still inactive.
s = csr.sim.EventScheduler(20);
s.run(11.013);
n = csr.nwk.Neighbors(1,s,struct(),struct());
n.receiveControl('KEY_UPDATE',2,struct());
s.run(20);
```

```matlab
% Overheard deadline: both keys complete; subsequent checks are rejected.
s = csr.sim.EventScheduler(20);
s.run(11.013);
c = struct('SendControl', ...
    @(kind,peers,payload,reliable) strcmp(kind,'KEY_UPDATE'));
n = csr.nwk.Neighbors(1,s,struct(),c);
n.receiveControl('KEY_UPDATE',2,struct());
n.controlCompleted('KEY_UPDATE',2,struct(),true);
s.run(25);
```

In the third recipe, key-update success sets `SentKey=true`. `evaluate` sends the first overheard check, stores `OverheardWhen=11.013`, and doubles its five-second delay to ten seconds. Rejected check admission synchronously clears `CheckActive`; the outer evaluation schedules the ten-second retry, which enters the demonstrated loop at its exact deadline. The peer remains inactive, as required.

A focused correction should make each due test use the same absolute deadline as its re-arm expression, e.g. `now >= entry.KeyRequestWhen + entry.KeyRequestDelay`. This resolves the contradiction at the timer owner without arbitrary epsilon, clock quantization, raised limits, or changed five/ten-second backoff policy. Root owns any implementation and source-parity check. Regression coverage should include all three paths, one representable instant before the deadline, exact deadline, delayed callback, and unrelated pending peer generations. At the exact deadline the corrected branch must progress and schedule its next doubled backoff in the future.

### Other audited HOP/NWK timer paths

- `Neighbors.controlCompleted` line 144 can insert an immediate retry using the old key-send deadline; it feeds the same `evaluate` predicates. It does not provide a fourth distinct loop mechanism, and correcting only line 144 would leave all three demonstrated paths defective.
- `checkFreshness` uses an elapsed-age comparison, but its next check is always `Now+FreshnessPeriodSeconds` (two seconds by default), not the same absolute age deadline. Rounding can defer a decision until another period; it cannot create this zero-time loop. Freshness is disabled in the failed mesh fixture.
- HOP `notifySent` schedules resend checking at `Now+wait+TicSeconds`. The default tick is `1/36e6` seconds, much greater than the double spacing near 900 seconds. `checkResends` uses elapsed-age tests but does not re-arm itself if the test is false. Its accepted resend returns to MAC and is not confirmed until actual transmission. No same-time or repeated tiny-delay feedback loop was demonstrated there.
- HOP DACK expiry stores an absolute `Expiry` and compares that same value against `Now`; its event is at `Expiry+TicSeconds`. `scheduleWake` has one pending flag, schedules one positive tick, and calls NWK wake once. NWK pump has no unconditional path back to HOP wake.
- NWK `wake/pump`, `scheduleRoutes/processRoutes`, snapshot responses, and chirps use coalesced same-time callbacks, but each immediate callback drains or marks finite work. Failed control/backlog admission defers by the positive eight-second `ControlRetrySeconds`. HOP completion requires a real transmit/receive or timeout before producing further work. No independent zero-time cycle was demonstrated.
- `Routes.m` owns no scheduler or time-based expiry callback. Its changes, candidate updates, and snapshot construction are finite synchronous operations. Request retransmission loops in NWK are bounded by `MaxRouteRequests` and use eight-second delays; snapshot watchdogs are one-shot twenty-second callbacks.

These findings do not establish that every possible positive-time traffic pattern fits the two-million-event budget. They establish one concrete source-level livelock and its three directly reachable branches, which should be repaired and verified before considering any event-budget change.
