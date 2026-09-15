# Tranche 8 portable multiseed and feedback acceptance

The portable R2025a diagnostic milestone is accepted, with the numerical residuals below. All 485 tests, ten observed cases, two tracing controls and both accepted T7 seed-128 anchors pass. This accepts the diagnostic instrumentation and evidence; numerical, full protocol and population equivalence remain unestablished.

The executed candidate is `89b62e729e588f396bb919afdff522f7e9419268`, including the run-row CSV repair. Owner MATLAB **25.1.0.2943329 (R2025a)** ran from **2026-09-10 19:17:21.583 to 19:49:40.794 UTC**, a total of **32 minutes 19.211 seconds**. The backend was portable. No new MATLAB run was performed during this review.

## Verification

- All **485/485 portable test identities and passing outcomes** match the candidate, including the 18 new T8 tests. No failed or incomplete tests remain.
- All **189 source/input hashes**, including **108 MATLAB files**, match the repaired candidate. All **192 reference-file hashes** match, with stable initial and final snapshots.
- The **257-file ZIP** passes CRC and membership checks; all **256 outer plus 398 nested artifact hash and size checks (654 total)** pass. Local MAT objects are intentionally excluded from the returned archive.
- All **ten fixed cases** complete at seeds 128–132 with complete application, admission, protocol, PHY and feedback observations. All 15 declared flow/seed combinations make progress.
- The two MATLAB tracing controls reproduce configuration, statistics and **24 existing CSV file pairs byte for byte**. The two seed-128 cases reproduce accepted T7 statistics and **22 existing CSVs byte for byte**, covering 468,300 rows, with identical statistics.
- The pinned ns-3 reference remains `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`; its suite hash is `5ea5a39c7751c856e710d2eaa09b5d71d4a23c543bafa894c605052f1ded9d5a`. Its observer controls and original T7 anchors pass.

This command did not rerun campus, the retained 18-case research sweep, the retained 28 scenarios, native adapters or OPNET. Passing their portable unit tests does not imply those complete scenario suites were executed.

## Five-seed application outcomes

Relative differences use ns-3 as the denominator. Attempts blocked before admission are not packet drops. Each admission case has 45,000 attempts; each contention case has 60,000.

| Case | Seed | MATLAB admitted | MATLAB delivered | ns-3 admitted | ns-3 delivered | Delivery difference | MATLAB pending |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Two-node admission | 128 | 11,395 | 11,385 | 11,380 | 11,364 | +0.185% | 10 |
| Three-node contention | 128 | 954 | 928 | 946 | 914 | +1.532% | 26 |
| Two-node admission | 129 | 11,358 | 11,354 | 11,234 | 11,227 | +1.131% | 4 |
| Three-node contention | 129 | 980 | 948 | 854 | 822 | +15.328% | 32 |
| Two-node admission | 130 | 11,326 | 11,315 | 11,412 | 11,396 | -0.711% | 11 |
| Three-node contention | 130 | 926 | 894 | 948 | 916 | -2.402% | 32 |
| Two-node admission | 131 | 11,265 | 11,249 | 11,334 | 11,330 | -0.715% | 16 |
| Three-node contention | 131 | 927 | 895 | 903 | 883 | +1.359% | 32 |
| Two-node admission | 132 | 11,369 | 11,359 | 11,383 | 11,375 | -0.141% | 10 |
| Three-node contention | 132 | 949 | 917 | 952 | 920 | -0.326% | 32 |

MATLAB admitted **61,449**, delivered **61,244**, recorded **zero terminal application drops**, and retained **205 pending applications** at the fixed stop times. ns-3 admitted 61,346 and delivered 61,147, leaving 199 unmatched sends whose terminal dropped-versus-pending status is not certified by its trace. Neither simulator has duplicate final delivery events in these cases.

| Fixture | MATLAB mean delivered | ns-3 mean delivered | Difference of means | MATLAB range | ns-3 range |
| --- | ---: | ---: | ---: | ---: | ---: |
| Two-node admission | 11,332.4 | 11,338.4 | -0.053% | 11,249–11,385 | 11,227–11,396 |
| Three-node contention | 916.4 | 891.0 | +2.851% | 894–948 | 822–920 |

Sample standard deviations of delivered counts are 52.91 MATLAB versus 66.70 ns-3 for admission, and 22.88 versus 41.29 for contention. These describe five seeds, not a population-equivalence test. Corresponding seed numbers identify paired experiments; the simulators do not share identical random streams.

## The seed-129 contention residual

The largest observed per-case delivery difference is **+15.33%**, 948 MATLAB versus 822 ns-3. That aggregate masks a larger per-flow difference:

| Flow | MATLAB admitted / delivered | ns-3 admitted / delivered | Delivery difference | MATLAB pending / ns-3 unmatched |
| --- | ---: | ---: | ---: | ---: |
| 2 → 1 | 526 / 510 | 369 / 353 | **+44.48%** | 16 / 16 |
| 3 → 1 | 454 / 438 | 485 / 469 | −6.61% | 16 / 16 |

