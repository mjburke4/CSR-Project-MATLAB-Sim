# Seed-132 receiver timer arithmetic review

The discovery comparison checks passed in MATLAB. The common-input run reached **45.662638077 seconds**, with **758 matched and consumed random inputs** and **129 verified physical transmissions**. Its next stop is a source-confirmed difference in receiver timer arithmetic: the acquisition deadline is one floating-point step higher in MATLAB, causing the PHY to test 52 payload bits where ns-3 tests 51.

This is a narrowly identified implementation mismatch. At this particular sample, both bit counts produce zero errors with the native random value; a delivery difference has not been demonstrated. The full-network target remains **±15%**, including the original 6,000-second accounting and latency comparison.

## Actual return

Input: `out_auto_20260928_075726.zip`, SHA-256 `4f4c6cfdb8505c1520c880b21f3ee69207c73d034947f93aea38fda288484512`, 38 members. The returned source manifest matches all 322 issued files. Runtime was MATLAB R2025a 25.1.0.2943329, PCWIN64. Import and all **45 component checks** passed, including the seven new discovery identity checks. The accepted natural capture was reused after its existing source, runtime, configuration and exact prefix gates passed.

| Actual J result | Value |
|---|---:|
| Stop time | 45.662638077 s |
| Matched and consumed random inputs | 758 |
| Consumed MAC / SYNC / PHY inputs | 150 / 348 / 260 |
| Rejected next input | Node 3, PHY draw 75 |
| Verified physical transmissions | 129 |
| Application attempts | 0 |
| MATLAB wall time | 85.35 s |

Independent comparison confirms that all 888 observed random-request and transmission-context events, including the rejected request, follow the same native global order and rounded-nanosecond times. The rejected request did not consume its random sample. The diagnostic capture contains 91,379 ordered observations, with no omitted service or transport-timing records. This validates the checked observable prefix, rather than every internal state or native wrapper field.

The prior 25.740-second discovery transmission now passes. Seven broadcast discovery children carry the explicit outer-identifier annotation; four have different raw native and MATLAB identifiers. Their payload session sequences remain equal and checked. All applicable reliable packet sequences retain strict checking.

## The acquisition deadline changes the bit count

Native schedules acquisition by adding a 6,630,000-nanosecond delay to the current integer time. MATLAB's existing receiver engine schedules `Now + 0.00663` in binary64 seconds. The earlier transport correction covers receive arrival, preamble end and signal end; it deliberately left this internal acquisition timer unchanged.

At the stopped occurrence, acquisition is scheduled from native time 45,656,008,077 ns. Both deadlines round to 45,662,638,077 ns, so the existing rounded-time audit alone cannot distinguish them.

| Calculation | MATLAB floating addition | Native integer-time scheduling |
|---|---:|---:|
| Deadline in binary64 seconds | 45.662638077000004 | 45.662638076999997 |
| Positive interval × payload bit rate | 52.00000000000977 | 51.999999999954042 |
| Truncated bit count | **52** | **51** |
| Error probability | 0.000054585990544445831 | Same |
| Error count using the captured random value | **0** | **0** |

The deadline difference is approximately 7.1 femtoseconds. Both PHY implementations correctly truncate the positive interval product; changing the bit-count formula or adding an epsilon would alter the native contract. The justified correction is the timer's integer-nanosecond scheduling semantics.

The pinned native arithmetic probe reproduces both products and error counts without running a network simulation. This signal had already been rejected while the receiver was transmitting, in agreement with the returned MATLAB state. The evidence therefore establishes an arithmetic/context mismatch at this point, not an observed packet-delivery or latency improvement.

## Batched timer correction and existing-evidence sweep

The continuation covers acquisition, the 28-nanosecond rejected-reception return, and the paired MATLAB PHY/MAC transmit-completion deadlines. Each target adds separately rounded current-time and delay nanoseconds, then converts the resulting tick count to seconds. The transmitter's busy-until value uses that same completion target.

