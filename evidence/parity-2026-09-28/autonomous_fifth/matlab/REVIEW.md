# MAC population publication diagnosis

Both actual owner E/F runs passed all eight new neighbor-condition checks and stopped at 14.534 seconds, node 1 MAC draw 8. Each logged 97 requests, consumed 96 native draws and checked 16 physical transmissions. Neither recorded a rounded-nanosecond request-time difference before this stop. Only local MAC population differs: MATLAB 3, native 2; profile, reported population, reservation state and inclusive bounds 0..31 match.

## Cause and boundary

At 14.400468077 seconds, node 1 receives ACKs from peer 3. An ACK completes its reliable Overheard proof. Both engines refresh peer 3's NWK last-heard marker and admit that peer, so the current NWK count correctly becomes 3 (self plus peers 3 and 5). Native does not publish this new count to MAC at an ACK completion. Its MAC population remains latched at 2. MATLAB's bridge republishes after every addressed received member and before every MAC enqueue, installing 3 immediately.

Native publishes only at explicit boundaries: qualifying ProcessHello, authenticated Discover that needs a group key, and public local ClearRoutes. The portable equivalents for the first two pass through Neighbors.observe, which commits the direct last-heard marker before admission responses. Routing sections reach that same observation through Layer.observe. ACK completion writes the marker separately and must not publish. Passive radio observations, key traffic and ordinary enqueue must not publish either.

The bounded design adds an optional callback immediately after observe writes Peers, including the admission-disabled early branch before its changed callback; NWK publishes its unchanged applicationState.ActiveNodeCount through the simulation's historical-mode guard. Both eager bridge refresh calls are removed in the isolated candidate. The current application count stays 3 independently of the MAC latch of 2.

Current portable Layer exposes no local ClearRoutes operation; remote routing FLUSH is a different operation. Native capture contains no ClearRoutes reset in 0–330 seconds. No speculative local-reset behavior is introduced. Malformed NoPath with broadcast/no destination still qualifies as a heard neighbor in both engines; its semantic no-op does not suppress observation. Invalid MATLAB-only numeric payload forms rejected before receive are outside the valid wire-input comparison.

## Consequence and limits

The current draw's support is identical because both populations 2 and 3 map to slot range31. A matching supplied integer and reservation list would therefore choose the same slot at this point. Population still has behavioral meaning: configured post-TX wait is 15 + 1.5×population + 0.5 seconds. Native next records an 18.5-second wait at 16.71576; the prematurely published MATLAB population implies 20 seconds, a 1.5-second counterfactual difference. This is not an observed long-run latency result. Native only publishes MAC population3 at 18.724108077 upon a qualifying peer3 check.

Native routing payload at 14.534 already advertises the current NWK count3 while its MAC draw uses latch2. These values must remain distinct. Existing transmission guards do not check that entire native control-header population field; opaque control metadata has incomplete portable representation. This change does not claim full header population parity or alter that coverage.

The same returned chronology also exposes an extra grouped routing control at 14.400468077, beyond the expected unicast snapshot. That independent route-candidate investigation is being reviewed before the next combined kit; weakening the population guard would merely conceal the current mismatch and reveal the next one later.

## Evidence

`audit_population.py` reads both returned ordered histories, strict mismatch and random summaries; writes `population_summary.json` and `population_chronology.csv`; and binds the exact input history hashes. No model or kit source was changed during this diagnosis, and no new MATLAB run was performed here. New candidate execution remains pending owner validation; the 15% full-network target is not established.

H targets the fresh, previously unobserved admission in this capture. Native stale-neighbor success can separately reactivate an existing direct route before admission; that separate recovery path is not established by this admission-only change.
