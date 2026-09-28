# Seed-132 discovery identity comparison review

The control-size corrections passed their actual MATLAB checks. The corrected routing requests transmitted with the expected 63-byte aggregate at 25.298 seconds. The run continued to **25.740 seconds**, consuming **290 matching random inputs** and verifying **49 physical transmissions**. The next guard stop compares an outer discovery label that ns-3 and MATLAB allocate differently but do not use to control this packet's network behavior.

The next step is a narrow comparison correction. The I simulation behavior remains unchanged. The full-network target remains **±15%** and is not established by this startup capture.

## Actual return

Input: `out_auto_20260928_073809.zip`, SHA-256 `c74ee8654d97cdc347ad142fea5d079a4cdf7cbfd243b8448449979889cb58f2`, 37 members. All 294 issued file hashes match the returned manifest. Runtime was MATLAB R2025a 25.1.0.2943329, PCWIN64. Import and all **38 component checks** passed, including six compact REQUEST and three NoPath checks. The natural A result was reused after its existing runtime, configuration, source and exact trace gates passed.

| Actual I result | Value |
|---|---:|
| Stop time | 25.740 s |
| Matched and consumed random inputs | 290 |
| MAC / SYNC / PHY requests | 61 / 131 / 98 |
| Verified physical transmissions | 49 |
| Next rejected transmission | Node 3, transmission 17 |
| Previous size mismatch | Cleared: 16 + 16 + 31 = 63 bytes |
| Application attempts | 0 |

Independent comparison confirms all 340 observed random-request and transmission-context events, including the rejected context, occur in the same global order and at the same rounded-nanosecond times as native. A rejected context is not counted as a transmitted packet. This validates the checked observable prefix, not every internal state or native wrapper field. The existing profile-4-irrelevant reported-population differences remain recorded.

The NoPath correction now has actual public MATLAB component coverage: forwarded-DATA rejection emits the reliable 16-byte check with its target preserved. There are still no NoPath packets in the accepted native 0–330-second network capture, so this does not establish its effect on an autonomous network trajectory.

## The remaining stop is an outer-label comparison

At 25.740 seconds, node 3 prepares the same three children in both engines: a 25-byte ACK, a 65-byte routing snapshot and a 19-byte broadcast DISCOVER, totaling 109 bytes. The first two children match. The discovery child's payload session number is one in both engines. Only its outer HOP sequence differs.

| Field | MATLAB | ns-3 |
|---|---:|---:|
| Discovery source | 3 | 3 |
| Destination | Broadcast | Broadcast |
| ACK required | No | No |
| Outer HOP sequence | **1** | **4** |
| Discovery payload session sequence | **1** | **1** |
| Discovery wire bytes | 19 | 19 |
| Aggregate wire bytes | 109 | 109 |

Native `SendProtectedDiscovery` increments a function-static 16-bit counter shared across all HOP instances in that process. The gateway's three earlier broadcasts receive outer numbers one, two and three. Node 3's first therefore receives four. MATLAB allocates its discovery broadcast number from that sender's destination sequence map, so node 3 begins at one. The discovery-session number carried inside the payload is a separate field and agrees.

## Why this label does not justify a model change

Native protects the discovery payload before constructing the outer HOP header. Authentication and replay protection use the source, security count and protected record's own key/sequence fields; they do not consume this outer sequence. The protected discovery receive path returns before ordinary HOP duplicate-window and ACK handling. NWK receives the decoded discovery payload and sender, including the real discovery-session number.

MAC does not use the outer sequence to schedule this non-ACK broadcast. PHY reception and interference identify signals using source plus physical-transmission ordinal, independently of this label. Its remaining native uses are diagnostic trace/log metadata. MATLAB likewise bypasses HOP duplicate windows and feedback for broadcast discovery and forwards its payload and source to NWK.

The native counter audit covers all 24 discovery broadcasts in the existing capture. Their numbers are one through 24 in generation order; 21 differ from a sender-local ordinal. Transmission order can differ from generation order because nodes contend, so reconstructing the native counter from transmission order would also be wrong. These are existing native observations, not a claim that MATLAB has executed the whole capture.

The sibling audit retains separate treatment for 36 SNMP packets, 15 KEY_REQUEST packets and 1,104 ACKs. Their sequence contracts are not changed. Other native global-counter packet types are absent from this capture and receive no new exemption. Introducing shared cross-node state into MATLAB just to reproduce the inert discovery label would not address traffic generation, receiver availability or latency.

## Narrow comparison policy

The new J continuation uses the same I network implementation and native inputs. Its isolated comparator excludes only `hop_sequence`, and only when **both** children identify the covered broadcast DISCOVER subtype, broadcast destination, no ACK requirement and no ACK window. The native child must also have broadcast destination type, group-security flag and a finite security count, limiting the exception to the audited protected path. Both raw outer values and an explicit explanation remain in the diagnostic output.

Source and destination, packet kind, child order, physical-transmission ordinal, discovery subtype, payload session sequence, active-peer list, byte counts, rate, power, preamble, reservation information and applicable feedback fields retain their checks. Reliable control, DATA, ACK and DACK sequence comparisons remain strict. Uncovered discovery forms also retain the prior behavior. The native fixture is unchanged.

A separate comparator and provider/simulation bindings preserve the issued I classes and natural-run path. Seven public comparator checks reconstruct the actual rejected aggregate, assert its old failure and narrowly accepted new result, and require mutations of the payload session, sizes, destinations, acknowledgment/protection flags and reliable sequences to fail. Their MATLAB runtime result remains pending. This is an explicit correction to the comparison contract, not a new model behavior fix or evidence of a latency improvement.

## Run the continuation

Download `autonomous-discovery-identity-tests.zip`, extract into a fresh folder, restart MATLAB and set Current Folder to `autocase`. Run:

```matlab
report = run_autonomous_tests;
```

Return the generated `out_auto_*.zip`, including any diagnostic stop. One new J case runs from zero to its first consequential checked divergence or 330 seconds. Existing I results remain historical evidence and are not rerun; the accepted natural run is reused when its gates pass. Existing component checks remain in the batch. No ns-3 command is required from you.

## Remaining acceptance

The final kit binds 322 files. All 137 MATLAB files pass static syntax parsing with MISS_HIT 0.9.44 using its MATLAB 2022a grammar. Independent review verifies 19 exactly reversible source transformations, all 99 unchanged model files, all 36 unchanged prior candidate/helper MATLAB files, and unchanged native fixtures. These are preparation checks, not execution of the new J case.

The request-size fix has now cleared its network stop, and all nine component checks added last turn passed in MATLAB. The new label-normalization comparison and continuation still require owner execution. The original 99 model files remain unchanged.

Application traffic starts at 300 seconds. This return therefore cannot establish the original 6,000-second source-by-source delivery, drop, unresolved-traffic or latency comparison. The ±15% target remains open, including comparable delivered populations, source mix and unfinished traffic. No new long network simulation was run for this review.
