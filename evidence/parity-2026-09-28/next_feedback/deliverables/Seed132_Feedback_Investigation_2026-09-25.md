# Seed 132: receiver feedback and the source of the ACK deficit

25 September 2026 · Existing evidence only · Network target remains ±15%

**The 139-versus-300 ACK difference is already present in node 2's receiver decisions. It is not an unexplained loss of eventual feedback completions, and the ACK/DACK selection rule agrees for all audited first DATA receptions on 8→2.** Source-7 traffic reaches node 2 under substantially greater per-flow custody pressure in MATLAB. We also located a specific early MAC service-order difference, then verified that the existing September 23 MATLAB replay already reproduces the native behavior under identical inputs. No production correction or repeat conditional MAC run is justified by these findings.

Native means the ns-3 C++ reference. Current MATLAB is the corrected model used in the returned 6,000-second batch. This investigation does not change the earlier ±15% result or constitute a new network-parity measurement.

## 1. Receiver decisions account for the complete difference

The recovered original native trace contains 4,991,634 events. The MATLAB trace contains 615,508 protocol events. We reconstructed node-2 custody by original source/destination, checked feedback selection for every DATA receipt from node 8, and joined each receipt to the same application's sender-side HOP completion.

| Original source | MATLAB receipts | MATLAB ACK / DACK | ns-3 receipts | ns-3 ACK / DACK |
|---|---:|---:|---:|---:|
| 7 | 911 | 75 / 836 | 759 | 114 / 645 |
| 8 | 221 | 64 / 157 | 486 | 186 / 300 |
| Total | **1,132** | **139 / 993** | **1,245** | **300 / 945** |

Every audited receipt is a first reception. In both histories, all ACK decisions have a pre-reception per-flow custody count of at most 15; all DACK decisions have a count of at least 16. Every received application eventually completes at node 8 with the corresponding ACK/DACK class. There are zero state-rule or receipt/completion classification mismatches.

The complete hop populations remain explicit:

- MATLAB: 1,149 admissions = 1,132 receipts/completions + 16 failures with no node-2 receipt + one unfinished HOP owner.
- ns-3: 1,271 admissions = 1,245 receipts/completions + 26 failures with no node-2 receipt.

These are 8→2 hop outcomes. A completed hop is not an end-to-end application delivery, and a failed hop is not automatically a proven global terminal drop.

NSDP here counts node-2 custody for the original `(source,destination)` pair, including owners already submitted to HOP. It is neither the total queue depth nor the sender's outstanding-capacity count. A DACK accepts receiver custody and retains sender capacity for its configured hold; it is not a receiver discard.

## 2. Greater source-7 pressure produces more DACK decisions

| Receiver state when a packet arrives | Corrected MATLAB | ns-3 |
|---|---:|---:|
| Source-7 mean pre-arrival NSDP | 75.91 | 25.16 |
| Source-7 maximum pre-arrival NSDP | 163 | 52 |
| Source-7 fraction receiving ACK | 8.23% | 15.02% |
| Source-8 mean pre-arrival NSDP | 19.76 | 16.90 |
| Source-8 maximum pre-arrival NSDP | 37 | 38 |
| Source-8 fraction receiving ACK | 28.96% | 38.27% |

The input mix also differs: source 7 supplies 911 of MATLAB's 1,132 receipts, versus 759 of native's 1,245. The lower pooled ACK count therefore combines different numbers of receipts, different source proportions and different per-flow custody states. It does not imply a different threshold or a missing ACK mechanism.

Across the entire [300,6000] interval, node 2 holds a time-average **72.96 source-7 applications in MATLAB versus 25.30 in ns-3**. These time averages differ from the arrival-weighted means above. MATLAB has a sequence of 665 source-7 arrivals classified DACK between 420.522 and 4485.739 seconds. “Consecutive” refers to that source's received-packet sequence; it does not assert continuously high custody between arrivals.

The attached backlog figure plots every custody change without sampling. MATLAB's source-7 population rises to roughly 160 and remains elevated for a substantial portion of the run. By cutoff it has fallen to 17, versus 21 native, illustrating why an end snapshot alone misses the delay-producing history. Source-8 time-average custody is much closer—15.89 versus 15.35—even though its arrival-weighted ACK fraction differs. The timing of arrivals relative to queue occupancy matters.

