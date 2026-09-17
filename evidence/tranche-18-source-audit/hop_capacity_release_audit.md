# T18 read-only HOP capacity and release audit

Scope: immutable MATLAB `csr17/+csr/+hop/Layer.m`, compared with native
`csr-hop-layer.h` at `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.
Native SHA-256: `0a826930bab43db429a2a3bd905672b370774274f7de826abf180f002156f10b`.
MATLAB SHA-256: `a56cd54fcd8bd863958b1addfc861f16f434ab79e4993fb182936a8b2b454f67`.
No production edits, MATLAB execution, or new numerical cause attribution.

## Result

The normal DATA admission and capacity-release contracts are equivalent at the
configured baseline. No new, unaccepted DATA HOP policy defect was established.
The queued-retry clock and overload differences are real, but explicitly accepted
since T2; their contribution to the campus source distribution is unmeasured.
Keep them unchanged while observing node 5 local/relay competition and the 4-to-5
retry bottleneck.

## Equivalent contracts

| Contract | MATLAB `Layer.m` | Native `csr-hop-layer.h` |
| --- | --- | --- |
| DATA admission allows global pending 16 to become 17; neighbor outstanding must be at most threshold; effective neighbor window is threshold + 1. Both new-peer thresholds start at zero. | 51-74, 91-97, 566-568; defaults 687-689 | 469-497, 529-550, 654-702, 1691-1695 |
| Ordinary ACK releases neighbor/global capacity before NSDP; every third ACK can increase threshold through 16, including a third ACK of a retried packet, then retry resets ACK accumulation. | 436-447 | 3827-3895 |
| DACK releases NSDP immediately but holds neighbor/global capacity; normal hold 20 s, doubled to 40 s when resend count has reached two; DACK clears ACK accumulation without shrinking threshold. | 424-434; defaults 687-689 | 4203-4271; default hold 974 |
| Each DACK schedules a scan for nominal expiry + TIC; a scan releases every nominally expired hold and requests coalesced HOP-origin NWK wake at one further TIC. | 433, 450-460, 642-649 | 4050-4164, 4263-4271, 863-885 |
| Final DATA expiration releases NSDP before capacity, resets ACK accumulation, shrinks threshold by one down to zero, and wakes NWK. Ordinary DATA failure does not invoke generic link failure. | 464-471, 511-516 | 4432-4476, 4596-4661, 4714-4718 |
| All final expirations in the scan precede retry admissions. Initial retry clock is disabled before actual MAC sent confirmation. Final ACK grace is twice normal resend period. | 91-94, 183-192, 463-493 | 619-650, 4380-4384, 4424-4446, 4725-4750 |
| Every readable feedback packet, including unknown feedback and disabled single-DACK, requests a coalesced HOP-origin +TIC wake. Cumulative DATA ACK bits dominate overlapping DACK bits; HOP ownership mutations precede cancellation at MAC. | 356-383, 642-649 | 2809-2867, 3638-3683, 863-885 |
| DACK decision uses pre-enqueue NSDP on a first relay reception; final-local delivery always ACKs. Final-local ACK is admitted before delivery callback; relay delivery callback precedes feedback admission. | 307-349 | 3537-3634 |
| NSDP-release callback does not create a same-time NWK pump; HOP owns the delayed wake. | `nwk/Layer.m` 397-405, 407-413 | `csr-nwk-layer.h` 1344-1388 |

## Existing accepted differences: observe, do not silently change

1. **Queued retry clock.** MATLAB 484 sets `Confirmed=false` on retry enqueue;
   checks 470 and 478 require confirmation before further timeout/retry action.
   Native 4741-4750 retains `initialTxConfirmed=true` and stores provisional
   enqueue time. Another list-wide timer may act on a native retry before its
   actual TX. MATLAB waits for `notifySent` 184-192. This is documented in
   `docs/parity-ledger.csv` 21 and `docs/tranche-2-hop.md` 75-79, and explicitly
   preserved in `docs/tranche-6-source-audit.md` 38. A relevant observation is
   whether a retry remains queued longer than its nominal 2 s / final 4 s
   deadline, and whether a native scan actually occurs in that interval.

2. **Transactional overload.** MATLAB `canSend` 51-53 includes a resend-capacity
   guard, refuses before losing custody at 81-87, and rolls back initial HOP
   ownership on MAC refusal at 99-104. Native admission 662-679 does not include
   resend queue size; 4360-4374 drops the resend owner on 512-entry overflow after
   flow capacity has already increased, and 1813 still forwards to MAC. MATLAB
   retry MAC refusal is terminal at 489-492; native 4749-4750 has no such HOP
   return-status path. This is accepted in ledger 20 and `tranche-2-hop.md` 69-74.
   DATA alone is limited to 17 outstanding, so 512 resend overflow needs other
   traffic or deliberately modified bounds. Do not presume this explains campus.

3. **Explicit relay custody refusal.** MATLAB 335-344 clears the receive mark
   and suppresses feedback on relay refusal. Native NWK delivery callback is
   void (3556-3566), and feedback follows it without a refusal handshake. This
   is accepted in `tranche-2-hop.md` 80-84. It can matter only if refusal occurs.

## Ordering distinctions with no demonstrated scheduling consequence

- On DACK native releases NSDP at 4213 while the resend entry still exists,
  then adds the hold and removes resend ownership (4261-4278). MATLAB adds the
  hold and removes resend ownership before releasing NSDP (429-431). Baseline
  NSDP callbacks only update custody and emit observations; neither pumps NWK.
  The final same-event state and scheduled wake agree. A snapshot taken inside
  the NSDP callback must not be mistaken for the post-completion state.
- DACK expiry removes the hold before emitting/scheduling in MATLAB 456-460;
  native schedules its wake before erasing the hold at 4161-4164. No callback
  runs between those operations; this is equivalent at the next event boundary.
- Reliable-control duplicate partial ACKs are suppressed in MATLAB 396 but
  deliberately notify native control success again at 3730-3733 and 3938-3964.
  This is outside the DATA-capacity question; a separate bounded control audit
  would need to inspect the callback's idempotence before calling it a defect.

## Suggested T18 observation fields

Record event ordinal plus full-precision time, node, peer/next hop, application
source/destination/sequence, HOP sequence, local-origin versus relay, retry
count, and reason. Preserve both before/after values of pending DATA, neighbor
outstanding, threshold, NSDP count, resend owner count and DACK-hold count at
admission and completion boundaries. Include signed global/neighbor spare
allowances, acceptance/blocked reason, and MAC enqueue outcome.

For the 4-to-5 path, link each initial admission, actual TX, retry enqueue,
feedback generation, feedback actual TX, feedback reception, terminal sender
retirement and end-to-end delivery by identity. Report queued-retry residence,
normal/final retry deadline, whether its timer was confirmed, DACK expiry,
HOP-origin wake request/due/fire and coalescing. Keep DATA reception from node 4
distinct from node 5's own DATA admitted toward its next hop.

Native already exports `hop_admission`, `hop_completion`,
`hop_capacity_release`, `hop_feedback`, and `nwk_nsdp_release` details; normalize
MATLAB event names to those meanings without changing state transitions.
MATLAB's existing `hop_admit`/`hop_ack` events carry post-state; its
`hop_dack`/`hop_failed` events do not carry all capacity fields. An observer can
take a read-only `admission(peer)`/`stats()` snapshot, but must label snapshot
boundaries, especially `network_custody_release` inside HOP completion.

No source-backed basis was found to change PHY/ECC, continuous time, DATA retry
limits, DACK holds or admission thresholds as part of this tranche.
