# Autonomous network investigation evidence — 25 September 2026

The findings are in `autonomous/Autonomous_Network_Investigation_2026-09-25.md`.
This archive is the analysis/reference record. For the user-run MATLAB batch,
use `autonomous-seed132-tests.zip`; its `autocase/README.md` gives the one command.

## Executed here

- Offline comparison of the original seed-132 traffic/admission/receiver traces.
- Pinned ns-3 environment restoration and an extended passive 0–330 s capture.
- Exact comparison of 48,919 canonical native rows and all 30 fields.
- Independent comparison of all 928 MAC samples with the earlier accepted capture.
- Source-transform reversal, syntax checks and static peer review of the new
  MATLAB diagnostic kit. These checks are not MATLAB runtime execution.

MATLAB's natural-prefix equivalence and coupled case remain pending an owner
run. A diagnostic stop does not itself prove a production bug. The 15% network
target remains separate and unmet.

## Contents and reproduction

`autonomous/traffic` and `autonomous/receiver` contain the offline audit scripts,
joined events, per-source counts, summaries, input hashes and reviews.
Their input manifests identify the original 6,000 s files. The large original
MATLAB return and original full native trace are retained separately:
`out_6000_20260924_152302.zip` and `t25up.zip`. Restore the former under
`return6000/data/` and the latter's seed132 trace under
`next_feedback/native_archive/evidence/tranche-25-ns3-reference/s132/` if rerunning
the full raw audits. The accepted native application ledger is included under
`return6000/kit/csr6000/reference/s132/`.

`autonomous/native_capture` contains the native driver, passive overlay
generators, compile/run recipes, exact prefix reference, raw new observations,
normalizers, random/TX/state fixtures and provenance receipts. The compiled
binary and engine libraries are excluded. Its README describes the precise
observation scope. `autonomous/native_env/build.json` records the restored
environment; the included `restore_native.py --root autonomous/native_env`
script can recreate the pinned repositories/build before rerunning the
native build/capture recipes. Those operations are for the analyst, not a task
Mike needs to perform.

`autonomous/design` and `autonomous/capture_design` contain instrumentation,
design and independent review. `autonomous/kit` contains the exact source-bound
MATLAB kit. `autonomous/tooling/final_syntax` records the syntax-only check,
parser version, output and source hashes. No installed parser package is
bundled. The original 99-file MATLAB model is included solely as a reference
for the reversible source-transform audit; it is not a new production release.

From the extracted archive root, the already captured native data can be
renormalized without running a simulator:

```sh
python3 autonomous/native_capture/normalize.py
python3 autonomous/capture_design/check_final_transform.py
```

The manifest `autonomous/EVIDENCE_CONTENT_SHA256.json` lists all archive members
except itself. It preserves exact captured and reviewed files, including
historical workspace paths inside provenance records.
