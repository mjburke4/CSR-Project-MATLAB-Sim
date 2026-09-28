# Seed-132 receiver-feedback evidence — 25 September 2026

Read `next_feedback/deliverables/Seed132_Feedback_Investigation_2026-09-25.md` first.
Native means ns-3. This package contains offline analysis and previously executed
MATLAB evidence. It is not a new MATLAB test kit. No simulation is required to
read the findings, and no new production model change is included.

## Main results

- MATLAB 139 ACK + 993 DACK decisions account for all 1,132 accepted 8→2 packets;
  native 300 ACK + 945 DACK account for all 1,245. All audited first receptions
  follow the same per-flow custody threshold, and completion classes agree.
- Source-7 arrival-weighted custody is 75.91 versus 25.16; its time average over
  300–6000 seconds is 72.96 versus 25.30. The source mix also differs.
- Native node 8 sends 34 feedback transmissions before its first DATA at
  316.719 seconds. The actual September 23 MATLAB return already reproduces
  this sequence under the same inputs. A repeat conditional MAC test is redundant.
- Autonomous network histories remain different. This audit does not explain
  all long-run latency or establish the ±15% network target.

## Included evidence

`next_feedback/matlab_receiver`, `native_receiver`, and `delivery` contain
receiver-state reconstruction, per-application outcome joins, physical-feedback
reconstruction, and the early scheduling investigation. `comparison` contains
the combined custody and service tables and plotting code.

`prior_coverage` contains capture provenance, byte-comparison results and the
native 0–330-second MAC fixture. `prior_acceptance` contains independent checks
against the actual earlier MATLAB outputs. The earlier owner's outputs, its
160 runtime-bound files, the four reused adapter files, and the current 99-file
MATLAB model snapshot are included so the acceptance-reuse checks can be rerun.
These model files are reference snapshots, not files the user needs to install.

The draft repeat replay kit and its superseded static assessment are excluded.
`CONTENT_SHA256.json` inventories every included file except itself.
`INPUTS.json` identifies original archives and records hashes of the external
large inputs. Those original long-run traces are not duplicated here.

## Reproduce the acceptance-reuse finding without a simulator

Extract this ZIP into a new directory and run from its root:

```sh
python3 next_feedback/prior_coverage/compare_prior_acceptance.py
python3 next_feedback/prior_acceptance/check_prior_actual_service.py
```

These scripts check existing actual MATLAB results against native references;
they do not run MATLAB or ns-3. Expected results are `pass: true`, 160 bound
files verified, 4,075 matched MAC input events, 192 matched full frames,
208 matched TX records and 241 matched random draws in the two-node prefix.
The second script checks the three specific service assertions.

The combined tables and figure can be regenerated entirely from included
derived data (Python 3; matplotlib is required only for the plot):

```sh
python3 next_feedback/comparison/compare_receiver_histories.py
python3 next_feedback/comparison/plot_receiver_pressure.py
```

## Reproduce the full raw-trace audit

The original source archives are separately retained in the project files.
Check their hashes against `INPUTS.json` before extraction. Extract
`out_6000_20260924_152302.zip` into `return6000/data/`, preserving its member
paths. Extract `evidence/tranche-25-ns3-reference/s132/` from `t25up.zip` into
`next_feedback/native_archive/`, preserving that path. Then run:

```sh
python3 next_feedback/matlab_receiver/audit_receiver.py
python3 next_feedback/delivery/audit_feedback.py
python3 next_feedback/native_receiver/analyze.py
python3 next_feedback/native_receiver/derive_service.py
python3 next_feedback/delivery/early_service/analyze_early.py
python3 next_feedback/comparison/compare_receiver_histories.py
python3 next_feedback/comparison/plot_receiver_pressure.py
```

The native audit streams about 1.17 GB of decompressed trace. It may take time;
all its resulting CSVs and summaries are already included. No new network run
is necessary. Individual audit reviews describe inference and capture limits.

For the auxiliary short-return archive/provenance check, place the original
`out_short_20260924_083651.zip` and `out_next_20260924_100916.zip` under
`next_feedback/recovered/NS3 to MATLAB Network Simulation/`, then run
`python3 next_feedback/prior_coverage/audit_coverage.py`. That script extracts
its inputs locally. This is optional for inspecting the already included
acceptance-reuse proof.
