# Independent Tranche 8 candidate review

The candidate is suitable for owner MATLAB validation, conditional on the
final local-check record and packaged-file verification. This is approval
of the diagnostic candidate, not acceptance of Tranche 8 MATLAB execution.
MATLAB and Octave are unavailable in this workspace. The owner must return
the actual MATLAB test, diagnostic and observer-control evidence before
runtime acceptance or paired simulator conclusions can be recorded.

The review used T7 acceptance commit
`68e18181d90b27e5cfaa11f4537595c2e6640809` and pinned ns-3 source
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. The last accepted MATLAB
execution remains candidate `28ed878f5673e308047cbea7878b933697d932f3`.

## Source and observer review

- Independently compared all 103 source-bound T7 MATLAB files with the
  accepted base: 100 remain byte-identical. The three changed files are
  `NetworkSimulation.m` for optional observation hooks, `exportResults.m`
  for observation exports, and `Artifacts.m` for C++ header hash coverage.
- All 22 tracked files under the PHY, HOP, MAC, NWK and data directories
  remain byte-identical. The review found no change to protocol policy,
  PHY/ECC behavior, default traffic configuration, scheduler calls or
  random-stream consumption.
- Inspected the MATLAB observation queue against the unchanged MAC:
  cumulative replacement follows the first queued peer, exact duplicate
  feedback retains the earlier decision, replacements restart the repeat
  count, and actual observations use the aggregate's final rate and power.
  Packets carry no new tags or observation fields.
- The received context and NWK peer snapshot are read-only observations.
  Missing peer S0 and HOP failure state remain unavailable rather than
  inferred. The observer's limit, omission and correlation failures are
  explicit; raw case exports precede rejection of an incomplete observer.
- Inspected the ns-3 overlay at feedback construction, received DATA
  context and actual aggregate transmission. It reads existing headers
  and peer entries into a separate observation map without scheduling
  events, drawing random values or rerunning link selection.

## Independently verified ns-3 evidence

The final suite manifest SHA-256 is
`8b4263474c7da9103885de21f913b290811deb30788e6ca81c8a4962b3492188`.
Verification used the copied final candidate reference, not the quarantined
preliminary runs.

| Check | Result |
| --- | --- |
| Declared file size and SHA-256 checks | 130 passed |
| Complete gzip decompression and original-byte hashes | 32 passed |
| Observer-on/off application trace and admission file pairs | 20 passed across 10 cases |
| Seed-128 pristine-runner controls | Both passed |
| T7 seed-128 trace, admission and aggregate anchors | Both passed |
| Actual feedback members linked to their selection | All 12,460 |

The reviewer independently reconstructed delivered application counts from
the retained event traces: admission seeds 128–132 deliver 11,364, 11,227,
11,396, 11,330 and 11,375; contention seeds deliver 914, 822, 916, 883 and
920. All ordinary cumulative DATA ACKs transmit at rate key 128 and
+33 dBm. The 139 aggregate rate overrides affect exact-window control
ACKs during startup, before 58.683 seconds. No power override or DACK is
observed. Recorded peer S0 is −103 dBm, HOP failures are zero and peers
are known throughout the sampled feedback selections.

The source formula uses peer S0 and path loss for rate/power selection;
HOP failures affect link cost. These observations do not cover unknown
peers, varying S0, relay DACK or the campus residual. The ns-3 on/off
evidence covers the enabled application/statistics trace and admission
records, not a separately serialized copy of all internal protocol state.
The source engine libraries were verified and reused; only the standalone
runner translation units were compiled.

Preliminary reference truncation was detected and failed validation. The
review found no subprocess ownership or compression stream-lifetime defect,
and the cause remains unestablished. The complete isolated reexecution and
copied final reference passed the checks above. The
[recovery record](../evidence/tranche-8-ns3-reference-recovery.json) preserves
the failed artifact identities and final verification boundary.

## Input, reporting and path contracts

All ten CSV inputs and their recipes match their recorded hashes. Direct
comparison with the T7 parents found changes only to declared scenario
identity, seed and derivation provenance fields. Geometry, traffic,
duration, physical profile and timing remain those of the two small
fixtures. No OPNET counterpart is claimed for either fixture.

The review identified and resolved initial contract mismatches in reference
anchor field names, test duration column names and the plan hash field.
Header membership is now consistent between MATLAB and Python source
snapshots. A mixed-format uint64 comparison could previously round distinct
large values through binary64; the repaired comparison uses exact decimal
values before applying floating-point tolerances, with a regression case.

Reporting tests exercise rejection of missing seeds, altered derivations,
duplicate or uncorrelated feedback, omissions, changed retained identities,
wrong operational rates and corrupted compressed controls. Replay tests
use actual exported T7 records to check short-directory controls and
accepted anchors. They are labeled fixture replay and are not new MATLAB
execution. Packet-weighted latency and means of populated bucket means
remain separate; unmatched ns-3 sends remain unclassified.

The MATLAB and Python case mappings agree exactly: `b/a128` through
`b/a132` and `b/c128` through `b/c132`; seed-128 controls use `c/a128` and
`c/c128`. The shared T7 reviewer keeps its original strict directory
default, while T8 supplies the explicit short path. Full scenario and
case identities remain in metadata, including the unchanged paths inside
the accepted T7 anchor ZIP.

For the owner's previously supplied OneDrive directory with `Tranche 8`
and `csr8`, the inspected candidate's longest relative file path is 132
characters, or 228 characters including that root. The planned longest
generated case artifact is 82 characters relative to the source root,
or 178 characters with that same OneDrive path. The bundle has no enclosing
directory. Final archive membership and bytes require verification after
packaging, without editing the frozen candidate.

## Release boundary

The handoff, README and five new parity-ledger rows correctly distinguish
executed ns-3 results from pending MATLAB diagnostics and preserve the
campus's measured 17.10% single-flow residual. No ACK-policy correction or
universal worst-case bound follows from the current observations.

The final [local checks](../evidence/tranche-8-local-checks.json) bind Python
results and scoped MATLAB static checks. Those checks and final ZIP
verification are release preparation only. Owner execution must complete
all portable tests, ten diagnostics, two observer-disabled controls,
source/reference stability, trace/accounting checks and both accepted T7
MATLAB seed-128 anchors. No remote publication is part of this review.
