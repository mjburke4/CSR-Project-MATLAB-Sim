# Seed-132 control wire-size audit, existing 0–330-second capture

The broad audit finds **17 compact ROUTING REQUEST child transmissions with a size disagreement, on nine physical transmissions**. The issued MATLAB formulas match the other **1,478 of 1,495 captured children**. All **98 actual ARL routing sections** have the correct size. The source review also confirms one uncaptured, narrowly defined mismatch: generated `NEIGHBOR_CHECK no_path` is 16 native bytes, while MATLAB charges 19.

This is an offline formula and source audit. No MATLAB code or network simulation was run, and no production source was changed. It does not establish autonomous parity beyond the returned H case's 47 accepted physical transmissions and 276 matched draws. That case stops before sending physical transmission 48, at 25.298 seconds.

## Complete captured population

The frozen fixture contains 811 physical transmissions and 1,495 child transmissions, from 10.465 through 329.836 seconds. Counts below include repeated transmissions, rather than unique application packets or controls. The currently enriched fixture and the issued fifth-kit fixture agree exactly on every shared column and row. All 811 parents have the declared child count, consecutive child indices, and a total wire-byte field equal to the sum of their children.

| Child category | Captured children | Native bytes | Issued MATLAB formula | Disagreements |
|---|---:|---:|---:|---:|
| Bare DATA, 185-byte application | 150 | 217 | 185 + 32 | 0 |
| Bare ACK without receive window | 920 | 25 | 25 | 0 |
| Bare ACK with receive window | 184 | 41 | 25 + 16 | 0 |
| DISCOVER broadcast | 24 | 19 | 12 + 7 | 0 |
| KEY_REQUEST | 15 | 18 | 11 + 7 | 0 |
| KEY_UPDATE | 14 | 62 | 11 + 51 | 0 |
| NEIGHBOR_CHECK discovery | 20 | 16 | 11 + 5 | 0 |
| NEIGHBOR_CHECK overheard | 17 | 16 | 11 + 5 | 0 |
| ROUTING, actual ARL section | 98 | 16 + actual section length | Same | 0 |
| ROUTING, compact legacy REQUEST | 17 | 16 | 16 + seven semantic bytes = 23 | **17** |
| SNMP_START | 28 | 31 | 17 + 8 + 6 | 0 |
| SNMP_DONE | 8 | 31 | 17 + 8 + 6 | 0 |

The compact REQUESTs span 25.298–117.546 seconds. Their per-transmitter counts are node 1:5, 2:2, 3:2, 4:2, 5:3, 7:1, 8:2. They contain 16 distinct source/destination/routing-sequence tuples; 17 is the transmission count. Charging seven extra bytes to each gives 119 excess bytes on these fixed fixture rows. That arithmetic does not predict a changed autonomous run: airtime and later aggregation depend on the correction.

The 98 actual sections contain 206 UPDATE, 35 INFO, 35 FLUSH, and 11 DELETE record occurrences. Every captured section is complete (`section=0`, `total_sections=1`); all are sized using the real serialized section length, including their six-byte section prefix. Routing destination lists have one, two, or three entries without additional modeled air bytes. SNMP node lists contain zero through six entries in this capture, and the 31-byte envelope remains fixed.

## Why compact REQUEST differs

Native `BuildRoutingRequestPayload` creates an empty raw packet and places the request operation and sequence in `CsrHelloHeader` metadata ([native source](../../autonomous/native_env/csr/model/csr-nwk-layer.h:8946)). Native routing envelope accounting removes that compatibility header before charging raw payload bytes ([envelope accounting](../../autonomous/native_env/csr/model/csr-opnet-envelope.h:46)). Therefore this generated request is `11 Routes + 5 Group16 + 0 raw = 16` bytes.

