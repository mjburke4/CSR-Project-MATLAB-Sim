# Tranche 3 ARL control codec

The portable routing payload codec follows `csr-arl-routing-message.h/.cc`
and `csr-nwk-arl-routing-stream-smoke.cc` at authoritative ns-3 commit
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.

## Record and section API

`csr.nwk.RoutingCodec.encodeRecords(records)` accepts a cell array of scalar
record structs, or a homogeneous struct array. `decodeRecords(stream)` returns
a cell row of scalar structs, preserving record order. Wire integers decode to
MATLAB doubles; all fields fit exactly within 32 bits. Encode validates ranges
before conversion, avoiding MATLAB integer saturation.

| Operation | Opcode | Following fields, in order |
| --- | ---: | --- |
| FLUSH | 0 | None |
| DELETE | 1 | `NodeId`: unsigned 24 bits |
| UPDATE | 2 | `NodeId`: unsigned 24; `Capability`: unsigned 8; `HopCount`: unsigned 16; `Cost`: unsigned 32; `Path`: exactly `HopCount` unsigned 24-bit IDs |
| REQUEST | 3 | None |
| INFO | 4 | Eight 16-bit fields described below |

Each record has a string `Operation` field. INFO stores fields under `Info`:
`MinSpeedKbps`, `MaxSpeedKbps`, `MinPowerDbmX10`, `MaxPowerDbmX10`,
`LinkMarginDbX10`, `LowPowerDbmX10`, `TempLowCx10`, `TempHighCx10`. The first
two values are unsigned and the other six signed. Multi-byte values are big
endian. Power, margin, and temperature use tenths of their named units.

`sections(stream, sequence)` produces a cell row of byte vectors. Each section
has a six-byte prefix: unsigned 32-bit message sequence, zero-based unsigned
8-bit section index, unsigned 8-bit total. Maximum section size is 700 bytes,
leaving 694 bytes for stream data. There can be at most 255 sections. Records
can cross section boundaries; parsing a section body independently is invalid.
`decodeSection(bytes)` returns `Sequence`, `Section`, `TotalSections`, `Body`.
The source permits a six-byte section with an empty body; section generation
rejects an empty complete stream.

Wire validation is distinct from routing policy. The wire codec permits every
24-bit value, including the broadcast ID, and 16-bit hop counts. The live route
policy rejects broadcast destinations, paths containing the receiver, and paths
exceeding the configured routing limit. This preserves the independent source
fixture with a 258-hop path without making it an admissible live route.

## Atomic bounded reassembly

`csr.nwk.Reassembly(config)` buffers by peer and routing-message sequence.
`[complete, records, sequence] = accept(peer, sectionBytes)` returns no records
until every section is present and the complete stream parses successfully.
Malformed input returns `complete=false`, an empty record cell array, and
increments `Malformed`. Sequence is `NaN` when the section header is invalid.
Unexpected programming exceptions propagate rather than becoming packet drops.

Identical duplicate sections are ignored. Conflicting duplicates and changed
section totals are rejected without overwriting earlier accepted bytes. A
malformed complete stream discards its buffer without returning any partial
records. `discardPeer(peer)` releases incomplete transactions on neighbor loss
or restart. Route state, sequence freshness, and atomic application belong to
the caller; this class does not advance route freshness on incomplete messages.

Defaults are `MaxMessages=64` globally and `MaxMessagesPerPeer=8`. The oldest
incomplete transaction is evicted when its applicable bound is reached. These
portable memory bounds are explicit implementation choices, not a claim of
matching ns-3's map retention limits. Wire limits bound each transaction to
176,970 record bytes. `stats()` reports pending transactions, buffered bytes,
accepted sections, completions, duplicates, conflicts, malformed messages,
evictions, and explicit discards. There is no independent wall-clock timer;
the control plane calls `discardPeer` when a relationship expires.

## HOP transport and security boundary

ARL payload bytes contain no simulator-only `CsrHelloHeader` metadata. The
following source mappings guide the portable logical control envelope; a
`*-size-only` security profile represents byte count and admission lifecycle,
not authentication or encryption.

| Logical control | Legacy packet type | Source security record | Reliability |
| --- | ---: | --- | --- |
| Discover | 4 | GroupEstablish: payload + 7 bytes | Broadcast; no ACK/resend |
| NeighborCheck | 9 | Pairwise16: payload + 5 bytes | Reliable unicast |
| RoutingUpdate | 8 | Group16: payload + 5 bytes | Broadcast or reliable grouped section |
| KeyRequest | 2 | 7 total bytes | No ACK/resend; newest unsent request per peer replaces older request |
| KeyUpdate | 1 | 51 total bytes | Reliable unicast |
| ACK/DACK | 0 | Pairwise16: logical ACK body + 5 bytes | No ACK/resend |

Packed key ID and security sequence each occupy 12 bits, jointly three bytes.
The ns-3 compatibility HOP envelope additionally carries an optional two-byte
security restart count. That count is distinct from security-record overhead.
No key bytes, authentication tags, or crypto operations are implemented here.

For portable on-air accounting, retain the existing 17-byte MAC packet model,
use an explicitly documented control body and HOP envelope size, then add only
the selected security-record overhead. Do not charge simulation metadata as
wire bytes. The authoritative source explicitly overrides NeighborCheck size
with the 11-byte Routes packet model plus 5-byte security plus raw payload;
other control paths retain compatibility headers. Compact portable control
sizing therefore requires an explicit parity-ledger boundary rather than a
claim of exact ns-3 control airtime.

Reliable routing sends group 1–10 peers into one HOP frame, each with its own
unsigned 16-bit HOP sequence. The routing sequence in the payload is separate.
Controls consume resend capacity and DSCP 7 service but do not consume DATA
pending counts, NSDP counts, or adaptive DATA flow windows. Duplicate controls
receive another ACK while delivery to NWK happens once.

HOP retries preserve the original grouped frame after partial ACKs. NWK retains
the original payload with a separate remaining-destination set, removes each
successful peer, and retries only the residual after HOP finishes its attempt.
Residual retries receive fresh HOP sequences, prune inactive peers, and wait
if any remaining peer has a full control buffer. Completion callbacks run
before HOP removes its owner; residual retry must run in a later event rather
than synchronously re-entering HOP. DATA retry exhaustion does not imply a
routing-link failure.

## Verification boundary

`tests/TestRoutingCodec.m` checks literal source-fixture bytes, signed INFO
fields, the 258-hop and 700+10-byte section cases, out-of-order and conflicting
sections, atomic malformed-stream rejection, peer isolation, sequence limits,
and bounded-buffer eviction. Adding tests does not establish MATLAB execution;
the tranche acceptance record must preserve the actual runtime and results.
