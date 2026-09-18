# Completed Tranches 22–24 checkpoint

This checkpoint adds the completed T22 and T23 controlled diagnostics and the
accepted T24 offline analysis to merged PR #9. It preserves the **404 accepted
T23 source bindings, including 181 MATLAB files**. T22 and T23 add 28 source
inventory paths to T20; none of the 376 T20 source bindings changed.

## Validation and findings

| Tranche | Evidence and disposition |
| --- | --- |
| 22 | Controlled production-HOP adaptive-window contract accepted: 89/89 MATLAB tests, 9 cases, and 364/364 state checkpoints matched. This is a focused contract gate, not a new full-campus or full-regression run. |
| 23 | Receiver-pressure/ACK-DACK diagnostic accepted: 79/79 MATLAB tests and 7 cases completed. All 91 feedback control-field records matched; 121/123 custody checkpoints matched. Two custody differences remain explicitly unresolved. |
| 24 | Accepted offline custody census of existing campus evidence; no new MATLAB/native simulations, no new MATLAB tests, and no production model change. |

The T22 and T23 owner runs used portable MATLAB R2025a
`25.1.0.2943329`. The native CSR source pin remains
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, with engine
`6b5cd24ea80713ce16d88575869aedd6f432bdae`.

T23's `dack_duplicate_pressure` checkpoint has custody 17 in MATLAB versus 18
in ns-3; `dack_reassessment_after_release` has 14 versus 15. Its accepted
diagnostic record deliberately retains `cross_engine_contract_passed=false`.
Neither diagnostic acceptance nor successful MATLAB unit tests erase these
differences.

T24 examined 11,338,973 native events and 37,008 relay-custody entries across
accepted campus seeds 129 and 130. At node 8/source 7, all 849 and 1,361 entries,
respectively, were distinct applications; there were no repeated entries.
The census found 10 and 9 repeated custody entries elsewhere. Their observed
share of HOP capacity-owner time was about 0.062% and 0.046%. Those measurements
do not establish a causal performance bound. The evidence did not justify a
production patch, and the node-8/source-7 backlog remains a separate finding.

The working **±10%** campus target remains descriptive. No new numerical-parity
or statistical-equivalence acceptance is claimed. The accepted full-campus
results through T20 and the T21 comparisons remain the latest published campus
ensemble in this checkpoint.

## Source, scope and provenance

The `actual-tx` queued-retry default, continuous timing and PHY/ECC behavior
remain unchanged. Battery, supervisory-layer and BBN-routing work remain outside
scope. T25 source, references, candidate files, packages and owner results are
excluded while its MATLAB run is in progress. This PR is for review and does not
merge or change `main`.

The publication includes:

- Exact issued T22/T23 additions and their pinned reference files.
- `evidence/t22/accepted/`: the accepted T22 review, original owner archive and
  issued update, preserving its closed manifest.
- `evidence/t23/review/` and `evidence/t23/review.zip`: the exact accepted T23
  package, including original owner and issued-update archives, returned source
  and reference snapshots, independent checks, and the documented differences.
- `evidence/t24/review/` and `evidence/t24/review.zip`: the exact accepted offline
  analysis, scripts, input identities, review and findings.
- `publication/tranches-22-24.json`, the independently verified input record,
  and the publication file inventory.

All prior repository files are retained. The root parity ledger advances to the
accepted T24 ledger. Because the issued T23 reference inventory binds the older
root ledger, its exact bytes are preserved separately at
`evidence/t24/baseline/tranche-23-issued-parity-ledger.csv`. This is the sole
relocated historical T23 reference; the other 292 reference bindings remain at
their original paths. The README status banner is also updated.

The historical T22/T23 candidate and handoff files retain their original
then-pending wording. Their exact bytes are part of the accepted identities;
the later acceptance records and this document provide their current status.
For exact historical reproduction, use the preserved issued installation and
its matching ledger instead of treating this combined checkpoint as a newly
executed candidate.

Publication creates a new Git commit identity. Original file hashes connect
that identity to the accepted owner runs; the publication commit itself was
not run in MATLAB. No simulations were repeated solely for publication. The
next engineering action is review of the separately running T25 five-seed
comparison when its owner return is available.
