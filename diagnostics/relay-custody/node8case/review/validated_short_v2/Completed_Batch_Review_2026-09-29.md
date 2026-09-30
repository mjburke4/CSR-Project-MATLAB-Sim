# Completed MATLAB/ns-3 common-input batch — 29 September 2026

Both bounded network cases completed on MATLAB R2025a: seed 132 through 400 seconds and seed 131 through 200 seconds. Independent raw-event reviews confirm the application-level comparisons and checked transmission/random/receiver histories. The retained-copy correction now reproduces ten native late first deliveries in the network. This clears the bounded checks for a new 6,000-second measurement; it does not yet establish full-run ±15% parity.

## Source identity and runtime validation

The returned archive `out_parity_batch_20260929_100458.zip` contains 180 intact members. Its embedded manifest matches all 466 bound files of the issued v2 kit, and all 162 resolved MATLAB source hashes agree. The run finished in 815 seconds, approximately 13.6 minutes.

- All 108 historical component checks and the native import passed.
- All three integrated accounting groups passed their 52 assertions.
- Both public receiver-order regression cases passed.
- The repaired result collector passed all 16 first/second-status combinations and preserved both completed network results.
- Both cases consumed every supplied random value and checked every transmission. No random-request context or time mismatch was recorded. Required protocol, PHY and admission traces have zero omitted records; neither case has trace rows exactly at its endpoint.

## Seed 132: 0–400 seconds

| Metric | ns-3 | MATLAB |
|---|---:|---:|
| Attempted applications | 30,000 | 30,000 |
| Admitted applications | 428 | 428 |
| Unique delivered applications | 208 | 208 |
| Admitted but undelivered | 220 | 220 |
| Delivered mean latency | 16.8089266424 s | 16.8089266424 s |
| First deliveries after HOP-owner expiry | 10 | 10 |
| Physical transmissions | 1,437 | 1,437 |
| Transmitted children | 2,201 | 2,201 |
| Random draws | 7,904 | 7,904 |

All 30,000 attempt/admission contexts agree. Delivered identities are paired by source and scheduled attempt; all 208 first-delivery times agree at integer nanoseconds. Independent checks also match 10,329 MAC states, 371 DATA HOP completions, and the merged random-draw/transmission order. Existing comparator exclusions remain unchanged and documented in the detailed audit.

The ten late deliveries reverse ten of the fifteen provisional application-drop events. MATLAB ends with five provisional drops and 215 raw pending applications, totaling 220 undelivered applications. These are not labeled proven terminal losses. The controlled relay case also confirms that late relay custody can reverse a provisional drop before final delivery, without allowing an older owner's failure to reclaim custody.

Latency-phase review finds matching application paths and all 586 NWK custody enqueue boundaries. Mean delivered NWK waiting is about 7.758196 seconds, followed by about 9.050731 seconds of MAC/HOP service in both implementations. A small internal timing distinction remains: 104 of 402 HOP admission timestamps occur 28 ns earlier in MATLAB, while 298 are identical. This shifts the reported phase boundary by nanoseconds; application delivery times, total latency, first physical transmissions, and the checked random-request times still match. The report therefore does not claim that every internal timestamp is identical.

At cutoff, the last recorded custody stage places 184 of the 220 undelivered applications in NWK waiting, 26 before their first physical transmission at that stage, and 10 after a first transmission. This is a queue-stage description, not a complete inventory of every surviving duplicate copy.

## Seed 131: 0–200 seconds

The MATLAB network reproduces the native discovery stall under common random inputs. It consumes all 1,255 draws and checks all 209 transmissions and 490 children. No application traffic is expected because the original sources start at 300 seconds.

Node 5 finishes its discovery at approximately 40.307731 seconds, before node 4's late route becomes usable at approximately 73.674 seconds. The completed discovery table does not expand through the intended 5→4→2 path. Nodes 2, 7 and 8 remain outside the discovered connected population in this window. This behavior is now reproducible in MATLAB with native random inputs; this capture provides no basis for another discovery-code change.

The earlier red-team finding about unrelated/repeated DONE messages remains a separately identified edge case. Its trigger is absent from these captured cases; it is not attributed as the cause of this stall.

## Next measurement and the ±15% target

The next batch uses the exact validated candidate sources for two autonomous 6,000-second MATLAB runs, seeds 131 and 132, against the existing native references. It uses MATLAB's own natural random streams and generates discovery, receiver availability, admission and feedback internally. It does not reuse a native random tape or replay receiver states.

The reporting retains attempted/admitted/delivered populations, raw provisional drop and pending counters, all undelivered applications as unresolved at cutoff, source-specific delivery and latency comparisons, source-weighted means, and supplementary fixed-age results. Source cells with no native deliveries retain an explicit undefined-relative-comparison status; their traffic is not silently discarded. Equal numeric seeds do not establish paired autonomous application histories.

The latest complete full-run measurements remain the previous +60.4% raw mean-latency gap and +41.5% source-weighted gap. The newly validated retained-copy and ordering corrections have not yet been measured over 6,000 seconds. The next return will show their actual effect; the matched short histories do not establish statistical equivalence or predict a particular reduction.

See the accompanying full-run kit README for its MATLAB command, output ZIP and resume rules. No additional native installation or owner-run ns-3 command is required.
