# Tranche 20 return analysis

Run `python3 scripts/analyze_tranche20_return.py --evidence PATH/t20.zip --source-root . --output PATH/t20-review` from the installed source root. Output must be a new directory outside the source and evidence trees.

The checker binds the complete current source, reference and test inventories; verifies immutable stage receipts; verifies portable MATLAB runtime equality with the accepted T19 return; and requires complete protocol/PHY traces and full admission counters. Only Config.Seed may differ from the accepted T19 actual-tx configuration, apart from relocation of its hash-bound original scenario path. All 358 prior source bindings remain unchanged.

Seed 128 is read exclusively from the accepted T19 `a128` archive. Its old source identity remains explicit. It is neither a fresh T20 execution nor substituted with the rejected `p128` experimental result. Fresh cases are seeds 129 and 130. Native seed-specific CSVs differ only in run.seed; their hashes remain distinct from the original MATLAB input CSV, which is imported before the explicit Seed override.

Every seed and every source flow is reported. Admissions and unique application deliveries are compared using per-seed residuals, arithmetic means and ranges, signed residual consistency, and a separately labeled pooled ratio of sums. These two percentage summaries can differ because native denominators differ. The five-percent band is descriptive; it never gates structurally valid evidence or establishes statistical equivalence. Three seeds give an initial variability screen, not a confidence claim. Cross-engine seed labels do not imply common random numbers.

The review also keeps per-case delay, terminal drops, pending applications, retry/capacity observations and 300-second timelines. Native duplicate delivery events are distinguished from unique delivered applications; native unmatched sends cannot be divided into drops and pending work without additional evidence. Separately verified 60-second aggregate series retain event-rate and bucket-mean semantics, including duplicate events. No additional OPNET seed is invented.

All automated checker fixtures are synthetic. Local Python checks and static MATLAB analysis do not claim MATLAB execution; the owner's returned evidence is required.
