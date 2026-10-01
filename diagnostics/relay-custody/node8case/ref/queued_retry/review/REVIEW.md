# Independent N owner-return audit

The actual N return passes **74 component checks**. Its first 4,971 merged random-request and transmission events match native in guarded context, unconditional global order and rounded-nanosecond timing. The next event at **324.753 seconds** selects a different DATA application. The previous feedback-classification stop is cleared.

| Evidence | Result |
|---|---:|
| Issued bound files verified | 361 |
| Resolved MATLAB source hashes verified | 149 |
| Actual component checks passed | 74 |
| Consumed MAC / SYNC / PHY requests | 885 / 1,863 / 1,454 |
| Consumed requests total | 4,202 |
| Registered physical transmissions | 769 |
| Strict merged context/order/time prefix | 4,971 events |
| Order/time matched positions, including rejected TX context | 4,972 |
| Earlier order / request-time / TX-time / PHY endpoint differences | 0 / 0 / 0 / 0 |

The comparison uses the **complete native chronological draw-plus-TX stream**, without filtering native events to the requested keys. The last strict event is node 5 MAC draw 148 at 324.753 seconds, native event 122180. The rejected node 5 TX 130 context is the next native event, 122181, at the same time. Every checked field agrees except HOP sequence and application attempt: MATLAB chooses sequence 36, source-5 attempt 250; native chooses sequence 29, source-5 attempt 11. Both have destination 1, flow index 3, 185 application bytes and 217 wire bytes. The rejected context is not counted as a physical emission.

All **125 emitted DATA children** have matching application flow/attempt and HOP sequence. The rejected 126th child is the first wire-lineage difference. Generation timestamps for the earlier children differ by zero nanoseconds in 80 cases and one nanosecond in 45 cases; these are separately logged metadata differences, not callback-time differences. The rejected applications were generated about 4.78 seconds apart: MATLAB at 304.980 seconds, native fixture at 300.199999999 seconds. Their distinct attempts and HOP sequences remain strict; no identity exception applies.

Source-5 attempt 11/sequence 29 previously matched at 313.820 and 320.879 seconds. The MATLAB service trace later records sequence 36's MAC admission at 322.260111113778, followed by sequence 29's second retry admission at 322.879000027778. It selects sequence 36 at the stop. This trace establishes local admission order; identifying the earlier native retry/queue-state difference requires the separate HOP lifecycle investigation. Matching wire events does **not** establish identical hidden queue contents before 324.753.

The N feedback change is exercised successfully at the previous 312.143-second boundary. All **1,081 actual feedback children** were independently checked against raw MATLAB frames, native outer type, independent ACK/DACK flags, four encoded flag bits, both complete bitmaps and window state. These comprise 1,060 ACKs and **all 21 DACK examples in the full native fixture**. The returned public component sweep additionally passed all 1,104 fixture feedback children and its two explicitly synthetic, source-supported edge cases. The 24 prior protected-broadcast DISCOVER annotations retain their independently verified narrow scope; 21 log different outer identifiers. No DATA identity normalization was introduced.

The earlier membership, receiver-timer, requester-lifecycle, KEY_UPDATE, wire-size, routing, neighbor and population boundaries remain passed. There are 37 previously declared profile-4 reported-population differences; this field is diagnostic and unused by that fixed profile. The service observer reports 18,488 records, zero omissions and 142 complete cancellation pairs. Receiver timing records contain 2,808 targets with zero omissions.

The returned manifest exactly matches the issued N kit; every bound file, resolved MATLAB source and both transformation descriptions match. Runtime is MATLAB R2025a on PCWIN64. Natural A was **reused**, with the three accepted traces byte-identical and configuration/runtime gates passed; it was not newly simulated.

This is a bounded common-input prefix, not a completed 330-second result, an autonomous RNG-distribution comparison, a 6,000-second result or a claim of 15% parity. The audit does not edit source, guards, fixtures or the kit.

Reproduce without a simulation: `python autonomous_twelfth/review/audit_prefix.py`. The JSON receipt records exact hashes and counts; companion CSVs contain every compared request, TX context, merged position, feedback annotation and DATA lineage, plus the stopped flow's MATLAB service history.
