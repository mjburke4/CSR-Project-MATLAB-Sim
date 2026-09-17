# Tranche 16 owner-return review

The focused T16 diagnostic review is complete. The issued MATLAB candidate and owner evidence remain unchanged. The two repairs affect Python review logic only; no MATLAB rerun was performed.

## Verified evidence

- Owner runtime: MATLAB R2025a, version 25.1.0.2943329, portable backend.
- 129/129 focused MATLAB tests; 12/12 paired real-PHY network cases; 192/192 structural checks.
- 304 issued source files and 453 references matched exact manifests; 308 returned artifacts passed integrity checks.
- 97/97 Python reviewer tests passed, including 28 targeted repair regressions and 69 issued T11/T16 reviewer tests.
- Full network acceptance and numerical parity remain unestablished.

## Reviewer-only repairs

1. Accept the issued file-only reference declaration (453 explicit files, empty roots), retaining exact inventory, path, duplicate, before/after stability, SHA256 and byte-size validation.
2. Match aggregate endpoints to their declared integer bin identities within four binary64 ULPs. Require every core series/bin and reject duplicates, actual time shifts, incomplete grids and invalid declarations. Preserve numerical values and missing samples.

The unmodified reviewer first rejected the valid explicit-reference declaration. Its first repair then exposed endpoint serialization differences between native and MATLAB aggregate exports. Both original failure reports are preserved separately. The final review uses an external hash-bound overlay against the unchanged issued source tree.

## Paired outcomes

All six continuous/nanosecond pairs have identical admitted/delivered/dropped/pending counts, blocked attempts, node counters (including retries and ownership), actual ACK feedback members, physical transmission counts and reconstructed service results. Exported latency summaries retain only floating-point serialization residuals; reconstructed application summary differences are zero. No benefit from promoting nanosecond receiver timing was observed.

| Case | MATLAB admitted | MATLAB delivered | MATLAB pending | ns-3 admitted | ns-3 delivered |
|---|---:|---:|---:|---:|---:|
| a128 | 11394 | 11384 | 10 | 11380 | 11364 |
| c128 | 954 | 928 | 26 | 946 | 914 |
| a129 | 11361 | 11357 | 4 | 11234 | 11227 |
| c129 | 980 | 948 | 32 | 854 | 822 |
| a130 | 11331 | 11315 | 16 | 11412 | 11396 |
| c130 | 926 | 894 | 32 | 948 | 916 |

MATLAB application drops are zero in all twelve runs. These fixtures stop with negligible drain time; their pending applications do not establish a structural failure. Native unmatched sends retain their original classification. Admission delivery totals are 34,056 MATLAB versus 33,987 ns-3 (+0.203%); contention totals are 2,770 versus 2,652 (+4.449%). These are descriptive differences across independent simulator RNGs.

Detailed service observations cover [300,320) seconds only. Zero recorded CapacityReleased flags must not be interpreted as zero real custody releases: network_custody_release callbacks were observed and match between policies.

## Next milestone

Prepare Tranche 17 as the full portable regression suite plus one unchanged 6,000-second campus run with continuous receiver timing. Keep nanosecond timing optional. Preserve PHY/ECC and the established battery/supervisory/BBN exclusions. Evaluate complete application accounting, ownership, finite-stop backlog, routing and native aggregate differences before declaring the campus gate complete.

## Identity

- Upstream ns-3 pin: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` (not a MATLAB Git commit claim).
- MATLAB candidate SHA256: `f22a893457fd7927342ed7fa176c1e227d387f6a6be3631fd0204f9a53bc1a36`.
- Owner source snapshot SHA256: `90b5506f4fdb54f64ae7dac61c0e48df9da2253a8408a4b50b3ad30309ac1905`.
- Owner archive SHA256: `4fbfb17ba654bee0a137f1fc2d3ac3f65a091bf936d6c44589b1db9db1f4be60`.

`return/review.json` contains the complete machine-readable audit. `REPORT.json` includes identities, exact pair comparisons, reviewer hashes and remaining scope. `reviewer-fixes.patch`, `overlay-manifest.json`, the standalone overlay and its tests reproduce the repaired review.
