# Tranche 12 clock boundary diagnostic

This six-case fixture follows up the single ingress/tick ordering incident in
the accepted Tranche 11 return. It executes the existing production MAC and
scheduler in each runtime. The first owner R2025a return passed all eight
clock tests and 72/72 clock checks. Only the continuous case differed from
native, in the expected three rows and four counter fields. The separate relay
fixture failed during construction-dependent callback use and requires a rerun.

The MAC starts Search at **1.699501 seconds** with one queued DATA frame. Its
24th real 13 ms tick occurs at **2.011501 seconds**, after the 300 ms holdoff.
Prescribed known-neighbor reservations leave slot 16 as the only free result
of the historical modulo-probe selection. This avoids requiring matching RNG
streams and does not use a forced-slot override. In native code that override
also changes the MAC timer phase, making it inappropriate for this diagnostic.
The synthetic neighbor occupancy is a public MAC input, not a 34-node network.

Five nanoseconds before the target tick, the reservation counter for neighbor 2
is reset to 16. A prescribed ingress then observes the local and neighbor
counters, updates that known neighbor's reservation to 16 through the public
MAC API, and observes again. A final observation two nanoseconds after the
boundary shows whether the tick happened before or after that reservation
update. The frame remains queued; this fixture does not transmit RF traffic.

| Case | Ingress scheduling | Expected order |
| --- | --- | --- |
| `tie_early` | Exact boundary, inserted at 1.989 s | Ingress before tick |
| `tie_late` | Exact boundary, inserted two ns beforehand | Tick before ingress |
| `before` | One ns before boundary | Ingress before tick |
| `after` | One ns after boundary | Tick before ingress |
| `continuous` | Reconstructed T11 airtime and propagation expression | Native ties; MATLAB follows tick |
| `quantized` | Same physical inputs, each duration resolved to integer ns | Ingress before tick |

The continuous expression is `1.989 + csr.phy.airtime(48,128,'short') + 1e-6`.
Its binary64 result is **2.0115010000000004**, one ULP above the MAC's
integer-anchored **2.011501**. `boundary.csv` retains each planned arrival's
binary64 hex encoding and offset from the anchored target, so rounding event
exports to nanoseconds cannot conceal that distinction.

There are **18 observations and 72 structural counter/queue checks**. Eight
MATLAB tests cover the six cases and the scope of the expected discrepancy.
The continuous case is intentionally included in strict native comparison:
all three of its observation rows differ, comprising four counter fields.
`MatchesNative` therefore remains false for the expected owner result, while
`SharedIntegerMatchesNative` must be true for the other five cases. Passing
structural checks use each runtime's declared time semantics; they do not
rewrite the continuous observation to its native value.

The native fixture has passed 72/72 checks against the unchanged pinned CSR
headers and the nine hash-verified libraries from the clean Tranche 11 build.
Its output, compile/run logs, source and input hashes are retained in
`evidence/tranche-12-clock-reference`. The original MATLAB files also passed static parsing. Actual owner MATLAB
execution is recorded in `evidence/t12r/owner.zip`; the independent audit is
`evidence/t12r/audit.json`.

Only the `quantized` test transport converts durations to integer nanoseconds.
The global scheduler and all existing MATLAB/Tranche 11 files remain unchanged.
This isolates event ordering and exposes the neighbor-state consequence; it
does not establish RF, HOP, NWK, relay, campus, or population parity.
