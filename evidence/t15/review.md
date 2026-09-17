# Tranche 15 review

The returned MATLAB R2025a run completes the focused Tranche 15 diagnostic: **117/117 tests, 8/8 cases and 528/528 structural checks passed**. Runtime was 365.942 seconds. The reviewer checked the supplied evidence; no new MATLAB or ns-3 execution is claimed.

All eight runs delivered their 96 prescribed application messages. Final application demand, HOP pending/resend/DACK holds, and MAC DATA/ACK queues drained. Scheduled periodic control activity is outside that drained-data claim.

## What the timing experiment changed

In the controlled DATA-loss case, the local nanosecond transport fixture brings these observed totals into line with the pinned native reference:

| DATA-loss measure | Continuous MATLAB | Nanosecond fixture | ns-3 reference |
| --- | ---: | ---: | ---: |
| Delivered application messages | 96 | 96 | 96 |
| Aggregate transmissions | 288 | 283 | 283 |
| Feedback transmissions | 246 | 242 | 242 |
| DATA retries | 2 | 2 | 2 |
| Blocked admission polls | 648 | 640 | 640 |
| Capacity-release callbacks | 144 | 144 | 144 |
| Mean delivery latency, seconds | 4.774319125 | 4.696278917 | 4.696278945 |

The other three cases retain their traffic totals. Nanosecond-mode random-draw usage matches the native reference. This is useful evidence that transport-time representation can affect an ACK opportunity and subsequent contention, even though every application ultimately arrives in both modes.

## Remaining differences

Nanosecond mode preserves the event order and packet identities of all 9,962 native event rows. Its shifted event times, all 1,475 draw times, all 1,592 transmission/arrival records and all 576 terminal times have a constant -28 ns offset relative to the native reference, with no observed drift. Some events scheduled at shared absolute times remain unshifted.

Strict comparisons also retain 20 release snapshots with a one-entry DACK/resend queue difference, 28 ACK/DACK kind labels carrying matching bitmaps, and 393 outage boundary-distance differences of 28 ns. The release snapshots observe opposite sides of the DACK queue transfer callback. In the pinned native code, cumulative DACKs satisfy both ACK and DACK predicates, and the transmit header classification tests ACK first; MATLAB retains the DACK kind. These are not extra feedback transmissions, and the prescribed loss policies agree. The complete comparison preserves every difference; this review does not claim exact trace parity. Large row-index timing differences in continuous-mode comparisons follow divergent event sequences and must not be interpreted as measured packet latency errors.

The controlled fixture does not establish campus-network, RF collision, PHY/ECC, or OPNET parity. Production scheduling and transport defaults have not changed.

## Provenance

- Returned archive: `t15.zip`, SHA-256 `a1c706fc66d2699ffcd4a0d4d811acaa5cfc10fe8bcc3fe459d85a18c94bca73`.
- Issued candidate SHA-256: `be665c0c733f2e71766cb3b066ca789ea6a2a3de1d8a198ccb0b0a5fe00a16f0`.
- Verified 95 inventoried artifacts, 294 source bindings including 149 MATLAB files, and 339 reference bindings.
- All 285 Tranche 14 sources, including 144 MATLAB files, remain unchanged.
- Continuous mode reproduces all six accepted Tranche 13 owner tables exactly.
- Pinned ns-3 source: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.

The next proposed milestone is to test an explicit, optional timing policy across multiple seeds and representative network cases, with the current behavior retained as the control. The 6000-second campus rerun and full regression remain the release gate after that broader evaluation. Tranche 15 does not automatically promote a production policy.

The archive contains the original owner evidence, the complete machine-readable comparison, and independent integrity/outcome notes. Repository publication of the separately approved Tranches 6–14 checkpoint is tracked separately.
