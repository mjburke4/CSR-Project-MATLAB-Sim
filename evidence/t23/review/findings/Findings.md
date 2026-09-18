# Tranche 23 independent behavioral review

T23 completed on MATLAB R2025a (25.1.0.2943329) in **72.141 seconds**. All
**79 focused tests passed**, all seven controlled cases completed, and all
**18 common milestones / 81 integer assertions passed**. No MATLAB rerun is
needed to obtain the intended behavioral evidence. Full source and archive
integrity acceptance is covered by the separate integrity review.

The diagnostic confirms a narrow difference in relay custody. It does not
show a difference in the generated ACK/DACK decisions for these cases.

| Observation after the retry | MATLAB | ns-3 |
|---|---:|---:|
| Relay custody while congestion remains high | 17 | 18 |
| NWK waiting packets in that case | 16 | 17 |
| Relay custody after three downstream ACK releases | 14 | 15 |
| NWK waiting packets after those releases | 12 | 13 |

Those are the only differing state fields, at two of the 123 checkpoints.
The other **121 checkpoints match**. HOP pending/outstanding/resend counts,
delivery-callback counts, completion counts and receive-window bits match at
the two differing checkpoints as well.

The return reports two differing feedback rows out of 91. Those differences
are **only the occupancy metadata attached to the feedback records**:
`relay_nsdp` and `nwk_owned`. All **91 captured ACK/DACK types, sequence
numbers and ACK/DACK bitmaps match exactly**; enqueue timestamps match within
the specified 1 ns tolerance. Decimal comparison of the raw CSV times gives
a maximum feedback-time difference of 3e-17 seconds and maximum state-time
difference of 1e-15 seconds. This is a comparison of captured control fields,
not an RF or complete protected-frame byte comparison.

| Replay | Feedback time (s) | Type | HOP sequence | ACK bitmap | DACK bitmap |
|---|---:|---|---:|---|---|
| Congestion remains high | 0.27 | DACK | 17 | `000000000001FFFE` | `0000000000000001` |
| After three releases | 0.33 | ACK | 17 | `000000000001FFFF` | `0000000000000001` |

Both engines retain the historical DACK bit when the reassessed retry is
ACKed. That overlap is equal in both outputs; native feedback consumption
gives the ACK bit priority. State checkpoints are deliberately recorded one
microsecond after each action, so the corresponding state times are 0.270001
and 0.330001 seconds.

## Confirmed source mechanism

The native NWK and HOP headers were freshly recovered at source commit
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` and hash-matched to the native
T23 evidence. The MATLAB NWK source hash matches the owner return.

- Native `CheckReceivedSeq` allows a DACK-marked HOP sequence to be reassessed.
  `HandleDataFrame` delivers that pass to NWK. `ReceiveFromHop` queues another
  relay entry and increments NSDP without an application-identity deduplication
  guard on that path.
- MATLAB `NWK.receiveData` finds the existing `Seen(SourceId, Id)` entry and
  returns accepted before adding custody. The fixture still records the HOP
  delivery callback, which explains why both engines show 18 callbacks but
  different retained owners.
- Both choose the ACK/DACK response from the pre-enqueue pressure. Before
  the tested retry, those counts are identical: 17 in the pressure case and
  14 after the three releases. The extra native owner is added afterward,
  so it has no immediate feedback consequence in these final actions.

MATLAB also deduplicates pending entries in `enqueueApplication` using
`pendingPosition`. Removing only the `Seen` guard would therefore not create
a faithful native custody model. An experimental change would require
distinct custody-instance ownership and correct release/completion mapping,
while carefully preserving application-delivery semantics.

## What T23 establishes and leaves open

The common tests confirm the relay ACK-to-DACK threshold, separate local and
relay accounting, suppression of already-ACKed duplicates, ACK reassessment
after capacity release, idempotent completions, DACK-hold expiry and local
delivery behavior. The local quota accepts 16 local packets and refuses the
17th even though relayed traffic can still acquire its own custody entries.

This is sufficient to accept the intended controlled diagnostic, while
retaining an explicit exact-contract discrepancy. It does not establish
numerical campus parity or identify which behavior better reproduces OPNET.
The replay cases stop immediately after the custody divergence; subsequent
admissions, queue drain, duplicate downstream transmissions, delivery and
delay are not measured. In particular, there is no local-origin admission
attempt after the divergent retry, so a direct effect on local quota has
not been demonstrated. PHY/ECC and autonomous MAC traffic are outside scope.

## Recommended next step

Keep the current production default. First count this specific event in the
accepted campus traces: repeated relay admission of the same source and
application identity following a DACK, especially at node 8 on the 8-to-2
path. Resolve whether the previous custody owner is still present, how long
extra owners persist, and whether they consume service or alter another
flow's admissions.

If the existing traces lack identity/custody lineage, use a bounded observer
replay around DACK loss/retry and subsequent queue drain. A matched optional
custody variant is warranted only if this behavior occurs often enough to
matter. Any later performance decision should use the existing plus/minus
10 percent goal for campus delivery and delay by flow. Another full-campus
run is not justified solely by T23's completion.

The reproducible raw comparisons, source hashes and complete differences are
in `findings.json`; the 81 recomputed milestone checks are in
`common_assertions.json`. No production source or owner evidence was changed.
