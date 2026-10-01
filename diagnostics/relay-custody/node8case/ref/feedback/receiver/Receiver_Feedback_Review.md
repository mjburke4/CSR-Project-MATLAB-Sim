M clears the previous discovery failure and reaches application traffic with matching receiver timing. Its stop at 312.143 seconds is a comparator representation mismatch: MATLAB records logical DACK; native MAC exposes the same feedback as outer ACK with the DACK flag set. No MAC, PHY, HOP, or NWK behavior change is supported by this stop.

The returned ordered history contains 649 physical transmission comparisons: 648 accepted and one rejected. All 3,518 random requests match their native context and nanosecond timestamp; every observed physical transmission comparison also occurs at its expected native timestamp. The summary's `native_transmissions_checked=648` counts accepted comparisons, excluding the stopped attempt.

The receiver audit compares each node's ordered `(time_ns, previous, current)` Idle/Search/Track transitions against native `receiver_history.csv`. All 4,731 transitions match:

| Node | Matching transitions | MATLAB-only Tx→Search records excluded |
|---:|---:|---:|
| 1 | 753 | 127 |
| 2 | 592 | 77 |
| 3 | 827 | 100 |
| 4 | 627 | 97 |
| 5 | 820 | 113 |
| 7 | 542 | 60 |
| 8 | 570 | 73 |

The 647 exclusions follow the instrumentation boundary. Native `run/overlay/ns3/csr-mac-core.h:153` records receiver transitions in `SetReceiveState`; native `csr-net-device.h:2634–2688` updates TX and its completion directly. MATLAB `ReceiverTimerMac.m:654–659,715–717` additionally logs TX completion through `onStateChange`. This comparison does not equate every private timer or boundary event.

The previous node-3 watchdog still fires at 116.340299163 seconds. Its fire and return are consecutive observations 380958 and 380959: no nested action is recorded, and no node-3 SNMP START is enqueued between 116 and 300 seconds. Node 3's TX86 is now the matching DATA transmission at 300.365 seconds. All six source nodes admit their initial application at 300 seconds.

The first DACK decision itself agrees. At 312.049812442 seconds, node 8 receives node 7's DATA with hop sequence 30 and network endpoints 7→1. MATLAB and native both report first reception with NSDP increasing from 16 to 17 against limit 16. MATLAB replaces the cumulative feedback queued for node 7 with logical DACK, base sequence 30, ACK bitmap `00000000000fff72`, and DACK bitmap `0000000000000001`. Native canonical event 33571 reports the same decision. Local MATLAB packet ID 102 and native application sequence 988 are separate labels; the causal match uses the time, endpoints, hop sequence, and recorded admission decision.

At the attempted 312.143-second transmission, radio settings, short preamble, reservation 18, address pair 8→7, sequence 30, both maps, DSCP7, non-ackable status, cumulative-window presence, and 41 wire bytes all match. The old comparator's sole failure is `child1.kind`.

The source path explains that sole difference:

- Native `csr-hop-layer.h:3570–3600` creates feedback with `IsAck=true`, sets `IsDack` from the actual admission decision, and initially chooses the logical type.
- Native `csr-net-device.h:3142–3151` gives `IsAck` precedence and emits outer type ACK while preserving `IsDack`.
- Native `csr-hop-layer.h:1324–1350` validates historical bare feedback, explicitly documents the common ACK outer type, and restores logical DACK from `IsDack`.
- Native receive processing at `csr-hop-layer.h:2809–2840` uses the cumulative-window branch before any exact ACK/DACK branch.
- MATLAB `model/+csr/+hop/Layer.m:268–278` retains logical `Kind='DACK'`. Both kinds use the same MAC ACK queue (`ReceiverTimerMac.m:130–154`), wire-size formula (`Frames.m:32–46`), and cumulative receive implementation (`Layer.m:370–395`). The cumulative bitmaps determine completion; the logical kind still matters for exact/no-window feedback and diagnostics.

The full existing native fixture contains 1,104 feedback children: 920 exact ACKs (25 bytes, flags34), 163 ordinary cumulative ACKs (41 bytes, flags42), and 21 DACK-flagged cumulative messages (41 bytes, flags46). Every one has outer kind ACK and `is_ack=1`; the first DACK-flagged transmission is the current stop. This supports a comparator projection that checks both logical flags and their encoded bits. It does not support changing MATLAB DACK generation, inferring subtype from a nonzero DACK bitmap, or dropping the exact/no-window distinction.

Reproduce the extraction with `python autonomous_eleventh/receiver/audit_feedback_receiver.py`. The accompanying JSON binds the inputs and source files by SHA-256. This was an offline evidence and source review. The returned run has not received the stopped feedback or continued to 330 seconds. Common random inputs and this matched prefix do not establish independent random-stream equivalence, 6,000-second behavior, or the 15% parity goal.
