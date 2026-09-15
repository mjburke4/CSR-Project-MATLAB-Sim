# Tranche 7 independent outcome review

The returned R2025a evidence supports the bounded portable campus benchmark
milestone. All retained outcome checks and the five strict shared application
comparisons pass. Numerical or full protocol parity is not established.

The original ZIP SHA-256 is
`ea39b86ef68f91a551e4e22d176e2e96dc5305f33673741eee0adc6039599655`.
The executed MATLAB candidate is `28ed878f5673e308047cbea7878b933697d932f3`.
The recorded run spans 14:25:45.905–15:53:49.092 UTC on 10 September 2026:
**88 minutes 3.187 seconds**, with **467/467 tests passing**. No local MATLAB
execution or new OPNET execution was performed during this review.

## Benchmark outcomes

| Case | MATLAB admitted / delivered | ns-3 admitted / delivered | Delivery difference | MATLAB dropped / pending |
| --- | ---: | ---: | ---: | ---: |
| Campus, 6,000 s | 12,382 / 11,727 | 12,417 / 11,769 | −0.357% | 401 / 254 |
| Two-node admission, 1,200 s | 11,395 / 11,385 | 11,380 / 11,364 | +0.185% | 0 / 10 |
| Three-node contention, 360 s | 954 / 928 | 946 / 914 | +1.532% | 0 / 26 |

Raw MATLAB generation/delivery identities and ns-3 send/delivery identities
were reconstructed independently. For each simulator and case, all **800
common aggregate points** match the reconstruction: **4,800 checked points**
overall. Every configured flow admitted and delivered packets. The complete
MATLAB admission counters record 1,710,000 / 45,000 / 60,000 attempts; every
blocked attempt was the documented local NSDP admission limit. Campus's bounded
admission trace omits 1,610,000 records; the admission counters and application
protocol trace remain complete.

All 401 campus application losses are recorded as retry exhaustion. Physical
receiver-observation losses are separate from application losses. Finite-stop
pending packets are retained as pending. The ns-3 unmatched sends (648 / 16 / 32)
are not sufficient to distinguish terminal loss from unfinished work.

The campus archived OPNET rates imply 12,072 sends and 11,410 receipts over
6,000 seconds. MATLAB's receive rate is **2.778% higher** than OPNET. OPNET's
five empty initial count buckets are missing while MATLAB/ns-3 represent them
as zeros; full-window rates and equal-support comparisons avoid comparing
means with different denominators.

## Delay and flow residuals

| Case | MATLAB mean of populated bucket delays, s | ns-3 same definition, s | Difference |
| --- | ---: | ---: | ---: |
| Campus | 102.941880 | 103.181006 | −0.232% |
| Two-node | 0.942589 | 0.947511 | −0.519% |
| Three-node | 1.727025 | 1.914475 | −9.791% |

Campus OPNET's corresponding delay is 112.748007 s; MATLAB is 8.697% lower.
These values average populated bucket means, not individual packet delays.
The independently reconstructed packet-weighted means are 103.963442 /
104.194771 s for campus, 0.937722 / 0.942770 s for two-node, and 1.640671 /
1.694846 s for contention (MATLAB / ns-3). The two delay definitions answer
different questions and should not be interchanged.

| Campus source | MATLAB delivered | ns-3 delivered | Difference |
| --- | ---: | ---: | ---: |
| 2 | 395 | 410 | −3.66% |
| 3 | 8,593 | 8,535 | +0.68% |
| 4 | 454 | 419 | +8.35% |
| 5 | 1,285 | 1,369 | −6.14% |
| 7 | 617 | 574 | +7.49% |
| 8 | 383 | 462 | −17.10% |

The near-equal campus total masks different allocation among flows. The
largest campus absolute delay-bucket difference is 140.468 s in the bucket
ending at 1,980 s; the largest received-count difference is 24 packets in the
bucket ending at 3,540 s. In contention, sources 2 and 3 differ by +7.43% and
−4.04% in delivery, respectively. No observed residual is causally attributed
to PHY, reverse-link control, routing, queues or RNG by this evidence alone.

## Retained regression gate

Every non-runtime field exactly matches the accepted T6 return in all 18 sweep
scenario rows, all 18 sweep performance rows, and all 28 retained T2/T3/T4
scenario rows. The only excluded column is `RuntimeSeconds`: **3,127 exact
non-runtime cell comparisons** passed. The retained 18 sweeps still deliver
334 of 357 applications, with 23 recorded losses and none pending.

The existing comparator was rerun with `--require-application-equality` for
`two_node_8`, `two_node_128`, `line_3_8`, `high_rate_500`, and `high_rate_1000`.
All five exit successfully with `application_match`, three applications each.
This preserves the bounded application outcome contract; latency differences
and PHY/MAC/NWK histories are not certified by that gate.

## Recommended next diagnostic

Repeat the smaller two-node and contention cases across several seeds before
drawing an inference about persistent bias. Add a short, instrumented reverse
ACK/DACK rate-and-power fixture and peer-S0/failure-state observations to
compare the already documented link-control decisions with ns-3. Use those
results to choose a bounded protocol correction. Investigate campus flow 8
after identifying persistent differences in the smaller fixtures. Preserve
the current MATLAB candidate and do not tune PHY/ECC to fit aggregate numbers.

`outcomes.json` contains counts, per-flow packet-weighted delays, bucket maxima
and exact regression comparison membership. `audit_outcomes.py` reconstructs
these checks independently of the candidate's aggregate and return reviewers.
`shared-comparison/` contains the five newly generated strict comparison reports.
