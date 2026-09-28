# G population preflight static review

No static blocker found. Six bounded checks are ready for owner MATLAB execution; none has been executed in MATLAB here. The helper uses the actual `PopulationSimulation` public NWK/HOP/MAC handles and a passive trace sink. It does not call the simulation run method, change the model, assign a MAC population, or override network reception. Exact ACKs are explicit component completion inputs, not claimed RF deliveries.

| Check | Boundary covered |
|---|---|
| Qualifying DISCOVER | Committed direct-peer count publishes before inline KEY_REQUEST reaches actual MAC enqueue. |
| ACKed proof | Actual HOP reliable-owner completion changes raw NWK count to 3 while MAC remains at 2. |
| Nonqualifying inputs and enqueue | Passive radio, key and DATA handling plus actual feedback and outgoing ROUTING enqueue leave the latch unchanged. |
| Next qualifying observation | DISCOVER, NeighborCheck and valid ROUTING each publish the current persistent count. |
| Freshness | A separate public Neighbors timer marks a peer stale without removing its last-heard count or publishing; re-observation republishes the same count. |
| Admission disabled | The early observation branch publishes before NeighborChanged and the later response. |

The exact-ACK helper uses each captured real outgoing control's source, destination and sequence with `HasAckWindow=false`. HOP resolves its own reliable control owner and invokes the normal NWK completion callback; it does not require a preceding physical send for this public component test. MAC start schedules its wake at 0.988 s and idle RTS at 0.013 s; ACK completion schedules the HOP wake strictly later by one TIC (approximately 27.78 ns). Therefore the two `Scheduler.run(0)` calls drain same-time NWK work without reaching a MAC draw or PHY transmission. The helper separately asserts clock zero, zero requested random variates and zero physical transmissions at runtime.

The actual accepted configuration has node 1 transit forwarding enabled and MAC population 1 initially. The DATA microcase comes from newly activated peer 3 toward still-unrouted destination 8, so the public NWK path returns `no_route`; passive radio observation of 8 only updates metrics. The test deliberately uses this rejection to avoid unrelated synthetic application delivery accounting.

All three G classes reproduce their declared source edits exactly and reverse to the source bytes. Qualifying publication occurs after the peer-map commit in both observation branches. ACK completion retains its direct last-heard update without publication. The Simulation removes both eager refresh callsites, retains the historical-generator guard, and passes the existing NWK count through the actual MAC setter. The unused old refresh helper has no callers. This review does not claim complete autonomous parity or acceptance of a production fix.

`population_preflight_review.json` binds the reviewed helpers, source classes and reference configuration by SHA-256. Root performs the final parser and package-integrity checks separately.
