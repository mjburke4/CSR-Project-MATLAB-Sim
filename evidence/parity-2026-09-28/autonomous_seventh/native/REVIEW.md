# DISCOVER outer-sequence investigation

The stop at 25.74 seconds is an identity-representation difference, not evidence of different network behavior. Native's outer DISCOVER sequence is a process-wide counter; MATLAB's is local to the sending HOP object and broadcast destination. Native node 1 previously generated three DISCOVERs, so node 3's first receives outer sequence 4. MATLAB node 3 assigns 1. Both carry the same behaviorally meaningful NWK discovery payload sequence 1, and all other checked fields match, including the three ordered children and 109 modeled bytes.

## Allocation and complete captured population

`CsrHopLayer::SendProtectedDiscovery` protects the payload first, then increments a function-local `static uint16_t discoverySequence` and inserts it into the outer header. This static is shared across sender objects in the process; it is not a node member, per-peer reliability counter, discovery-session identifier, physical-transmission identifier or security replay sequence. It persists for the process lifetime, including across `Simulator::Destroy` if the same executable creates another scenario. It increments before MAC enqueue, including an eventual MAC drop.

The accepted 0–330 capture contains 24 generated DISCOVERs and 24 transmitted DISCOVER children. Joining the passive pre-encryption observations to their source/frame IDs proves exact global generation ordinals 1 through 24. Node1's first three are 1/2/3; node3's first is 4. Twenty-one of 24 labels differ from that source's own discovery-send ordinal. The counters follow generation order: transmissions with global labels 16 and 15 occur in that order around 77 seconds because the senders contend independently. A global transmission-order counter would therefore be incorrect even as a label emulator.

MATLAB `csr.hop.Layer.sendControl` assigns DISCOVER from that object's `LastSequences(16777215)`. The broadcast entry is separate from every unicast peer's sequence entry. It rolls back on failed MAC admission; native's function-static counter does not. That unobserved failure-path distinction would change only this outer label on the audited DISCOVER branch. No queue failure or counter wrap appears in the accepted population.

## Why this outer label does not drive the captured behavior

- **Protection and replay:** GroupEstablish protection receives only the payload and sender security state before the outer sequence exists. Native `HandleProtectedHello` passes source, security count, mode/type and the protected record into `ReceiveGroupMessage`. The record contains its own 12-bit group sequence; replay uses `(groupKeyId <<12) | groupSequence`. It never uses the outer HOP sequence. The stopped native DISCOVER has outer 4, security group sequence 5, and NWK discovery payload sequence 1: three distinct quantities.
- **Receive dispatch:** native `ReceiveFromMac` dispatches DISCOVER/HELLO through `HandleProtectedHello` and returns before reliable `CheckReceivedSeq`. It forwards plaintext and source to NWK. NWK uses `CsrHelloHeader::GetDiscoverySequence`, matching MATLAB `Payload.Sequence`, for discovery response/repetition behavior. MATLAB likewise excludes broadcast controls from the reliable receive window.
- **MAC and PHY:** non-ACK MAC enqueue orders by DSCP, not sequence. ACK cancellation and sent/timeout callbacks exclude non-ACK frames. PHY signal identity uses source plus an independently incremented physical-transmission ordinal. `RxSignal.sequence`, including its SYNC callback argument, is logging/trace metadata; SYNC eligibility and event scheduling do not depend on it. Frame size is unchanged by a different value in the fixed-width outer field.

This is a source-derived equivalence for the audited field under these pinned implementations. It is not a claim that MATLAB reproduces native cryptographic security. Exact source spans and file hashes are preserved in `source_path_proof.json`; no new network run or component probe was needed.

## Sibling audit

| Family | Observed children | Native allocation | Treatment |
|---|---:|---|---|
| DISCOVER, including the same send API for chirps | 24 broadcasts, 0 chirps |Process-wide function-static 16-bit counter |Outer label is representation metadata; keep all payload semantics strict |
| SNMP | 36 |Constant 0; no reliable allocation |Already agrees; retain strict check |
| KEY_REQUEST | 15 |Sender-local per-destination stream shared with reliable controls/DATA |Retain strict check: allocation affects later reliable identities, despite this packet being non-ACKed |
| ACK | 1,104 |Echoes the acknowledged sequence or window base |Retain strict check: directly drives cancellation/completion |
| HOP bare HELLO | 0 |Separate function-static counter |Source-only finding; no broad exception justified |
| HOP authenticated HELLO | 0 |Separate function-static counter |Source-only finding; no broad exception justified |
| APP_NEIGHBORCAST | 0 |Separate function-static counter |Source-only finding; no broad exception justified |
| MAC-internal HELLO | 0 |Per-MAC-object `m_helloSeq` |Different allocator again; no broad exception justified |

The audit covers all 1,495 child rows and their non-ACK control inventory. DATA and acknowledged NeighborCheck/KEY_UPDATE/ROUTING identities retain their existing strict checks. A blanket “ignore non-ACK sequence” rule would be wrong.

## Recommendation and limits

Classify only outer `hop_sequence` of the observed broadcast subtype of protected DISCOVER as nonbehavioral representation metadata in the semantic comparison. Preserve both values in diagnostics and retain source/physical-transmission lineage, child order/count, actual type, broadcast destination, non-ACK status, subtype, NWK discovery sequence, active-peer membership, wire size, radio, timing and reservation checks. Do not replace actual values with native values or change the fixture. A comparison exception must require the expected and actual child to be the matched broadcast-subtype DISCOVER branch, not merely non-ACK traffic. Chirps have no captured coverage and receive no exception. The expected native frame must also retain the group-protection flag and security-count metadata; MATLAB represents this through its unchanged behavioral DISCOVER model.

Adding a shared MATLAB counter solely to duplicate the native label would introduce cross-node state without correcting autonomous traffic or receiver behavior. If exact serialized transport-label parity is a separate requirement, a per-simulation replica of native allocation would be appropriate; that is distinct from this network-behavior investigation and would need failure/wrap/reset checks.

No production, fixture or comparator edits were made here. No continuation past 25.74 seconds was run, and no performance-parity improvement is claimed. `audit_discovery_sequence.py` reproduces the read-only capture/source audit; `sequence_audit.json` contains every DISCOVER generation/transmission/sequence identity and sibling counts. `evidence_receipt.json` binds these artifacts to the accepted capture and returned mismatch.
