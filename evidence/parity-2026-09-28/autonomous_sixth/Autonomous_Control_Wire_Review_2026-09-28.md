# Seed-132 compact control wire-size review

The returned G/H batch validates both preceding corrections. G publishes the correct MAC population and then exposes the predicted extra routing DELETE. H removes that extra control and advances from 14.534 to **25.298 seconds**, consuming **276 matching random inputs** and passing **47 physical-transmission context checks**. The next stop is a specific routing-request wire-size discrepancy. The full-network acceptance target remains **±15%**.

## Actual MATLAB return

Input: `out_auto_20260928_071516.zip`, SHA-256 `e6a37b87c56f4be8273175b07f7347bc7a0a9eae0e8c0add7d91b0ad3fb47446`, 50 members. All 247 issued files match the returned source manifest. MATLAB R2025a 25.1.0.2943329, PCWIN64 passed import and all 29 component checks: seven KEY_REQUEST, eight neighbor-control, six population-publication and eight route-admission checks. The accepted natural A capture was reused after its existing source, runtime, configuration and exact trace gates passed.

| Actual result | G: population publication | H: G plus route admission |
|---|---:|---:|
| Stop time | 14.534 s | 25.298 s |
| Matching consumed random inputs | 97 | 276 |
| Matching physical transmissions | 16 | 47 |
| Additional rejected transmission | 1 | 1 |
| Previous population guard | Cleared | Cleared |
| Extra grouped DELETE at 14.534 s | Present, as predicted | Removed |
| Application attempts | 0 | 0 |

G correctly consumes gateway MAC draw 8 with population two and value 13. Its following transmission still contains eight children and 241 bytes versus native's seven children and 215 bytes: the previously identified 26-byte extra routing DELETE. H reproduces that seven-child, 215-byte transmission and continues. This confirms the two corrections address separate behaviors.

H's successful random requests comprise 57 MAC, 125 SYNC and 94 PHY samples. All 276 are matched and consumed; the stop rejects a subsequent transmission, not a random draw. Independent comparison confirms the merged request/transmission sequence and rounded-nanosecond timestamps match the existing native capture through the rejected transmission. Profile-4-irrelevant reported-population differences remain logged; they are outside the active population guard. This evidence establishes the checked observable prefix, not equality of every internal state or wrapper field.

## First remaining mismatch

At 25.298 s, gateway transmission 18 contains two routing requests and one SNMP_START in both engines. Destinations, HOP sequences, ordering, decoded routing sections and checked control semantics match.

| Child | Destination / HOP sequence | MATLAB bytes | Native bytes |
|---|---|---:|---:|
| Routing REQUEST, routing sequence 6 | 3 / 7 | 23 | 16 |
| Routing REQUEST, routing sequence 7 | 5 / 9 | 23 | 16 |
| SNMP_START | 3 / 0 | 31 | 31 |
| Aggregate | Three children | **77** | **63** |

The routing sections used for semantic comparison are `00000006000103` and `00000007000103`. Each is a six-byte ARL section prefix followed by the one-byte REQUEST record. Those seven bytes are a normalized comparison representation for these native requests; they are not additional native modeled on-air bytes.

Native `BuildRoutingRequestPayload` places REQUEST information in its compatibility header and adds no raw ARL section. Native envelope accounting removes that compatibility header, then charges the 11-byte Routes envelope plus five-byte Group16 security record: **16 bytes**. The comparison normalizer synthesizes the equivalent seven-byte section so routing semantics can still be checked. Its recorded wire-size field independently retains native's value of 16.

MATLAB generates the equivalent REQUEST through its ordinary ARL routing-message path and charges `11 + 5 + numel(Bytes)`: **23 bytes**. Frames and aggregation propagate that size into MAC/PHY service. This is a modeled transmission-size mismatch, not a corrupt fixture or a reason to weaken the packet guard.

The original native capture records a 63-byte aggregate and 87.72 ms duration. With the same rate and physical settings, 77 bytes would produce 102 ms: **14.28 ms additional airtime**. That is a formula-based counterfactual. The returned MATLAB guard stops before transmitting the mismatched frame, so the 14.28 ms is not measured latency or an executed receiver-availability difference.

