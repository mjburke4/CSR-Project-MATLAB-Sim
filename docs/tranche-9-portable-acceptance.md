# Tranche 9 portable acceptance

Tranche 9 is accepted for the source-confirmed MAC reservation correction,
matched subsystem contracts, and complete portable diagnostics. The returned
run proves a local scheduling change; it **does not reduce the measured
seed-129 delivery gap or establish numerical parity**.

The executed candidate is `99fff0381fe9621ccd76fbdce41eac9aba5a9469`, based on
accepted Tranche 8 metadata commit `d0f3c5657f9f2dcf678f32900020caf3696bf90a`.
The ns-3 reference remains pinned to
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. Post-return Python reporting repair
`419f2c18d0ab92ce9c60f9a1c9fa1f4fbf8486a1` changes no MATLAB files and is not
substituted for the executed candidate's source identity.

## Actual execution and verification

The owner ran MATLAB **25.1.0.2943329 (R2025a)** with the portable backend on
2026-09-11, from 18:01:56.345 to 18:25:37.630 UTC: **23 minutes 41.285 seconds**.
The review executed Python only; MATLAB and Octave remain unavailable in the
review workspace.

| Gate | Result |
| --- | --- |
| Portable MATLAB unit tests | 514/514 passed; none failed or incomplete |
| Matched MAC/HOP contracts | 101/101 checkpoints across six fixtures; exact agreement with native values |
| Diagnostic experiments | Six complete: contention seeds 128–132 and admission seed 129 |
| Tracing controls | Both pass; statistics/configuration exact and 24 CSV pairs byte-identical |
| Executed source | 206 files verified, including all 115 MATLAB files |
| Reference snapshot | All 294 files verified against the frozen candidate |
| Returned artifact hash/size checks | 438 passed across outer and nested inventories |
| Early service observations | 120,835 rows reconciled; 101,000 application attempts |
| Cancellation observations | 1,373 paired callbacks; five queued entries removed; reservation preserved |
| Python review and regression suite | Complete returned-evidence review passed; 254/254 Python tests passed |

The uploaded ZIP contains 177 files, 10,194,267 compressed bytes and 154,809,567
expanded bytes. Its SHA256 is
`ddcede0a83b5ff906a7736f63406fc4cecb11e841795e39e93237364e0e11edf`.
The nine declared MAT files stay on the owner's laptop; they were not required
to reconstruct the archived CSV/JSON evidence.

The [acceptance record](../evidence/tranche-9-portable-acceptance.json) binds
the complete archive, selected owner records, primary comparisons, and the
[independent gate](../evidence/tranche-9-r2025a-accepted/independent/independent-review.md).
All 115 executed MATLAB files remain unchanged by this acceptance.

## What changed versus Tranche 8

The correction preserves MAC preparation and the live reservation when DATA
or control cancellation empties a queue. Both cancellation fixtures and the
HOP capacity-release ordering contract now pass in actual MATLAB, matching the
recorded native execution. These fixtures prescribe subsystem conditions and
are not RF equivalence tests.

At contention seed 131, a cancellation leaves reservation counter zero.
Tranche 9 transmits node 3's queued application 4 at **303.823 s**, compared
with **303.901 s** in Tranche 8: **78 ms earlier**. The old reset caused the
reservation to expire and be redrawn. Eight application receive times change;
the net latency sum increases by 0.052 s across 895 deliveries. Mean latency
changes from 1.7154320223 to 1.7154901228 s, approximately **+58.1 microseconds**.
This is a measured local correction with no throughput improvement.
The actual ACK schedule, radio settings and feedback content remain unchanged
in all six cases when local decision-link identities are excluded; all six
application-admission traces are exact. The faster DATA transmission therefore
does not advance the observed ACK or application-admission schedule.

The other four contention cases have a positive reservation counter at their
early cancellation. The old code reactivated preparation before expiry without
redrawing that reservation. Tranche 9 removes one redundant preparation event
in each case; their application outcomes and full statistics remain equal.
The admission control retains all eleven compared legacy CSV observations.
Across all six cases, 54/66 legacy CSV comparisons are semantically equal;
the changed internal traces are retained, not erased or relabeled as equal.

## Application outcomes against ns-3

All six admission, delivery, explicit-drop and pending totals are unchanged
from the accepted Tranche 8 run. Delivery differences below use ns-3 as the
denominator.

| Experiment | Seed | MATLAB admitted | MATLAB delivered | MATLAB pending | ns-3 admitted | ns-3 delivered | ns-3 unmatched | Delivery difference |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Contention | 128 | 954 | 928 | 26 | 946 | 914 | 32 | +1.53% |
| Contention | 129 | 980 | 948 | 32 | 854 | 822 | 32 | +15.33% |
| Contention | 130 | 926 | 894 | 32 | 948 | 916 | 32 | −2.40% |
| Contention | 131 | 927 | 895 | 32 | 903 | 883 | 20 | +1.36% |
| Contention | 132 | 949 | 917 | 32 | 952 | 920 | 32 | −0.33% |
| Admission | 129 | 11,358 | 11,354 | 4 | 11,234 | 11,227 | 7 | +1.13% |

