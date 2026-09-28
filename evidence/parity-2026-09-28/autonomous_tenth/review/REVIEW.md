# Independent L return review

All **61 public component checks passed**, and the return matches the issued L kit: **389 bound files**, **141 resolved MATLAB files**, exact transform metadata and the accepted runtime. Natural A was reused, not rerun; its three traces are byte-identical to the accepted files and its prefix/configuration gates pass.

Both previous lifecycle boundaries now agree with native. Node 4 MAC draw 25 occurs at **62.870833632 seconds**, with no previous +10.166368 ms delay or subsequent +13 ms timing shift. Node 5 TX 68 at **71.942 seconds** now sends its SNMP_START child to node **1** in both the HOP and final-destination fields. The 45.662638077-second receiver allocation still passes with 51 payload bits, and earlier wire/population boundaries remain passed.

The strict unconditional random/TX prefix is **3,216 events: 2,729 consumed draws and 487 successful TX contexts**. It ends at **112.775012442 seconds**, node 8 SYNC draw 84, native event 66352. Every native random/TX event through the actual 116.415-second stop belongs to that matched prefix. No earlier paired timing or global-order difference is present. All recorded PHY interval/component nanosecond fields also agree. There are 37 differences in the diagnostic reported-population field, which fixed MAC profile 4 does not use; its controlling active-population field agrees. This comparison does not assert equality of all private network state or raw floating-point endpoints.

The following three observations are extra early work, rather than a continuation of that strict prefix:

| Observation | MATLAB time | Matched per-source native tape time |
|---|---:|---:|
| Node 3 MAC draw 102 | 116.350 s | 300.001 s |
| Node 3 MAC draw 103 | 116.415 s | 300.365 s |
| Node 3 TX 86, rejected | 116.415 s | 300.365 s |

Thus 2,731 random requests were logged and consumed (563 MAC, 1,226 SYNC, 942 PHY), but only the first 2,729 belong to the matched global prefix. The next **global** native request is node 7 MAC draw 32 at **117.377 seconds**. Per-source stream lookup permits the two early node 3 draws because their guarded MAC contexts match; the timing diagnostics retain this difference. The failed TX was neither registered nor physically emitted.

At **116.340299163 seconds**, MATLAB admits an extra SNMP_START with source 3, final destination **7**, next hop **5**, and 31 bytes. This starts the extra MAC work. Its next per-source native TX, at 300.365 seconds, is instead a 217-byte DATA frame to node 1. The difference is real control generation, not a packet identity/comparison exception. All 24 protected broadcast DISCOVER annotations were independently checked; 21 outer identifiers differ under the existing narrow policy, which does not cover SNMP or DATA.

Source inspection explains the membership boundary: MATLAB `advanceScan` merged every currently reachable route into `ScanKnown` whenever it advanced, including at a watchdog. Native `CheckDiscoveryTable` walks existing discovery entries. Route learning can be correct while an extra membership insertion is incorrect. A late route therefore became a new scan target during the 116.340299163-second watchdog. The bounded candidate removes that merge from advancement while retaining legitimate route-based population at local discovery completion and population from received DONE reports. The short trace does not directly expose every membership field before that callback; no broader state-equality claim is made.

The observation capture is complete through the stop, with zero omitted service records and valid cancellation pairs. NoPath and the 28 ns rejected-return branch retain their prior network-coverage limitations. No new simulation was run by this audit, and full 330-second, 6,000-second or 15% parity has not been established.

Reproduce with `python autonomous_tenth/review/audit_prefix.py`. It writes `l_audit.json`, complete request/TX/global-order comparison CSVs, validated DISCOVER annotations and `stopped_snmp_raw_evidence.json`.
