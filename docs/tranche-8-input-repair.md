# Tranche 8 input-schema repair

The owner reported `Populated field scenario is unsupported on a node row`
when `run_tranche8_validation` called `csr.scenario.linkDiagnosticSuite`.
The error occurs during initial scenario import, before unit tests, output
creation or any diagnostic simulation. This was a packaging mistake in
candidate `010793b402cc63c1bd434328d80d0b6b53c39ebf`.

The canonical importer allows `scenario` on the run row only. The derivation
incorrectly repeated it on all 25 node rows and 15 flow rows across the ten
CSV files. The Python verifier reconstructed that same incorrect derivation,
so its passing tests did not detect the MATLAB schema violation. MATLAB
static lint does not execute imports and could not establish runtime success.

The repair regenerates each input from its accepted T7 parent, changing only
the run row's scenario, seed and recipe-provenance hash. Node and flow rows
now match the parent exactly, including empty run-only fields. The recipes
state this rule explicitly, and all recipe, input and plan hashes are updated.
The corrected plan SHA-256 is
`ed648ee4f54ebf14e14b98d6fcecce224590727139db83f0f4d23161ddfc7a09`.

The verifier now applies substitutions only to the run row. New regressions
reject both node-row and flow-row contamination even if the altered CSV is
rehashed. A separate preflight test reads the actual MATLAB importer's
allowed-field declarations and checks every populated cell in all ten CSVs
without using the derivation verifier. It rejects the original 40 invalid
rows and accepts the corrected 50-row suite.

All MATLAB files, including the importer and observer, are unchanged from
`010793b`. Geometry, load, seeds, duration, PHY/ECC and protocol policy are
unchanged. The pinned ns-3 loader uses the scenario label on the run row;
the corrected metadata does not alter simulated stimuli. The full ten-case
reference suite is freshly executed to bind evidence to the corrected hashes,
and its simulation and feedback outputs are compared with the original
candidate. See the [reference comparison](../evidence/tranche-8-input-repair-ns3.json),
[checks](../evidence/tranche-8-repair-checks.json), and
[independent review](tranche-8-repair-review.md).

The original candidate, its input hashes and its local-check records remain
recoverable at `010793b`. The [input mapping](../evidence/tranche-8-input-repair.json)
records the old and new hashes and the owner-reported failure. The original
T8 recovery record applies to that earlier reference; it is not relabeled as
evidence for the repaired inputs. Accepted T7 evidence remains untouched.

Extract the complete replacement `csr8.zip` into a fresh short folder such
as `C:\csr8`, select that folder in MATLAB, and run:

```matlab
report = run_tranche8_validation;
```

The compact result layout and the ten diagnostics plus two controls are
unchanged. Return the resulting `tranche8_evidence.zip`. This repair has not
been executed in MATLAB here; actual owner execution remains the gate.