Across these six diagnostics, 345,000 application attempts produce 16,094
MATLAB admissions, 15,936 deliveries, no explicit drops and 158 pending
applications. The corresponding ns-3 counts are 15,837 admissions, 15,682
deliveries and 155 unmatched sends. The native unmatched category is not
reclassified as MATLAB pending or dropped work. Neither simulator records a
duplicate final delivery in these cases.

Five-seed contention means remain **916.4 versus 891.0 deliveries (+2.851%)**.
Packet-weighted delay is 1.6841942313 s in MATLAB and 1.7364124220 s in ns-3.
These five seeds are descriptive samples; matching seed labels do not imply
matched random streams or population equivalence.

## Early ACK service and capacity release

The main outlier persists: source 2 to gateway 1 at seed 129 delivers **510
versus 353 packets (+157, +44.48%)**. During `300 <= t < 320`, it delivers
152 versus 35; that early interval still accounts for 117 of the 157-packet gap.

| Seed-129 source-2 milestone | MATLAB T8/T9 | ns-3 |
| --- | ---: | ---: |
| First DATA delivery at gateway | 302.519104 s | 301.401104 s |
| First transmitted ordinary ACK toward source 2 | 302.549 s | 303.849 s |
| Next application admission after initial saturation | 302.574 s | 303.874 s |

The native trace explains its ACK delay through two receiver-Track intervals,
a slot-28 reservation countdown, and replacement of the queued cumulative
ACK before its first transmission. MATLAB reaches a different first reception
and contention sequence. The reservation correction does not align those
initial conditions or remove their numerical difference.

Both returned and native observations release capacity before the next queued
HOP admission. The delayed wake is approximately 27.7778 ns in MATLAB and
28 ns at the native clock's nanosecond resolution. The controlled ordering
contract agrees exactly. There is no demonstrated additional capacity-release
policy defect in these observations.

Ordinary DATA ACKs continue to use the same **128-kbps profile and +33 dBm**
in both models. This profile corresponds to 133,333.333... operational bits/s.
The sampled evidence supports no radio-rate or power-policy adjustment.
Startup control ACK choices, unexercised DACK/relay paths and varied link state
retain their earlier limits. Service row counts have different observation
boundaries in the two simulators and must not be compared as protocol totals.

The [independent service inspection](../evidence/tranche-9-r2025a-accepted/service/inspection.json)
retains per-flow values, changed packet times, cancellation state, and exact
raw-file comparisons.

## Reporting repair and reproducibility

The original Python reviewer rejected two valid representations in this return:
MATLAB logical JSON values versus CSV `1`/`0`, and the input installation path
moving from `csr8` to `csr9`. The narrow repair handles six declared logical
fields and verifies the input path suffix and SHA256 before allowing only its
installation prefix to differ. Every other configuration field compares
exactly. Ten new regression tests reject value, identity, hash and path masking.
Both initial failures, the repair diff and passing logs are preserved in the
[repair record](../evidence/tranche-9-return-repair.json).

No returned files or MATLAB sources were edited. No MATLAB rerun is required
for these review-tool corrections. To reproduce the review, use the repaired
Python scripts with a separate frozen checkout of `99fff038` as `--source-root`:

```bash
python3 scripts/analyze_tranche9_return.py \
  --evidence /path/to/tranche9_evidence.zip \
  --source-root /path/to/frozen-csr9 \
  --output /path/to/new-review
```

Keep the original `csr9.zip` when reproducing this exact owner run. The
acceptance metadata and Python repair make the current source snapshot
different from the original package, even though MATLAB code is identical.

## Next milestone and retained limits

Keep the **6,000-second campus benchmark** as the next milestone: one campus
rerun on the accepted correction, with the retained regression checks and
comparison to the frozen T7 campus/ns-3/archived OPNET evidence. The current
small-case gate supports carrying the correction forward; it predicts no
campus performance improvement.

For the unresolved parity investigation, isolate initial reservation selection
and receiver-busy timing with controlled, equivalent stimuli. A prescribed
receiver/occupancy fixture can separate scheduler behavior from different
random reception sequences. Do not tune ACK rate, power, load or numerical
tolerances to remove this single-seed gap; another policy change needs an
observed source mismatch. The two simulators' existing forced-slot overrides
are not equivalent and cannot be treated as matched controls.

No new campus, retained scenario/sweep, OPNET or MATLAB R2026a/native execution
is present here. T7's single-flow campus difference of −17.10%, prior outage
and retry limits, and full numerical/protocol/statistical parity remain
unresolved. No remote push, PR or merge was performed for this acceptance.
