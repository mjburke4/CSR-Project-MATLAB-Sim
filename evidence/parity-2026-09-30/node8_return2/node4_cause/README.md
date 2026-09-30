# Node 4 causal trace — seed 132

The stopped common-input replay exposes a real relay-custody mismatch. It is not
an application-identity import error. The first different physical transmission
is at **895.115 s**, but the responsible queue occurrence is lost in MATLAB at
**694.821813632 s**.

| Time (s) | Event | Native ns-3 | MATLAB |
| --- | --- | --- | --- |
| 694.262813632 | Node 4 receives source 7, attempt 2873 from node 2, HOP sequence 162 | First reception; DACK; enqueues one relay copy; source-7 NSDP 25→26 | Same |
| 694.821813632 | Same DATA arrives again before its sender processes DACK | DACK-marked sequence remains a first reception; enqueues another relay copy; NSDP 26→27 | HOP also classifies first reception, but NWK `Seen` guard returns early; NSDP stays 26 |
| 883.466292500 | Capacity permits HOP handoff | First source-7 copy becomes HOP sequence 211; second copy remains at queue head | Only source-7 copy becomes sequence 211; next queue head is source 8, attempt 3684 |
| 894.464292500 | Old HOP sequence 193 DACK hold expires and wakes NWK | Pending/outstanding 3, threshold 3 permits one new admission; duplicate source-7 copy becomes HOP sequence 212 | Same capacity state admits source-8 application as sequence 212 |
| 895.115 | Node 4 physically transmits to node 5 | Source 7, attempt 2873 | Source 8, attempt 3684; strict context check stops replay |

The sub-nanosecond handoff values in MATLAB are preserved in the JSON timelines.
The table rounds those handoff timestamps to nanoseconds; the physical TX time
is identical. The mismatch is application content and queue ownership.

## Scope of verification

`investigate_node4.py` independently joins accepted native `(source, sequence)`
identities and MATLAB packet IDs to `(source, attempt)`. It checks every NWK
enqueue through the stopping time across all seven nodes. The only unmatched
occurrence is the extra native node-4 copy at 694.821813632 s. There are no
MATLAB-only enqueues. Node 4's first 198 enqueue events match in identity and
nanosecond timestamp; total enqueue counts are 286 native and 285 MATLAB.

The ordered waiting-queue reconstruction subtracts a MATLAB application at its
`network_submit` event, so submitted custody owners are not confused with waiting
traffic. Every reconstructed native queue depth matches the recorded
`queue_after`. Just before the final differing handoff, queue depths are 88
native and 87 MATLAB. Their leading identities are respectively
`[(7,2873),(8,3684),(7,2906)]` and `[(8,3684),(7,2906),(2,9499)]`.

## Source explanation and repair boundary

The active class is `ac.DiscoveryMembershipNwk`, selected by
`ac.TerminalSimulation` line 162. Its `receiveData` lines 124–127 immediately
return when `Seen(appKey)` is present, and lines 153–155 set that marker after the
first relay enqueue. The second arrival therefore never reaches the enqueue
callback. The model `csr.nwk.Layer` has the same behavior.

Native `csr-hop-layer.h` lines 3575–3600 explicitly treats a DACK-marked retry as
a first reception and delivers it to NWK again. `CheckReceivedSeq` checks the ACK
bitmap, so a DACK mark is deliberately eligible for reassessment. Native
`csr-nwk-layer.h::ReceiveFromHop` increments relay NSDP and appends a new
`NwkQueueEntry` for each such reception.

Removing only the NWK `Seen` guard is insufficient: `enqueueApplication` also
returns early for an existing `pendingPosition(app)`, and pending lookup,
submission, and custody release are keyed by the end-to-end application identity.
A repair needs distinct local custody-occurrence identity so one feedback
completion cannot remove the sibling occurrence. Keep final-destination
application accounting and reporting deduplication separate.

Useful isolated tests before replay are: (1) two successful DACK-marked receptions
of the same HOP sequence create two relay custody owners and increment NSDP twice;
(2) first-copy completion releases only that owner and the next copy receives a
new outbound HOP sequence; (3) ordinary ACK-marked duplicate reception creates no
new owner; (4) final-destination reporting still counts an application once.

No model code was changed for this analysis. This cause does not quantify the
effect of a future repair on the autonomous 6,000-second latency gap.

## Reproduce

From the workspace root, run:

```sh
python node8_return2/node4_cause/investigate_node4.py
```

The script writes identity-joined application timelines, enqueue evidence,
ordered queue snapshots, source input SHA-256 hashes, and `findings.json`.
