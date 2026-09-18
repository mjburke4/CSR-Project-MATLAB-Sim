# CSR port engineering instructions

- Inspect current source main in `mjburke4/CSR-Project-NS3-part2` before each new
  behavior tranche; pin its SHA and preserve scenario/config provenance.
- Work in cohesive subsystem tranches. Use parallel source/PHY/MAC/NWK/QA
  specialists when independent, with an independent reviewer at the gate.
- Prioritize functional MATLAB, end-to-end behavior, maintainability and
  practical R2025a/R2026a support. No line-by-line C++ translation.
- CSR core is release-independent. Native simulator classes belong in adapters.
- Do not claim MATLAB execution without actual MATLAB. Preserve exact release,
  test outcomes and logs; static checks are not runtime evidence.
- Keep docs/parity-ledger.csv current. An unavailable OPNET packet trace is not
  a blocker. Unresolved PHY/ECC uncertainty is documented, not silently fixed.
- Baseline excludes battery, supervisory layer and BBN routing.
- Structural failures block tranche completion. Minor numerical/stochastic
  differences normally go to the backlog, with honest labels.
- No remote push, PR creation, merge, branch deletion or other consequential
  repository mutation without explicit owner authorization. Local commits do
  not require approval per method or minor fix.
- Each tranche handoff reports objective, capabilities, architecture/files,
  actual tests/releases, ns-3/OPNET comparisons, discrepancies/deferred items,
  and recommended next tranche. Never disguise controlled links as real PHY.
