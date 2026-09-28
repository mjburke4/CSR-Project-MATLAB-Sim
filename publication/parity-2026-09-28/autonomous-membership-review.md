# Seed-132 discovery worklist review

The latest MATLAB return passes all **61 component checks** and clears both prior lifecycle mismatches. The first **2,729 random inputs and 487 transmission contexts** now agree with ns-3 in guarded context, unconditional global order and rounded-nanosecond time. The next discrepancy is an extra discovery request: MATLAB adds a newly learned route to its discovery worklist at a watchdog expiry, while ns-3 advances only its existing discovery table.

The source-confirmed correction removes that automatic worklist expansion. It preserves the route itself and the legitimate ways discovery learns new scan targets. The ±15% full-network target remains open.

## Actual return

Input: `out_auto_20260928_090828.zip`, SHA-256 `979706b7d4f545b60cb5bfd1b4ac11c485783ec91a1eaa49b4858c50a3e0f2a7`, 47 members. The returned provenance matches all 389 issued files. Runtime was MATLAB R2025a 25.1.0.2943329, PCWIN64. Import and accepted natural-run reuse gates passed. The natural run was reused, not newly simulated.

| Actual L result | Value |
|---|---:|
| Guard stop | 116.415 s |
| Component checks passed | 61 |
| Strict merged prefix | 3,216 events |
| Random inputs in that prefix | 2,729 |
| Verified transmissions in that prefix | 487 |
| Total random inputs consumed | 2,731 |
| Extra rejected transmission context | Node 3, TX 86 |
| Application attempts | 0 |
| MATLAB wall time | 196.52 s |

The last event in the strict merged prefix is node 8's SYNC draw 84 at **112.775012442 seconds**. This comparison includes every native random-draw and transmission event in order, rather than filtering the native timeline to the events MATLAB happened to consume. No request interval endpoint differences remain in this return. The previously permitted outer broadcast DISCOVER identifier differences remain explicitly annotated; this is not a claim of byte-for-byte packet identity.

The two final node-3 MAC requests still pass their semantic draw guards but consume that node's native 300-second inputs too early. The first occurs at 116.350 seconds against native node-3 MAC draw 102 at 300.001 seconds. This is extra work, not a 183.651-second latency improvement or a clock-conversion error. The next event on the unconditional native timeline is instead node 7's MAC draw 32 at 117.377 seconds.

At 116.415 seconds, the transmission guard rejects a 31-byte, unacknowledged SNMP START from source 3 to final destination 7 via HOP peer 5. Native node 3's next transmission is DATA to node 1 at 300.365 seconds. The rejected MATLAB context is not counted as a physical transmission: the guard stops before registration and emission.

The return contains 381,268 ordered observations, 6,034 protocol rows, 7,406 PHY rows, 5,636 service records, 2,922 transport timing records and 1,818 relative timer records. The diagnostic summaries report no omissions.

## Earlier corrections now hold

Node 4's KEY_UPDATE-related MAC draw 25 now occurs at **62.870833632 seconds**, and its response transmission occurs at **62.985 seconds**, matching ns-3. The prior 13 ms transmission delay is gone. Node 5's transmission at **71.942 seconds** now sends the discovery request to node 1 as expected. The earlier receiver-timer boundary at 45.662638077 seconds also remains matched, with the expected 51-bit PHY sample.

Thus the two lifecycle fixes were exercised successfully by the actual network return, in addition to their eight component checks passing. All earlier component suites passed again.

## Why the extra discovery traffic appears

Node 3's explicit discovery membership contains nodes 1, 5 and 4. Its local discovery completion supplies nodes 5 and 1; a DONE report from node 5 supplies nodes 4, 3 and 1, with self and duplicate entries ignored. Node 7 is absent from these discovery inputs.

At **56.340299163 seconds**, node 3 receives DONE from node 5, advances to discovery target 4 via peer 5 and starts the corresponding 60-second watchdog. Later, ordinary routing updates teach node 3 additional destinations. In particular, a routing UPDATE from peer 5 at **96.268879163 seconds** advertises destination 7 along path 4→2→8→7. An alternate route via peer 1 arrives at 96.388928077 seconds. These are valid routing updates; they do not add discovery-table entries in ns-3.

The active watchdog fires at **116.340299163 seconds** in MATLAB, exactly 60 seconds after the DONE receipt. The earlier superseded watchdog at 100.385728077 seconds performs no work. This is therefore not an early timeout or stale-watchdog ownership failure.

Native `CheckDiscoveryTable()` walks its existing entries. Its node-3 entries are exhausted, so it schedules no further discovery handoff. MATLAB `advanceScan()` first calls `mergeScanKnown(Routes.reachableDestinations())`. That refresh imports late routes into the discovery worklist and selects node 7. The resulting NWK admission, MAC preparation and extra transmission attempt follow from this single membership mismatch.

The correction removes that refresh from scan advancement. Discovery completion still seeds membership from the applicable known-node snapshot, and received DONE reports still add their advertised members. Routing lookup and application forwarding retain newly learned routes. Timer durations, scan ownership, unrelated DONE gating, receiver behavior and comparison guards are preserved.

The full existing 0–330-second native capture supports this boundary: all 34 logged discovery-table registrations occur at idle START, local completion or received DONE; all 28 handoffs select the first existing entry that needs discovery. The audit also covers 17 watchdog callbacks. A source call-site inventory confirms that ordinary route creation updates a separate destination-order list. Node 3 never registers node 7 for discovery anywhere in this native capture.

## Batched continuation

The next isolated case is `M_discovery_membership`. It retains all prior corrections and all 61 established component checks, then runs the new worklist component checks and one common-input network continuation through the first guarded divergence or 330 seconds. The accepted natural run is reused only after its exact gates pass. Historical L and earlier cases remain evidence and are not rerun.

Five added public NWK component checks exercise the baseline extra-handoff reproducer; suppression of late-route-only discovery work while retaining the route; ordinary transit DATA admission through that route; legitimate DONE membership expansion; and route-based membership at a later local discovery completion. These checks use callbacks and short component timers, with no MAC/PHY network execution or random draws. They do not assert native equivalence for unrelated unsolicited-DONE interruption rules.

Download `autonomous-discovery-membership-tests.zip`, extract it into a fresh folder, restart MATLAB and set Current Folder to `autocase`. Run:

```matlab
report = run_autonomous_tests;
```

Return the generated `out_auto_*.zip`, including any diagnostic stop. No owner-side ns-3 command is needed.

## Acceptance boundary

The new M case and its new component checks still require MATLAB execution. Static source review and parsing do not establish runtime success. This review used existing native evidence and pinned source; no new long native simulation was commissioned.

The sealed kit binds 424 files. All 151 MATLAB files pass static syntax parsing with MISS_HIT 0.9.44 using its MATLAB 2022a grammar. Review verifies 26 exactly reversible transformations, 99 unchanged original model files, 50 unchanged prior candidate/helper MATLAB files and unchanged native references. Its `FILES.json` SHA-256 is `dbe65dd9feb20d7d1d6aae90caa07e9490a1c46188c71cd38469d93b2d455b88`.

Application offers begin at 300 seconds. This return therefore cannot establish the original 6,000-second attempted/admitted/delivered/dropped/unresolved accounting or latency for comparable delivered populations. The ±15% target still requires those full-network results, with source mix and unfinished traffic accounted for.
