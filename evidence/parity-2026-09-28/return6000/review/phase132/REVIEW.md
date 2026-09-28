# Corrected MATLAB seed 132: causal phases and backlog locations

All 11,887 delivered applications have complete reconstructed paths: 16,302 causal hops, zero failed decompositions, and exact closure after converting all path boundaries to integer nanoseconds. The complete protocol trace has 615,508 records and no omitted records. Delivered paths include each node's NWK admission waiting plus HOP admission to the next causal receipt; upstream ACK/DACK custody after receipt is excluded from delivered latency.

The reconstruction uses the archived validated parser unchanged through its per-case results. `analyze_current.py` changes only the input archive/case selection and omits the original five-case final source-binding report. Current return SHA-256: `a3f7fd6fc09a5b0505c6a759a5c025390151bef484e7e15c9818e51a3f4f1484`.

| Source | MATLAB current delivered | Mean latency: current / old MATLAB / ns-3 (s) | Current NWK / post-HOP (s) | ns-3 NWK / post-HOP (s) |
|---|---:|---:|---:|---:|
| 2 | 294 | 521.68 / 894.34 / 454.69 | 488.69 / 32.99 | 423.25 / 31.43 |
| 3 | 8,504 | 10.29 / 10.40 / 10.37 | 0.03 / 10.26 | 0.09 / 10.28 |
| 4 | 490 | 230.17 / 247.94 / 274.22 | 198.21 / 31.96 | 246.72 / 27.50 |
| 5 | 1,721 | 51.40 / 43.35 / 63.54 | 24.61 / 26.79 | 39.56 / 23.97 |
| 7 | 703 | 1,401.94 / 1,636.61 / 857.84 | 1,365.79 / 36.14 | 825.00 / 32.84 |
| 8 | 175 | 1,036.37 / 1,451.66 / 671.71 | 1,003.40 / 32.97 | 637.89 / 33.82 |

Source 7's 544.10-second current excess over ns-3 comprises 540.79 seconds of NWK waiting and 3.30 seconds after HOP admission. Source 8's 364.67-second excess comprises 365.52 seconds of NWK waiting, partly offset by 0.85 seconds less post-admission service. The large residual is still queue admission waiting.

The queueing location has changed substantially since the original MATLAB run:

| Source | Queue node | Old MATLAB mean NWK wait (s) | Current MATLAB (s) | ns-3 (s) |
|---|---:|---:|---:|---:|
| 7 | 8 | 160.36 | 600.19 | 248.69 |
| 7 | 2 | 1,119.14 | 470.71 | 196.18 |
| 8 | 8 | 126.35 | 320.07 | 184.24 |
| 8 | 2 | 1,038.45 | 413.48 | 187.54 |

Waiting at node 2 decreased, while more backlog accumulated at node 8. For source 7, the post-admission service on 8→2 is 1.508 seconds MATLAB versus 1.493 seconds ns-3; on 2→4 it is 2.082 versus 2.191 seconds. These successful-hop intervals do not explain the hundreds of extra seconds.

## Finite-stop state and capacity accounting

`queue_capacity_audit.py` independently reconstructs NWK custody, submitted/waiting states, per-neighbor HOP windows, retries, ACK growth, failures, and DACK holds from all positive-byte DATA events. Every NWK enqueue depth, final NWK/HOP node counter, peak ownership count, and HOP capacity admission condition closes. Every expired DACK hold matches the configured 20/40-second duration plus one tick. All 372 pending applications map to exactly one current NWK custody owner. This is a state-accounting check using the supplied implementation semantics; it is not proof that every cross-engine rule is correct.

At stop, node 8 has **201 applications still waiting for HOP admission: 185 from source 7 and 16 from source 8**, plus one submitted source-7 custody owner. Node 2 has 32 waiting and two submitted owners. No node reports a route-blocked pending application. Node 8's average waiting population during 300–6000 seconds is 151.72 applications.

The recovered ns-3 capacity ledgers provide an existing-evidence comparison:

| Link | Current MATLAB / ns-3 DATA admissions | ACKs | DACKs | Mean effective window slots | Mean DACK-held slots |
|---|---:|---:|---:|---:|---:|
| 8→2 | 1,149 / 1,271 | 139 / 300 | 993 / 945 | 4.006 / 3.894 | 3.607 / 3.449 |
| 2→4 | 1,500 / 1,760 | 368 / 370 | 1,094 / 1,360 | 4.830 / 5.918 | 4.092 / 5.070 |

