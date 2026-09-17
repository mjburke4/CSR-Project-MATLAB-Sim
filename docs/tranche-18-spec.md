# Tranche 18: real-PHY relay/local service diagnosis

## Objective and baseline

Measure local-versus-relayed admission and transmission service at node 5 and
feedback/retry behavior on 4 → 5 before selecting any behavior correction.
Preserve all 313 reviewed T17 source bindings, including 160 MATLAB files.

T17 passed 660 portable tests and the original 6,000-second campus structural
gate. All campus Statistics and eleven retained raw CSVs reproduce accepted
T10 exactly. MATLAB delivered 11,825 applications versus 11,769 in ns-3
(+0.476%), but source 5 gained 275 deliveries while the other sources netted
219 fewer. Source 4 delivered 16.95% fewer and source 5 delivered 20.09% more.
The 402 terminal retry-exhaustion drops include 309 at relay node 4; that
custody-owner count is not the number of drops originating at node 4.

Node 5's difference predominantly concerns admitted volume: 1,669 MATLAB
versus 1,397 native admissions. Conditional delivery was approximately
98.50% versus 98.00%. Consequently total delivery alone cannot distinguish
service allocation from differences in forwarding success.

The exact T17 owner archive and acceptance records are retained under
`evidence/t17`. Its source snapshot is `evidence/tranche-18-baseline.json`.
The current upstream main was inspected and remains
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, with engine
`6b5cd24ea80713ce16d88575869aedd6f432bdae`.

## Source audit and deliberate boundaries

The native and MATLAB source audit found no explicit local-over-relay DATA
priority. Both insert zero-DSCP DATA at the queue tail and higher-DSCP DATA
at the head, use per-original-flow NSDP admission, retain capacity after DACK,
and release it at the corresponding expiry. The compared DATA-window and
ACK-growth rules agree.

Known distinctions remain visible:

- MATLAB's accepted retry policy pauses the next timeout while a retry waits
  for actual MAC transmission. Native uses a provisional queued timestamp and
  can retry or expire before that retransmission is sent. T17 contains long
  waits that exercise this distinction; its source audit lists their counts.
- NWK wake timing and same-time callback sequencing differ. These ordering
  observations are not yet established causes of the campus distribution gap.
- Native unsent NWK queue depth is not equivalent to MATLAB's full retained
  custody count. Compare MATLAB entries not yet submitted to HOP separately.
- Intermediate DACK callback snapshots can differ even when completed state
  agrees. Preserve callback-stage meaning when comparing counters.
- Existing transactional overload and custody-bound choices remain explicit
  accepted differences. This tranche does not replace them to fit throughput.

Source findings and exact source identities are under
`evidence/tranche-18-source-audit`. No production timing, PHY/ECC, queue policy
or random-number implementation is changed.

## Workloads

`scripts/prepare_tranche18_scenarios.py` derives ten cases from the hash-bound
original campus CSV. It preserves every retained node/flow field and records
the only run overrides: name, duration and seed. `scenarios/t18/plan.json`
binds every resulting input and recipe, observation budget and execution order.

Nine three-node runs compare relay-only, local-only and mixed application
traffic using seeds 128, 129 and 130, each for 600 seconds with traffic starting
at 300 seconds. All preserve original node-1/4/5 geometry and radio profiles,
autonomous routing and the 0.02-second historical offer interval. Removing
other nodes and interferers makes these synthetic isolation diagnostics.

The tenth observed case keeps all original campus nodes and flows but stops
at 900 seconds. It retains upstream sources 7 and 8: all 37 original 4 → 5
DACKs before 900 seconds belonged to those sources. Reduced-topology cases
are not required to produce DACKs and cannot claim coverage when none occur.

One additional MATLAB run disables the observer for mixed seed 128 without
changing its configuration. Core statistics and exported observations must
match the observed run. There are eleven MATLAB runs and 6,900 simulated
seconds in total. No traffic-stop extension, artificial queue drain, fixed
route, controlled loss, timing injection or PHY adjustment is used.

## Observation and comparison

MATLAB uses the existing `csr.sim.AckServiceDiagnostics`. The observation
window ends one second after the fixed horizon so callbacks at the stop are
captured; simulation itself still stops at the declared 600 or 900 seconds.
The observer retains its existing six public MAC scalar reads per cancellation
snapshot. There is no new HOP/NWK peer polling, scheduled event or RNG draw.

Raw service, feedback, protocol, PHY and admission exports retain full identity
and callback details. Cohort analysis uses application origin, not hop-local
frame source, to distinguish local and relayed DATA. Control identities are
kept separate. Packet lifecycle reconstruction reports observed NWK enqueue,
HOP submission, actual transmission, ACK/DACK/failure and custody-release
stages. It is not an arbitrary instantaneous queue snapshot, and silent queue
scan skips are not directly observed.

Fresh native runs use the exact pinned CSR and engine sources with passive
observation. Native build, observer control and case provenance are retained
under `evidence/tranche-18-ns3-reference`. Native observation rows are broader
than MATLAB callback rows; their inventories are independently complete rather
than forced to have equal row counts. Equal seed labels do not imply common
random draws or cross-simulator packet-ID equivalence.

The campus-prefix comparison uses events strictly before 900 seconds to avoid
conflating the shortened horizon with an original run that continued. T17's
admission trace contains only its first 100,000 attempts, through about
633.32 seconds. Compare those common rows exactly; the remaining T18 admission
observations have no T17 row-level counterpart. T18 itself must capture all
180,000 attempts and reconcile them with complete counters.

## Gate, runtime status and handoff

The focused gate binds the candidate, all source files, complete reference
inventory, exact selected test methods, all case manifests and raw artifacts.
It rejects altered inputs, omitted required traces, incomplete tests or cases,
and observer perturbation. Numerical differences and finite-stop pending work
remain measured results, not invented equality thresholds.

New scenario/contract preflight precedes the runs. The retained regression
covers NWK/HOP ownership and controls, observer behavior, historical application
generation, aggregate/performance accounting and custody scenarios. T17's full
portable suite remains the accepted baseline; this tranche is a focused
diagnostic rather than another full campus release gate.

MATLAB is unavailable in this preparation environment. Fresh native execution,
Python checks, independent source review and MATLAB static analysis do not
establish MATLAB runtime success. The exact preparation results are recorded
under `evidence/tranche-18-preparation`; runtime acceptance awaits the owner
return described in `T18.md`.

After return review, select a policy change only if it is supported by a
localized source/behavior discrepancy and its effects across the bounded
cases. Otherwise retain the implementation and document the measured model
distinction. PHY/ECC, battery, supervisory behavior and BBN routing remain
outside this change.
