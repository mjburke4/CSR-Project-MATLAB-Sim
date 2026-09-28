# J returned-prefix audit

J passes the earlier DISCOVER identity boundary and reaches 45.662638077 seconds. Its next request is node 3 PHY draw 75, sampling the second payload interval of node 5 TX37: MATLAB requests 52 bits and native expects 51. The semantic TX identity, interval ordinal, component, BER and all recorded interval/component endpoints agree. The guard stops before consuming the native value; equal nanosecond endpoints do not establish equality of the underlying floating-point endpoints.

| Audited prefix | Result |
|---|---|
| Random requests | 759 logged; 758 consumed: 150 MAC, 348 SYNC, 260 PHY |
| Rejected request | PHY request 261 overall; node 3 PHY75; only `bits` differs |
| Physical TX contexts | All 129 verified and registered |
| Unconditional merged request/TX history | All 888 events match native order and rounded-nanosecond times through native event 20233 |
| Earlier boundaries | 183-bit PHY, four-child/82-byte TX, population-2 MAC, seven-child/215-byte TX, 63-byte REQUEST aggregate and 109-byte DISCOVER aggregate pass |

The independent comparison includes every request, including the rejected request; it also checks request/TX interleaving rather than only per-stream order. All earlier controlling request fields and recorded PHY interval/component endpoints match. The existing profile-4 `reported_nodes` diagnostic differences remain recorded explicitly. No conclusion is drawn about unrecorded floating-point precision or every internal callback/state.

Seven transmitted DISCOVER children carry the new explicit identity annotation. Three gateway children retain equal outer counters. Three node-3 children retain actual/native counters 1/4, 2/5 and 3/6; node 5's first retains 1/7. All seven discovery payload sequences remain 1. The audit independently checked the annotation's eligibility against each native child and actual raw MAC frame: protected native broadcast DISCOVER, broadcast subtype, single broadcast target, no ACK and no ACK window. All four raw counter differences are confined to that scope; no other transmitted field mismatch was hidden by the annotation.

The first annotated node-3 aggregate at 25.740 s passes with three children and 109 bytes and is registered as transmitted. The earlier wire correction still passes node 1 TX18 at 25.298 s with 16-byte REQUEST, 16-byte REQUEST and 31-byte SNMP_START, totaling 63 bytes. Native's full captured fixture still has no NoPath TX, so that correction remains exercised only by its component checks.

The return matches the issued manifest: all 322 bound files, 131 resolved MATLAB source hashes and source/candidate transform copies verify. All 45 component checks pass (7 KEY, 8 neighbor, 6 population, 8 route, 6 REQUEST, 3 NoPath, 7 DISCOVER identity), as does native import preflight. A was reused, not rerun; its accepted trace bytes and exact prefix gate remain valid for 12,200 protocol, 12,198 PHY and 9,000 admission rows. Configuration matches after canonicalizing only documented source-path metadata. The service observer reports no omitted rows and complete cancellation pairs through the stop.

Run `python autonomous_eighth/review/audit_prefix.py` to reproduce the assertions and comparison files. This audit did not change the kit or run a simulation. It establishes checked-prefix agreement, not complete 330-second or 6,000-second autonomous behavior or the 15% performance target.
