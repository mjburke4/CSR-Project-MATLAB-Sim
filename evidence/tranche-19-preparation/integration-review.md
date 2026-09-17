# T19 independent integration review

Scope: read-only integration QA of the MATLAB runner, scenario suite, policy
contract, immutable stage checkpoint helper, return checker and metrics. No
MATLAB runtime is available here. All executed checks below are Python/static
checks using existing accepted evidence or explicitly labeled adapter fixtures.

## Review findings addressed

1. The initial checker passed the new `Hop.DataQueuedRetryPolicy` field directly
   to the older T7 configuration validator, which requires the exact legacy HOP
   field set. This rejected both valid T19 cases. The new checker now verifies
   the requested policy, compares the whole remaining configuration with T17,
   and passes an independently stripped copy to the legacy validator.
2. The initial aggregate-comparison call required a legacy
   `benchmark_manifest.json`, but the T19 runner writes its own `case.json`
   schema. A dedicated T19 input adapter now builds comparison inputs outside
   the original evidence; it neither modifies owner bytes nor synthesizes a
   historical execution manifest.
3. The original new metrics and case verifier did not explicitly connect the
   reconstructed final application population to the raw whole-run counters.
   The checker now binds admitted, delivered, dropped, pending, attempt and
   blocked totals. The metrics also reject duplicate delivery and inconsistent
   delivery endpoints, times or payloads.

The root reviewer separately identified valid unmatched DATA sent indications:
`Transmitted` can exceed emitted `hop_sent` callbacks when ownership has already
retired. The metrics now require a nonnegative per-node remainder and report it
without assigning those indications to a packet or link. All other exported
HOP event/counter identities and ownership endpoint checks remain strict.

## Executed integration checks

- The ownership metrics consumed the original full T17 campus files and
  reproduced 1,710,000 attempts, 12,484 admissions, 11,825 deliveries, 402 drops
  and 257 pending applications. Reconstructed HOP and NWK endpoint ownership
  matched all seven exported node rows.
- Both intended policy fields pass the exact configuration adapter on T17's
  original configuration. An additional `MaxResends` change is rejected.
- The repaired legacy configuration call passes on the policy-stripped copy.
- The new aggregate adapter runs on archived T17 raw and aggregate bytes and
  produces all three MATLAB/ns-3/OPNET inputs over 6,000 seconds, 60-second
  buckets and 100 buckets. The adapter fixture is explicitly labeled as
  T17-derived offline QA, not T19 execution evidence.
- The provisional frozen preparation check passes with 356 source bindings,
  60 reference files, 700 planned MATLAB tests and two planned cases. Exactly
  the two declared HOP files differ among the 346 accepted T18 source bindings.
  This provisional check binds candidate SHA-256
  `e165198754a51946a868f186bf9a3dee3ea3e6873fbed8eff1366ed25ef73a87`;
  any later source/test change requires refreezing and rechecking.

## MATLAB and handoff review

The source/reference arrays are column struct arrays before JSON serialization;
the test-name cell arrays are wrapped as scalar summary fields. Case and stage
schemas match the checker after the fixes above. Complete stages require exact
candidate, runtime, source, reference and artifact identities. Partial stages
are rejected, preserved and documented for copying only completed stages into
a fresh output directory. The old T17 checkpoint implementation is unchanged.

The original seven-node/six-flow scenario, seed 128, 6,000-second duration,
real PHY, continuous timing, full attempt counts and trace budgets are fixed in
the plan and checked by the suite. Original benchmark metadata is retained.
The default case must reproduce T17 raw statistics and original core CSV
bytes; the experimental case can change scheduling and later RNG consumption.

No numerical acceptance gate or default-policy promotion is introduced. The
plus/minus 5-percent band is descriptive for total and per-flow admissions and
deliveries. Full runtime acceptance, the new policy's behavior and any numerical
improvement remain pending the owner's MATLAB return.

## Final frozen integration gate

Independent final preparation/schema verification passed for candidate
`37b87a253a217824b0160f14b23f2b498e9df7a99cdc46648f3d9785a2fda777`:
358 source bindings, 170 MATLAB files, 60 references, 700 planned MATLAB tests
and two full-campus cases. Per-file reviewed hashes are in `final_gate.json`.
No unresolved integration blocker remains in the reviewed source.

The full-schema replay test was also reviewed against the MATLAB runner. It
does not bypass or mock the review function. It intentionally uses T17's
accepted outputs for both policies inside a clearly labeled temporary
synthetic envelope, so it validates checker compatibility rather than T19
execution. Its simplified inventories omit optional MAT files and CSV row
count annotations; separate focused tests cover these representations. The
actual runner's additional manifest/metadata fields do not conflict with the
checker. The checker author owns execution of that replay and its final test
result. Actual MATLAB serialization and all 700 MATLAB tests remain pending.
