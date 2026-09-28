# Seed-132 population publication and route admission review

Both returned neighbor-control cases reproduce the missing four-child, 82-byte transmission and continue to 14.534 seconds. They consume 96 matching native random inputs and pass 16 transmission-context checks. The next guarded mismatch is a gateway MAC population of three where native retains two. A parallel trace review identifies a separate extra routing DELETE queued before that stop.

Both issues concern when a state change should trigger work. ACK completion legitimately changes the current NWK neighbor state, but native neither publishes a new MAC population nor invents a direct route candidate at that boundary. The next two-case package tests population publication first, then adds the route-admission correction. The full-network target remains **±15%**.

## Actual owner results

Input: `out_auto_20260925_135836.zip`, SHA-256 `fe57cce08371cc469995afd5fbdd6a2aa52518aa3296057b7edd7f053324d6e6`, 47 members. The returned manifest matches all 198 issued files. MATLAB R2025a 25.1.0.2943329, PCWIN64 passed native import, all seven KEY_REQUEST checks and all eight neighbor-control checks. The accepted natural case was reused after its unchanged source, runtime, configuration and exact trace gates passed.

| Result | E: eligible overheard check | F: E + message-only flag |
|---|---:|---:|
| Previous 12.402-s transmission | Four children, 82 bytes; passes | Same |
| Consumed matching random inputs | 96 | 96 |
| Verified physical transmissions | 16 | 16 |
| Request order/time differences through the stop | None at recorded nanosecond precision | None |
| First rejected request | Gateway MAC draw 8, 14.534 s | Same |
| MAC population: actual / native | 3 / 2 | 3 / 2 |
| Application attempts | 0 | 0 |

There are 97 logged requests: 96 successful requests and the unconsumed rejected request. The successful draws comprise 20 MAC, 44 SYNC and 32 PHY samples. Native has a seventeenth transmission at the same timestamp, but it follows the rejected draw in event order. That transmission is unexecuted continuation, not an unexplained missing earlier packet.

The complete 13,386-row ordered event logs are byte-identical between E and F, as are their random-request, protocol and PHY traces. The additional message-only flag correction has no observed network effect in this prefix. Every received overheard control encounters a discovery proof already active or a peer already active, which independently suppresses a message response. The successful public component checks exercise the separate branch where F matters; this network return does not.

## Current NWK population and published MAC population are different states

Both engines count self plus persistent direct NWK peers with a qualifying last-heard marker. Admission and staleness do not remove a peer from that historical count. The counting formula agrees.

| Boundary | Native current NWK count | Native published MAC count | Returned MATLAB MAC count |
|---|---:|---:|---:|
| Last relevant node-5 HELLO, 13.266211086 s | 2 | 2 | 2 |
| Node-3 ACK completes gateway's overheard proof, 14.400468077 s | 3 | 2 | 3 |
| Gateway MAC draw, 14.534 s | 3 | 2 | 3; guard stops |
| Later native node-3 check, 18.724108077 s | 3 | 3 | Not executed |

Native refreshes the ACKed peer's last-heard marker and admits it, but does not publish a new MAC population in that callback. The native routing packet immediately after the rejected draw advertises the current NWK count of three while MAC still uses its last published count of two. Reducing the NWK count to two would therefore be incorrect.

MATLAB's simulation bridge instead refreshes the MAC count before every enqueue and after every addressed HOP member. Both paths publish the updated count too early. Native publishes at qualifying HELLO processing, authenticated-discovery key-needed processing, and local route clearing. The existing 0–330-second capture has no local route clearing, and the portable model has no matching local ClearRoutes API; a received routing FLUSH is not a substitute for it.

Candidate G removes the two eager bridge refresh calls and adds an explicit publication callback when a qualifying neighbor observation commits its last-heard marker, before admission callbacks can enqueue controls. This covers the portable DISCOVER/check and first accepted routing-section paths. ACK completion can still change the current NWK count without publishing it to MAC. The historical-generator condition remains, and the count formula is unchanged.

The immediate MAC draw has bounds 0–31 for either count. Nevertheless this state matters: the post-TX wait formula is `15 + 1.5 × count + 0.5`, giving **18.5 versus 20 seconds**. Native next starts an 18.5-second wait at 16.71576 s. A premature count of three would lengthen that calculation by 1.5 seconds. This is a source-grounded sensitivity calculation; the returned MATLAB run stops before that continuation, and intervening events may cancel a wait. It is not a measured latency improvement.

