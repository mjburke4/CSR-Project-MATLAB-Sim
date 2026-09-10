# Tranche 5 returned sweep outcomes

The returned R2025a evidence at candidate `536b288` supports a completed,
bounded research experiment. Independent reconstruction of all **357 generated
applications** across 18 sweeps found **336 delivered, 21 dropped through
retry exhaustion, and none pending**. These measured losses do not contradict
the fixture contract: delivery was an outcome, not a required all-delivered
gate. No protocol adjustment is justified solely by these counts.

This review did not execute MATLAB or tune the simulator. Its
[machine-readable record](../evidence/tranche-5-return-outcomes-review.json)
binds the original archive, metadata, summaries and traces by SHA-256 and
retains per-case exceptions. Test-suite acceptance and shared MATLAB/ns-3
comparison checks are separate from this outcome review.

## Observed groups

Each row combines seeds 128, 129 and 130. Mean latency is the range of the
three **delivered-application** means; maximum latency is the largest delivered
latency across the group. It excludes lost applications rather than treating
them as zero latency. Route changes are per-run event counts. HOP and NWK
control-failure counts are separate observations, never added as unique losses.

| Experiment | Delivered / generated | Drops | Mean latency range (s) | Maximum latency (s) | Route changes per run | HOP / NWK control failures, group total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Offered load ×1 | 48 / 48 | 0 | 1.131–1.459 | 2.901 | 14–15 | 1 / 1 |
| Offered load ×2 | 90 / 90 | 0 | 1.163–1.306 | 4.625 | 14–15 | 1 / 1 |
| Offered load ×4 | 171 / 174 | 3 | 1.373–1.562 | 4.981 | 14–15 | 1 / 1 |
| Freshness 60 s | 15 / 15 | 0 | 68.000–68.919 | 135.940 | 102–118 | 5 / 1 |
| Freshness 180 s | 6 / 15 | 9 | 13.083–16.593 | 29.601 | 41–52 | 3 / 0 |
| Freshness 300 s | 6 / 15 | 9 | 1.729–1.779 | 3.024 | 17–18 | 0 / 0 |

Offered load ×4 delivered **58/58, 56/58 and 57/58**, respectively. The two
seed-129 terminal drops were packet 28 at 277.871 s and packet 53 at 307.121 s;
seed 130 lost packet 20 at 268.875 s. All three have `retry_exhausted` as their
terminal reason. DATA retry counts increased from 6–8 at ×1, to 12–14 at ×2,
to 27–32 at ×4. This supports reporting load-associated loss and retry growth
within this synthetic hidden-source fixture, without assigning every failed
attempt to a collision or inferring a statistically established capacity.

The offered-load seed-128 KEY_UPDATE owner fails at **20.302 s** for every
load setting, well before first application generation at 240 s. Its failure
must not be attributed to application-load saturation. Seeds 129 and 130
have no HOP control-owner failures in these cases. Neighbor deactivations are
zero for all nine offered-load runs.

## Recovery timing and survivor selection

The common relay receive blackout is **405–540 s**, and application generations
are **450, 486, 522, 558 and 594 s**. Administrative rediscovery requests are
scheduled at **576, 581 and 586 s** after restoration. This is an explicit
receive-eligibility experiment, not physical motion or a power-loss model.

With 60-second freshness, the first application's network submission to HOP
waits until **582.642–582.707 s** across the three seeds. All five applications
survive and eventually deliver. First delivery occurs at **584.199–585.940 s**,
or **44.199–45.940 s after receive restoration** and **8.199–9.940 s after the
first scheduled rediscovery request**. Thus the 134.199–135.940 s maximum
latencies include retained custody, the blackout and the scheduled discovery
stimuli; they are not standalone measurements of autonomous convergence.

With 180- and 300-second freshness, all six runs submit the first application
to HOP at **450 s**, while the relay cannot receive. The first three generated
applications exhaust their retry ownership **before restoration**, between
458.649 and 532.502 s across the six runs. Packets four and five deliver. The
smaller reported means therefore compare a different set of survivors from
the 60-second case; they do not establish a better overall recovery policy.

