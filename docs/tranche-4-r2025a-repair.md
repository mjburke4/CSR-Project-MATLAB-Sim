# Tranche 4 initial R2025a run and evidence-utility repair

The owner ran candidate `a6d017a` on MATLAB R2025a
`25.1.0.2943329`. The pasted console reports 330/331 tests passed, one failed
and incomplete method, and 100.1566 seconds of test execution. The failing
method was `TestResearchEvidence/inventoryUsesPathsRelativeToItsDirectory`.
No machine-readable results or source hashes accompanied this transcript;
the [runtime record](../evidence/tranche-4-r2025a-initial-run.json) preserves
that evidence boundary. The original candidate manifest is retained as
[`tranche-4-initial-candidate.json`](../evidence/tranche-4-initial-candidate.json).

The test failure stopped validation before the separate Tranche 2/3 export
loops and the new shared/research scenario loops. Passing scenario unit tests
does not establish completion of those longer exports. Tranche 4 remains a
candidate; neither the repair nor a MATLAB/ns-3 comparison has run in MATLAB
in the engineering workspace.

## Root causes and bounded changes

The relative inventory path was passed directly to Java after MATLAB changed
folders. Java resolves relative files using `user.dir`, whereas MATLAB `pwd`
identifies MATLAB's current folder. The observed empty inventory is consistent
with scanning the wrong folder. A shared helper now anchors relative paths to
`pwd` before Java canonicalization. It is used for inventories, output roots,
source snapshots and imported scenario provenance. Java global properties are
unchanged. See [Java File](https://docs.oracle.com/javase/8/docs/api/java/io/File.html)
and [MATLAB pwd](https://www.mathworks.com/help/matlab/ref/pwd.html).

Failure reporting then errored inside the Java hash update. The specific file
was not identified, but empty logs reach that path and expose ambiguous
empty-array dispatch to Java's overloaded update methods. Both Tranche 4 hash
helpers now skip the update for empty input and finalize the empty digest.
Existing nonempty byte conversion is unchanged. See the overloads and digest
lifecycle in [MessageDigest](https://docs.oracle.com/javase/8/docs/api/java/security/MessageDigest.html).

The runner now excludes its live diary, self-metadata and ZIP before hashing.
Its failure handler guards test-result reads and inventory generation, falls
back to a minimal JSON failure record, and preserves the original exception
if recording or archiving fails. Missing inventory directories now fail
explicitly. The original test uses a fatal assertion before accessing the
single entry, preventing the secondary `MATLAB:minrhs` diagnostic.

## Verification and next run

Two prepared regressions cover empty/single-byte SHA-256 and a cheap failed
validation with a relative output root. The latter disables tests/scenarios,
requests an unknown catalog case and checks the original error plus the
partial metadata/ZIP. It restores the surrounding test diary afterward; MATLAB
exposes the current diary state and filename through root properties documented
in [diary](https://www.mathworks.com/help/matlab/ref/diary.html).
Existing importer regressions now also check relative provenance after `cd`
and an empty CSV's intended validation error. The portable suite now contains
333 methods. Static verification and retained Python/reference evidence are
recorded separately in the candidate manifest. These are prepared MATLAB
regressions, not passing runtime claims.

Extract the corrected full ZIP into a new folder and run:

```matlab
report = run_tranche4_validation;
```

Return the generated `tranche4_evidence.zip`. The default run retains the
portable suite and earlier scenarios, then runs five shared cases and six
research layouts. The 6000-second and native gates remain optional. Existing
PHY/ECC, HOP, MAC, NWK and scheduler code is unchanged by this repair.