The portable transmission checker validates routing-section bytes, but does not establish equality of every native wrapper field, including the routing header's population metadata. The fix preserves the distinct current NWK getter and MAC latch; it does not claim full wrapper-byte parity.

## The extra routing message has a separate source

At 14.400468077 s, both engines arrange the intended routing snapshot to newly admitted node 3. MATLAB additionally creates a grouped DELETE for destination 3, addressed to nodes 3 and 5. The extra section bytes are `00000004000101000003`: routing sequence 4, section 0 of 1, DELETE destination 3. This is not a population INFO advertisement.

MATLAB's `neighborChanged` calls `Routes.setNeighbor`, a helper also used for qualifying link observation. That helper creates a missing direct candidate, marks it valid and updates its link fields. In this ACK-only admission, native has no direct candidate for node 3 yet. Native admission releases existing candidates for that destination and compares the selected state; it does not create or revalidate a candidate. The synthetic MATLAB candidate has capability zero, so its selected-state change produces the spurious DELETE.

Candidate H adds a separate admission operation that records the active peer and retains native destination-order insertion, but does not fabricate a candidate or modify its validity, cost or timestamp. It releases eligible existing candidates for the admitted destination and preserves selected-state change reporting. The existing HELLO/observed-link path retains direct-candidate creation. Both G and H retain the previously tested callback timing, inline KEY_REQUEST and neighbor-check corrections.

This isolates admission itself. Native proof completion also has a separate recovery path for an already stale peer, which can revalidate existing candidates before admission. The captured peer is not stale and has no direct candidate; H does not establish full parity of that separate stale-peer recovery path.

G alone may clear the population guard and expose the already queued routing difference at the next transmission. H tests both independently diagnosed corrections. Keeping both cases makes that distinction observable without another owner round trip.

Native public-API component probes passed the corresponding cases. With no observed direct candidate, a real key exchange and ACK of the overheard proof admit the peer and raise the current NWK count to three, while MAC stays at two and no grouped route change is generated. A later HELLO publishes three and creates the direct candidate. When a candidate already exists, admission preserves it and generates the appropriate DELETE or UPDATE according to capability. These probes use an unattached MAC and run only the same-time NWK callbacks through nanosecond-scale stops; they create no PHY/channel network and do not establish a new network performance result.

## Run the next batch

Download `autonomous-population-routing-tests.zip`, extract into a fresh folder, restart MATLAB and set Current Folder to `autocase`. Run:

```matlab
report = run_autonomous_tests;
```

Return the generated `out_auto_*.zip`, including any diagnostic stop. G and H run independently from zero until their first semantic divergence or 330 seconds. A stop in G does not suppress H. The accepted natural run is reused when its existing gates pass; E/F remain historical actual results and are not rerun. No new 6,000-second run or owner-side ns-3 command is needed.

The package retains strict random-context, bit-count, transmission and unused-input guards. The original 99 model files remain unchanged; candidate classes and 14 exactly reversible source transformations identify the experimental changes. Six new public-API checks target population publication and eight target route-admission boundaries. Their MATLAB runtime result and the G/H network outcomes remain pending.

## Limits and validation

The final kit binds 247 files. All 127 MATLAB files pass static syntax parsing with MISS_HIT 0.9.44 using its MATLAB 2022a grammar; their hashes are unchanged during parsing. Independent review verifies the publication callback order, route-admission scope, unchanged natural-run gates and exact source transformations. Static validation does not substitute for executing the new MATLAB cases.

The comparison has advanced through 16 matching transmissions, but its evidence also exposes an earlier queued-control difference. A matching draw/packet prefix must not be presented as equality of all internal state. The accepted natural run remains a provenance gate, not acceptance of the new candidates.

Application traffic begins at 300 seconds, so these 14.534-second captures cannot measure admission, delivery, unfinished traffic or latency against the original 6,000-second case. The **15% network target remains open**. Once the autonomous control paths align sufficiently, the source-by-source accounting and comparable delivered-population latency analysis remain the acceptance criteria.

The report and evidence archive preserve the actual owner return, exact kits, original native observations, reproducible audits, independent reviews and validation receipts. No long network simulation was commissioned for this review.
