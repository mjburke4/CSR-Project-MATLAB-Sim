# T18 independent scientific review

The returned results do not support changing node 5 to correct an unconditional local-DATA priority bug. The three isolated mixed-traffic seeds show no consistent local-traffic advantage over native ns-3, and their completed local/relay queue waits are similar within each simulator. The campus prefix reproduces substantial full-network pressure, including the accepted queued-retry timer distinction, but its local-traffic difference has the opposite sign from the final T17 campus result. These observations localize a state- and time-dependent interaction; they do not establish a new implementation defect.

This review independently joins the raw application records, service callbacks and native trace identities. It does not replace the official structural/integrity gate. Identical seed labels are configuration labels, not common random-number streams, and packet identifiers are joined only inside each simulator.

## Application results

Counts below are accepted application admissions and unique delivered applications by the fixed stop. Offers blocked by the historical NSDP rule are not admitted applications. All three-node MATLAB cases have zero terminal application drops; undelivered admitted work remains pending at the finite stop.

| Case | Source | MATLAB admitted/delivered | ns-3 admitted/delivered |
|---|---:|---:|---:|
| Relay only, 128 | 4 | 297 / 251 | 278 / 248 |
| Relay only, 129 | 4 | 298 / 251 | 292 / 252 |
| Relay only, 130 | 4 | 295 / 253 | 287 / 249 |
| Local only, 128 | 5 | 599 / 583 | 589 / 573 |
| Local only, 129 | 5 | 595 / 579 | 596 / 580 |
| Local only, 130 | 5 | 589 / 574 | 603 / 587 |
| Mixed, 128 | 4 | 215 / 171 | 220 / 180 |
| Mixed, 128 | 5 | 194 / 178 | 171 / 155 |
| Mixed, 129 | 4 | 218 / 187 | 214 / 169 |
| Mixed, 129 | 5 | 172 / 156 | 174 / 158 |
| Mixed, 130 | 4 | 214 / 171 | 225 / 181 |
| Mixed, 130 | 5 | 173 / 157 | 173 / 157 |

For source 5 in mixed traffic the delivery differences are +23, -2 and 0 across seeds 128–130. Source 4 differences are -9, +18 and -10. Three seeds are not sufficient to establish statistical equivalence, but they do not reproduce a stable local-over-relay bias. Local-only delivery differences also change sign (+10, -1, -13).

## Node 5 service

These are completed elapsed intervals between an observed NWK enqueue and its first HOP submission. Pending intervals remain separate in `independent_metrics.json`; no finite-stop lower bounds are averaged into these completed means. Native unsent queue occupancy is not equated to MATLAB's full retained-custody occupancy.

| Mixed seed | MATLAB local mean (s) | MATLAB relay mean (s) | ns-3 local mean (s) | ns-3 relay mean (s) |
|---|---:|---:|---:|---:|
| 128 | 15.45 | 15.60 | 17.59 | 17.44 |
| 129 | 16.97 | 16.44 | 16.60 | 16.98 |
| 130 | 17.87 | 16.98 | 16.34 | 16.39 |

These queue-wait observations are consistent with the source audit's absence of an explicit local-over-relay priority. They do not prove fairness under all topologies, nor eliminate effects from per-flow admission, queue scanning, reservations or callback ordering.

## Campus prefix

The 900-second prefix delivers 1,224 MATLAB applications versus 1,245 native applications (-1.69%). MATLAB admits 1,536 and records 52 terminal application drops plus 260 pending applications; all 1,536 outcomes reconcile. Native's 1,606 admissions minus 1,245 deliveries leave 361 unmatched sends in this review; this is not classified as 361 drops or pending applications because native custody completion does not alone prove the end-to-end fate.

| Application source | MATLAB admitted/delivered | ns-3 admitted/delivered |
|---|---:|---:|
| 2 | 102 / 45 | 85 / 44 |
| 3 | 930 / 917 | 876 / 862 |
| 4 | 82 / 51 | 64 / 43 |
| 5 | 150 / 133 | 256 / 236 |
| 7 | 143 / 34 | 188 / 35 |
| 8 | 129 / 44 | 137 / 25 |