The effective window is the threshold plus one, consistent with the inclusive admission rule. These links operate at their available capacity almost continuously in both histories. DACK capacity retained after successful receipt consumes slots and delays later applications; it is deliberately not added again to the delivered packet's completed hop.

All time averages in `queue_capacity_by_node.csv` and `link_capacity_comparison.csv` integrate piecewise-constant state over **[300,6000] seconds**, then divide by 5,700 seconds. Waiting/custody counts are measured in applications; HOP outstanding, window, and DACK-held counts are measured in slots. Percentages divide qualifying seconds by 5,700 and multiply by 100. The capacity gate is closed when outstanding DATA exceeds the per-neighbor threshold or global pending DATA exceeds 16; the threshold itself is not a slot count until one is added. These tests do not independently reproduce MAC/route eligibility. `waiting_while_gate_open_s` is total elapsed time in seconds, not a percentage. Node 8 accumulates only 0.00002870 seconds of waiting while that capacity gate is open, consistent with tick-spaced wakeups rather than a seconds-long eligible-but-unserved stall.

The path table's `mean_queue_at_arrival` uses the emitted full NWK custody-owner count at enqueue, including already-submitted owners. It must not be equated with the time-averaged NWK waiting population above.

The input mix at node 8 differs materially. Current MATLAB queues 1,111 source-7 arrivals versus 795 ns-3, and generates 239 local source-8 applications versus 512 ns-3. It forwards 926 source-7 applications versus 775 ns-3, and 223 local source-8 applications versus 496 ns-3. Thus node 8 ends with 201 waiting applications versus 36 reconstructed from the ns-3 enqueue/forward ledger. A shared nominal traffic schedule does not imply equal admitted populations or equal contention.

## Interpretation

The corrected model improves the historical source-2/7/8 delivered-latency means, but their populations also change, so these differences are not an isolated causal estimate of the grouped-routing fix. Sources 7 and 8 remain outside the 15% latency target; source 8 also has a large delivery deficit.

The specific residual to investigate is the coupled **8→2→4 capacity and traffic-allocation history**, including why source 7 supplies substantially more traffic to node 8 while source 8's own admitted population falls. Existing data already identify the queues and capacity histories; another full simulation is not needed to establish this location. A production fix requires a same-state, same-input behavioral mismatch. This audit demonstrates neither a missing ns-3 mechanism nor a new MATLAB rule violation.

An additional offline comparison already checks the narrow capacity-rule hypothesis. `check_native_capacity_rules.py` translates the current MATLAB HOP capacity arithmetic and supplies the archived ordered ns-3 admission/completion/expiry inputs. All **8,353 events** across 8→2 and 2→4 reproduce **41,765 before/after scalar state fields**, with zero differences. All 2,291 ns-3 DACK-expiry events match the assigned 20/40-second hold plus 28 ns. This addresses outstanding counts, ACK window growth, failure window reduction, DACK retention, and expiry release under the same completion inputs. It is not execution of the production MATLAB callbacks and does not validate ACK bitmap decoding or the receiver's choice of ACK versus DACK.

The smallest remaining executable common-input check would feed the original node-8 HOP implementation the observed DATA admissions and feedback history, comparing its capacity releases and next eligible admissions. The recovered `s132-capacity-events.csv` is enough for the state-transition check just completed; it lacks full ACK bitmap envelopes, receiver NSDP snapshots, and all wake/retry scheduling inputs needed for a faithful production callback replay. First check whether the previously captured short receiver/ACK traces contain the required node-8/node-2 fields. If they do not, a focused **ns-3-only trace capture** of the relevant interval is needed to construct that richer replay. Neither a new full ns-3 6,000-second reference nor another MATLAB 6,000-second run is needed merely to fill that narrow evidence gap. The state-rule result weakens the hypothesis of a missing capacity rule; the next replay should investigate how different feedback and competing traffic arise, not retest arithmetic that already agrees.

Scope limits: delivered-path means condition on delivery by 6000 seconds; dropped/pending applications are retained separately in the companion accounting analysis. Equal seed values do not imply shared RNG streams or matched application identities. The original ns-3 trace does not provide complete per-application first-TX/retry subphases, so only NWK waiting and combined post-admission service are compared across engines. No simulation or production source edit was performed for this review.

Main machine-readable outputs: `source_phase_comparison.csv`, `source_node_phase_comparison.csv`, `queue_capacity_by_node.csv`, `pending_copy_locations.csv`, `link_capacity_comparison.csv`, `link_source_traffic_comparison.csv`, and both validation JSON files. `packets-132.csv` and `causal-hops-132.csv` retain all reconstructed current paths.