The node-2 difference is already present in admissions: both admission and delivery differ by 157 packets. The previously measured **17.10%** was a single campus flow at seed 128; it was not a general worst-case bound. This diagnostic did not rerun or revise that campus result.

Independent event inspection localizes 117 of the 157 additional MATLAB node-2 deliveries to the first 20 traffic seconds (300–320 s): 152 versus 35. Over the remaining 40 seconds the counts are 358 versus 318. ns-3 observes its first node-2 DATA earlier (301.401104 versus 302.519104 s), but the first ordinary ACK back to node 2 transmits later (303.849 versus 302.549 s). Admissions resume at 303.874 versus 302.574 s, about 25 ms after those transmissions. These are first-event observations: ns-3's first ACK selection was replaced, so the interval is not the residence time of one unchanged ACK. This localizes an early feedback-service and admission-release difference; it does not establish which scheduler, contention, collision or random-stream behavior caused it.

## Latency conventions

Packet-weighted means pool actual delivered-application delays. Bucket-weighted means give each populated receive bucket equal weight. Empty buckets remain missing; pending applications are not counted as delivered delay samples.

| Fixture | MATLAB packet-weighted delay (s) | ns-3 packet-weighted delay (s) | Difference | Difference of populated-bucket means |
| --- | ---: | ---: | ---: | ---: |
| Two-node admission | 0.937928 | 0.941006 | -0.327% | -0.135% |
| Three-node contention | 1.684183 | 1.736412 | -3.008% | -9.078% |

At contention seed 129 alone, the packet-weighted case mean differs by −16.47%, while the mean of populated bucket means differs by −26.46%. These are different latency measures and do not replace the delivery-count differences above.

## ACK rate and power

All observed ordinary cumulative DATA ACKs in **both simulators** select and transmit at the **128-kbps profile and +33 dBm**. There are no ordinary DATA ACK rate or power overrides and no DACK observations. These runs provide no evidence that replacing MATLAB ACK radio selection would improve their outcomes.

| Observation | MATLAB | ns-3 |
| --- | ---: | ---: |
| Feedback decisions / constructions | 61,543 | 61,472 |
| Actual transmitted feedback members, including repeats | 12,438 | 12,460 |
| Ordinary DATA ACK decisions / actual members | 61,247 / 10,958 | 61,154 / 10,870 |
| Exact-control ACK decisions / actual members | 296 / 1,480 | 318 / 1,590 |
| Actual-versus-selected aggregate rate changes | 29 | 139 |
| Power changes | 0 | 0 |

All 29 MATLAB and 139 ns-3 rate changes affect exact-control ACKs during startup, before application traffic begins at 300 s. Control selection distributions also differ: MATLAB selects rate key 8 for 151 control ACKs and key 128 for 145, versus 66 and 252 in ns-3. MATLAB copies the incoming rate while ns-3 applies reverse-link control; these observations do not establish that replacing the MATLAB rule would reduce the delivery gap. Each actual feedback member correlates to its recorded local decision; no diagnostic trace omission or correlation failure remains. Queue replacement and repeated transmission explain why decision counts and transmitted-member counts are different populations.

MATLAB records decisions after MAC admission; ns-3 records feedback construction after source link control. Those stages are not interchangeable for raw count equality. MATLAB still does not expose source-equivalent peer S0/HOP failure state. The ns-3 samples use known peers, fixed S0 and zero HOP failures; these direct-to-gateway cases do not test variable S0, unknown peers or relayed DACK.

## Disposition and next milestone

Keep the validated MATLAB code, PHY/ECC and ACK radio policy unchanged. The next bounded engineering target is **early contention and ACK scheduling/admission release at seed 129**, preserving full per-flow accounting and tracing the first DATA → ACK → HOP-capacity-release exchanges. A controlled schedule comparison would be needed before attributing the observed lag to a policy defect; equal seed numbers alone do not isolate random-stream effects. A later relay/DACK case can cover the link states missing here.

Acceptance covers the completed diagnostic capability and its evidence. It does not certify numerical parity, statistical equivalence, campus residual resolution, complete end-of-run drain, R2026a/native behavior, or improved outage recovery. The prior T6 recovery limits remain recorded. No further MATLAB run is needed for this acceptance record.

## Evidence and reproduction

The original returned ZIP is preserved at `evidence/tranche-8-r2025a-accepted/tranche8_evidence.zip`, with SHA-256 `bfc4f7f05f0800316b371df3ec316f309f14e3482ef259c3f9c7bd7eea025d77` (17,925,128 bytes). Forty-one selected files retain their exact uploaded bytes. The full Python review, ten aggregate comparisons, independent integrity audit and independent numeric findings accompany it.

The executed input-plan hash is `ed648ee4f54ebf14e14b98d6fcecce224590727139db83f0f4d23161ddfc7a09`; the returned source-snapshot hash is `9bf7f657c08826ab1b502c7ef919b1dbca95dfa815636e69b4b088d82d4a64c7`. Preserve the **89b62e7** candidate to reproduce the exact accepted source snapshot. This acceptance update changes no MATLAB code, input scenario, comparator or ns-3 reference. Source-baseline metadata advances to identify the accepted run. Remote publication is a separate action.
