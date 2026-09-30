# Seed 132: local population publication at 14.400468077 s

The native/MATLAB discrepancy is **when NWK publishes its local population to MAC**, rather than which peers belong to the population. Keep the strict context guard. Both E and F match 96 random requests and 16 transmitted packet signatures, then stop on node 1 MAC draw 8 at 14.534 s: MATLAB local count 3, native published local count 2. The draw's integer bounds remain 0–31 in both implementations.

Native `GetActiveNodeCount` counts one local node plus every persistent NWK neighbor with `lastHeardSec >= 0`. It does not filter by ARL admission or stale status, and does not count route-only placeholders. The marker survives route clearing. Passive HOP observations and KEY_REQUEST/KEY_UPDATE traffic do not by themselves give an existing NWK entry that marker. A successful reliable NeighborCheck ACK can refresh it.

| Boundary | Native current NWK population | Native MAC population | MATLAB MAC population |
|---|---:|---:|---:|
| Last node-5 HELLO before the mismatch, 13.266211086 s | 2 | 2 | 2 |
| Node-3 ACK completes node-1 Overheard proof, 14.400468077 s | 3 | 2 | 3 |
| MAC slot request, 14.534 s | 3 | 2 | 3, then guard stops |
| Native first received node-3 Discovery proof, 18.724108077 s | 3 | 3 | Unexecuted continuation |

The count of three at the ACK boundary follows the native assignment in `NoteNeighborCheckSuccess`: node 3's `lastHeardSec` becomes current, its stale flag clears, and two-sided keys allow ARL activation. That callback does not call `UpdateMacActiveNodes`. This separation is directly confirmed by two observations at the failed request's time: native MAC draw 8 records local count **2**, while the native node-1 routing section transmitted immediately afterwards contains `routing_active_nodes=3`. The model needs both values; reducing its current NWK count to two would be incorrect.

Native publishes through three explicit call sites: `ProcessHello` after its link-neighbor update, `NoteAuthenticatedGroupKeyNeeded` after its qualifying direct-neighbor update, and `ClearRoutes`. The full accepted 0–330-second native log contains no `ClearRoutes` execution. Its first MAC publication of three is at 18.724108077 s, when node 3's Discovery NeighborCheck finally reaches the HELLO path. Route clearing and stale/inactive transitions retain the historical count rather than shrinking it.

MATLAB currently calls `refreshHistoricalPopulation` both before every MAC enqueue and after every addressed HOP member. On this ACK-only incoming aggregate, `Neighbors.controlCompleted` refreshes node 3's last-heard marker; the unconditional bridge immediately copies the new count into MAC. In both returned ordered logs, the first node-1 MAC boundary showing three is `receiverChanged_before` at 14.400468077 s, immediately after `neighbor_active` / `hop_control_ack`. Subsequent routing enqueue also invokes the eager publisher.

An isolated correction should publish after the corresponding qualifying NWK observation and preserve the independent current-population getter for application and routing payloads. ACK completion and generic enqueue must not trigger publication merely because the getter changed. A publisher at the observation boundary must run before admission callbacks can enqueue controls. Do not infer a local `ClearRoutes` equivalent from a received routing FLUSH; these are different operations.

The guard catches a real receiver-state input difference even though this immediate integer draw uses the same range. With the recorded profile, populations two and three both map to range 31. Population also determines preamble freshness and post-transmission waiting: `15 + 1.5*n + 0.5` gives 18.5 versus 20 seconds. The existing native capture next starts an 18.5-second post-TX wait at 16.71576 s, before the population is republished. A premature value of three would change that timer's formula by 1.5 seconds. This is a sensitivity calculation, not an executed MATLAB continuation or a measured delivery/latency effect; intervening events can cancel timers.

The same returned logs expose a second traffic discrepancy for parallel investigation: at 14.400468077 s MATLAB enqueues routing HOP sequence 4 to node 3 and sequence 5 to `[3,5]`; native logs enqueue only the node-3 snapshot sequence 4. This was sent to the MATLAB/parent investigators without changing any guard or injecting a divergent transmission.

## Bounded native component confirmation

After the evidence-only review, three public-API native component cases were compiled and executed. They use an unattached MAC, actual authenticated HOP KeyUpdate and ACK processing, public NWK HELLO/snapshot APIs, a selected-route getter, and the existing grouped-routing observer. There is no device, channel or PHY. The scheduler drains only same-time NWK work, with a one-nanosecond stop per drain and at most four nanoseconds elapsed per case. No network replay or private-state override is involved.

| Component condition at proof ACK | Current NWK / MAC population | Selectable direct route after ACK | Grouped changed-route operation |
|---|---|---|---|
| No direct candidate | 3 / 2 | No | None |
| Previously observed capability-zero candidate | 3 / 3 | Yes | DELETE |
| Previously observed candidate with capability one learned by self-UPDATE | 3 / 3 | Yes | UPDATE |

All cases passed. In the absent-candidate case, a subsequent qualifying HELLO publishes three, creates the direct route, and emits the genuine capability-zero DELETE change. This independently confirms both the publication boundary and the traffic agent's route-creation diagnosis: native admission alone does not synthesize a missing direct candidate, while existing observed candidates must still trigger real selection changes. The automatic full snapshot and grouped changed-route notification remain distinct operations.

Candidate-field preservation is a contract of `TryMakeNeighborActive`, not a blanket claim about every NeighborCheck completion. The broader native `NoteNeighborCheckSuccess` first revalidates existing direct candidates if the peer was stale and recomputes valid routes through that peer. The observed 14.400468077-second case is fresh (`stale=0`) with no candidate. Stale recovery and independent link-price changes remain outside these component assertions.

## Final G/H source review

All 14 candidate transformations and declared SHA-256 hashes passed independent forward/reverse verification; all 99 baseline model files remain identical to the previous kit. Separately removing the new admission method and normalizing the candidate class namespace recovers the original Routes file byte for byte. The admission method retains logical destination insertion, allocates no route candidate, changes no validity/price/time/capability fields, and releases only valid deferred candidates for the admitted destination with a usable next hop. The actual observation path still invokes the original `setNeighbor` implementation.

The population callback runs immediately after the qualifying observation commits its state and before admission callbacks. Neither generic enqueue nor addressed-member receipt invokes the eager refresh. The current-population application getter remains byte-identical, preserving current NWK population separately from the published MAC value. The runner keeps the accepted natural gate and executes H independently after a diagnostic stop in G. `candidate_scope_review.json` records exact reviewed source/runner hashes and limits; `review_candidates.py` reproduces the checks. Owner MATLAB execution remains required.

`analyze_population.py` regenerates the excerpts, structured summary and `population_receipt.json`. `native_tx_population_proof.json` preserves the native routing child with population three; `native_population_excerpt.txt` records native publication/ACK/timer provenance. Returned causal JSONL excerpts retain original observation order. `source_excerpts.txt` includes source line numbers and hashes. `population_route_probe.cc`, its `.log`, compile recipe and `run_component_probe.py` reproduce the bounded native tests. No full network simulation was rerun, and no production source or native fixture was edited.
