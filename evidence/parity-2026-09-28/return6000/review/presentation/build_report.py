"""Assemble the reviewed conclusions and complete source accounting table."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'deliverables'
accounting = (ROOT/'return6000/review/accounting/REVIEW.md').read_text()
source_table = accounting.split('## Complete source outcomes\n\n',1)[1].split('\n## Equal observation time',1)[0]
report = '''# Corrected 6,000-second MATLAB return: accounting and latency review

25 September 2026 · Seeds 131 and 132 · Target: ±15% per source

**The returned batch is valid, but the corrected MATLAB model does not yet meet the ±15% network-behavior target.** Total delivery is only 1.48% below ns-3, while source allocations and delivered latency remain substantially different. Only source 3 passes both delivered-count and mean-latency gates in both seeds. The strongest remaining lead is the feedback and competing-traffic history around seed-132 nodes 8 and 2; another retry-cleanup change is not supported by this review.

“Native” means the pinned ns-3 C++ reference. “Corrected MATLAB” is the issued model containing the grouped-routing retry-cleanup fix. “Original MATLAB” is the earlier long-run evidence on these same two seeds. This is a two-seed review, not a new five-seed ensemble result.

## 1. What was verified

Both cases ran through exactly 6,000 simulated seconds in MATLAB R2025a. The successful batch took 3 h 38 min 38 s. All 99 model/data files match the issued plan; all 26 sealed evidence files per case match their recorded hashes. The protocol and PHY captures omit no records. The attempt-detail trace intentionally retains only the first 100,000 attempts per case; complete counters cover all 1,710,000 attempts per case.

The independent accounting audit passed **26,526 numerical checks**. Every one of the **23,698 delivered applications** has a reconstructed causal path with exact nanosecond latency closure. Four repeated ns-3 delivery events in seed 132 are deduplicated; the reference contains 24,055 unique deliveries across the pair.

The two initial invocations stopped before simulation on the stale-model cache guard. The later successful invocation completed both cases. Its embedded archive-completed flag was written before ZIP packaging; ZIP integrity and the completed case seals verify the returned evidence.

No new simulation or production-code change was made for this review.

## 2. Full accounting and the ±15% result

All engines have 3,420,000 scheduled attempts across the two seeds. A rejected application interrupt does not create an admitted application. Attempted, admitted and delivered counts therefore describe different populations.

| Same two seeds | Original MATLAB | Corrected MATLAB | ns-3 |
|---|---:|---:|---:|
| Admitted applications | 25,306 | 25,072 | 25,090 |
| Not admitted | 3,394,694 | 3,394,928 | 3,394,910 |
| Unique delivered | 23,839 | 23,698 | 24,055 |
| Recorded terminal drops | 759 | 760 | Unknown |
| Model-pending at cutoff | 708 | 614 | Unknown |
| Undelivered identities with unresolved fate | — | — | 1,035 |
| Raw delivered mean latency | 146.90 s | 135.16 s | 64.50 s |
| Mean with common native source/seed weights | 112.86 s | 96.18 s | 64.50 s |

Corrected MATLAB closes as 25,072 = 23,698 delivered + 760 dropped + 614 pending. Native closes as 25,090 = 24,055 delivered + 1,035 unresolved. Those 1,035 cannot be classified as either terminal losses or live queued traffic from the final reference ledger.

The raw latency difference falls from **+127.77% to +109.56%** on the same two seeds. Holding seed/source weights at the native delivered counts reduces the corrected difference to **+49.12%**, improved from **+74.98%** originally. Weighting excludes 1,353 corrected MATLAB deliveries from seed-131 sources 2/7/8, which have no native deliveries. It corrects the delivered source mixture descriptively; it does not equalize admitted application identities or remove the extra traffic those sources impose on other flows.

For each source, signed relative error is 100 × (MATLAB − ns-3) / ns-3. A metric passes when its absolute error is at most 15%. Zero native deliveries make three source comparisons undefined. Among the other nine source/seed comparisons, delivered count passes **2/9**, mean latency **3/9**, and both **2/9**. The original MATLAB pair passed both in 3/9. Thus the lower weighted mean does not establish overall improvement in parity.

Do not compare this pair's +109.56% raw gap to the earlier five-seed +21.53% result: those use different seed populations.

### Complete source accounting

''' + source_table + '''

## 3. Unfinished traffic changes the interpretation

Unfinished ages are not completion latencies. Corrected MATLAB's 614 pending applications have mean age 620.20 s, 95th percentile 1,815.32 s and maximum 1,995.66 s. The seed-132 event-state audit independently locates all **372 pending identities** as exactly one owned NWK custody copy each; seed 131's 242 remain final model-pending outcomes without that additional full custody audit.

To give all applications equal observation time, use a 1,200-second delivery deadline and generation interval **[300,4800)**. This has exactly 225,000 scheduled attempts per source in each model. The admitted populations differ; both timely counts and timely/admitted fractions are needed.

| Seed 132 | Original MATLAB: timely/admitted | Corrected MATLAB: timely/admitted | ns-3: timely/admitted |
|---|---:|---:|---:|
| Source 7 | 145/905 (16.02%) | 170/1,014 (16.77%) | 536/657 (81.58%) |
| Source 8 | 154/522 (29.50%) | 103/230 (44.78%) | 307/373 (82.31%) |

Source 7's mean falls from 1,636.61 to 1,401.94 s, but its deadline completion fraction barely improves. Source 8's mean falls from 1,451.66 to 1,036.37 s while total deliveries fall 407→175 and timely deliveries fall 154→103. Its improved conditional fraction comes with substantially fewer admitted applications. Neither delivered mean alone demonstrates better timely service.

## 4. Where delivered latency accumulates

For each winning delivered path, **NWK waiting** runs from source creation or accepted relay custody to successful HOP admission. **Subsequent service** runs from HOP admission to accepted downstream custody or final receipt. The latter contains MAC scheduling, transmission and retry effects. Upstream ACK ownership after downstream receipt is excluded from path latency to avoid double counting overlapping custody.

The existing native evidence supports this combined post-admission phase. It does not support a complete comparable subdivision into first-transmission waiting, airtime and retry delay; those are not invented here.

| Flow | Corrected MATLAB: NWK + subsequent service | ns-3: NWK + subsequent service | Total latency gap |
|---|---:|---:|---:|
| Seed 131/source 4 | 220.12 + 32.80 = 252.93 s | 64.50 + 23.04 = 87.55 s | +188.91% |
| Seed 131/source 5 | 34.95 + 27.98 = 62.93 s | 13.15 + 23.45 = 36.61 s | +71.91% |
| Seed 132/source 7 | 1,365.79 + 36.14 = 1,401.94 s | 825.00 + 32.84 = 857.84 s | +63.43% |
| Seed 132/source 8 | 1,003.40 + 32.97 = 1,036.37 s | 637.89 + 33.82 = 671.71 s | +54.29% |

The displayed rounded components can differ by 0.01 s from rounded totals; unrounded paths close exactly. For seed-132 source 7, 540.79 s of the 544.10 s excess is NWK waiting. For source 8, the post-admission phase is slightly faster than native; its entire positive gap is explained by increased NWK waiting at this phase level. This identifies where delay accumulates, not which upstream event caused the queue to grow.

The accompanying figure shows original, corrected and ns-3 means with delivered population sizes. Full six-source phase tables and packet/hop ledgers are included in the evidence package.

## 5. Seed 131: different reachability creates different competition

Corrected MATLAB discovers all seven nodes by 117.314 s. All six sources admit traffic from 300 s. Native sources 2, 7 and 8 remain topology-blocked for all 855,000 combined scheduled attempts.

Those additional MATLAB sources contribute 1,353 delivered paths through node 4. Node 4 participates in **1,799 ultimately delivered paths versus 1,567 native**, while its own deliveries fall to 446. Its own source represents 24.8% of those paths, versus 100% in native. These are delivered-path loads; failed and unfinished applications add further work.

Consequently, fewer source-4 deliveries are not evidence that node 4 provides less total forwarding service or violates its admission rule. With native weights on common sources 3/4/5, corrected MATLAB is still 52.04 s versus 26.01 s (+100.08%). However, weighting cannot remove competition from the extra reachable sources. The native discovery stall remains a distinct population difference. MATLAB should not be made to lose connectivity merely to match native zero counts.

## 6. Seed 132: queue pressure moved toward node 8

For delivered source-7 traffic, node-2 NWK waiting falls from 1,119.14 s originally to **470.71 s**, versus 196.18 s native. Node-8 waiting rises from 160.36 to **600.19 s**, versus 248.69 s native. In the corrected run, pressure is redistributed rather than the remaining gap closing uniformly. Because delivered populations differ, these changes are not an isolated causal estimate of the cleanup fix.

The corrected trace shows **201 applications waiting at node 8 at cutoff**, including 185 from source 7 and 16 from source 8. Node 2 has 32 waiting. Over [300,6000], node 8 averages 151.72 waiting NWK applications. Delayed acknowledgments hold an average 3.61 capacity slots out of 4.01 outstanding slots. These are time-weighted counts, not per-application durations or percentages of a fixed 16-slot maximum.

| Seed-132 sender history | Corrected MATLAB | ns-3 |
|---|---:|---:|
| Node 8 effective admission window, mean slots | 4.006 | 3.894 |
| Node 8 ACK completions | 139 | 300 |
| Node 8 DACK completions | 993 | 945 |
| Node 8 HOP admissions | 1,149 | 1,271 |
| Node 8 enqueues from source 7 | 1,111 | 795 |
| Node 8 enqueues from its own source 8 | 239 | 512 |
| Node 2 effective admission window, mean slots | 4.830 | 5.918 |

The effective admission window is the neighbor threshold plus one under the inclusive admission rule. Node 8 does **not** have a smaller average effective window. It has a markedly different ACK/DACK completion mix and source mix. That distinction matters when choosing the next test.

The MATLAB event audit reproduces every NWK enqueue depth, final node counter, HOP capacity-admission condition and 20/40-second DACK hold plus scheduler tick. A separate calculation applies the current capacity-state rules to **8,353 native events** on links 8→2 and 2→4: **41,765 before/after state-field checks match**, and all **2,291 completed native DACK holds** match 20/40 seconds plus the native 28-ns tick.

This is a state-transition arithmetic comparison using the same completion inputs. It does not execute the MATLAB ACK-bitmap decoder, production callbacks, receiver feedback selection or all wake-up scheduling. It is sufficient to reject an unsupported claim that the observed backlog by itself proves different window growth or DACK expiry rules.

## 7. Recommended next investigation and stopping rule

**Investigate the origin and delivery of node 2's feedback to node 8 in seed 132, using the saved traffic histories.** The concrete question is why node 8 observes 139 ACK and 993 DACK completions in MATLAB versus 300 ACK and 945 DACK completions in ns-3, while receiving more source-7 relays and admitting less source-8 traffic.

Build a receiver-to-sender event ledger joining original source/application identity, node-2 NWK NSDP custody count for the original source/destination pair before receipt acceptance, duplicate/retry status, chosen ACK/DACK and bitmap, scheduled and actual feedback transmission, node-8 feedback receipt/processing, and resulting capacity/admission decisions. Record receiver per-flow custody separately from sender HOP outstanding slots. Examine receiver feedback selection and feedback transmission/processing together so a lost or cumulatively processed ACK is not mistaken for a receiver decision mismatch.

Use the existing original native trace if its receiver events can be recovered. The locally recovered native capacity tables contain sender state/completion history but lack the full receiver state and bitmap history required for this final distinction. The ordinary returned MATLAB trace also lacks explicit per-flow pre-reception counts, first-reception flags and ACK bitmaps; some state can be reconstructed from custody events, but complete feedback attribution cannot be assumed. Inspect the previously returned short captures for those fields before commissioning any capture. If essential fields were never recorded, first identify that exact gap; this review does not justify another full MATLAB batch.

The decision criterion is concrete: **same relevant state and input, different required action → minimal reproducer and targeted code fix**. If the actions match and only arriving traffic/feedback timing differs, continue attribution to that earlier divergence; do not tune queue, retry or DACK constants to match the plotted means. The seed-131 discovery difference can remain a separate analysis of existing startup evidence rather than another generic long run.

The current evidence establishes a network-level mismatch, not that MATLAB is fundamentally broken or that a particular ns-3 mechanism is missing. No further MATLAB command is needed from the user for this completed review.

## Evidence and reproduction

- Returned archive: `out_6000_20260924_152302.zip`; SHA-256 `a3f7fd6fc09a5b0505c6a759a5c025390151bef484e7e15c9818e51a3f4f1484`.
- Issued batch: `csr-6000-batch.zip`; SHA-256 `fc3e8acff9b1fda90693a7ba299c0d201b7ad7d4edcd1dddf85d706ca92683bf`.
- Historical evidence: `csr-6000s-accounting-evidence.zip`; SHA-256 `5326c8050c2d00f6dca0ea06482c0a7c66ac865921dfb0b6b8820bad7a3abfd9`.
- Reference ns-3 source commit: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.

The companion evidence ZIP contains the analysis scripts, verification outputs, detailed accounting and phase tables, causal packet/hop ledgers, queue/capacity audits and preserved reference archives. Its README distinguishes calculations reproducible from the package alone from raw-trace verification requiring the original returned ZIP. No individual application IDs are treated as matching across engines merely because their numeric values coincide.
'''
(OUT/'CSR_6000s_Corrected_Run_Review_2026-09-25.md').write_text(report)
print('Wrote corrected-run review.')
