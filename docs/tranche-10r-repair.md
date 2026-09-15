# Tranche 10 retry repair

The owner console log stopped in retained case 27/29, `research_mesh_6_seed_128`,
at the original two-million-event limit. Before that failure, all 534 contract
checkpoints passed, the unit-test gate completed, and 26 retained scenarios
completed. Campus had not started. The printed Tranche 4 failure belongs to an
intentional failure-preservation unit test. The full owner return archive was
not supplied, so the failed mesh callback and exact simulation time are unknown.

## Concrete defect and correction

Neighbor admission compared elapsed time with a retry interval, but scheduled
the callback using the corresponding absolute deadline. Double arithmetic can
make those operations disagree. Starting at 11.013 seconds, adding 5 seconds
produces 16.012999999999998. At that deadline, subtracting the start gives
4.9999999999999982: the old code considered the retry premature, calculated
zero remaining delay, and scheduled the same callback at the same instant.

This is reachable through public controls in three branches: missing-key
requests, rejected key updates, and overheard neighbor checks. The repair tests
the same absolute deadline used to schedule the callback, and schedules that
deadline directly when it is still in the future. Retry intervals, exponential
backoff, completion ownership, admission proof and the event limit are retained.
No tolerance, extra jitter or global time quantization is introduced.

The current ns-3 main was checked on 2026-09-14 and remains
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. Its admission timer uses native `Time`
values. The source excerpt and blob identity are included in
`evidence/tranche-10r`. This is a floating-point repair in the MATLAB port;
it is not a change to the source admission policy or evidence of numerical
parity. The known loop is a plausible cause of the owner failure, pending the
focused mesh rerun.

Only `+csr/+nwk/Neighbors.m` changes protocol execution. The scheduler change
adds the current time and last/next callback names to its existing event-limit
exception, only when the limit is exceeded. PHY/ECC, MAC, HOP, RNG, scenarios,
source/reference inputs and all accepted archives retain their original bytes.

## Run the focused check first

Extract the complete `csr10r.zip` into `C:\csr10r`. Start a fresh MATLAB session,
then use the Command Window:

```matlab
cd('C:\csr10r')
report = run_tranche10_mesh;
```

The command runs 32 focused tests, then only the unchanged six-node mesh at
seed 128 for 900 simulated seconds and with `MaxEvents=2000000`. It does not
repeat the preceding 26 cases or launch campus. No runtime estimate is promised;
the accepted T6/T7 version of this mesh took about 60 wall seconds on the owner's
earlier runs.

Upload the `mesh.zip` path printed at the end, whether the mesh succeeds or
fails. Output stays under the short `results/m10/r...` path. The archive contains
exact config, source hashes, test outcomes, MATLAB version, closed console log,
and a MAC/HOP/NWK state snapshot. A successful run also includes complete raw
traces and the existing structural/accounting checks. A failure preserves the
original exception and available scheduler/node state. MAT files remain local.

This is diagnostic evidence. Full Tranche 10 acceptance remains blocked until
the mesh repair is confirmed and the complete `run_tranche10_validation` gate
passes against this exact repaired source. The package includes all previous
tranche entry points. Original accepted evidence and the original `csr10.zip`
remain recovery anchors; this candidate does not replace their acceptance.

## Validation and limits

Local checks passed: all 303 Python reporting tests and static MATLAB parsing
of the five affected/new MATLAB files. Five new neighbor-test methods cover
seven fractional deadline cases plus completion/discovery safeguards; one new
scheduler test verifies that diagnostic error text preserves the pending queue.
Those tests are included among 550 prepared portable test methods.

The arithmetic contradiction was executed independently in Python binary64.
No MATLAB, Octave or new native simulation was executed for this repair.
MATLAB regression outcomes, owner failure attribution, mesh completion,
campus performance and full acceptance remain pending. Local validation,
independent review, exact changed-file hashes and the package baseline are
recorded in `evidence/tranche-10r-candidate.json` and `evidence/tranche-10r`.
