# Tranche 5: research sweeps and performance diagnostics

The objective is to turn the accepted Tranche 4 experiments into controlled,
repeatable research studies and identify which measured discrepancies warrant
protocol work. The accepted implementation is on `agent/tranche-5-research-performance`,
based on merged PR #4 at `7edaab558f4f00290d11e0681d883364141d547c`.
Source main was checked on 2026-09-09 and still points to
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.

## Capabilities

| Component | Purpose |
| --- | --- |
| `csr.scenario.researchSweep` | Explicit, bounded configurations varying offered load or neighbor freshness across repeated seeds; optional 6000-second workload |
| `csr.analysis.performanceSummary` | Application outcomes and latency, DATA/control member counters, route churn, queue/retry failures and finite-stop ownership |
| `run_tranche5_validation` | Retained regressions plus sweep execution, complete source/evidence inventories and a compact upload ZIP |
| `scripts/analyze_research_sweep.py` | Verify completed evidence and produce descriptive summaries with equal seed weighting; retain losses, pending work and undefined metrics |
| Residual audit | Reconstruct where T4 timing differs and when route/control failures occur; keep source evidence separate from inferred causes |

The default 18 cases use three load multipliers and three freshness timeouts,
each with seeds 128/129/130. Offered-load cases keep their first and last
generation times fixed. Recovery cases retain the same administrative receive
blackout and scheduled rediscovery. Timeout changes are an experimental
parameter, not a recommended production setting or a claim of autonomous
recovery. The full set reruns the portable unit suite, five shared inputs,
six T4 research layouts, eight T3 scenarios and nine T2 scenarios first.

All experiments use the existing packet-level physical model. They do not
install controlled links or routes, import historical campus geometry, or
implement native wireless packet transport. High-rate extensions remain in
the retained, separately labeled shared regression cases.

## Validation status

The owner R2025a run passed all 367 portable tests and completed all 18 sweeps
plus 28 retained scenarios in 19 minutes 56 seconds. All 88 MATLAB source
hashes and all 550 bundled artifact hashes verify. The five shared application
comparisons pass for this return. See [portable acceptance](tranche-5-portable-acceptance.md)
and the independent integrity/outcome reviews.

All 88 MATLAB files passed static lint before packaging. A Python review-tool
repair handles integral file sizes written in MATLAB JSON exponent notation;
all 75 Python tests pass afterward. It changes no MATLAB source and requires
no MATLAB rerun. Keep code `536b288` as the validated MATLAB baseline. No
MATLAB runtime was available in the engineering workspace; actual execution
was on the owner's R2025a machine. R2026a remains a separate gate.

```matlab
report = run_tranche5_validation;
```

The command reproduces the accepted run. The runner reports case progress;
return `tranche5_evidence.zip` for any subsequent validation.
See [validation options](tranche-5-validation.md) for a smaller diagnostic
selection and the explicit 6000-second/native options. Skipping tests does
not establish tranche acceptance.

## Boundaries and next work

The candidate changes research/analysis/evidence tooling. It does not alter
PHY/ECC, protocol timers, retry policies, link adaptation, routing or RNG
behavior. A source-backed defect would justify a separate bounded correction;
a favorable seed-128 latency mean does not. The retrospective audit reran all five archived application comparisons and
matched all 15 final-envelope transit durations. All 15 delivery gaps are
whole 13-ms slots and already exist at final transmission; RNG/history
attribution remains unproven. Eleven of 24 recovery neighbor deactivations
occur before the blackout. See the
[residual audit](tranche-5-residual-audit.md) for evidence and remaining uncertainty.

Research completion means requested execution and structural checks completed.
It does not mean every application delivered, every control exchange succeeded,
all periodic events ended, or MATLAB/ns-3 performance is statistically equal.
Pending work, failure counters and unavailable metrics remain explicit.

The new sweeps delivered 336/357 applications, with 21 retry-exhausted drops
and no application pending. The three 300-second freshness cases retain
controls newly queued at the 900-second stop. The next material target is
stale-route and retry/custody interaction during outages, first compared
against the same pinned ns-3 scenario. Full ACK-feedback adaptation,
R2026a native transport, historical generator equivalence and OPNET aggregate
comparisons remain possible follow-on work. The 6000-second experiment is
synthetic and does not certify the historical campus scenario. Battery,
supervisory behavior, BBN routing, GUI, Simulink and waveform expansion remain
outside the baseline. Portable acceptance is recorded locally; no Tranche 5
publication has occurred.
