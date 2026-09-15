# Tranche 11: focused MATLAB milestone passed

The repaired Tranche 11 package passed its focused structural gate on **MATLAB R2025a (25.1.0.2943329)**. All four controlled replay cases completed, and **52/52 MATLAB tests plus 56/56 service checks passed**. The returned execution interval was approximately 18.3 seconds, excluding final archive creation.

This review verified the returned evidence against the exact repaired candidate. No simulator code was changed after the owner run. The full Tranche 10 accepted baseline remains intact: **225 source files, including 124 MATLAB files, are byte-identical**. All **241 current source bindings and 78 reference bindings** verified successfully.

## Complete replay results

| Check | Result |
| --- | --- |
| Controlled cases | 4/4 completed |
| Applications delivered | 32/32 |
| Capacity releases | 32; no applications pending at the horizon |
| Service assertions | 56/56 passed |
| Contention draws | 133/133 exact matches, including time, raw input and resolved selection |
| Tape usage accounting | 12/12 rows exactly matched |
| Event timestamps | 1,756/1,756 exact matches at exported nanosecond resolution |
| Complete event rows | 1,754/1,756 exact matches; two counter-only differences |
| Transmitted radio settings | 128 kbps and +33 dBm throughout this fixture |

| Case | Delivered | First ACK transmission, s | First capacity release, s |
| --- | --- | --- | --- |
| `ab` | 8/8 | 0.698501 | 0.723042 |
| `ba` | 8/8 | 0.698501 | 0.723042 |
| `slow` | 8/8 | 1.049501 | 1.074042 |
| `track` | 8/8 | 0.711501 | 0.736042 |

All timings in that table are identical in MATLAB and native ns-3. Swapping source draws swaps their initial DATA transmission times. The slower gateway draw delays the first ACK by 351 ms; the Track case delays it by 13 ms. The Track interval covers preparation and ends before the ordinary first ACK, so it does not establish a separate ACK-ready holdover result.

## Two retained differences

In `slow`, source 3's fourth application arrives at gateway 1 at **2.011501 s**. The observations immediately before and after reception (case orders 437 and 438; combined rows 1283 and 1284) record reservation counter **15 in MATLAB and 16 in ns-3**. Every other exported field in those rows matches.

The source and arithmetic reconstruction support a difference in event ordering at that clock boundary. MATLAB computes arrival as `1.989 + 0.022500000000000003 + 0.000001 = 2.0115010000000004`, just after the MAC tick represented as `2.011501`. Native ns-3 uses integer nanoseconds; its arrival callback was inserted before that tick. Both observation times export as 2,011,501,000 ns.

The owner return does not retain raw double timestamps, so that causal explanation is reconstructed from source and scheduling evidence, rather than an additional instrumented MATLAB run. There was **no observed effect on this replay's transmissions, ACK timing, admission, capacity release, delivery or contention draws**. Other workloads could expose sensitivity, including neighbor reservation state; the difference is retained as a bounded residual rather than declared universally harmless.

The strict comparator still correctly reports `MatchesNative=false` and two mismatched rows. No comparison rule, tolerance or source behavior was changed to obtain a pass.

## Disposition and next milestone

Keep **csr11r** as the successfully executed focused diagnostic package. No further Tranche 11 rerun is needed for this disposition. The earlier ACK-power harness failure is resolved by the returned execution.

The next useful investigation is a small **campus 4 → 5 → 1** experiment, concentrating on how node 5 shares service between locally generated applications and relayed traffic. Inspect admission, relay custody, queue service, ACK scheduling and capacity release under controlled inputs before changing production policy. This review does not begin that new milestone.

These results support the prescribed MAC/HOP service chain. They do not establish RF, full NWK admission/routing, OPNET, stochastic-population or full campus parity, and they do not replace the full acceptance suite. PHY/ECC, radio policy, routing and the normal RNG implementation remain unchanged.

## Provenance

- Repaired candidate SHA256: `6e06098a3d3f32568940685da181ae70c90749a5cde17a86ff33d9a8da668efe`.
- Owner archive SHA256: `ef989210fc9e5c1e85573a097bee6f9b4cdac9a5cbda79069d99a6a98f804e6a`.
- Native source commit: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.
- Full repaired package SHA256: `76b2d2ba6bd653efb0657730d3b286f03b7d0fc782ff242f92243c69e7f0f57e`.

The companion `t11rev.zip` contains the authentic owner ZIP, strict machine-readable review, independent residual analysis, milestone record and documentation updates. The review environment did not execute MATLAB.
