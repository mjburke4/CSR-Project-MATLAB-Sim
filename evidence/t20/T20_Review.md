# Tranche 20 review

**Accepted for portable regression and full-campus multi-seed structural validation. No MATLAB rerun is needed.**

The returned R2025a evidence passes all 716 portable tests and both new 6,000-second campus cases. Owner wall time was 153.83 minutes. Seed128 is reused from the authentic accepted T19 actual-tx case. All 376 source bindings and 98 reference files match the issued candidate; all 358 prior source files remain unchanged.

## Network totals

| Seed | MATLAB unique delivered | ns-3 unique delivered | Difference | MATLAB admitted | ns-3 admitted |
| --- | ---: | ---: | ---: | ---: | ---: |
| 128 | 11,825 | 11,769 | +0.476% | 12,484 | 12,417 |
| 129 | 11,851 | 11,787 | +0.543% | 12,551 | 12,463 |
| 130 | 11,758 | 11,765 | -0.059% | 12,454 | 12,661 |

The pooled delivery difference is +0.320% (35,434 versus 35,321). All three network delivery totals meet the descriptive ±5% target. This is an initial three-seed screen, not statistical equivalence.

## Individual flow delivery differences

Percent difference is (MATLAB − ns-3) / ns-3, using unique delivered application identities.

| Source | Seed128 | Seed129 | Seed130 |
| --- | ---: | ---: | ---: |
| 2 | +0.24% | -2.92% | +9.72% |
| 3 | -0.74% | +0.48% | +0.48% |
| 4 | -16.95% | -6.57% | -6.37% |
| 5 | +20.09% | +5.03% | -12.70% |
| 7 | -7.14% | +0.66% | -29.57% |
| 8 | -9.74% | -2.17% | +263.16% |

The close network total hides substantial flow differences. Source3 accounts for roughly 72% of MATLAB deliveries and agrees closely; other flows can offset each other. Only source3 is inside ±5% in every seed.

Source4 is lower in all three seeds (−16.95%, −6.57%, −6.37%). The decomposition differs: seed129 admissions are almost equal but conditional delivery is worse; seed130 has fewer admissions and almost the same conditional delivery. A universal retry or admission cause is not established.

Source5 changes from +20.09% to +5.03% to −12.70%; these results do not support a persistent local-traffic advantage. Its conditional delivery rates differ by less than one percentage point, so most delivered-count variation follows admission variation.

Seed130 deserves a bounded trace investigation: source7 admissions are 802 MATLAB versus 1,381 ns-3, while source8 admissions are 654 versus 181. Source8 delivery conditional on admission is almost equal (73.85% versus 73.48%); its large delivered-count residual mainly reflects admission allocation. These observations identify where behavior diverges, not a proven model defect.

## Latency and complete accounting

| Seed | MATLAB mean delivered delay (s) | ns-3 mean first-delivery delay (s) | Difference | MATLAB drops | MATLAB pending at stop |
| --- | ---: | ---: | ---: | ---: | ---: |
| 128 | 98.97 | 104.19 | -5.01% | 402 | 257 |
| 129 | 103.04 | 102.26 | +0.76% | 436 | 264 |
| 130 | 99.14 | 156.02 | -36.46% | 432 | 264 |

Latency is conditioned on delivered applications, so different admitted/delivered populations affect the averages. Seed130 ns-3 source7 mean delay is 1,563 s versus 708 s in MATLAB, and source8 is 1,055 s versus 586 s. Network delivery agreement does not establish delay parity.

All admitted MATLAB applications are accounted for as delivered, retry-exhaustion drops or pending at the finite stop. Each new case has 1,710,000 offered attempts. Protocol and PHY traces are complete; admission counters are complete, with the original first-100,000-attempt trace prefix retained. Native unmatched sends are not relabeled as either drops or pending work.

The native references contain six repeated application delivery events in seed129 and four in seed130. Those events retain source-proven lineage and are included in event-based aggregate statistics, but each application is counted once in the delivery comparisons above. No duplicates are removed from raw evidence.

Archived OPNET evidence remains aggregate context for seed128 only; there are no matched OPNET runs for seeds129/130.

## Decision and next milestone

Keep the accepted actual-tx default, PHY/ECC and continuous timing unchanged. T20 meets the few-percent goal for whole-network delivered counts across these seeds; it does not meet that goal for every flow or for delay.

Recommended T21: use the existing complete traces to explain the seed130 source7/source8 admission and delay split, and check source4’s persistent deficit. Separate route availability, relay custody/backpressure, and retry loss in time before considering a behavior change. Do not launch another full campus run solely to repeat this accepted validation.

## Verification and reproducibility

The issued return checker completed its full source/reference, native lineage, aggregate, protocol-accounting and receipt checks. Independent integrity review and independently derived per-flow counts agree. Twenty-two focused Python checks passed; the opt-in synthetic replay was skipped because the real owner return was reviewed. The issued preparation record already contains its earlier full 23-test synthetic replay. No reviewer executed MATLAB.

Run the issued checker from the exact T20 installation:

```bash
python3 scripts/analyze_tranche20_return.py --evidence PATH/t20.zip --source-root . --output PATH/new-t20-review
```

The package preserves the original return, machine-readable acceptance and comparisons, independent audit scripts/reports, and source-recovery provenance. The original issued source is unchanged.
