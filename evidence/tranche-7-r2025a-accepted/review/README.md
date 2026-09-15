# Returned Tranche 7 review

The original owner archive is `../tranche7_evidence.zip`. Its SHA-256 is
`ea39b86ef68f91a551e4e22d176e2e96dc5305f33673741eee0adc6039599655`.
`../archive-selection.json` maps the 65 selected files to their original
archive members and records their unchanged bytes and hashes. Full protocol,
PHY and admission traces remain inside the ZIP.

`review.json`, `flow_progress.csv`, and the three case comparison directories
are unchanged outputs from the candidate's Python reviewer. The reviewer
passed without repair. Its `acceptance_established: false` is intentional:
this program verifies evidence and computes descriptive differences; the
subsequent engineering decision is recorded in
`../../tranche-7-portable-acceptance.json` and the acceptance document.

The comparison JSON and input manifests preserve the absolute paths used
during review, including a temporary extraction directory that is now gone.
They are execution records, not relocatable input manifests. Input hashes
bind the selected aggregate/provenance files, original ZIP traces, and
unchanged `evidence/tranche-7-ns3-reference/` files. Recreate fresh reports
from the ZIP with the original source checkout:

```bash
git worktree add --detach ../tranche7-validated 28ed878f5673e308047cbea7878b933697d932f3
python3 ../tranche7-validated/scripts/analyze_tranche7_return.py \
  --evidence evidence/tranche-7-r2025a-accepted/tranche7_evidence.zip \
  --source-root ../tranche7-validated \
  --output ../tranche7-return-review
```

Run these commands from the repository root; the new worktree and output
directories must not already exist. The frozen checkout matters because
the source snapshot also binds candidate-time metadata. Updating the current
acceptance pointer is not a change to the MATLAB code that was executed.

MATLAB R2025a execution occurred on the owner's laptop. This review workspace
ran Python checks against the returned records; it did not execute MATLAB,
rerun OPNET, or rerun ns-3. Reference runs were completed during candidate
preparation and remain bound to their original production records.

`independent-integrity/` contains a separate standard-library audit against
immutable Git blobs, including its script and output. `independent-outcomes/`
contains an independent reconstruction of all 4,800 MATLAB/ns-3 core points,
retained T6 outcome checks, and five strict shared application comparisons.
Their recorded absolute paths describe the review host. The integrity
script accepts paths and the candidate commit through its documented CLI
(`--help`). The outcome script is the one-off review snapshot and retains
the original `BASE`, `REPO`, `OUT` and `ZIP` path constants; adapt those in
a copy for another checkout. Neither audit modifies the candidate or the
returned evidence.
