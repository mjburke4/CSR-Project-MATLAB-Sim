# Tranche 6: network freshness and outage recovery

The bounded NWK correction at `21c0a3f` is accepted on returned portable R2025a
evidence: 380/380 tests, all 18 sweeps and 28 retained scenarios. Recovery
performance remains qualified: 60-second delivery fell from 15/15 to 13/15.
See [portable acceptance](tranche-6-portable-acceptance.md) for the exact
evidence, regression mechanism and remaining gates.

This tranche corrects NWK freshness behavior identified while investigating
the accepted Tranche 5 outage losses. It starts from merged PR #5 at
`243ed8610df807e47d3b0be36d4ce2eae0527898` on local branch
`agent/tranche-6-outage-recovery`. Current ns-3 main was inspected on
2026-09-10 and remains `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, tree
`b611b233fb369569b98f0914ece24d029ccc2f42`.

## Finding and correction

Tranche 5 delivered 15/15 recovery applications with 60-second freshness and
6/15 each at 180/300 seconds. The longer-timeout runs submitted their first
three applications to a disabled relay and exhausted retries before restoration.
The 60-second result also includes deliberate rediscovery stimuli; it is not
a measurement of autonomous convergence.

Source inspection confirms that ordinary DATA exhaustion removes local HOP
ownership without a generic routing-link failure callback. Automatically
invalidating the route or requeuing every failed DATA packet would change the
reference protocol. This candidate preserves that policy.

Two separate port discrepancies are corrected:

| Behavior | Accepted MATLAB T5 | Tranche 6 / pinned source |
| --- | --- | --- |
| Passive decoded DATA, ACK, overheard reception | Renewed NWK last-heard time | Updates radio observations; does not renew NWK liveness |
| First qualified Discover, NeighborCheck or valid routing section | Refreshed through broad reception path | Refreshes through the specific delivered control path |
| KeyRequest/KeyUpdate and duplicate reliable controls | Broad reception path could renew NWK freshness | Do not renew the network deadline |
| Quiet-peer expiry | Added a failure penalty and invalidated key/retry callbacks | Clears admission/routes/routing transactions; preserves failure count, key owner, backoff history and pending admission work |
| Valid NeighborCheck completion after expiry | Generation invalidation could reject it | Qualifying proof can readmit the peer; obsolete Verify remains rejected |

The freshness timer remains strict (`age > timeout`), with unchanged configured
periods and timeouts. Radio measurements remain available for HOP/link control.
No DATA retry, MAC, PHY/ECC, RNG or fixture parameter is changed.

## Architecture and files

| Component | Change |
| --- | --- |
| `+csr/+sim/NetworkSimulation.m` | Route passive radio observations separately from NWK liveness |
| `+csr/+nwk/Layer.m` | Qualifying control observations and validated routing-section refresh |
| `+csr/+nwk/Neighbors.m` | Source-aligned expiry state and retained admission callback behavior |
| `tests/TestOutageRecovery.m` | Focused freshness and terminal custody regressions using explicit fake MAC ingress |
| `run_tranche6_validation.m` | Fresh candidate wrapper around retained portable regression and 18 sweeps, with exact source/artifact inventory |
| `scripts/analyze_tranche6_return.py` | Compare identical configurations and every application outcome with the original accepted T5 ZIP |
| `scripts/ns3/` and reference runners | Reproducible unchanged-source contract and outage observations |
| `+csr/+validation/Artifacts.m` | Include reference C++ fixtures in source snapshots |

## Actual validation and evidence

The unchanged pinned ns-3 HOP/NWK contract fixture passed **45/45 assertions
across 11 cases**, including passive DATA/ACK, duplicate routing, strict timer
expiry, retained key/retry state and valid post-expiry admission proof.
The standalone C++ translation unit was compiled against verified headers and
hashed preserved libraries. The full ns-3 engine was not rebuilt. These direct
ingress contracts do not exercise a physical channel.

The separate nine-case outage reference completed using actual ns-3 CSR PHY/MAC/HOP/NWK
with the same geometry, offered applications, blackout interval, discovery
schedule, freshness values and seed identities. Its result manifest and
`case_summary.csv` are under `evidence/tranche-6-ns3-reference/`.
Read their explicit coupling boundaries before comparing counts: the ns-3
gate runs after MAC bookkeeping, MATLAB's gate runs before it; security and
random streams also differ. A local no-ACK trace is not sufficient to certify
global application loss. Unresolved ns-3 terminal custody remains labeled.

| Freshness | Accepted T5 MATLAB delivered | T6 MATLAB delivered | Pinned ns-3 delivered |
| --- | ---: | ---: | ---: |
| 60 seconds | 15/15 | 13/15 | 14/15 |
| 180 seconds | 6/15 | 6/15 | 6/15 |
| 300 seconds | 6/15 | 6/15 | 6/15 |

The reference has 19 local retry-exhaustion completions among its 19
undelivered applications and zero duplicate application deliveries. Its
maximum delivered delay is 135.655 seconds. These measurements support the
shared-policy finding; they do not establish MATLAB/ns-3 numerical parity.
An output snapshot was restored by exact same-binary replay after a later
truncation; the replay reproduced both original snapshot and complete trace
hashes. The reference evidence documents that recovery.

The candidate's Python suite passed **98/98 tests** and all **90 MATLAB source
files** passed static lint before handoff. The owner's subsequent R2025a run
passed **380/380 portable MATLAB tests**, including 13 new focused tests.
All 127 returned source hashes match `21c0a3f`. All five strict shared-input
application comparisons pass. Static/Python details remain in
`evidence/tranche-6-local-checks.json`; the historical candidate review is
[tranche-6-review.md](tranche-6-review.md), and the actual runtime disposition
is [tranche-6-portable-acceptance.md](tranche-6-portable-acceptance.md).
MATLAB ran on the owner's machine; this workspace reviewed its unchanged ZIP.

## Remaining work

The default run completed in 13 minutes 15.758 seconds. All existing tests and
delivery assertions remained in the gate. The same 18 sweep configurations
provide the T5 comparison; no timeout tuning was mixed into the correction.
The review preserved the original `21c0a3f` source and returned archive.

Acceptance reviewed delivery, pending ownership, duplicate deliveries,
control failures, route churn and restoration-relative timing together. A
shorter mean among fewer survivors does not establish better recovery. The
Python report computes paired latency only for the same applications delivered
in both versions and retains all other outcome transitions.

The next target is the route-selection/DATA-retry boundary. In two 60-second
cases, a packet entered HOP at 450 seconds and exhausted retries before the
route expired at 465 seconds. T5 had held it unsent until rediscovery. The
source-compatible policy remains the baseline; any extension that retains
failed DATA or invalidates a path must be an explicit resilience experiment.
Native R2026a packet transport, 6000-second synthetic runs
and full protocol timing parity remain separate gates. Battery, supervisory
behavior and BBN routing remain outside the baseline.