Native has one transmit-completion callback, which clears MAC transmit state and invokes device completion. MATLAB represents that work with a PHY callback followed by a MAC callback at the same time. Both MATLAB targets are corrected together, preserving their existing insertion order. Generic MAC timers and the scheduler itself are unchanged. Physical propagation, signal boundaries, header/payload boundaries and bit-count truncation are unchanged.

The existing native capture supports a broader check without commissioning another network run:

| Existing-evidence check | Result |
|---|---|
| Native PHY allocation intervals | 4,070 reconstructed |
| Recorded native PHY random samples | 1,542 reproduced bit counts |
| Floating acquisition-only counterfactual | 15 changed interval bit allocations; 9 sampled bit-count differences |
| Corrected callback-time arithmetic on the fixed history | No bit-count differences |
| Observed J acquisition schedules | 230; 58 have noncanonical floating deadlines |
| Observed J transmit-completion pairs | 129; 36 have noncanonical floating deadlines |

The first sampled counterfactual difference is the actual J stop. The other differences are predictions from arithmetic on fixed native traffic and event history, not executed MATLAB continuation outcomes. The 28-nanosecond return is source-confirmed but does not occur in this J prefix; it needs separate component coverage.

There is a bounded conversion caveat: the pinned Linux ns-3 build's fixed-point/extended-precision `GetSeconds()` differs by one binary64 step from direct nanosecond division at two of 10,301 inspected clock values. Neither conversion changes any of the 1,542 sampled bit counts or 4,070 interval bit allocations in this capture. The kit uses direct division, consistently with its existing transport timing. It does not claim universal bit-for-bit reproduction of ns-3's clock conversion. Across 1,352 native acquisition schedules, floating addition differs from direct-division targets in 335 cases, or from the pinned native conversion in 336 cases; those counts concern distinct conversion policies.

## Continuation and acceptance

The kit retains all 45 existing checks and adds eight timer checks in the same batch. They cover all 1,352 acquisition targets, all 811 transmit-completion targets, the source-only 28-nanosecond return calculation, the observed 52-to-51-bit boundary, the public allocator over all 1,542 sampled geometries, a public receiver acquisition transition, unchanged continuous/absent timing behavior, and the public paired PHY/MAC completion order. The final component uses one radio with seed-owned MAC draws; the geometry and acquisition checks request no random variates. The rejected-return check tests arithmetic and source binding, not an executed network rejection.

One new network case, `K_receiver_timers`, starts at zero and stops at the first checked divergence or 330 seconds. It retains the J protocol behavior and comparison policy, with only the mapped timer corrections. Separate timer-target records are exported even after a diagnostic stop. The original 99 model files, earlier candidate classes, native random inputs and semantic transmission fixtures remain unchanged. Neither a forced reception nor a forced admission is introduced.

Download `autonomous-receiver-timer-tests.zip`, extract it into a fresh folder, restart MATLAB and set Current Folder to `autocase`. Run:

```matlab
report = run_autonomous_tests;
```

Return the generated `out_auto_*.zip`, including any diagnostic stop. The accepted natural case is reused when its gates pass; historical J and earlier common-input cases are not rerun. No owner-side ns-3 command is needed.

The new MATLAB checks and K continuation remain pending owner execution. Application traffic begins at 300 seconds, so the current return cannot establish source-by-source attempted, admitted, delivered, dropped or unresolved application counts, comparable delivered-population latency, or the ±15% full-network target.

The sealed kit binds 355 files. All 143 MATLAB files pass static syntax parsing with MISS_HIT 0.9.44 using its MATLAB 2022a grammar. Independent review verifies 22 exactly reversible source transformations, all 99 unchanged model files, all 40 unchanged prior candidate/helper MATLAB files, and unchanged native reference fixtures. These checks do not substitute for MATLAB execution. Manifest SHA-256: `3721006cdd23beac861cf9356a78b859b2599345e06625204034bbff7dabafa2`.

No new long network simulation was commissioned for this review. The native comparison uses the existing 0–330-second capture; the local native execution is a component arithmetic probe.
