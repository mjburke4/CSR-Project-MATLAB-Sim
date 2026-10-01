# Seed 132 ACK/DACK wire-type audit

The M stop at 312.143 s compares different layers of packet identity. MATLAB's `Kind='DACK'` is the correct logical subtype. Native HOP also constructs a logical DACK, with both `IsAck=true` and `IsDack=true`. Native MAC then writes the common ACK outer packet type because its wire-assembly expression checks `IsAck` first. The DACK flag and cumulative maps remain intact. Native receive authentication restores the logical subtype before HOP processing.

The stopped node 8 transmission has sequence 30, ACK map `00000000000fff72`, DACK map `0000000000000001`, one 41-byte child, rate 8 kbps, power 33 dBm and a short preamble in both implementations. The native serialized header is `000008000007001e072e01000800000000000fff720000000000000001014afbfa`: its flags byte is `2e` and outer type is `01`. The sole reported mismatch is MATLAB logical kind 2 versus native outer kind 1.

The triggering native reception at 312.049812442 s is DATA from peer 7, network source 7 to destination 1, HOP sequence 30. NSDP is 16 before admission and 17 afterward, correctly requesting DACK. The preceding sequence 29 had NSDP 15 before admission and received an ordinary ACK. The returned MATLAB history independently matches this boundary.

The complete native fixture contains 1,104 feedback children:

| Native feedback class | Children | Wire type |
|---|---:|---:|
| Exact ACK | 920 | 1 |
| Ordinary cumulative ACK | 163 | 1 |
| DACK-flagged cumulative feedback | 21 | 1 |

All 21 DACK examples occur at nodes 8 and 4 between 312.143 and 320.788 s. They represent six transmitted frame IDs following eight DACK-generation decisions; cumulative ACK-queue replacement and repeated sends account for the differing counts. Every feedback header, flag and cumulative bitmap was checked directly against serialized packet bytes. The first example is the M stop; later examples are native evidence and have not yet been reached by M.

The correction belongs in semantic TX comparison. Project genuine logical ACK and DACK to native outer type 1, add strict checks for `is_ack=1` and `is_dack` matching the current logical kind, and validate those fields against the native flags byte. Record both raw labels. Continue comparing window presence, both maps, sequence, destination, bytes, radio settings and timing. Native outer type 2 must fail for these generated feedback frames. No production protocol change is indicated.

The source projection does not depend on window presence. Keep the single-DACK versus cumulative-window receive distinction unchanged. Also avoid deriving logical subtype from whether the DACK bitmap is nonzero: native HOP copies prior cumulative maps independently of the current feedback decision. A logical ACK may retain older DACK bits. That and a logical nonwindow DACK are useful source-supported component boundaries, although neither appears among this fixture's transmitted frames.

Source pin: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. `source_path_proof.json` includes construction, queue, wire projection, authentication and custody-dispatch code. `native_dack_wire_children.csv` lists all 21 examples. `audit_feedback_kind.py` reproduces the read-only native audit from the existing fixture, canonical trace and M stop. No native network or component simulation was rerun, and no new MATLAB candidate was executed here.