Source 5 has 106 fewer admissions and 103 fewer deliveries in the prefix, whereas the full T17 run ended with 272 more admissions and 275 more deliveries. The 900-second slice therefore must not be described as reproducing the long-run source-5 surplus. The existing T17 full-run timeline localizes repeated sign changes without another simulation. The parent review's independently reconstructed 300-second timeline (`../timeline/t17_flow_timeline_300s.csv`) reports source-5 cumulative delivery differences of -103 at 900 seconds, +15 at 1,500, -19 at 1,800, -2 at 2,700, +55 at 3,000 and +275 at 6,000. Several large positive increments occur late (3,600–3,900: +75; 4,800–5,100: +87; 5,400–5,700: +93). Those timeline results are attributed to the parent reconstruction rather than this script.

At node 5, completed enqueue-to-submit means are 40.37 seconds for MATLAB local traffic versus 23.28 seconds native. For relayed sources 2,4,7,8, MATLAB means span 62.54–107.94 seconds versus native 36.82–58.48 seconds. Both cohorts experience the full-network pressure; these are different realized queue populations and not a matched-packet causal experiment.

## DATA retry and DACK observations on 4→5

| Case | MATLAB retry submissions | Native retry submissions | MATLAB DACK completions | Native DACK completions |
|---|---:|---:|---:|---:|
| Relay only, 128 | 8 | 11 | 184 | 183 |
| Relay only, 129 | 9 | 17 | 183 | 183 |
| Relay only, 130 | 9 | 25 | 184 | 178 |
| Mixed, 128 | 14 | 14 | 143 | 154 |
| Mixed, 129 | 9 | 18 | 152 | 143 |
| Mixed, 130 | 12 | 26 | 147 | 148 |
| Campus prefix, 128 | 171 | 142 | 37 | 10 |

These are DATA-only link observations; including CONTROL produces a different retry count. Retry submission is not synonymous with an actual over-the-air retransmission. Local-only cases do not generate DATA for this link.

In the prefix, 171 MATLAB retry requests resolve into 167 actual retransmissions and four terminal callbacks before the next retransmission; none remains awaiting retransmission at stop. The completed retry-submission-to-TX wait averages 2.308 seconds and reaches 16.824 seconds. Of those 167 waits, 51 exceed 2 seconds, 27 exceed 4 seconds, and 10 exceed 10 seconds. The intervals establish that queued waiting is materially exercised. They do not establish how changing the queued retry clock would alter this run: a changed expiry can alter later capacity, admissions, reservations and RNG consumption.

MATLAB has 28 terminal DATA hop failures on 4→5; native has 31 `no_ack` DATA custody completions. These are link/custody outcomes, not application-origin counts or a direct measure of final application loss. The 37 MATLAB DACK completions comprise 19 source-7 and 18 source-8 applications; native's ten comprise nine source-7 and one source-8 applications. DACK is receiver pressure feedback, not a drop. Both engines exercise the intended upstream-flow pressure, with different magnitudes.

## Warranted next milestone

Preserve the accepted production behavior, continuous timing and PHY/ECC. T18 does not justify a local/relay priority correction or a throughput-fitting change.

The next bounded parity question is whether the documented difference in queued-retry expiration materially drives the later campus admission redistribution. The existing T17 timeline now localizes repeated early sign changes and strong later divergence, so a shortest-prefix-only experiment would be insufficient. If further behavior parity is required, compare the current retry-clock policy against a diagnostic native-compatible clock policy inside the same MATLAB engine, using controlled draws/replay for the mechanism test and several seeds under the full topology for network sensitivity. Preserve the simulation history into the selected later observation intervals; do not restart a late window with empty queues and call it equivalent. Confirm actual TX, retry expiration, NSDP/capacity release and per-source admissions. A policy switch should remain experimental until its effects and any regression in custody reliability are demonstrated. Treat native timer behavior as an accepted parity exception if the experiment does not show a worthwhile benefit.

No additional full 6,000-second baseline rerun is warranted merely to accept this return. No causal claim or production change follows from aggregate differences alone.

## Reusable outputs

- `analyze_independent.py`: reproducible independent raw aggregation.
- `independent_metrics.json`: per-case/source outcomes, node-5 service waits, finite-stop unsubmitted ages, and link event counts.
- `flow_comparison.csv`: flattened admitted/delivered/delay comparison.
- `prefix_retry_waits.json`: 167 actual prefix retry service intervals with within-MATLAB packet provenance.

Counts in the broad native `link45_events` inventory outside the explicitly summarized hop events can carry radio-level source fields; they are not used as original-application cohort identities. The scientific tables use application-origin identity on NWK/HOP records.