The fixture normalizer synthesizes a seven-byte ARL REQUEST section solely to compare equivalent routing semantics ([normalizer](../../autonomous/native_capture/normalize.py:109)). Independent parsing of every captured routing packet confirms the distinction: all 17 normalized REQUESTs have **zero real raw section bytes**, whereas each of the other 98 carries exactly the recorded section bytes. The existing MATLAB request generator sends an actual seven-byte section through its general routing path ([request generation](../../autonomous_fifth/kit/autocase/model/+csr/+nwk/Layer.m:783)); `controlWireBytes` then charges those seven bytes ([MATLAB sizing](../../autonomous_fifth/kit/autocase/model/+csr/+nwk/controlWireBytes.m:33)).

At the observed H stop, node 1's three-member aggregate is `16 + 16 + 31 = 63` bytes in native and `23 + 23 + 31 = 77` in MATLAB. The two request semantic signatures and SNMP signature agree; the strict comparison reports only these two child sizes and the parent sum. The native packet-only API probe independently recovers 63 bytes from the captured packet hex and preserves these modeled sizes through packet copies ([probe results](../native/control_size_probe.log)).

The correct repair needs to preserve the distinction between the generated compact request and an actual serialized ARL REQUEST section. A real seven-byte REQUEST section is legitimately 23 bytes. A compound section beginning with REQUEST also keeps its complete serialized size. An opcode-wide size reduction would break those representations.

## Additional source-confirmed mismatch to batch

MATLAB `sendNoPath` creates a payload whose `TargetId` is metadata, then `controlWireBytes` adds three bytes for `Subtype='no_path'` ([generator](../../autonomous_fifth/kit/autocase/model/+csr/+nwk/Layer.m:827), [sizing](../../autonomous_fifth/kit/autocase/model/+csr/+nwk/controlWireBytes.m:30)). Native `SendNeighborCheck` creates an empty raw packet and puts the unreachable target in `CsrHelloHeader` ([native generator](../../autonomous/native_env/csr/model/csr-nwk-layer.h:7881)). Its HOP layer explicitly removes that header and sets modeled bytes to `11 + 5 + rawPayloadSize` ([native HOP](../../autonomous/native_env/csr/model/csr-hop-layer.h:1856)). Thus generated NoPath is **16**, not 19 bytes.

There are **zero NoPath children in this fixture**, so this finding is source-confirmed and packet-probe-confirmed, not a second observed startup divergence. The packet probe distinguishes metadata-only NoPath (16) from an otherwise identical packet with three actual raw payload bytes (19). A separate component check can cover the metadata-only generator while the next single strict startup run covers the corrected REQUEST and NoPath code together.

Native also has metadata-only nonself DELETE markers, which are 16 bytes, while a real four-byte DELETE record inside a six-byte ARL section is 26. The captured 11 DELETE records are actual sections and already match. Native's current self-DELETE generation intentionally uses that actual section ([native distinction](../../autonomous/native_env/csr/model/csr-nwk-layer.h:8906)). No compact non-REQUEST routing marker occurs in this capture. This is a reason to preserve packet-construction origin in sizing, not evidence to shrink all MATLAB DELETE/INFO/FLUSH sections.

## Coverage boundaries and reproduction

The fixture does not exercise NoPath, verify/message checks, chirp discovery, compact non-REQUEST markers, actual ARL REQUEST records, multi-section routing, DACK, protected ordinary DATA/ACK, or other native-only packet kinds. The audit therefore makes no execution-parity claim for those branches. It also cannot determine the 6,000-second latency or delivery effect of the correction.

Run from the workspace root:

```bash
python autonomous_sixth/receiver/audit_wire_sizes.py
```

The script performs packet/compatibility-length checks, independently extracts actual routing raw bytes, checks the normalizer's synthesized REQUEST representation, evaluates the issued MATLAB byte formulas, verifies every aggregate, and asserts the sole captured mismatch class. It records source/input SHA-256 hashes in [wire_size_audit.json](wire_size_audit.json), all child results in [fixture_child_size_audit.csv](fixture_child_size_audit.csv), and the 17 disagreements in [compact_request_disagreements.csv](compact_request_disagreements.csv). These are formula checks on existing native rows, not a replacement for the next strict MATLAB run.
