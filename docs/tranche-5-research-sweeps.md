# Tranche 5 research sweeps

`[cases, plan] = csr.scenario.researchSweep(options)` constructs controlled
experiment configurations from the accepted Tranche 4 synthetic layouts. It
does not run the simulator, tune the protocol, or assert an outcome. Cases use
the existing portable network stack, physical propagation, stochastic PHY,
admission and learned routes. There are no preinstalled paths, controlled
receive-erasure faults, high-rate extensions or disabled-transit leaf cases.

The default plan has **18 cases**: three parameter values for each of two
experiments, repeated at seeds 128, 129 and 130. It schedules 357 applications
over 13,500 aggregate simulated seconds. This is a simulation-duration budget,
not a wall-clock estimate. Optional long runs add one 6000-second case and 160
applications per seed, giving 21 cases and 31,500 simulated seconds with the
default three seeds.

| Option | Default | Accepted values |
| --- | --- | --- |
| `Seeds` | `[128 129 130]` | 1–20 distinct integer seed identities, 0 through `2^32-1` |
| `Experiments` | `{'offered_load','recovery_freshness'}` | Distinct names from those two; empty only with `IncludeLongRun=true` |
| `LoadMultipliers` | `[1 2 4]` | Distinct integer interval-rate multipliers from 1 through 8 |
| `FreshnessTimeoutSeconds` | `[60 180 300]` | 1–8 distinct integer timeout values from 30 through 600 seconds |
| `IncludeLongRun` | `false` | A logical scalar; the numeric value `1` is rejected |

Unknown options, duplicates, nonfinite values and plans exceeding 200 cases
are rejected before simulation. Numeric vectors are normalized to double row
vectors. Seed, parameter and experiment ordering are preserved. Configuration
construction does not draw random numbers or change MATLAB's global RNG.

```matlab
[cases, plan] = csr.scenario.researchSweep();
result = csr.runScenario(cases(1).Config);

% Construct only the explicit 6000-second workload for one seed:
[longCases, longPlan] = csr.scenario.researchSweep(struct( ...
    'Seeds',128,'Experiments',{{}},'IncludeLongRun',true));
```

## Controlled comparisons

The `offered_load` experiment uses the Tranche 4 `hidden_node` layout. Its two
sources each generate a baseline eight 64-byte, DSCP-zero applications between
240 and 303 seconds. For multiplier `m`, an original flow with `N` packets and
interval `dt` becomes `1+(N-1)*m` packets with interval `dt/m`. First generation,
last generation, synchronization of the two application starts, the 600-second
stop and the 297-second drain allowance remain the same, subject to floating
point roundoff. Default values therefore produce **8, 15 and 29 packets per
source**, at 9, 4.5 and 2.25-second intervals. The multiplier scales the interval
rate; it does not literally multiply the finite packet total because the two
endpoints remain included.

Topology, radio settings, payload size, DSCP, protocol queue limits, discovery
requests and freshness settings are identical within each seed's offered-load
comparison. Collisions, delivery, latency and control retries are measurements;
the layout does not force two packets to collide or guarantee their delivery.

The `recovery_freshness` experiment uses the existing `route_recovery` layout.
Only `Nwk.Neighbor.FreshnessTimeoutSeconds` changes among protocol inputs. Its
5-second inspection period, 900-second duration and five-packet workload stay
fixed. The relay's administrative receive blackout remains at 405 through 540
seconds, and the same discovery requests occur before and after restoration.
This isolates the timeout setting under identical external stimuli. It does
not turn the administrative blackout into physical motion, RF power loss, or
automatic rediscovery. A longer timeout can affect stale-neighbor residence,
route churn and application latency; the direction and size of those effects
must be measured.

The same seed identities are paired across parameter values. Each complete
configuration is reproducible, but a changed workload or timeout can change
event order and random-draw consumption. Equal seeds do not guarantee identical
packet-level noise realizations across different configurations. Three default
seeds are a bounded first experiment, not a statistical precision claim.

## Long-run and trace bounds

The optional long run retains the Tranche 4 `long_run_6000` traffic, topology,
discovery, protocol settings and five-million-event ceiling. It sends 160
applications from 600 through 5370 seconds and retains a 630-second drain
allowance. This is a synthetic four-node line, not an imported historical
campus scenario or numerical OPNET parity gate.

| Case family | Protocol trace cap | PHY trace cap | Event ceiling |
| --- | ---: | ---: | ---: |
| Offered load and recovery freshness | 250,000 | 250,000 | 2,000,000 |
| Optional 6000-second line | 1,000,000 | 500,000 | 5,000,000 |

Caps are uniform within each family and remain finite. These limits provision
headroom beyond the Tranche 4 short-run caps of 100,000 each and the long-run
caps of 200,000 each. In the accepted R2025a seed-128 evidence, hidden-node
traces contained 5,316 protocol and 2,171 PHY rows; route-recovery traces
contained 10,162 and 5,275. Those measurements are scale references, not bounds
on new parameter choices or longer runs. The new capacities are provisional
and require actual execution. Check both omitted-record counters; trace
truncation invalidates complete evidence even when the simulation returns.
Pending custody and unfinished control work are finite-stop outcomes that
must also be reported.

## Plan and case records

`cases` is a column struct array with `CaseId`, `Experiment`, `Parameter`,
`Value`, `Seed` and validated `Config`. A case ID is stable for its full
experiment/value/seed identity, for example `offered_load_x2_seed128`,
`recovery_freshness_s180_seed128` or `long_run_s6000_seed128`.
`Config.Name` equals that ID. `Config.Research.Sweep` records the baseline
fixture, parameter, seed, hypothesis and explicit uncertified-outcome flag.

The serializable plan uses schema `csr-matlab-research-sweep-plan-v1` and
status `planned-not-executed`. It records normalized `Options`, `Cases`
descriptors without configurations, `CaseCount`, `MaxCaseCount`,
`LongRunCaseCount`, `TotalSimulatedSeconds`, `TotalApplications`, ordering,
seed interpretation and trace policy. Delivery and numerical parity remain
uncertified in a construction-only plan. Runtime evidence belongs in the
runner's separate report.

`TestResearchSweep` checks preserved controls and traffic endpoints, parameter
and seed identity, ordinary-rate and physical-channel boundaries, provenance,
long-run opt-in, input validation and reproducibility. Static lint is not
MATLAB execution; the Tranche 5 candidate needs its R2025a run before these
new tests or experimental outcomes can be accepted.
