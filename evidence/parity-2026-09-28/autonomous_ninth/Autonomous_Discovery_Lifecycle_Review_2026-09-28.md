# Seed-132 discovery lifecycle review

The receiver-timer correction passed its actual MATLAB checks and cleared the prior 45.662638077-second stop. All **53 component checks passed**, and the run reached **71.942 seconds**. This return reveals two independent lifecycle mismatches: a reliable KEY_UPDATE response is admitted too late in MATLAB, and a discovery requester arriving during an active scan is incorrectly removed from future scan work.

The first timing difference occurs at **62.870833632 seconds**, before the final packet guard stops. The complete run must therefore not be described as a temporally matching prefix. Both confirmed causes are included in one continuation; the ±15% full-network target remains open.

## Actual return and comparison limits

Input: `out_auto_20260928_083055.zip`, SHA-256 `54ade5a199624644263f1ef33e17edc917a12849b040f2c5fac37668f6fa08b7`, 46 members. All 355 issued file hashes match the returned manifest. Runtime was MATLAB R2025a 25.1.0.2943329, PCWIN64. Import, the accepted natural reuse gates and all 53 component checks passed. No fresh natural simulation was required.

| Actual K result | Value |
|---|---:|
| Stop time | 71.942 s |
| Consumed random inputs with matching semantic context | 1,450 |
| Consumed MAC / SYNC / PHY inputs | 286 / 658 / 506 |
| Verified transmission contexts | 243 |
| Next rejected transmission | Node 5, TX 68 |
| Random requests with a different timestamp | 341 |
| Transmission contexts with a different timestamp | 58 |
| Application attempts | 0 |
| MATLAB wall time | 134.37 s |

The unconditional merged audit checks all 1,694 random-request and transmission-context events. The first 1,281 match native order and rounded-nanosecond times: 1,097 consumed draws and 184 successful transmission contexts, ending with node 8's second SYNC draw at 62.829015346 seconds. Three positions differ in the eventual merged order: node 4's 25th MAC draw is delayed past node 8's third and fourth PHY draws. One request is delayed by 10.166368 ms; another 340 requests and 58 transmission contexts are delayed by 13 ms. Diagnostic PHY interval endpoints differ for 121 requests even though their controlling sample contexts pass. The final rejected context is not counted as a physical transmission.

The capture contains 180,186 ordered observations, 1,458 transport-timing records, 924 new relative-timer records and 3,237 service records, with no reported omissions. The earlier PHY sample now uses 51 bits and passes. All eight timer checks also passed in MATLAB, including the full 1,542-row allocator fixture, public acquisition transition and paired PHY/MAC completion order. This is actual runtime evidence for those checks; it does not prove the entire network trajectory matches.

## KEY_UPDATE admission misses the receiver transition

At 62.870833632 seconds, node 4 receives node 2's KEY_REQUEST while its receiver is still Track. Native constructs and queues the reliable KEY_UPDATE response before returning the receiver to Search. That transition sees pending work and immediately prepares transmission, including the next MAC reservation draw.

MATLAB creates the same response but schedules its NWK pump for a later callback at the same simulation time. The receive callback first returns the receiver to Search while MAC has no queued response. The pump then admits KEY_UPDATE, and preparation waits until the next slot at 62.881 seconds. This postpones the MAC draw by 10.166368 ms and the resulting transmission by one 13 ms slot.

The earlier inline-admission correction covered KEY_REQUEST only. It did not cover this reliable KEY_UPDATE response. The newly exposed mismatch belongs at NWK-to-HOP admission; changing MAC's slot or post-transmission waiting policy would treat the consequence instead of the cause.

The returned prefix contains ten KEY_UPDATE generations, all deferred across the Track-to-Search boundary in MATLAB. Earlier cases have existing work or a carried reservation that masks the delayed-admission effect. The node-4 response is the first case where an empty queue and unassigned reservation expose it.

The full native capture contains 14 KEY_UPDATE generations, 14 distinct transmitted frames and 14 successful ACK completions, with no observed retransmission or resend-queue overflow. They are reliable 62-byte controls with DSCP 7. Native registers resend ownership before MAC enqueue and starts its ACK clock on the actual sent confirmation. The correction preserves reliable ACK/radio options, registers the MATLAB owner before the send callback, and re-finds it afterward to handle synchronous completion safely.

