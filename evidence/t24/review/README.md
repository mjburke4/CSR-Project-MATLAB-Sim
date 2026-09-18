# Tranche 24 completed diagnostic

Read `T24_Review.md` for the result and engineering decision. No MATLAB command or simulator update is needed for T24.

## Reproduce the native census

Use Python 3 and the accepted T20/T23 installation containing the original references under `evidence/tranche-20-ns3-reference/s129` and `s130`. The analyzer checks the exact compressed and uncompressed native trace identities, and the scenario's zero-DSCP prerequisite.

```sh
python3 analysis/custody_census.py --source-root /path/to/accepted/csr23 --output /path/to/new/native-results
python3 analysis/service_lineage.py --source-root /path/to/accepted/csr23 --census-dir /path/to/new/native-results
```

The output includes per-flow totals, one row per custody entry, repeat lineage, observed queue/capacity areas and verification counts. The original compressed traces remain in the accepted `t20up.zip`; their hashes are recorded in the results and `input-verification.json`. They are not modified by this analysis.

For the separate raw-event reconstruction and repeat-lifetime audit, use the native reference directory containing `s129` and `s130`:

```sh
python3 review/independent_raw.py --native-reference-root /path/to/accepted/csr23/evidence/tranche-20-ns3-reference --output /path/to/new/independent-results
python3 review/audit_repeat_lifetimes.py --native-reference-root /path/to/accepted/csr23/evidence/tranche-20-ns3-reference --output /path/to/new/independent-results
```

## Reproduce the MATLAB return analysis

Extract the accepted owner `t20.zip` into a folder containing `s129` and `s130`. Use the accepted T21 diagnostic supplied in `context/t21-diagnostic.json`.

```sh
python3 analyze_matlab.py --owner-root /path/to/extracted/t20 --t21-diagnostic context/t21-diagnostic.json --output /path/to/new/matlab-results
```

This reads already completed MATLAB evidence; it does not invoke MATLAB. Each input table is checked against the original per-case receipt, and the retained counts and occupancy are checked against T21.

## Input archives

| Input | SHA-256 |
|---|---|
| Original owner `t20.zip` | `41ee42fd72d3246b005cffa6eb0731aef1f465ac19747be82feb481571a72861` |
| Accepted `t21review.zip` | `4778405d7948a43a2b40ffadbacc2c88e5965b5afce504d60d3b1d2c4cd7c739` |
| Native seed-129 `ns3-trace.csv.gz` | `aa4ae4e40309ef956d5e89d20040828c3fab47062747eaa51a637506764c2643` |
| Native seed-130 `ns3-trace.csv.gz` | `404b719dcb8c2762cb60a2f60eb2489b0b5c41f198baa25b3fe93630c1b07930` |

The full input verification can be repeated with `verify_inputs.py --baseline-root PATH --inputs PATH --output PATH`. Its input layout is `NS3 to MATLAB Network Simulation/t20.zip`, `NS3 to MATLAB Network Simulation/t21review.zip`, and the extracted `t20/` and `t21review/` folders. It verifies the accepted archive hashes, T21's closed manifest, all T23 candidate source bindings and the original MATLAB receipts.

`SHA256SUMS.json` binds every package member except itself. `acceptance.json` records the diagnostic gate separately from numerical parity. Raw input archives remain unchanged; the compact package includes derived evidence and exact input hashes rather than duplicating the large campus trace archives.
