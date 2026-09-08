# Current ns-3 source map for the MATLAB port

Inspected 2026-09-08. Authoritative reference: `mjburke4/CSR-Project-NS3-part2`, main commit [`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`](https://github.com/mjburke4/CSR-Project-NS3-part2/commit/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b). This is a source inspection, not a fresh ns-3 or MATLAB execution report.

## Baseline and recent change boundary

Current main merges PR #50, `6d32ab2` (MAC acquisition and HOP ACK-window ordering), after PR #49's reconstruction. The [current residual review](https://github.com/mjburke4/CSR-Project-NS3-part2/blob/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b/docs/opnet-residual-review.md) explicitly retains PHY/ECC; its BER timing experiment was reverted before publication. MATLAB should initially match that retained implementation. Porting the experimental BER interval behavior would be an intentional change requiring a separate decision.

The review reports 38/38 executable workflows passing for the final two-fix tree. Its fresh 6,000-second multihop run reports 2.06950 sent packets/s, 1.96150 received packets/s, and 103.18101 seconds mean of bucket delay means, respectively +2.86%, +3.15%, and -8.49% versus the selected OPNET run. These are recorded upstream results, not tests rerun in this port. Historical 60,000-second hidden-node results in that document do **not** belong to the final two-fix candidate. Neither the small application residuals nor delivery accounting establishes equivalent ECC-drop statistics.

## Subsystem ownership and MATLAB implementation targets

| Subsystem | Current source and entry points | Behavior to preserve | MATLAB boundary |
| --- | --- | --- | --- |
| Scenario/application | [`csr-opnet-scenario-runner.cc`](https://github.com/mjburke4/CSR-Project-NS3-part2/blob/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b/csr-opnet-scenario-runner.cc), `ImportedScenario`, `ConnectStack`, `SendFlowPacket` | Node/radio/topology configuration; periodic generator attempts; ordered discovery, topology, gateway/route, destination and NSDP admission gates; flow destination policy; exact generated-size meaning | `csr.scenario` structs, runner and traffic processes; count attempted and admitted generation separately |
| NWK/ARL routing | [`model/csr-nwk-layer.h`](https://github.com/mjburke4/CSR-Project-NS3-part2/blob/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b/model/csr-nwk-layer.h), `CsrNetLayer::Send`, `ReceiveFromHop`, `ProcessHello`, `StartDiscovery`, `ConfigureLinkControl`, owned routing-control callbacks | Discovery/admission, gateway finding, route cost/capability/path, self-route advertisement, reliable INFO/UPDATE/FLUSH propagation, route loss/recovery, custody without route, NSDP and relay holdoff | NWK object owns route and neighbor tables plus routing retries; keep it independent of native simulator nodes |
| HOP/reliability | [`model/csr-hop-layer.h`](https://github.com/mjburke4/CSR-Project-NS3-part2/blob/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b/model/csr-hop-layer.h), `SendData`, `ReceiveFromMac`, `HandleAckFrame`, `HandleDackFrame`, `CheckDack`, `CheckResend`, `NotifyMacFrameSent` | Per-neighbor flow window, outstanding/resend custody, cumulative ACK/DACK, retry expiration, partial-destination ownership, security state, TX-sent time and capacity release | HOP owns reliable packet identity/state; MAC reports actual TX completion rather than pretending enqueue means sent |
| MAC | [`model/csr-mac-core.h`](https://github.com/mjburke4/CSR-Project-NS3-part2/blob/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b/model/csr-mac-core.h), `State`, `GetOpnetSlotRange`, `SlotTick`; much implementation resides in `csr-net-device.h` | IDLE/SEARCH/TRACK/TX, half duplex, queue ordering, DSCP, reservation choice/decay, wake/holdoff, preamble freshness and selection, concatenation, ACK servicing, acquisition/capture and overhearing | Cohesive MAC state machine; do not map CSR onto a stock Wi-Fi MAC |
| Device/radio delivery | [`model/csr-net-device.h`](https://github.com/mjburke4/CSR-Project-NS3-part2/blob/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b/model/csr-net-device.h), `SendFramesToPeers`, `BeginReceiveSignal`, `EndReceivePreamble`, `EnableOpnetAlignedDutyCycling`, `AssignStreams` | Physical peer fanout, closure before delivery, propagation delay, all active interfering signals, admitted-SYNC callback ordering, tracked RX acceptance, radio state | Channel and simulator adapter handle delivery/scheduling; protocol core keeps acquisition state. `CsrNetDevice` derives from ns-3 `Object`, not a standard ns-3 IP-facing `NetDevice` |
| PHY/channel | [`model/csr-phy-model.h`](https://github.com/mjburke4/CSR-Project-NS3-part2/blob/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b/model/csr-phy-model.h), `ComputeFrontEnd`, `CalculateBer`, `AllocateErrors`, `EvaluateEcc`, `EvaluateAllocatedRx` | Band overlap, three-path gain, background noise, SYNC threshold, distinct same/different-rate interference, interval BER/error draws, inclusive full-packet ECC, rejection precedence | Pure functions plus bounded active-signal state. Network PHY abstraction; waveform generation is unnecessary |
| Packet/wire semantics | [`model/csr-opnet-packet-model.cc`](https://github.com/mjburke4/CSR-Project-NS3-part2/blob/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b/model/csr-opnet-packet-model.cc), `GetFixedSizeBits`, serializer; [`model/csr-opnet-envelope.h`](https://github.com/mjburke4/CSR-Project-NS3-part2/blob/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b/model/csr-opnet-envelope.h), `CsrAnnotateOpnetEnvelope` | Physical byte count, inherited payload nesting and field order, separate zero-bit metadata, profile-specific security overhead | Packet struct with separate payload bytes, modeled wire size and observation identity; byte arrays for control serialization |
| Routing/security records | [`model/csr-arl-routing-message.h`](https://github.com/mjburke4/CSR-Project-NS3-part2/blob/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b/model/csr-arl-routing-message.h), builder/parser; `csr-hop-security.{h,cc}`, `csr-legacy-crypto.{h,cc}` | ARL stream sectioning/reassembly, mission/group/pairwise envelope policy, authenticated/replay outcomes that affect admission/reliability | Reproduce wire widths and behavioral acceptance; any temporary security abstraction must be explicit, not labeled cryptographic parity |
| Observation | [`model/csr-differential-trace.h`](https://github.com/mjburke4/CSR-Project-NS3-part2/blob/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b/model/csr-differential-trace.h), `CsrDifferentialTraceEvent`, `CsrDifferentialAppTag` | Stable app identity, ordered events, drop reason, radio/queue/route fields; correlation identity adds no radio bytes | MATLAB counters plus optional bounded trace export with identity preserved through retries |

## Source-backed first-tranche primitives

The [wire-format definitions](https://github.com/mjburke4/CSR-Project-NS3-part2/blob/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b/model/csr-wire-format.h) define seven operational rate keys. Nominal keys are not exact payload bit rates:

| Nominal key, kbit/s | Four-bit interval, microseconds | Actual payload bit rate, bit/s | Mode |
| ---: | ---: | ---: | --- |
| 8 | 510 | 4 / 0.000510 | Legacy spread |
| 16 | 254 | 4 / 0.000254 | Legacy spread |
| 32 | 126 | 4 / 0.000126 | Legacy spread |
| 64 | 62 | 4 / 0.000062 | Legacy spread |
| 128 | 30 | 4 / 0.000030 | Legacy spread |
| 500 | 8 | 500000 | DPSK |
| 1000 | 4 | 1000000 | DQPSK |

`LEGACY_SOURCE_EXACT` caps operation at key 128; the compatibility-named `EXTENDED_DQPSK` profile includes both high rates. Baseline tests should explicitly select min=max=8; separate tests may select extended rates. The compact ns-3 speed byte encodes high keys as 0x81/0x82, but the physical OTA Speed field is 16 bits. Do not infer a second DQPSK mode from the profile's old name.

`CsrNetDevice::SendFramesToPeers` gives the airtime contract, where `B` is the sum of modeled MAC-frame envelope bytes in the transmission:

```text
S0 = 4 / 0.000510 bits/s
P = 7888 bits (long) or 104 bits (short)
preamble duration = P / S0
packet duration = (P + 48) / S0 + (8*B + 32) / payload_bit_rate
```

Thus long preamble is 1.00572 seconds and short preamble is 0.01326 seconds. The MAC's 0.013-second slot tick and 0.988-second periodic wake are separate constants, not replacements for these airtimes. Header SOF/speed/length contributes 48 S0 bits; the 32-bit FCS uses the payload rate. Propagation delay is distance divided by `CsrPhyModel::SPEED_OF_LIGHT_METERS_PER_SECOND`.

The [envelope review](https://github.com/mjburke4/CSR-Project-NS3-part2/blob/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b/docs/opnet-packet-envelope-parity.md) and actual envelope functions establish:

| Quantity | Value and qualification |
| --- | --- |
| Concrete node IDs | 0 through 0xFFFFFE; 0xFFFFFF reserved for broadcast; 24-bit big-endian wire addresses |
| Bare DATA MAC envelope | Application payload + 7-byte NWK + 8-byte HOP + 17-byte MAC = application + 32 bytes |
| Production Pairwise16 DATA | Bare DATA + 5 security bytes; production is current runner default |
| ACK envelope | Bare exact 25 bytes, cumulative ACK/DACK 41 bytes; production Pairwise16 adds 5 bytes |
| MAC/HOP bounds | MAC DATA queue 512; ACK queue 256; HOP resend queue 512; global outstanding DATA cap 16; concat cap 16 segments |
| Core timers | MAC slot 0.013 s, holdoff 0.3 s; HOP resend default 2 s and DACK hold default 20 s; respect owning state machine before scheduling |
| Radio defaults | `CsrPhyProfile`: 0 dBm TX, -106.975 dBm noise at 1 MHz, 30 MHz lower band edge, 1 m antenna heights, SYNC mean -11 dB/variance 0.25 dB squared, ECC fraction 0.1 |
| Scenario radio defaults | `ImportedNode`: 400 MHz RX/TX, min/max TX -36/33 dBm, rate keys 8/128, 10 dB link margin. `main` overrides radio default power/frequency/height from node configuration |
| ECC | Preamble excluded; fixed header and payload/FCS protected; correctable errors = floor(0.1 * protected bits); accept at or below threshold after earlier receive-state gates |
| ARL routing sections | Maximum section 700 bytes including 6-byte prefix; 24-bit IDs, 16-bit hop count, 32-bit route cost; stream records may span sections |

For a new MATLAB scenario schema prefer unambiguous `applicationPayloadBytes`. Upstream imported `flow.packetBytes` means something else: `SendFlowPacket` removes eight bytes of legacy application bookkeeping and seven NWK header bytes before creating its application payload. Importing `packetBytes=200` therefore produces 185 application bytes, 192 NWK bytes, and 217 bare/222 production MAC-envelope bytes. This conversion belongs in the importer, not in every packet constructor.

## Framework machinery to replace, not transliterate

- Replace `Object`/`TypeId`, `Ptr<>`, `CreateObject`, `Callback`, `TracedCallback`, `Packet`/`Tag` and `Buffer::Iterator` machinery with ordinary MATLAB handles/structs, function handles, byte vectors and trace records. Preserve ownership and modeled bytes, not ns-3 storage sizes.
- Replace `Simulator::Schedule/Cancel`, `EventId`, ns-3 `Time` and stream allocation with an adapter contract. Preserve deterministic time-plus-sequence ordering and explicit cancellation. `CsrOpnetTic()` is 1/36 MHz quantized to 28 ns at the current ns-3 nanosecond resolution; exact equivalence of near-simultaneous events remains a later controlled-test question.
- Replace CMake registration, standalone ns-3 wrappers and `std::cout` diagnostics with MATLAB package setup, scenario functions, unit/subsystem tests and optional logging. Do not implement IP, sockets or Wi-Fi just because ns-3 has them; this stack connects app/NWK/HOP/MAC directly.
- Keep the existing OPNET import/extraction/comparison Python tooling usable outside MATLAB where practical. Rewriting the tfile decoder or hardened subprocess publication workflow offers no baseline networking capability.

## Validation handoff and risk priorities

Use current source tests as behavioral specifications, not a claim of MATLAB coverage: `csr-wire-format-smoke.cc`, `csr-opnet-packet-envelope-smoke.cc`, `csr-phy-front-end-smoke.cc`, `csr-phy-ber-ecc-smoke.cc`, `csr-live-high-rate-dqpsk-smoke.cc`; then MAC/HOP queue, reservation, receive-contention, ACK-window and retry tests; then `csr-nwk-autonomous-convergence-smoke.cc` and the ARL routing/security tests. The repository tracks 36 `*-smoke.cc` files plus the demo and scenario-runner programs.

The [scenario/differential runbook](https://github.com/mjburke4/CSR-Project-NS3-part2/blob/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b/docs/opnet-scenario-differential-harness.md) defines rectangular `csr-opnet-scenario-v1` CSV run/node/flow rows. `utils/testdata/csr-scenario-fixture.csv` and the reservation/collision fixture provide reusable inputs. Preserve application/MAC/security profile choices; historical compiled variants are selected explicitly by evidence, never inferred from topology names. Start with source-derived deterministic airtime/envelope/front-end vectors and a collision-free MATLAB packet transfer. That first transfer is a simulation foundation, not operational MAC/routing completion.

For stochastic comparison, equal numeric MATLAB and ns-3 seeds do not imply equal draw sequences. Use controlled error-free or forced-error subsystem cases, then multiple-seed aggregate distributions with matched duration and offered traffic. Compare sent versus delivered identities and sizes before numerical metrics. The [aggregate contract](https://github.com/mjburke4/CSR-Project-NS3-part2/blob/486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b/docs/opnet-aggregate-comparison.md) requires matching scenario/statistic/unit/aggregation identities and preserving missing buckets. A mean of bucket latency means is not packet-weighted mean latency.

Major risks worth resolving early: physical envelope bytes versus metadata; rate keys versus actual bps; overlapping-signal acquisition versus simple PER-only reception; HOP custody and actual send-time retry ownership; routing-control section/retry ownership; silent security/profile substitutions. Low-impact micro-ordering and unavailable OPNET event traces should not block the first integrated MATLAB network. Battery, supervisory and BBN behavior remain excluded by project scope.
