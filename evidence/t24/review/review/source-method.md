# T24 source semantics and observability review

T24 is an offline census of accepted 6000-second campus traces, with traffic active from 300 to 6000 seconds. It does not execute MATLAB or ns-3 and does not change production behavior. Current upstream main was checked during T24 and remains `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`; the analysis retains the exact T20 trace inputs and T23 source contract at that commit.

The independent review read the native NWK and HOP headers and MATLAB NWK layer directly. Native source hashes are `bc871898c628eec08c82636507cb23cbf6b29d80a3738be18466cb0a9525ecfc` (NWK) and `0a826930bab43db429a2a3bd905672b370774274f7de826abf180f002156f10b` (HOP). MATLAB NWK hash is `7ef09931c83c55697ce96b400ee1d90459a44af4c0527b396829d62ab9125300`.

## Identity and custody instances

Application identity is `(src, dst, sequence)`. In NWK enqueue, forward and admission events, and in HOP admission, completion, feedback and delayed-capacity-release events, the CSV `sequence` is the differential application tag. HOP reliability sequence is separately recorded in `detail.hop_sequence`; it must not replace application sequence. Include transmitter/receiver node and peer when joining the HOP state. A global HOP sequence key without lifetime checks would be unsafe if the 16-bit sequence wraps.

Each native `ReceiveFromHop` relay callback increments flow NSDP and inserts a new queue entry. Native NWK has no application-identity duplicate suppression at this point. Every `nwk_enqueue` therefore establishes a separate owner, even when its application identity has appeared before. Distinguish a repeated enqueue after an earlier owner has completed from a repeated enqueue while another owner remains. Only the latter creates simultaneous multiple NSDP owners of one application.

Both accepted scenarios specify `flow_dscp=0` for all six flows and the `legacy-send-only-no-dscp` application profile. Native NWK appends zero-DSCP arrivals and scans from the head. Within an application identity, the oldest waiting instance is consequently the correct match for a forward. `nwk_admission` with reason `admitted` is written before removing that queue entry; `nwk_forward` follows, then HOP `SendData` produces `hop_admission`, all synchronously at the same simulation time. Verify identity, node, next-hop and time across that chain. Failed NWK admission events are polls, not distinct owners or refused application admissions.

MATLAB `receiveData` uses permanent `Seen(SourceId, Id)` suppression, and `enqueueApplication` separately checks `pendingPosition` before adding an owner. Removing `Seen` alone cannot implement multiple native custody entries: pending ownership, release and matching would also need to support instance identity. This review does not authorize or implement that behavior change.

## Release and capacity endpoints

Native `nwk_nsdp_release` deliberately contains only flow identity, with no application sequence. It is emitted synchronously by `NotifyNsdpFromEntry` before the identifying `hop_completion`. Exact per-instance release uses the identifying completion event after validating the flow-level release counts and same-time ordering; blindly assigning each unlabelled release to the oldest application would be incorrect.

ACK and terminal no-ACK completion release both NSDP custody and HOP capacity. DACK completion releases NSDP immediately but moves the HOP entry into delayed hold. The later `hop_capacity_release` with matching HOP sequence releases capacity only; it must not release NSDP again. Thus custody duration ends at completion, while HOP capacity duration ends at completion for ACK/no-ACK and at delayed expiry for DACK. Censor unfinished custody and capacity intervals at the 6000-second stop; do not count their ages as completed durations.

Conservation should be checked separately for enqueue/forward/waiting owners, enqueue/completion/NSDP owners, and admission/immediate-or-delayed-capacity-release/held capacity. Validate reported NSDP snapshots against independently accumulated enqueue-minus-release state. Attribute repeated-owner work by its actual local custody instance, and avoid calling all such work avoidable: only a policy counterfactual can establish what would disappear or move in time.

## Linking DACK-marked replay

At a relay, native HOP determines ACK/DACK using pre-enqueue NSDP, invokes NWK synchronously, then writes `hop_feedback`. Match each relay enqueue with its following same-time feedback using receiver node, ingress peer and application identity. A feedback with `first_reception=1` and a one-count NSDP increment substantiates the callback. To classify a repeat as DACK-marked HOP replay, additionally require an earlier DACK feedback at the same receiver/ingress peer/HOP sequence and application identity. A repeated application arriving on a different HOP sequence is a different category, potentially reflecting duplicate propagation from an upstream relay.

HOP's receive register treats ACK-marked entries as duplicates but permits DACK-marked sequences to be reassessed. Under security replay detection, the exception is restricted to a DACK-marked reliable DATA sequence. A later ACK/DACK decision may match MATLAB despite native post-callback owner multiplicity, as T23 demonstrated.

## Conclusions permitted by these traces

The traces can establish repeated enqueue frequency, simultaneous-owner duration, queue service consumed by tagged repeated instances, and observed custody/capacity residence, with exact event joins and explicit pending-at-stop state. They can test whether duplicate ownership is frequent enough to explain the observed native node-8 backlog scale.

They cannot establish the end-to-end delivery improvement of suppressing native duplicates, the MATLAB outcome after enabling them, or a unique cause for stochastic cross-engine differences. ACK loss can cause no-ACK completion despite eventual application delivery, and duplicate receive events must remain separate from unique delivered applications. Cross-engine application sequences and random draws are not paired. Historical seed 128 lacks equivalent detailed native custody events; unavailable measurements are not zero.

## Physical-transmission attribution limit

The pinned `model/csr-net-device.h` was additionally fetched and byte-matched to the archived tracked-source manifest (`112f9ac73e2ced44a40d6fcc3dc0a8d2cf19996f4f1d52adb0b9a5fbfe103dfb`). Its `tx_start` record uses only `frameCopies.front()` for node/peer/HOP sequence/type, while `sizeBytes` is the sum of all aggregate members. A join from `tx_start` therefore sees a leading member only. It cannot establish a complete per-owner transmission count or assign aggregate airtime to repeated owners. Full NWK-forward counts, HOP admissions and HOP capacity residence provide the supported service measures for T24.

HOP retry frame copies can remain queued at MAC after their HOP resend entry is released. `NotifyMacFrameSent` explicitly tolerates an absent resend entry; no owner-active constraint should be imposed on an observed later transmission. These facts are source semantics, not evidence that every repeat generated an extra OTA transmission.
