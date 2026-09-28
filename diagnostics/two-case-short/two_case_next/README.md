# Seed-131 discovery and seed-132 source-5 short replay kit

Package v3 corrects receiver-state ownership in the replay harness. Actual
wake/sleep transitions are inputs; PHY receive/transmit completion states
are checked as outputs. The production candidate is unchanged. The v2
return passed the HOP and MAC checks; its receiver comparisons need this
corrected short rerun. See `review/Short_Replay_Review_2026-09-23.md`.

## Run in MATLAB

1. Extract the complete ZIP to a short local path, for example `C:\csr\short`.
2. In MATLAB R2025a or later, set **Current Folder** to the extracted
   `two_case_next` folder containing `run_short_tests.m`.
3. Run:

```matlab
report = run_short_tests;
```

The command runs all four short checks using the candidate and prepared
native inputs bundled in `candidate` and `native`. It creates an
`out_short_YYYYMMDD_HHMMSS.zip` file in the same folder and prints its full
path. **Return that ZIP, even if a check fails.** It includes comparison
reports, runtime/source provenance and any errors needed for review.

No path arguments, Python commands or ns-3 installation are needed for this
MATLAB run. If the package reports a missing bundled input, return its
result ZIP so the package can be corrected.

## What the short checks cover

This kit runs the two investigations together. It instruments the original
native experiment without changing its model logic, demands exact equality
to the original native trace from time zero, then feeds native history into
bounded MATLAB checks. The MATLAB grouped-routing candidate is the version
from the accepted fix milestone. There is **no production code change** in
this kit.

| Case | Native run and decision window | MATLAB checks | Limit of the result |
| --- | --- | --- | --- |
| Seed 131 discovery | Start at 0, stop at 85 s; inspect 25–85 s node 4→5 acquisition and node 4→2 propagation | Recorded physical transmissions, external receiver states and actual receiver random draws; 22 target decisions, plus three seed-132 long-link controls | PHY acquisition is conditional on captured history. NWK discovery handoff and aggregate child delivery need their own rule comparison. |
| Seed 132 source 5 | Start at 0, stop at 330 s; inspect 300–330 s node-4 ACK reception and node-5 admission/service | Node-4 physical receiver with captured inputs and draws; first 16 native-timed application HOP admissions; node-5 MAC scheduling | ACK outcome alignment and HOP/MAC results have separate gates. Native `prior_stage` subtypes and full NWK state remain unresolved. |

The original unfiltered canonical reference prefixes are included, SHA-bound
and checked row by row: 8,710 events before 85 s for seed 131 and 48,919
before 330 s for seed 132. The native recorder includes all seven nodes,
every transmitted aggregate child and its wire bytes, receiver events, and
MAC random draws. The prior accepted MAC capture baseline is bundled in
`accepted_mac_native` so the seed-131 overlay can be built without finding
an older 112 MB history archive.

## Maintainer: prepare both native captures

The steps below prepare the inputs before issuing the complete MATLAB ZIP.
They are not part of the MATLAB run above.

On the machine with the original native CSR source checkout and matching
Debug ns-3 build, from this kit's `two_case_next` directory:

```bash
python3 run_two_native.py \
  --native-source-repo /path/to/original/native/checkout \
  --source-model /path/to/original/native/checkout/model \
  --engine-repo /path/to/ns3/engine \
  --engine-build /path/to/ns3/engine/build \
  --out /path/to/new/two_case_native
```

The exact source and engine commits are
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` and
`6b5cd24ea80713ce16d88575869aedd6f432bdae`. The scripts also check
source file hashes, scenario hashes, every field and order of the native
canonical trace prefix, tape/observer consistency, and require a new output
directory. The two simulations run concurrently by default; add `--serial`
on a memory-limited machine. If one fails, the other completes and the batch
is marked open. Check `batch.json` and each case log. The native scripts need
Python 3, g++ with C++23, and the original ns-3 Debug libraries.

After a successful run, `discovery131.verified.manifest.json` and
`source5_132.verified.manifest.json` in the result directory should each
pass `schema_review/validate_two_case.py`. They are **capture** manifests:
their replay statuses remain `replay_pending` until MATLAB runs. A missing
or changed reference prefix cannot turn into a passing capture.

## Maintainer: bind inputs and assemble the MATLAB package

Convert the new seed-131 receiver tape, using the native MAC input tape from
the **same** verified capture:

```bash
python3 discovery_replay/convert_capture_draws.py \
  --capture /path/to/two_case_native/seed131/capture.jsonl \
  --mac-inputs /path/to/two_case_native/seed131/mac_csv/inputs.csv \
  --mac-tx /path/to/two_case_native/seed131/mac_csv/tx.csv \
  --fixture discovery_replay/fixture \
  --output /path/to/two_case_native/seed131/phy_draws.csv
```

This rejects missing or ambiguous physical TX identities, changed packet
sizes or receiver states at 25 s, and missing/duplicate draws. It also
writes `receiver_inputs.csv` and actual-power `tx_inputs.csv` beside the
draws for the two target receivers.
Bind the seed-132 receiver inputs and every transmitted child from its
verified native capture:

```bash
python3 source5_receiver_replay/bind_capture.py \
  --capture /path/to/two_case_native/seed132 \
  --output /path/to/two_case_native/bound_node4
```

The binder verifies all 48,919 original prefix rows, the clean node-4 state
at 300 s, all 299 physical transmissions and ordered children, native ACK
outcomes, actual transmit powers, and the named PHY interval/draw tape.
Copy the accepted candidate tree (containing `+csr`) to `candidate` in the
kit. Copy the verified, bound native result directory to `native` in the
kit. The resulting package must contain `native/batch.json`,
`native/seed131/phy_draws.csv` and its provenance/receiver/transmission
inputs, `native/seed131/capture.jsonl`, the verified seed-132 capture tapes,
and `native/bound_node4`. Issue the complete package only after both native
capture fidelity checks and input binders succeed.

One call runs the discovery PHY reconstruction, the production HOP capacity
fixture, the node-4 receiver reconstruction, and node-5 conditional MAC replay,
recording separate reports and a
`summary.json`. It continues to the remaining checks if one fails. Read the
first differing event or capacity field, along with the captured receiver
state/ACK and relay traffic, before treating a discrepancy as a model rule
bug. The source-5 HOP fixture supplies historical native actual-send and
feedback times; its test-owned NWK FIFO is **not** the native 300-second NWK
state. Discovery success, arrival time, collision and errors are reported
separately; a Boolean success match alone is not a receiver parity pass.
The node-4 replay compares 255 physical outcomes (including ten node-5 ACK
signals), interference intervals, random draws, and delivered ACK children.
Even exact outcome alignment leaves the broader native `prior_stage` rule
subtypes open, so its result is **not** a complete receiver-rule parity pass.

## Interpreting results

The wrapper's `completed` field records whether all four replay procedures
finished. Their separate outcome and rule gates remain in
`replays/summary.json`; completion is not a parity pass. The wrapper retains
each gate without combining them into a network parity claim. A missing
native capture or failed prefix-fidelity check cannot be replaced with an
older reference trace. Only a concrete same-input rule mismatch should
lead to a production fix; full 6,000-second network parity still requires
the broader comparison.

For detailed schemas and individual diagnostics, see
`schema_review/INTERFACE.md`, `discovery_capture/README.md`,
`discovery_replay/README.md`, `source5_capture/README.md`, and
`source5_replay/README.md`, plus `source5_receiver_replay/README.md`.