The existing MATLAB reliable-admission gate and blocked/failed-send fallback are retained. This is not a saturation-parity fix: native can transmit after failing to install resend tracking when its resend queue is full, while MATLAB gates admission earlier. That adjacent source difference is unexercised in this capture and is explicitly outside this change.

## Active-session START wrongly suppresses a future target

The SNMP mismatch begins earlier and is independent of that MAC timing difference. Node 5 receives START from node 3 at 40.900359163 seconds and begins discovery. It then receives START from node 1 at 41.202171086 seconds while discovery is already active.

Both implementations retain node 1 as a requester that should receive the completion report. Native marks the initiating requester as not needing another scan only when START begins a new discovery session. MATLAB also puts the source of an already-active START into `ScanRequested`, which makes the later scan scheduler skip that node.

After node 4's DONE arrives at 71.827352444 seconds, native selects node 1 next. MATLAB has incorrectly marked node 1 as already requested, so it selects node 2 via node 4. The resulting third child triggers the packet guard at 71.942 seconds.

| Third child of node 5 TX 68 | MATLAB | ns-3 |
|---|---:|---:|
| Command | SNMP START | SNMP START |
| Source | 5 | 5 |
| HOP destination | **4** | **1** |
| Embedded final destination | **2** | **1** |
| Wire bytes | 31 | 31 |
| ACK required | No | No |

The other children—an ACK and a routing update—and the 166-byte aggregate size match. These destination fields control behavior and remain strict comparison fields.

The existing native capture contains 28 START and eight DONE transmissions. Twenty START packets intentionally use an intermediate HOP destination and are dropped after that hop if their embedded destination is not local; this existing native behavior is already modeled and is preserved. The only observed START received during active discovery is the node-5/node-1 occurrence above. Seven DONE packets reach NWK, each from its pending target, and the maximum requester list is two. The audit does not justify changing unrelated DONE advancement rules, list limits, route lookup or watchdog behavior.

## One batched continuation

The isolated `L_discovery_lifecycle` case combines only these two corrections: mark a START requester as already requested only when it initiates a new session, and submit a fresh reliable KEY_UPDATE during the receive callback after the existing admission checks. It keeps the K receiver timers, radio/bit formulas, native input fixture and packet/draw guards. The original model files and earlier candidate classes remain unchanged.

All 53 existing checks remain, with eight new public NWK component checks. They cover no-ACK KEY_REQUEST when the reliable gate is closed; reliable KEY_UPDATE owner registration and ACK/wire fields; blocked and failed admission retries; capacity rejection; preservation of unrelated queued work; synchronous ACK completion with legitimate follow-on control work; active START requester retention and selection; and subsequent DONE progression without duplicate handoffs. These are bounded component checks, not a separate network simulation for each case. Queue-capacity checks validate retained MATLAB ownership safety, not native overflow equivalence.

Download `autonomous-discovery-lifecycle-tests.zip`, extract it into a fresh folder, restart MATLAB, and set Current Folder to `autocase`. Run:

```matlab
report = run_autonomous_tests;
```

Return the generated `out_auto_*.zip`, including any diagnostic stop. The accepted natural run is reused after its gates pass. One new common-input L case runs from zero to its first guarded divergence or 330 seconds. Historical K and earlier cases are retained as evidence and are not rerun. No owner-side ns-3 command is required.

## Acceptance boundary

The next continuation retains K's timer correction and all existing strict semantic guards. New MATLAB execution remains pending. Application offers begin at 300 seconds, so this return contains no application attempts and cannot establish the original 6,000-second attempted/admitted/delivered/dropped/unresolved accounting or comparable-population latency. The ±15% target still requires those full-network results, including source mix and unfinished traffic.

The sealed kit binds 389 files. All 147 MATLAB files pass static syntax parsing with MISS_HIT 0.9.44 using its MATLAB 2022a grammar. Independent review verifies 24 exactly reversible transformations, all 99 unchanged model files, all 46 unchanged earlier candidate/helper MATLAB files, and unchanged native references. The final manifest SHA-256 is `0125e2c6e70c5047a604a9a77fa1155dfabcb8251c1cc461d9b54aaeff592bae`. Static checks do not substitute for the pending MATLAB execution.

The review uses the existing native capture and pinned source. No new long network simulation was commissioned.
