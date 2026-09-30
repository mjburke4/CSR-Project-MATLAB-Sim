# Native queued DATA retry audit

The 324.753-second identity mismatch comes from an earlier HOP-to-MAC handoff, not a receiver, packet-size, or identity-classification difference. Native queued node 5's second retry of DATA sequence 29 (source 5, application attempt 11) at **318.498000028 s**. MATLAB's selected `actual-tx` policy skipped that handoff because its first retry was still waiting in MAC. MATLAB therefore put the newer DATA sequence 36 (attempt 250) ahead of the second retry.

The existing MATLAB `DataQueuedRetryPolicy='native-provisional'` implements the observed native DATA rule. Selecting this policy in the common-input case requires no HOP implementation change. Natural case A, default configuration, random tape and identity guards can remain unchanged.

| Event | Native | Returned MATLAB N |
|---|---|---|
| Sequence 29 first actual TX | 313.820 s | Same |
| Sequence 29 retry 1 handed to MAC | 315.820000028 s | Same rounded ns; confirmation then cleared |
| Sequence 32 actual TX | 316.498 s; installs independent global scan | Same |
| Sequence 32 ACK | 318.061111086 s; scheduled scan survives | Same |
| Sequence 32's global scan | 318.498000028 s; queues sequence 29 retry 2 | Same scan runs; skips unconfirmed sequence 29 |
| Sequence 29 retry 1 actual TX | 320.879 s; native retry count already 2 | Same TX; MATLAB retry count is 1 |
| Sequence 36 initial admission | 322.260111114 s | Same rounded ns |
| Sequence 29 retry 2 handoff | Already queued at 318.498 s | 322.879000028 s, behind sequence 36 |
| Next differing DATA TX | 324.753 s: sequence 29, attempt 11 | 324.753 s: sequence 36, attempt 250 |

`CsrHopLayer::EnqueueResend` initializes an unconfirmed owner. `NotifyMacFrameSent` confirms it, replaces the provisional timestamp with the actual sent instant, and schedules an independent list-wide resend scan. `CheckResend` increments the retry count and stores the handoff time without clearing confirmation or creating another timer. An already scheduled scan may therefore queue a further retry while the previous copy waits in MAC. The MATLAB option applies this same rule to DATA. Its default `actual-tx` choice clears confirmation until the next physical TX.

The complete existing native MAC tape contains 734 enqueues, including 177 DATA enqueues for 146 DATA owners. Three DATA cases directly prove a second retry was queued while the first retry remained pending: node 5 sequences 29, 33 and 35. Sequence 35 is forwarded source-4 traffic, so the DATA policy must cover forwarded as well as originated packets. The later new copies for sequences 33 and 35 are unfinished at the 330-second capture boundary. The audit proves pending status by the earlier copy's subsequent physical transmission; it does not infer the fate of other never-transmitted copies.

Native uses the same confirmation-retention mechanism for reliable controls. The current MATLAB option is deliberately DATA-only. No control overlap is directly demonstrated by this capture, so this evidence does not justify expanding the present correction to controls or changing cancellation and final-expiry behavior.

The existing option additionally tracks the latest global timer handle and enables an unmatched-DATA-sent fallback scan when that handle is no longer pending. Native `NotifyMacFrameSent` supplies this source contract; the fallback does not recreate custody. All 150 captured native DATA transmissions have a matched sent-confirmation log entry, so the fallback remains a source-supported component-test boundary rather than an observed network event. Matched owners retain independent scans under both policies.

The new component fixture begins with three public DATA/sent/ACK exchanges to open the fresh peer's two-owner admission window. It drains those timers, records the warmup separately, and preserves sequence continuity through the public allocator. This setup is explicitly separate from the captured chronology. The fixture then checks the five captured admissions and the remaining sequences 29/36 through an isolated real MAC queue. Its timing and queue checks remain owner-side MATLAB work; this review does not claim they have run here.

Run `python autonomous_twelfth/native/audit_queued_retry.py` from the evidence workspace to regenerate the inventory and selected event tables. The accepted native capture, native source checkout, and returned owner files are inputs; the script does not run either simulator or modify those inputs. `source_path_proof.json` records the native/MATLAB source windows and hashes. Candidate scope and final evidence receipts are generated separately once the isolated runner and public preflight are frozen.

N matched 4,202 random requests and 769 earlier physical transmissions before its identity stop. This result establishes the next source-grounded correction, not full 330-second equivalence or 15% performance parity.
