# Five-seed feedback diagnostics

`plan.json` declares the two smaller T7 fixtures at seeds 128 through 132,
in seed-major order. There are ten new experiment identities. Each CSV has
its own derivation recipe, parent hash and output hash. Only the experiment
label, random seed and recipe provenance fields change on the run row;
node and flow rows are copied unchanged, with run-only fields empty. Geometry, offered
traffic, duration, historical profiles, PHY and radio limits are retained.

The two-node fixture runs for 1,200 simulated seconds with 45,000 attempts.
The contention fixture runs for 360 seconds with 60,000 attempts across two
flows. Both send to the gateway. No OPNET counterpart is claimed for these
synthetic cases. They do not replace the accepted 6,000-second campus case.

In MATLAB, `csr.scenario.linkDiagnosticSuite` imports and validates this
fixed plan. `run_tranche8_validation` uses an external passive observer,
leaving configuration, random draws and event scheduling unchanged. It
repeats both seed-128 cases with observation disabled and compares all
existing trace, node, route and admission CSV bytes plus exact application
statistics. A mismatch, omitted diagnostic row or uncorrelated feedback
transmission fails the diagnostic gate.

The ns-3 reference separately compares observation on/off for all ten cases
using complete application event traces and admission counters. Fresh
unmodified runner checks and accepted T7 references anchor seed 128. This
does not establish complete ns-3 protocol-event equivalence.

Five seeds give descriptive variation for these fixtures. Equal seed numbers
do not give identical random streams across MATLAB and ns-3, and neither
close averages nor a small empirical range certify statistical equivalence.
