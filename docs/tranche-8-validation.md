# Run the smaller multiseed and ACK diagnostics

The R2025a owner run at `89b62e7` is now accepted: 485/485 tests, ten cases
and two tracing controls passed in 32 minutes 19 seconds. These instructions
remain for reproduction; see the [acceptance report](tranche-8-portable-acceptance.md).

Extract `csr8.zip` directly into a short folder such as `C:\csr8`. The ZIP
has no enclosing directory. Preserve the earlier accepted `csr7` package and
its evidence for reproduction.

Use the replacement package that includes `docs/tranche-8-input-repair.md`.
The original `010793b` package incorrectly populated run-only metadata on
node and flow rows and failed during initial import. Extract the replacement
into a fresh directory so the corrected CSVs, plan and reference hashes stay
together. No diagnostic run had started at the reported import failure.

New results use `results\t8`, a short timestamp/token run folder, and compact
case folders: `b\a128` means admission seed 128, `b\c128` means contention
seed 128, and `c\a128`/`c\c128` contain tracing-disabled controls. Full
experiment names remain in the manifests and summary CSV. For example,
`C:\csr8\results\t8\r260910_160000_a1b2c3d4\b\a128\raw\summary.json`
avoids repeating long experiment names or nesting older validation runs.

Open MATLAB R2025a in the new folder and run:

```matlab
report = run_tranche8_validation;
```

The command runs all current portable unit tests, then the 1,200-second
admission fixture and 360-second contention fixture at seeds 128 through
132. Both seed-128 fixtures also repeat with the observer disabled. That is
ten diagnostic cases and two control runs. The campus benchmark and retained
18-case research sweep are not part of this command.

The accepted T7 simulations took about 170 seconds for admission and 40
seconds for contention on the owner's laptop. Applying those observations
to twelve runs gives about **21 minutes of simulation time**, before unit
tests, added observation cost and exports. Allow additional time; this is
an estimate, not a measured T8 runtime. Completion messages appear before
and after each case. There is no periodic in-case heartbeat.

Upload the printed **`tranche8_evidence.zip`** when it finishes. The archive
contains full protocol/PHY/application records, feedback decision and actual
transmission observations, hashes, manifests, unit-test results and the
observer control comparisons. MAT objects remain in the local results folder.
If execution fails, return the partial archive or the original error and
printed evidence directory. Completed raw observations are saved before a
diagnostic completeness check can reject a case.

The observer records choices already made by MATLAB. It neither implements
ns-3 reverse-link control nor changes the accepted ACK, MAC, routing or PHY
policies. A separate return review will compare all seeds with ns-3 and the
seed-128 T7 anchor. No T8 MATLAB execution or acceptance is claimed before
that returned evidence is verified. R2026a/native execution remains separate.

For a deliberate run without the unit-test gate:

```matlab
report = run_tranche8_validation([],struct('RunTests',false));
```

That result is diagnostic-only. Seed, duration and offered-load overrides
are not accepted under these experiment identities. Run each new candidate
in a fresh folder so its source snapshot and reference hashes are unambiguous.

After return, use the exact frozen candidate checkout:

```bash
python3 scripts/analyze_tranche8_return.py \
  --evidence /path/to/tranche8_evidence.zip \
  --source-root /path/to/frozen-candidate \
  --output /path/to/new-review-directory
```

The reviewer verifies provenance, test membership, the declared ten-case
plan, trace completeness and accounting before computing descriptive paired
seed differences. Failed or partial evidence cannot pass the full gate.
