# Independent red-team audit: returned seed-132 replay

The stop at **895.115 s** is a real transmitted-application mismatch relative to the pinned ns-3 reference, not an import, packet-ID, or source-lineage artifact. The run is partial; it does not establish 1,200-second completion or ±20% autonomous-network parity.

## Evidence independently verified

- The returned manifest matches the corrected issued kit; all **494 sealed files** match. All **160 resolved MATLAB file hashes** match that kit. All **17 preflight groups** pass.
- All **6,008 observed physical TX-start events** match native global order, node, per-node ordinal, and rounded integer-nanosecond time. The first **6,007** pass strict payload-context comparison. Event 6,008 is the attempted node-4 TX #962 that throws before physical transmission completes.
- All **34,260 random requests** match native request order, integer-nanosecond time, supplied value and tested context. Independently checking the interval timestamp fields excluded by the runtime comparator also found zero differences. `reported_nodes` remains outside the fixed-profile-4 comparison contract.
- Protocol, PHY, application-admission, service, receiver-timing and transport-timing omission counters are zero. The **4,475,736 ordered JSONL records** have consecutive observation IDs. Completeness here means complete evidence of the partial run, not endpoint completion.
- Reading the native MAC **TXHEX bytes directly** decodes network source **7**. The MATLAB actual frame has network source **8**. Native raw HOP admission joins this to source-7 attempt **2873**, and its original successful application admission independently confirms that lineage. MATLAB selected source-8 attempt **3684**. Scheduling, HOP sequence 212, destination 5 and packet size agree at this TX.

## Earlier causal mismatch

Node 4 receives source-7 attempt 2873 over 2→4, HOP sequence 162, at **694.262813632 s** and again at **694.821813632 s**. Both simulators identify both receives as first receptions under their DACK retry bookkeeping.

| Receiver observation | ns-3 | MATLAB |
| --- | --- | --- |
| First receive NSDP | 25 → 26 | 25 → 26 |
| Retry NSDP | 26 → 27 | 26 → 26 |
| NWK retained occurrences | 2 | 1 |

The active MATLAB class is `ac.DiscoveryMembershipNwk`, instantiated in `TerminalSimulation.m` line 162. Its `receiveData` returns success immediately when `Seen(appKey)` is present (line 124), after the first receive set that entry (line 153). This occurs **before** the additional duplicate suppression in `enqueueApplication` at line 459. `pump`, `pendingPosition` and custody releases also identify ownership by application key.

Native `CsrHopLayer::HandleDataFrame` explicitly treats DACK-marked retries as eligible for reassessment and NWK delivery. Native NWK increments NSDP and pushes a relay queue occurrence on each such callback (`csr-nwk-layer.h` lines 1490 and 1503). Native raw canonical traces contain both enqueues, independently of passive observation output.

This is a confirmed behavioral mismatch to the current reference. It does not by itself decide which design is preferable, prove the original OPNET implementation, or explain the full 6,000-second latency gap.

## Fix-review implication

Removing one duplicate guard is insufficient. A candidate must preserve distinct relay occurrence ownership through queueing, HOP admission and release, while retaining unique source-application accounting. Review ordinary ACKed retries separately: the HOP duplicate window should still suppress those. Test two retained occurrences with one in HOP service, one waiting; release each owner exactly once; verify NSDP and queue capacity. Keep common-input comparators strict.

Reproduce the audit without a simulation:

```sh
python node8_return2/redteam/audit_return.py
python node8_return2/redteam/audit_retry_cause.py
```

The scripts expect the returned data, corrected kit and native evidence at the relative paths declared near their tops. Detailed JSON, the full physical-TX prefix comparison, and native/MATLAB retry excerpts accompany this note.