At 300 seconds, packet four delivers at **560.881–561.024 s**, before the
first scheduled post-restoration discovery request. Retained neighbor state
supports that observed early transfer, while also allowing the earlier three
applications to exhaust their attempts during the blackout. A blanket change
to the longer timeout would trade these behaviors rather than fix a proven
implementation error.

The 60-second cases have **24, 29 and 25** neighbor-deactivation events;
**11, 11 and 8** occur before the imposed blackout. The 180-second cases have
**7, 10 and 6**, with **2, 2 and 1** before the blackout. Churn therefore includes
quiet-neighbor freshness behavior outside the failure interval. All five HOP
control failures in the 60-second group belong to seed 128: three ROUTING
owner failures during the blackout and two at 870.892 s. Each 180-second run
has one ROUTING owner failure near 531 s. These are separate from the terminal
application losses and do not certify stable convergence when delivery passes.

## Finite-stop ownership

All 18 runs have zero pending applications, HOP pending DATA, NWK pending
custody, DACK holds, physical receiver observations, and exported queue
admission/feedback rejection counts. Protocol and PHY omitted-record counters
are also zero. Fifteen runs report `OwnershipDrained=true`.

The three 300-second-freshness runs correctly report **`DataDrained=false`,
`ControlsDrained=false` and `OwnershipDrained=false`**. At exactly **900 s**, the
simulation stop, node 2 marks neighbor 1 inactive and admits a ROUTING control
toward node 3 plus a DISCOVER control. The final exported state has **one
reliable HOP control owner, one outstanding target, one shared resend entry
and two NWK pending control messages**, all at node 2. These are newly admitted
stop-boundary controls; no DATA application is left pending.

The naming of `DataDrained` is conservative: `csr.hop.Layer.statistics`
exports `ResendQueueDepth` from the common `Resends` map, which stores both
DATA and reliable CONTROL ownership. `csr.analysis.researchSummary` requires
that entire depth to be zero when computing `DataDrained`. The flag must
remain false here; it cannot be restated as unfinished application DATA or
silently recomputed using only `PendingData`. Current MAC feedback queue depth
is unavailable, so none of these flags certifies globally empty queues or an
empty scheduler. The stop-boundary evidence establishes why these controls
remain; it does not show their eventual completion beyond 900 s.

## Independent consistency checks

The audit rebuilt each application's ordered state history from
`app_generate`, `relay_accept`, `app_drop` and `app_receive`. It checked unique
generation identity, payload size, receive destination and DSCP, event times,
terminal outcomes, delivered bytes, latency sums, and every row of the exported
`applications.csv`. All 18 cases agree with the final counters and diagnostic
tables. Each `tx_start` count also agrees with its physical transmission count.

All **12 within-seed parameter comparisons** have exactly the expected config
changes. Offered load changes only the two flow packet counts and intervals,
plus the case name and sweep value. Recovery changes only
`Nwk.Neighbor.FreshnessTimeoutSeconds`, plus the case name and sweep value.
This matches the implementation in `researchSweep.m`; topology, traffic
endpoints, queue limits, blackout and discovery schedule are isolated as
claimed. Equal seeds still do not imply identical random draw sequences after
configurations change their event histories.

The seed-128 ×1 and 60-second cases match their returned Tranche 4 regression
baselines in **all final statistics**. Their protocol/PHY traces and HOP, NWK
and MAC node tables are **byte-identical**. Config differences are restricted
to name, sweep provenance and increased trace capacities. This supplies direct
baseline preservation evidence in addition to the source pin and manifest
checks handled by the acceptance audit.

## Recommended boundary

Accept these as measured results of the documented short research sweeps,
with loss and finite-stop control flags retained. No return-driven change to
freshness, retry budgets, protocol timing or PHY/ECC is warranted. Repairing
an external evidence analyzer does not by itself require regenerating these
unchanged MATLAB results.

The explicitly deferred 6,000-second workload and R2026a execution remain
useful next validation gates. If future work asks whether the 900-second
boundary controls finish, add a separately identified observation extension
with unchanged traffic, blackout and rediscovery timestamps; do not alter or
replace this accepted experiment. Three seeds do not establish an optimal
freshness setting, broad network timing equivalence, or historical campus/OPNET
parity.