## 3. Feedback delivery recovers the observed receiver choices

The MATLAB delivery audit reconstructs 3,830 feedback transmissions from node 2 to node 8 using the observed receive, feedback-queue, replacement, TX and PHY events. It checks the reconstructed cumulative windows against every observed DATA completion.

- 3,601 feedback transmissions are accepted by the PHY; 151 are not acquired and 78 encounter half-duplex reception.
- 511 queue replacements occur, including 118 before that feedback generation's first transmission.
- Nevertheless, all 1,132 receiver decisions reach the matching completion. Mean receipt-to-completion time is **0.3275 s**, maximum **1.5625 s**.
- Native receipt-to-completion means are **0.3092 s for ACK** and **0.3111 s for DACK**, with maximum **1.9655 s** across the two classes.

Thus physical feedback misses and replacement occur, but there is no permanent completion attrition among accepted DATA in either captured history. Their possible effects on later timing are not ruled out by this statement.

Outer feedback frame labels cannot be counted as individual application outcomes: ten MATLAB ACK completions are carried in DACK-labeled frames, and seven DACK completions in ACK-labeled frames. Cumulative bitmap membership determines the per-application result.

The MATLAB CSV does not directly export full feedback bitmaps. Queue contents and bitmaps are inferred from the pinned production rules, then checked against observed TX heads, PHY envelopes and all completions. That inference is distinguished from directly captured fields. Native's long-run PHY trace exposes aggregate-front identity; its per-application logical feedback/completion events support the outcome joins without identifying every physical control child.

## 4. A concrete early service-order difference

Source 8's first application begins at the same nominal traffic start, but reaches node 2 at **301.381275 s in MATLAB versus 316.963815 s in native**. The native packet succeeds on its first transmission; retransmissions do not explain this particular gap.

| First source-8 DATA service | Corrected MATLAB | ns-3 |
|---|---:|---:|
| MAC enqueue | 300.000000 s | 300.000000028 s |
| First physical DATA TX | 300.144 s | 316.719 s |
| Accepted at node 2 | 301.381275 s | 316.963815 s |
| First source-7 DATA receipt at node 8 | 301.740812 s | 300.336812 s |

In native, source-7 traffic reaches node 8 first. Node 8 then sends **34 ACK/DACK transmissions to node 7 before its own DATA**. Twenty feedback generations and 19 replacements keep restarting the feedback repeat count; three generations are replaced without transmitting. The final feedback generation sends its fifth copy at 316.472 s, after which DATA transmits at 316.719 s.

The issued MATLAB model uses the same relevant wire sizes and packing limit: 41 bytes of cumulative feedback plus 217 bytes of DATA is 258 bytes, which exceeds the 256-byte 8-kbps aggregate limit. DATA cannot be appended to that feedback aggregate. In MATLAB's autonomous history, its own DATA starts transmitting before the first source-7 reception creates this feedback competition.

This locates an actual difference in traffic/service ordering. It does not establish that a 15.58-second first-arrival difference alone causes the full later backlog, or that the scheduler acts differently under the same inputs. During 300–400 seconds, node 2 admits original-source `(2,7,8)` traffic onward in counts **(29,6,17) MATLAB versus (31,0,0) native**; the competing populations and drain history have already diverged.

## 5. The relevant conditional MAC behavior was already tested

The September 23 accepted `out_mh_20260923_121427.zip` covers startup through just before 665 seconds for nodes 2, 4 and 8, not merely its labeled 657–665-second target interval. We recovered the actual MATLAB R2025a outputs and the issued `mac-history-fix.zip`, verified all 160 runtime-bound files, and compared their 0–330-second prefix with the newly recovered native fixture.

| Previously executed MATLAB prefix | Node 2 | Node 8 |
|---|---:|---:|
| MAC input events matched | 2,155 | 1,920 |
| Full native frame records matched | 101 | 91 |
| Actual TX records matched | 110 | 98 |
| Actual random-draw records matched | 130 | 111 |

