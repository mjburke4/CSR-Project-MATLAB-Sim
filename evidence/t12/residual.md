# Tranche 12 repaired return: independent residual review

The repaired owner run supports the focused relay/local service milestone with explicit residuals. Strict MATLAB/native trace equality remains false. This analysis reads the owner CSVs directly, independently of the acceptance gate, and leaves both source trees unchanged.

| Comparison | Result |
| --- | --- |
| Applications admitted/delivered | 120/120, same identities and order; no owner-reported drops |
| NWK release callbacks | 180, same order, custody and NSDP counts |
| Relay events | 2,344 in each implementation; all event identities/order agree |
| Event timing | 1,566 rows are 28 ns earlier in MATLAB; 778 timestamps match exactly |
| Random replay | All 332 raw values, ranges, resolved slots, purposes and ordering agree; times are 28 ns earlier in MATLAB |
| Tape usage | All 12 rows agree, including unused suffixes |
| ACK/DACK bitmaps, MAC state/counters, rate/power | Exact at every exported row; transmit radio settings were fixed at key 128 and +33 dBm |
| Other state residual | Five release rows: MATLAB has one fewer resend and one more DACK hold |
| After ingress | All 422 non-time state snapshots match |
| Checkpoint/final | All 24 complete rows match exactly |

The runner's 1,898 unmatched rows are 1,566 event rows plus 332 draw rows. The five transient state mismatches are already included among those event rows; they are not additional lost packets or failed service checks.

The earliest event mismatch is relay row 37 (`tx_start`): MATLAB 351,000,000 ns, native 351,000,028 ns. The first draw is MATLAB 13,000,000 ns versus native 13,000,028 ns. Native `ScheduleCheckNwkQueue` waits `CsrOpnetTic()` (1/36 MHz, rounded to 28 ns); MATLAB `wake` schedules `pump` at the current time. The source and measured common offset support a first-service clock-epoch explanation. No counterfactual simulator run was used to assert sole causality.

The five non-time residuals occur at mix case orders 480, 481, 482, 530 and sw order 573. Native calls the NWK release callback before inserting a DACK hold and removing its resend; MATLAB performs that migration first. NWK custody and NSDP release, total HOP pending and the subsequent stable state agree. This is observable callback ordering, with no service impact demonstrated in these cases.

| Case | Delivered | Last MATLAB delivery (s) | DACK holds at 16 s | DACK holds at 24 s |
| --- | ---: | ---: | ---: | ---: |
| relay | 20 | 2.556462000 | 0 | 0 |
| local | 20 | 2.453501000 | 0 | 0 |
| mix | 40 | 2.634021000 | 4 | 0 |
| sw | 40 | 2.142481000 | 1 | 0 |

Every delivered application is 28 ns earlier in MATLAB, so mean delay, maximum delay and last-delivery time have the same 28 ns offset. The mixed-case temporary holds drain by 24 seconds. The owner CSV does not expose exact DACK-expiry events, so the returned data must not be described as an exact expiry-time comparison.

Recommended next milestone: retain this short chain and introduce bounded DATA/ACK loss with offers continuing across retransmission and DACK-expiry boundaries. Check custody, duplicate suppression and capacity reuse under active demand. Include callback and one-TIC sensitivity microcases before considering a production timing/order change. The long campus test can follow that bounded recovery milestone.

This fixture uses controlled successful addressed transport and prescribed routes/radio settings. It cannot establish RF/collision/half-duplex behavior, adaptive power/rate decisions, route convergence or campus parity. No production files were changed and no new MATLAB execution is claimed by this review.

Exact input/source hashes, field counts, transient rows and per-flow statistics are in `residual.json`. Reproduce from the workspace root with `python t12v/analyze_residual.py`.
