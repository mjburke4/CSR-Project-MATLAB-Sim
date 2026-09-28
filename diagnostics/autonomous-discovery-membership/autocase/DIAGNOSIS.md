# Discovery membership review of the tenth owner return

The actual L return passed all 61 component checks and reused accepted natural A through its unchanged gates. Its first 2,729 random requests and 487 physical transmission signatures match the native fixture in merged order and recorded nanosecond timing, ending at 112.775012442 seconds. The previous KEY_UPDATE delay and active-requester destination mismatch are cleared in this returned prefix.

The new divergence begins when node 3's discovery watchdog expires at 116.340299163. MATLAB creates an extra SNMP_START for final node 7 through HOP peer 5. Its MAC preparation then uses two samples whose native requests occur at application startup, and the strict transmission guard stops the 31-byte control at 116.415. Native's next transmission from node 3 is DATA to node 1 at 300.365; other native nodes continue to run in the intervening period. This is an extra control, not a representation-only identifier difference.

## Correct watchdog, incorrect population refresh

Node 3 receives its initial START from node 1 at 25.385728077. Local discovery completes at 40.385728077, reports known nodes 5 and 1, and hands discovery to node 5. At 56.340299163 it receives node 5's DONE containing nodes 4, 3 and 1, then starts final node 4 through peer 5. This arms the 60-second watchdog that later expires at 116.340299163. The superseded timer at 100.385728077 is a no-op in MATLAB; the active timer's expiry itself matches native behavior.

Between those membership-defining events and the watchdog, routing learns additional destinations. Node 3 receives UPDATE for node 2 at 65.832808077, for node 8 at 78.858819163, and for node 7 through peer 5 at 96.268879163. The node 7 advertised path is `[4,2,8,7]`; an alternate UPDATE arrives through peer 1 at 96.388928077. These are legitimate routing facts and should remain available to application forwarding.

Native discovery advancement scans its existing discovery table. Entries 1, 5 and 4 have already been marked complete, so the watchdog emits no new START. Native does not refresh that table from current routes while advancing it. MATLAB's `advanceScan` calls `mergeScanKnown(Routes.reachableDestinations())` on every advance, including a watchdog expiry. That imports the late routes, with node 7 first in the current destination order, and manufactures new discovery work.

## Smallest correction

`DiscoveryMembershipNwk` is an exact copy of L's NWK class except its class identity and removal of that one executable population-refresh line. `DiscoveryMembershipSimulation` only changes its class identity and NWK binding. The change applies consistently to advancement invoked by watchdogs, received DONE, local completion and neighbor activation; it does not change those callers or their gates.

The explicit population boundaries remain intact: local discovery completion merges its bounded known-node snapshot, and a received DONE merges its advertised nodes. Idle START still marks its initiating requester complete. Native's ten-node limit applies to each completion report, not to the total discovery table; removing the eager refresh also avoids bypassing that existing snapshot limit. No global table cap is added.

All routing knowledge and forwarding logic remain unchanged. The public component tests must establish that a late route can still carry transit DATA while remaining absent from discovery work until a legitimate population event. Watchdog scheduling, cancellation/generation checks, unrelated DONE-source gates, requester capacity, L's key-update admission correction, K's receiver timers, random inputs and comparison guards are unchanged. All 99 original model files remain byte-identical.

## Validation boundary

The next kit retains all 61 existing component checks and adds five public membership checks: the original extra-control reproduction, corrected watchdog behavior with the route preserved, actual transit DATA submission through that route, legitimate DONE-based insertion, and population at a subsequent local discovery completion. These use public controls and callbacks without a forced network state or native random tape.

Only one new `M_discovery_membership` network case runs from zero. L remains actual historical evidence and is not rerun. Accepted A reuse still requires its exact source, runtime, configuration, returned-file hashes and three CSV-prefix checks. No MATLAB runtime is available here, so the new checks and M remain pending owner execution.

This diagnosis explains an extra control transmission that can alter contention and receiver availability. Its removal has not yet been measured in a corrected network run, and no ±15% full-network accounting or latency parity is claimed.
