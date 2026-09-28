# Original 6,000-second CSR evidence review

24 September 2026. Historical T25 seeds 128–132. No new simulation or production change.

Start with `reports/CSR_6000s_Accounting_Review.md`. The adjacent images render with that report.
The complete engine/seed/source table is `longrun_review/ensemble/per_seed_source_accounting.csv`.
Deadline comparisons are `longrun_review/ensemble/fixed_age_delivery.csv`; unfinished ages are
`longrun_review/ensemble/unfinished_ages.csv`. Native undelivered fate stays unresolved: it is
not classified as a known terminal drop or a confirmed live pending application.

## Reproduce the ensemble and independent arithmetic review

Requires Python 3.10 or newer, standard library only. From this extracted directory run:

```sh
python3 longrun_review/ensemble/analyze_ensemble.py --workspace .
python3 longrun_review/method_crosscheck.py
```

The first command regenerates ensemble CSVs and summary from the ten included historical
packet ledgers, accepted metric table and seed-131/132 admission counters. The second
independently checks 2,192 fields against those ledgers. Both commands overwrite generated
outputs in this copy only. No simulator or MATLAB installation is invoked.

Optional figure reproduction requires matplotlib and numpy:

```sh
python3 longrun_review/build_figures.py
```

The original recovered latency-review archive is included in its expected relative location,
with its original SHA256SUMS.json. Its archived documentation reflects the September 21 state;
the September 24 report above supplies the current interpretation and limits.

## Raw-trace verification and scope

The completed MATLAB and native seed-131/132 raw-verification results and parsers are included
under longrun_review/matlab, native_s131, native_s132 and shared. Their admitted-application and
causal-hop CSVs are included. Re-running these raw-verification parsers additionally requires
the original large T25 MATLAB and native trace archives at their recorded paths; those raw
traces are intentionally not duplicated here. Consult the parser arguments and its audit
JSON provenance before rerunning. The ensemble/arithmetic commands above need no external files.
Older seeds 128–130 reuse the archived ledger provenance; their raw traces were not reparsed
in this review. The native raw captures do not identify every application's first physical
transmission and retry span, so the comparable complete latency split remains NWK waiting
versus subsequent HOP-to-causal-receipt service. No terminal fate or latency was imputed.

Original recovered archive SHA-256 values are in longrun_review/recovery.json.
Original T25 owner ZIP: d215f2b5ecb2ac5cc6213d77ce5bd631a9609fb46460e1798b7e3e3d2c9cd436
Original latency-review ZIP: 591e4033515ddf7e3f5573043fcbd9c7e1d0fbc0e775d63d39b47c87915e1aba

These results predate the grouped-routing cleanup fix and do not establish current-candidate
6,000-second acceptance. This is an analysis evidence package, not a MATLAB run kit.

FILES.sha256.json binds every other file shipped in this package. Verify it before executing
commands that regenerate outputs; subsequent formatting/platform differences can change hashes.