## Audit of other packet types

A separate audit covers all 1,495 child transmissions in the existing 811-transmission native capture. The 17 compact REQUEST appearances, spread across nine transmissions and all seven nodes from 25.298 through 117.546 seconds, are the only captured disagreement with the current control-size formulas. The other 1,478 child sizes agree, including all 98 routing children with actual serialized ARL sections. This is a size-formula audit of native evidence, not execution of the candidate through those later times.

The source audit also confirms a separate NoPath mismatch outside this captured population. Native puts the neighbor-check target in compatibility metadata and models the check as 16 bytes. MATLAB adds three bytes for that target and charges 19. No NoPath transmission occurs in the existing 0–330-second capture. The next package therefore includes this correction and a separate public component check; its network effect cannot be validated by this capture.

A compatibility-header DELETE can likewise cost 16 bytes, but actual serialized DELETE sections still cost 26. No compact DELETE occurs in this capture, and no additional DELETE correction is justified here. The candidate does not infer wire format from the decoded routing opcode alone.

Twelve native packet/model API cases passed. They reconstruct the three stopped-transmission children from their captured packet bytes, independently recover the 16 + 16 + 31 = 63-byte aggregate, and distinguish compact metadata from actual raw request, compound, DELETE and NoPath bodies. Packet copies retain their modeled sizes. These are bounded native component executions with no simulator scheduling, device, channel or network run; they do not constitute a new performance result.

## Focused correction

Candidate I retains H's behavior and distinguishes the compact native REQUEST representation from a raw ARL routing section. Provenance starts at the actual request-generation path and follows the queued message, materialized payload and retry owner. Only a tagged, structurally valid single-section REQUEST receives the 16-byte compact size. The same isolated helper corrects metadata-only NoPath accounting from 19 to 16 bytes, preserving its target and delivery semantics. An ordinary untagged ARL REQUEST remains 23 bytes; unrelated or mixed routing records retain their raw-section accounting.

The provenance must survive initial queueing, pending-control recalculation and residual retries. All three NWK sizing sites use the isolated helper. A single new network case tests the combined size correction; independent component cases distinguish the two changes without duplicating a replay that contains no NoPath traffic. The semantic section bytes remain available to the existing strict transmission checker and routing receiver; no random input, reception, ACK or admission is forced.

## Run the next batch

Download `autonomous-control-wire-tests.zip`, extract into a fresh folder, restart MATLAB and set Current Folder to `autocase`. Run:

```matlab
report = run_autonomous_tests;
```

Return the generated `out_auto_*.zip`, including any diagnostic stop. The new candidate starts all seven nodes at zero and runs until its first semantic divergence or 330 seconds. The accepted natural result is reused when its existing gates pass. Actual G/H results are retained as history and are not rerun. No owner-side ns-3 command or new 6,000-second simulation is requested.

## Interpretation and remaining acceptance

All 133 MATLAB files in the final candidate pass static syntax parsing with MISS_HIT 0.9.44 using its MATLAB 2022a grammar. Independent review verifies 16 exactly reversible source transformations and the original 99 model files. Six new REQUEST component checks cover provenance, invalid tags, public request generation, failed admission, residual retry and scheduled renewal; three NoPath checks cover its size, public DATA-rejection sender and unchanged sibling controls. These nine MATLAB checks and the new I network case remain pending owner execution. Static parsing and source review are not MATLAB runtime results.

The matched transmission prefix has increased from 16 to 47, and the two preceding mismatches now have actual MATLAB validation. This is measurable progress in startup control behavior. Application traffic begins at 300 seconds, so the return still cannot establish delivered counts, unfinished traffic, source mix or latency against the original 6,000-second discrepancy.

The ±15% criterion remains a full-network accounting and comparable-population latency target. Startup replay is identifying specific mechanisms that can change autonomous traffic and receiver availability; passing one prefix is not a substitute for that acceptance test. The original 99 model files and all native fixtures remain unchanged in the diagnostic kit. New candidate runtime results remain pending owner MATLAB execution.
