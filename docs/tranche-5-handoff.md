# Tranche 5: research sweeps and performance diagnostics

The objective is to turn the accepted Tranche 4 experiments into controlled,
repeatable research studies and identify which measured discrepancies warrant
protocol work. This candidate is on `agent/tranche-5-research-performance`,
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

No MATLAB or Octave runtime is available in this engineering workspace.
The current candidate therefore needs an owner R2025a run, followed by the
separate R2026a gate. Static checks and Python tests are implementation checks;
reanalysis of the T4 evidence uses the owner's already accepted MATLAB run.
All 88 MATLAB files pass MISS_HIT static lint. All 71 Python tests pass,
including 24 report-integrity tests and five residual-audit tests. The candidate
contains 367 portable MATLAB test methods; execution of them is pending.
The independent review found no unresolved blocker. The 33 accepted protocol
and simulator source files are byte-for-byte unchanged. Exact hashes and
commands are in `evidence/tranche-5-candidate.json` and
`evidence/tranche-5-local-checks.json`.

```matlab
report = run_tranche5_validation;
```

Return the generated `tranche5_evidence.zip`. The runner reports case progress.
The default workload is larger than T4; elapsed time has not yet been measured.
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

After the new R2025a evidence is reviewed, prioritize material delivery,
congestion or route-stability problems it reveals. Full ACK-feedback adaptation,
R2026a native transport, historical generator equivalence and OPNET aggregate
comparisons remain possible follow-on work. The 6000-second experiment is
synthetic and does not certify the historical campus scenario. Battery,
supervisory behavior, BBN routing, GUI, Simulink and waveform expansion remain
outside the baseline. This candidate is local; no Tranche 5 publication or
acceptance has occurred.
