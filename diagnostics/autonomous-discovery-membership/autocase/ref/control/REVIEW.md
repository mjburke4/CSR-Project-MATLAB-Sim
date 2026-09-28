# Native control wire-size investigation

The H stop at 25.298 seconds is a real MATLAB envelope-size mismatch. Native emits two compact REQUEST controls of 16 modeled bytes each and one SNMP control of 31 bytes: 63 bytes total. MATLAB has the same control identities and semantics but charges each REQUEST 23 bytes, producing 77. The fixture's seven-byte REQUEST sections are normalized receiver semantics, not seven raw payload bytes present in this native sender representation.

## Existing capture and source proof

The original captured transmission is node 1, physical ordinal 18, `tx_id=4294967314`. Its routing children target nodes 3 and 5 with HOP sequences 7 and 9; their frame IDs are 58 and 59. Native packet hex independently reconstructs modeled sizes 16 and 16, followed by SNMP31. The original passive `mac_tx` observation at event order 8174 records a duration of `0.087719999999999992` seconds. The TX fixture's parent event order is 8173.

`CsrNetLayer::BuildRoutingRequestPayload` creates an empty packet and adds a `CsrHelloHeader` containing the REQUEST operation and routing sequence. HOP Group16 protection contributes five modeled bytes. The routing envelope strips the compatibility header and charges Routes 11 + Group16 security 5 + actual raw body 0 = 16. The normalizer sees the empty raw body, synthesizes `sequence[4] + section0 + total1 + REQUEST3`, and explicitly labels it `normalized_legacy_request`.

A real native ARL REQUEST section with these same seven semantic bytes has seven actual raw bytes and costs 23. An opcode-only or blanket seven-byte exemption would be wrong. Provenance must originate at the compact REQUEST sender, persist through backlog/control owners/retries, and be checked before removing semantic-only bytes from the modeled size.

At rate key8 with a short preamble, the native PHY duration formula is `(104+48)/4*0.00051 + (wireBytes*8+32)/CsrRateKeyToBps(8)`. Native 63 takes 87.72 ms; uncorrected MATLAB 77 would take 102 ms, an excess 14.28 ms. The guard stopped MATLAB before transmission. No resulting delivery, contention or latency improvement has been measured.

## NoPath actual sender path

The additional NoPath correction is supported by the real native send path, not just a packet that can be constructed:

1. Public `CsrNetLayer::SendNoPath(neighbor, unreachableDest)` calls `SendNeighborCheck(neighbor, NoPath, unreachableDest)`; the relay no-route branch invokes this public method.
2. `SendNeighborCheck` starts with an empty packet, writes subtype and target into `CsrHelloHeader`, and adds only that header. It does not append three raw target bytes.
3. `CsrHopLayer::SendNeighborCheck` removes that compatibility header from a copy to determine `rawPayloadSize=0`, protects the actual payload with Pairwise16, and explicitly attaches a Routes envelope of 11 + security 5 + raw 0 = 16. The target remains in the serialized compatibility metadata for receiver behavior.
4. The HOP resend owner copies the annotated frame. `CsrMacCore::EnqueueTxFrame` calls `CsrAnnotateOpnetEnvelope`, which preserves an existing envelope. The PHY sums these modeled child sizes.

Baseline MATLAB `sendNoPath` likewise stores `TargetId` in its behavioral payload metadata, but its sizing helper adds three bytes solely because the subtype is `no_path`. Removing that charge gives 16 without changing target, subtype, acknowledgment requirement, callback or retry ownership. Source excerpts and exact file hashes are in `source_path_proof.json`.

The packet component probe confirms target-in-metadata NoPath 16 and a deliberately different packet containing three actual raw bytes NoPath 19. The accepted 0–330 native fixture contains **zero NoPath controls**. We did not execute the full native `SendNoPath` sender path dynamically in this step. The source chain and packet API component passed; the separate owner-side MATLAB public NoPath preflight remains required. No NoPath network coverage is claimed.

## Sibling audit and executed checks

The accepted fixture contains 1,495 child frames. All observed NWK control sizes agree with the native source formula. Seventeen are compact REQUESTs at 16; 98 are real ARL sections and retain 16 plus their actual section byte count. The remaining observed controls are Discovery 24, KEY_REQUEST 15, KEY_UPDATE 14, NeighborCheck Discovery 20 and Overheard 17, and SNMP 36. These counts are packets, not bytes. ACK 1,104 and DATA 150 are inventoried but their arithmetic is outside this control audit.

Native also exposes compatibility-only targeted DELETE marker APIs: their target is metadata and their modeled size is 16. Actual group DELETE sections contain a six-byte section prefix plus four-byte DELETE record and cost 26. The probe verifies both. The observed routing sections are real ARL, and this investigation does not justify changing ordinary DELETE/INFO/UPDATE sizes. No Message/Verify/NoPath NeighborCheck or Discovery chirp appears in the accepted fixture.

`control_size_probe.cc` executed 12 packet cases: three original captured children, generated compact REQUEST, actual REQUEST section, actual compound section, compatibility DELETE, actual DELETE section, metadata NoPath, NoPath with three actual raw bytes, Discovery check and Overheard check. All passed, including `Packet::Copy()` retaining modeled size and the aggregate/airtime checks. It used the pinned native security, header, envelope, packet model and PHY rate APIs. It created no device/channel, called no `Simulator::Run`, and made no production or fixture edits.

## Candidate I review

The isolated `ControlWireNwk` diff against H changes only the class identity, three calls to the isolated sizing helper, optional routing representation propagation, and the REQUEST sender's explicit compact marker. `ControlWireSimulation` changes only class identity and the NWK binding. The helper first delegates baseline validation, then changes metadata-only NoPath to 16 and strictly validates marked unicast single-section REQUEST before selecting 16. Untagged real ARL sections, including REQUEST 23 and DELETE 26, retain baseline sizing.

The independent static audit verifies all 16 declared transforms forward and backward, all 99 baseline model files unchanged, retained payload metadata during residual retries, and the natural-run gate plus new REQUEST and NoPath preflights before the single `I_control_wire` continuation. MATLAB execution is pending. The native fixture and strict comparison guards remain unchanged. The earlier H limitations are inherited; this is not acceptance of a production fix or a claim of 15% network parity.

## Reproduction and files

With the pinned native environment restored under `autonomous/native_env`, run `python autonomous_sixth/native/run_packet_probe.py`, then `python autonomous_sixth/native/audit_evidence.py` from the workspace root. The first compiles and executes only the packet component; the second reads the accepted capture and candidate sources without simulating. `compile_command.json` records the exact compiler command. Three local wrapper headers resolve restored include paths without editing the pinned source or build.

`evidence_receipt.json` records source pins, source/input/artifact hashes, compiler identity, actual runtime-library hashes, argv, executed scope and limits. `fixture_control_audit.json` retains the observed inventory, all 17 compact REQUEST identities, the original target MAC observation and target children. `candidate_scope_review.json` records candidate hashes and exact transform results. The binary and native checkout/build need not be shipped with these source, log and receipt files.
