# Reproducing the review

Use the exact issued r2 installation with candidate SHA in `milestone.json`.

```text
python <r2-installation>/scripts/analyze_tranche14_return.py --evidence owner.zip --source-root <r2-installation> --output gate-out
python check.py --evidence owner.zip --source-root <r2-installation> --output check-out.json
```

These commands inspect owner-returned evidence; they do not execute MATLAB.
The independent `diff/analyze.py` preserves its original workspace defaults:
put that script under `t14a/diff`, the return under `upload/t14(2).zip`, and the
issued installation under `csr14s`, beneath the same workspace root, then run
`python t14a/diff/analyze.py`. Exact reference CSVs are also copied under
`native` for direct inspection. All outputs and their source bindings are
already included in this record.

The supplied `docs/parity-ledger.csv` is a review addendum for the next candidate,
not an instruction to replace files in the validated installation. No rerun or
installation change is needed merely to retain this review record.
