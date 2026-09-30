# Independent M owner-return audit

The actual M return passes all 66 component checks and extends the strict common-input event prefix to **312.143 seconds**. The previous discovery-membership failure is cleared. The new stop is the feedback packet's outer kind label; no earlier request/TX ordering or rounded-nanosecond timing difference was found.

| Evidence | Result |
|---|---:|
| Issued full-kit bound files verified | 424 |
| Resolved MATLAB source hashes verified | 145 |
| Component checks actually returned passed | 66 |
| Consumed MAC / SYNC / PHY requests | 752 / 1,574 / 1,192 |
| Consumed requests total | 3,518 |
| Registered physical transmissions | 648 |
| Strict merged request/TX prefix | 4,166 events |
| Order/time matched positions, including rejected TX context | 4,167 |
| Earlier order / request-time / TX-time / PHY endpoint differences | 0 / 0 / 0 / 0 |

The comparison uses the **complete native chronological draw-plus-TX stream**, not a stream filtered to requested keys. The last strict event is node8 MAC draw82 at312.143 seconds, native event103244. The next event is the rejected node8 TX74 context at the same time, native event103245. Its sole checked mismatch is `child1.kind`: MATLAB's logical DACK label maps to2, while the native fixture records outerkind1 with both `is_ack=1` and `is_dack=1`. Source/destination8→7, HOP sequence30,41wirebytes, DSCP7, ACK-window state, ACK bitmap`00000000000fff72` and DACK bitmap`0000000000000001` all agree. The rejected context is not counted as a physical emission. This audit preserves the mismatch; it does not change the comparator or infer post-stop behavior.

The five new public membership checks actually pass. At the previous network boundary116.340299163, the watchdog callback fires and returns in adjacent observations without new work. Node3 MAC requests102/103 now occur at native times300.001/300.365; its TX86 is the matching DATA transmission to1 at300.365. The previous extra SNMP transmission at116.415 is absent. Earlier receiver-timer, KEY_UPDATE timing, SNMP requester, REQUEST wire, routing, neighbor, population and discovery identity boundaries remain passed.

Twenty-four protected broadcast DISCOVER annotations were independently checked against raw frames and native conditions;21 retain a logged outer identifier difference. No extra normalization was used. Thirty-seven profile4 reported-population differences remain diagnostic only, as already declared by the harness; the controlling MAC inputs match. Receiver timer logging contains2,371 targets with zero omissions. The service observer reports13,264records with zero omissions and93 complete cancellation pairs.

The issued manifest exactly matches the return; all bound bytes and both transforms match. Runtime is MATLAB R2025a onPCWIN64. Accepted natural A is explicitly **reused**, with its three trace files byte-identical and configuration/runtime gates passed; it is not a new natural run.

This is bounded common-input evidence, not a completed330-second comparison, autonomous RNG-distribution proof,6,000-second result, or a claim of15% parity. The comparator-only feedback interpretation and component tests need their own reviewed candidate and actual owner return.

Reproduce without a simulation: `python autonomous_eleventh/review/audit_prefix.py`. Inputs, hashes, exact stop, prior boundary, and counts are recorded in `m_audit.json`; companion CSVs contain every compared request, TX context and unconditional merged position.
