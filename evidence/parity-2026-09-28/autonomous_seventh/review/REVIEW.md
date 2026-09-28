# I returned-prefix and DISCOVER identity review

The REQUEST wire-size correction passes its first real captured transmission: node 1 TX18 at 25.298 s contains the expected 16-byte REQUEST, 16-byte REQUEST and 31-byte SNMP_START, totaling 63 bytes. The run then reaches 25.740 s and stops before node 3 TX17 on one outer DISCOVER HOP sequence value: MATLAB 1 versus native 4. Its discovery payload sequence is 1 in both engines; the three children, 109-byte total, payloads, destinations, reservation and other checked fields agree.

The independent audit checks all 290 consumed requests (61 MAC, 131 SYNC and 98 PHY), all 49 successful TX contexts and the 50th rejected TX context. All 340 events have the same unconditional merged request/TX order and rounded-nanosecond times as native through native event 8533. Controlling request contexts and recorded PHY interval/component endpoints agree. The known noncontrolling profile-4 `reported_nodes` differences remain explicitly recorded. Earlier 183-bit PHY, four-child/82-byte TX, population-2 MAC and seven-child/215-byte TX boundaries continue to pass.

The outer sequence difference has a source-level explanation separate from discovery state:

| Field | Native source | MATLAB source | Role at this stop |
|---|---|---|---|
| Outer HOP DISCOVER sequence | Function-static `discoverySequence` in `CsrHopLayer::SendProtectedDiscovery` (`csr-hop-layer.h:1479`), shared across instances | Each HOP instance's `LastSequences` map, indexed by broadcast destination (`model/+csr/+hop/Layer.m:131`) | Gateway broadcasts take 1, 2, 3; the next node's first broadcast is native 4, MATLAB 1 |
| Discovery payload sequence | `CsrHelloHeader` discovery sequence supplied by NWK | `Control.Payload.Sequence` | Both are 1; this drives the discovery protocol |
| Inner HELLO compatibility sequence | Separate static `helloSeq` in `SendHelloBroadcast` | Separate compatibility representation | Not the outer HOP field that triggered this guard |

Native group protection occurs before the outer HOP sequence is assigned. `HandleProtectedHello` supplies source, security count, security mode, legacy packet type and protected record to authentication; it does not supply or inspect the outer HOP sequence. Successful handling forwards plaintext and source identity to NWK and returns before the normal HOP sequence-window/ACK paths. MATLAB's broadcast control path similarly bypasses `checkSequence` and does not request feedback. These inspected paths support treating this narrowly defined outer broadcast-DISCOVER value as an allocator identity difference. They do not support relaxing reliable-control sequences, discovery payload sequences or all broadcast fields. This audit did not modify a comparator or simulation source.

Returned provenance matches all 294 issued bound files and 127 resolved MATLAB file hashes, and the source/candidate transform copies match. All 38 component checks passed (prior 29 plus 6 REQUEST and 3 NoPath), along with import checks. A was reused rather than rerun; accepted trace bytes and exact prefix gate remain valid for 12,200 protocol, 12,198 PHY and 9,000 admission rows. Configuration differs only in documented source-path metadata. Service capture reports no omitted rows and complete cancellation pairs through the stop. The complete native fixture still contains no NoPath TX, so that correction has passed component checks but has no exercised network effect here.

`audit_prefix.py` reproduces the independent assertions and writes `i_audit.json` and the comparison CSVs. No new simulation was run. This is evidence about the guarded prefix, not complete 330-second or 6,000-second autonomy, all internal states, or the 15% performance target.