Capture-local frame IDs differ. A bijection follows ordered enqueue events and validates every other frame field, including packet bytes and ACK/DACK masks. Global observer event numbers also differ; per-node input order, including tied times, matches. Numeric fields are compared exactly with decimal arithmetic. The MAC adapter and scheduler are byte-identical; the driver's change only affects its displayed target-window label. The changed production HOP file is outside this conditional MAC replay boundary.

The prior actual MATLAB output already satisfies all three newly identified assertions:

1. Node 8 first DATA transmits at **316.719 s after exactly 34 feedback transmissions to node 7**.
2. Node 2 first DATA toward node 4 transmits at **301.639 s**.
3. Node 2's later DATA frame transmits at **319.215 s after five feedback transmissions to node 8** while waiting.

The proposed two-node conditional MAC replay is therefore redundant and is not being issued. No new MATLAB command is required for this investigation.

## 6. Engineering decision

The receiver threshold, eventual feedback classification, reconstructed feedback delivery, and conditional MAC service all have supporting evidence. Changing ACK/DACK thresholds, hold durations, feedback priority or packing limits to move the aggregate means toward ns-3 would be unsupported.

The unresolved boundary is **how the autonomous network produces the different arrivals, receiver availability, cancellations and random-service history supplied to those components**. The existing MAC replay supplies these histories; its adapter explicitly gives the recorded receiver state control over sleep/wake availability. Its pass does not validate autonomous PHY/duty-cycle behavior or the complete coupled feedback loop.

The same numeric seed is not a common random-input tape. The current `RandomStreams.m` uses independently owned MATLAB `mt19937ar` streams and explicitly does not promise ns-3 stream equivalence. This makes different autonomous event histories possible without a local algorithm mismatch; it does not prove randomness explains the entire latency difference.

The ordinary long-run MATLAB export records MAC event names and times but omits their state/reservation details, raw random draws and draw ordinals, sleep/wake causes and timer deadlines, and a shared ordering across diagnostic tables. Zero omitted trace records only proves that configured rows were retained, not that these unexported fields are available. The existing optional `AckServiceDiagnostics` observer can preserve callback details and ordered service observations without owning events or RNG draws. It is a useful starting point for a focused capture, but its current callback coverage has not been shown to supply every missing autonomous PHY/timer/random input.

The highest-value next experiment, if additional execution is needed, is a short coupled contention case covering the **7→8→2→4 path**, with explicit initial state and shared exogenous traffic/random inputs, that leaves receiver availability and feedback generation endogenous. It should identify the first consequential divergence and follow its effect on admitted source mix and queue growth. Repeating the already-passed isolated MAC or capacity replay would not answer this question. Different numeric seeds or another long run without that control would also not distinguish an implementation mismatch from stochastic congestion sensitivity.

This is a proposed experimental boundary, not a claim that a complete coupled test package has been executed or prepared. Existing captures should be reused for its reference construction. Preserve the ±15% network goal; a component pass is not a substitute for the network acceptance table.

## Evidence and reproduction

The companion evidence archive contains the receiver, delivery, early-service, prior-acceptance and coverage audits; per-application joins; custody trajectories; source/time tables; the plotted data; and source/input hashes. Its README lists required original archives and commands. The large original native and MATLAB traces are preserved separately rather than duplicated in this package.

Key source identities:

- Native seed-132 compressed trace: SHA-256 `3da17e3397756f8890964d571932a44f7c94573b4d38eac9387342588883a4ef`, recovered from `t25up.zip`.
- Corrected MATLAB return: `out_6000_20260924_152302.zip`, SHA-256 `a3f7fd6fc09a5b0505c6a759a5c025390151bef484e7e15c9818e51a3f4f1484`.
- Prior executed MAC return: `out_mh_20260923_121427.zip`, SHA-256 `a513c157d7ba79d86cf32555fa412b6087a745e6a301c4771f14e1f4e8e5d7c4`.
- Its issued kit: `mac-history-fix.zip`, SHA-256 `0c53a1f28e3557a605361d30ca9a720298e3427b9cf190336625960cad89889b`.

All new work in this investigation was offline analysis of existing evidence. No new network simulation, production source change, or new MATLAB owner run was performed.
