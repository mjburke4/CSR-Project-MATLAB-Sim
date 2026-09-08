# Tranche 2 frames and configuration contract

Source baseline: `mjburke4/CSR-Project-NS3-part2` main
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. The relevant implementation is
`model/csr-opnet-packet-model.cc`, `csr-wire-format.h`, `csr-hop-layer.h`,
`csr-mac-core.h`, and `csr-net-device.h`; byte fixtures come from
`csr-opnet-packet-envelope-smoke.cc`.

## Runtime frame contract

`csr.hop.Frames.data(app, hopSource, nextHop, sequence, radio)` constructs one
logical DATA frame. `acknowledgment(hopSource, peer, sequence, ackBitmap,
dackBitmap, radio)` constructs cumulative feedback. The MAC aggregates these
frames in a cell array named `Segments`, preserving order.

| Field | Meaning |
|---|---|
| `Id` | `uint64` transmission observation ID; initialized to zero and stamped by integration |
| `SourceId`, `DestinationId` | Physical hop endpoints; exact double integers in the 24-bit address space |
| `App` | Original application packet, including its own observation ID and original/final endpoints |
| `Kind` | `DATA`, `ACK`, or `DACK` |
| `Sequence` | Live source 16-bit sequence, represented as `uint16` |
| `AckRequired` | HOP DATA retry ownership flag |
| `HasAckWindow` | Whether feedback carries the two cumulative registers |
| `AckBitmap`, `DackBitmap` | Exact `uint64` receive registers; never converted through double |
| `Dscp` | DATA priority or source ACK value 7; aggregate DSCP excludes ACK members |
| `RateKeyKbps`, `Preamble`, `TxPowerDbm` | Selected physical transmission settings |
| `GeneratedSeconds`, `ApplicationPayloadBytes` | Application observation metadata |
| `WirePayloadBytes` | Complete modeled MAC member bytes, excluding OTA preamble/header/FCS |
| `EnvelopeProfile` | `bare` or explicitly `pairwise16-size-only` |
| `RetryCount` | Observation field; the HOP resend entry owns retry state |

An unresolved `TxPowerDbm=[]` may exist during construction; integration resolves
it to the transmitting node's radio setting before MAC queue admission. DATA
keeps the supplied application object unchanged. Constructors do not apply
routing decisions, authenticate packets, or increment a sequence counter.

## Modeled sizes and aggregation

| Member | Bare bytes | Pairwise16 size-only bytes |
|---|---:|---:|
| DATA | application + 17 MAC + 8 HOP + 7 NWK | application + 37 |
| Single ACK/DACK | 25 | 30 |
| Cumulative ACK/DACK | 41 | 46 |

The five additional bytes only reproduce the source envelope size. They do not
provide authentication, encryption, replay protection, keys, or a real security
record. A complete security implementation remains future work.

The source aggregate sums **complete member sizes**, including each 17-byte MAC
envelope; it does not replace them with one shared MAC header. The OTA wrapper is
then added once by `csr.phy.airtime`. At 8/16/32/64/128 kbps the MAC uses strict
less-than packing limits of 256/512/1024/2048/4096 bytes. At 500/1000 kbps the
source supplies no concatenation capacity and sends the queue head alone.

Aggregate rate is the slowest selected rate. Power is the maximum **among
members at that slowest rate**, matching `CsrMacCore::DoTx`; a faster member's
larger power does not override it. Aggregate DSCP is the maximum across DATA
members only. Selection, retries, queue limits, reservation and preamble policy
remain MAC/HOP responsibilities.

## Serialization boundary

`serializeModel(format, fields, payload)` and `deserializeModel` implement the
eleven exact fixed field layouts in `CsrOpnetPacketModel`, using its original
lower-camel-case field names. All integers use big-endian order. Node IDs occupy
three bytes. The NWK DSCP byte follows inherited payload; OTA FCS follows payload;
OTA long and short preamble placeholders contain 986 and 13 zero bytes.

The legacy modeled `Hop` packet has an eight-bit `sequence8` field, whereas the
current live ns-3 HOP logic uses a 16-bit sequence in its compatibility header.
Both facts are preserved explicitly. The MATLAB runtime keeps `Sequence` as
`uint16`; the standalone legacy serializer accepts its separate `sequence8`
field and rejects overflow. It does not silently truncate live sequence values
or pretend its bytes encode every item of runtime metadata.

`serializeAckBody` preserves the eight-byte ACK fields and optional two 64-bit
registers. This is the source ACK body and cumulative extension, excluding MAC
and security bytes. `encodeRateKey`/`decodeRateKey` expose the compact ns-3
compatibility codes 129/130 for 500/1000 kbps. The exact OTA serializer instead
stores literal 500/1000 in its 16-bit `speed` field.

Byte serialization is independently testable; the network simulation passes
logical structs, as ns-3 also retains simulator metadata outside modeled sizes.
Malformed field values and lengths are rejected before conversion. C++ callers
that intentionally narrow an oversized integer must make that narrowing
explicit when supplying the corresponding MATLAB wire field.

## Configuration ownership

`csr.mac.Layer.defaults()` and `csr.hop.Layer.defaults()` own their defaults.
`csr.hop.validateConfig(config)` merges the top-level `Mac`/`Hop` overrides,
rejects unknown fields, validates units/ranges, and normalizes numeric types.
There is no second copy of the defaults. Important source defaults include:

| MAC | Default | HOP | Default |
|---|---:|---|---:|
| DATA queue | 512 | Resend queue | 512 |
| ACK queue | 256 | Resend interval | 2 s |
| ACK transmissions | 5 total | DATA resends | 2, after initial TX |
| Concatenation limit | 16 segments | DACK hold | 20 s |
| Slot interval | 13 ms | Pending threshold | 16; inclusive admission allows 17 |
| Holdoff | 300 ms | Generic wake TIC | 1 / 36 MHz |

Scenario tests may lower limits or set `MaxResends=0` or `NsdpLimit=0` explicitly.
Those are controlled fixture settings, not newly claimed operational defaults.

## Validation

`tests/TestHopFrames.m` prepares eleven tests covering independent original
source golden byte vectors, all fixed sizes, inherited field ordering, full
64-bit ACK registers, 24-bit endpoints, DATA identity across hops, envelope
profiles, aggregate sizing/power, malformed input rejection and configuration
normalization. MISS_HIT static parsing passes. The original unchanged ns-3
`csr-opnet-packet-envelope-smoke` was built and executed successfully in this
workspace as part of the 17/17 source workflows; hashes and logs are in
`evidence/tranche-2-ns3-workflows.json`. This establishes executable source
reference evidence, not MATLAB test success. Actual MATLAB execution is
reported only in the tranche validation evidence after an owner/runtime run.
