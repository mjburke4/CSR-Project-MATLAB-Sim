# Tranche 6 source audit

Read-only audit of ns-3 commit `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, tree `b611b233fb369569b98f0914ece24d029ccc2f42`. The checkout at `/workspace/scratch/4bc527402fde/CSR-Project-NS3-part2` was clean. MATLAB references below are the Tranche 5 accepted tree at `/workspace/scratch/1a5b1ad6ce1b/publication`, local commit `1f515648de89c950a8bc6beccfb6a0f815a82eb9`; its two additional provenance documents were untracked and not involved in behavior inspection.

## Shared limitation: DATA exhaustion is terminal without route invalidation

`model/csr-hop-layer.h:4406–4750` performs final-expiration pass before resend admission, waits twice the ordinary resend interval after the final transmission, and releases NSDP/outstanding/resend ownership on exhaustion. Lines 4469–4478 and 4594–4600 explicitly distinguish ordinary DATA from controls carrying Packet_Tx_Info and forbid the generic link-failure callback on DATA exhaustion. `model/csr-nwk-layer.h:2397–2483` retains an unsent packet when no usable route exists, scanning other destinations. Once submitted to HOP, it is not returned to NWK on exhaustion.

MATLAB `+csr/+hop/Layer.m:463–516` and `+csr/+nwk/Layer.m:337–362,427–449` implement the same DATA lifecycle. The 135-second administrative outage can outlast the roughly eight-second minimum retry lifetime; a still-selected stale route therefore consumes packets, while an already-invalid route retains unsent packets. This is a source-backed explanation, not proof that every numerical recovery difference is caused by that path. The accepted 60-second setting had substantial pre-outage churn and is not evidence of an optimal outage detector.

The first no-route relay reception suppressed without ACK followed by duplicate ACK is also shared: ns-3 `csr-hop-layer.h:3514–3536`, MATLAB `hop/Layer.m:314–319`. The MATLAB application ledger explicitly accounts this as an unretained ACK. Replacing this policy would be a separate protocol change.

## Concrete port discrepancy 1: passive observation is conflated with NWK freshness

ns-3 `csr-hop-layer.h:937–962` updates only the HOP neighbor table for any decoded non-SNMP packet, called at 2736 before address filtering. The HOP table supports link observations; it is distinct from `CsrNetLayer::m_nwkNeighbors`. NWK `lastHeardSec` is written at these source locations only:

| Path | Source location | NWK refresh |
| --- | --- | --- |
| Qualified NeighborCheck success callback, after obsolete discovery-Verify guard | `csr-nwk-layer.h:824–862` | Yes |
| Authenticated Discover with missing group key | `csr-nwk-layer.h:4399–4424` | Yes |
| HELLO/Discover or first NeighborCheck/routing control delivered through ProcessHello | `csr-nwk-layer.h:4484–4560`; HOP first-delivery gates 3227 and 3336 | Yes |
| Received Verify in ProcessHello | `csr-nwk-layer.h:7320` | Yes, redundant with ProcessHello |
| DATA, ordinary ACK/DACK, overheard non-HELLO, duplicate NeighborCheck/routing, KEY_REQUEST, KEY_UPDATE | HOP dispatch and key callbacks | No |
| SNMP | HOP early bypass | Neither HOP nor NWK refresh |

MATLAB `NetworkSimulation.receive:431–435` calls NWK `observe` for every non-SNMP decoded envelope. `nwk/Layer.observe:306–310` invokes `Neighbors.observe:60–69`, which updates the NWK timestamp and clears Stale. DATA/ACK/overheard/duplicate/key traffic therefore shifts network freshness deadlines when it should only update passive radio/link observations. The correction should separate these observations and refresh NWK only at accepted control-delivery/callback boundaries, including each first routing section before reassembly completes.

## Concrete port discrepancy 2: freshness expiry destroys extra state

Source `CheckNeighborFreshness:6741–6889` calls `MakeNeighborInactive:4096–4196`. This clears admission/check flags, reassembly/routing sequencing, direct learned capability and transit candidates. The freshness path additionally clears requests, inbound/outbound snapshots, INFO and sets stale. It schedules a coalesced chirp. It **does not** increment `numFailures`, clear `keySendActive`, cancel the admission retry, or reset key/request/overheard timing and validity histories.

MATLAB `Neighbors.checkFreshness:365–375` calls the generic `failNeighbor:184–197`, which increments Failures, clears KeySendActive, increments Generation and cancels RetryEvent. Repeated quiet-peer expiry therefore changes link cost (`nwk/linkCost:42–43` uses failures in 3-dB margin tests) and rejects outstanding callbacks that the source still owns. The failure penalty affects cost; the current MATLAB linkCost rate/power calculation itself is independent of Failures.

Separate a source-backed freshness transition from explicit generic failure; retain the latter's existing behavior unless separately justified. Preserve key/retry owners at expiry, clear the correct route/snapshot state, provide the exact `freshness_timeout` event cause and timestamp/age/timeout details, and test a successful completion arriving after expiry. Source `ScheduleAdmissionRetry:3836` rejects active peers, while `EvaluateNeighborAdmission:4214` additionally rejects stale peers; a preserved timer may harmlessly fire while stale.

## Existing deliberate differences to preserve

- MATLAB pauses queued retransmission timing until actual MAC transmission. ns-3 keeps a provisional timestamp and initial confirmation across requeue (`csr-hop-layer.h:4731–4750`). This difference is already explicitly accepted in Tranche 2 and `docs/parity-ledger.csv`.
- MATLAB makes MAC/resend admission transactional and refuses unretained relay custody rather than reproducing source overload bookkeeping loss; accepted Tranche 2 difference.
- Bounded NWK control cycles/storage are explicit MATLAB policies; do not silently enlarge them to improve outage delivery.
- NeighborCheck failure does not automatically inactivate the neighbor in either implementation. Source `NoteNeighborCheckFailure:4453–4480` only clears check flags/restores pending discovery-check state and schedules admission retry.

## Recommended bounded tranche and verification

Implement the two NWK freshness corrections as one cohesive change; retain DATA/HOP retry and custody semantics, PHY/ECC and the accepted Tranche 5 scenario definitions. Use deterministic unchanged-source contracts for refresh eligibility, strict expiry, no failure penalty and preserved key/retry state. Rerun original recovery settings after correction, retaining per-app/drop/deadline evidence and explicit rediscovery timestamps. Delivery improvement is not established until actual MATLAB results return. The separate source outage fixture should identify whether shared protocol limits remain after corrected freshness behavior.

Source SHA-256: HOP `0a826930bab43db429a2a3bd905672b370774274f7de826abf180f002156f10b`; NWK `bc871898c628eec08c82636507cb23cbf6b29d80a3738be18466cb0a9525ecfc`; MAC `64a71ad280ba14ab2b00d5d2b9dac708fabea939dfa385ad62dd73e5e40203e9`.
