# Broadcast DISCOVER identity review

The seventh owner return passed all 38 existing component checks and continued through the previous REQUEST wire-size boundary. It stopped at 25.74 seconds on node 3's seventeenth physical transmission. All three children, 109 aggregate bytes, radio parameters and payload semantics matched. The sole difference was the third child's outer DISCOVER HOP sequence: MATLAB 1, native 4. Its payload discovery-session sequence was 1 in both. Before this stop, 290 random requests and 49 physical transmissions passed the existing comparisons, with no rounded-nanosecond request-time difference recorded.

## Origin and ownership

MATLAB `csr.hop.Layer.sendControl` allocates every non-SNMP control from that node's `LastSequences(destination)` map. The broadcast destination is independent of all unicast destinations, so node 3's first DISCOVER has outer sequence 1. Native `CsrHopLayer::SendProtectedDiscovery` instead increments a function-static uint16 counter shared by all nodes in the process. Node 1's three earlier sends consumed 1–3; node 3's first send therefore has label 4. This counter does not represent the node's discovery session.

The native capture contains 24 DISCOVER creation hooks. Joined to their frame identities, they carry global labels 1–24 in creation order. Transmission order can differ from creation order, so fitting labels by global transmission ordinal would be incorrect. All 24 captured subtypes are broadcast. See `native_discovery_allocation.csv` and `discovery_sequence_audit.json`.

## Behavioral audit

MATLAB treats this frame as non-ACK broadcast. HOP `receiveControl` bypasses its per-peer duplicate/ACK window and passes only control payload plus source to NWK. MAC uses sequence fields for ACK replacement and ACK-required cancellation, neither applicable here. Its PHY uses separate physical transmission identity and never reads the outer HOP sequence. The simulation records it in traces.

Native group protection occurs before this outer header is allocated. Receive/authentication uses source, security count, protected group record and packet type, then returns before `CheckReceivedSeq`; pending security replay stores the group record rather than this outer sequence. Native MAC and PHY source audit also identifies the sequence as trace-only for this path. At the stopped frame, outer label 4, security group sequence 5 and payload discovery-session sequence 1 are three distinct values with different ownership. The latter two must not be replaced by the outer label.

This finding is a comparison-of-identifiers problem, not evidence that network behavior needs a shared global discovery counter. A candidate that changed HOP allocation would add process-wide model state solely to match a trace label.

## Bounded comparator candidate

J runs the exact I protocol behavior through copied simulation/provider classes. Only `DiscoveryTxSignature` changes the comparison. Both actual and native children must be DISCOVER kind 4, have broadcast destination 16777215, require no ACK, have no ACK window, and have subtype `broadcast`; native must also retain its broadcast destination type, group-security flag and security count. The actual frame must also have exactly one broadcast destination. Only then is outer `hop_sequence` classified as a trace-only identifier. Raw MATLAB/native values, policy and reason remain in the ordered transmission evidence.

All other checks continue, including payload discovery-session sequence, source, destination, subtype, children/order, size, rate, power, reservation, flags and semantic content. Reliable HOP sequences, KEY_REQUEST, SNMP, chirp and unrepresented HELLO types get no exception. Original `TxSignature`, `Streams`, I classes, all 99 model artifacts and native fixtures remain unchanged. J's copies are bound by reversible transforms.

## Sibling audit and limits

DATA, KEY_REQUEST, KEY_UPDATE, NeighborCheck and reliable ROUTING share the per-source/per-destination transmit sequence space; their exact values can affect subsequent reliable ownership. They remain strict. SNMP is fixed zero without sequence allocation in both engines. Native plain HELLO and authenticated routing broadcasts have other static counters, but the portable control API has no corresponding HELLO type and the captured fixture has none; no general broadcast normalization is introduced. Discovery chirps share the native producer but are absent from this capture and outside J's eligibility.

Public comparator preflights reconstruct the stopped three-child transmission using public Frames APIs, require the original comparator to reproduce its sole mismatch, and require the new comparator to preserve raw labels while accepting the documented identity difference. Negative mutations keep payload sequence, size, addresses, ACK/window, reliable sequence and uncovered kind/subtype checks strict. These are comparator tests, not network or receiver simulations.

No MATLAB runtime is available here. J and its new preflight remain pending owner execution. Existing accepted-natural reuse and all 38 component checks remain in the runner; previous I evidence is historical. This local diagnostic does not establish full-network ±15% accounting or latency parity.
