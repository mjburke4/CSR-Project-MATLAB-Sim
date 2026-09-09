# Tranche 4 portable acceptance

**Accepted for the bounded R2025a portable scope at code commit `6fdf238`:**
333/333 tests pass, all 11 shared/research exports complete, and all five actual
MATLAB/ns-3 comparisons pass strict application equality. The retained eight
Tranche 3 and nine Tranche 2 scenarios also complete. This update changes
evidence and documentation only.

## Runtime and evidence integrity

| Gate | Verified result |
| --- | --- |
| Runtime | MATLAB R2025a `25.1.0.2943329`, portable backend |
| Run | 2026-09-09 16:51:49.382–17:03:55.783 UTC; 726.401 seconds |
| Tests | Exact set of 333 methods in 27 classes; zero failed or incomplete |
| Test duration | 116.5233913 seconds summed method time |
| Source identity | All 83 MATLAB file hashes match committed code `6fdf238` |
| Inputs | All 90 top-level source/BER/catalog/input/candidate hashes match |
| Bundled evidence | 291 top-level artifact hashes/byte counts, 126 case artifact hashes and 115 declared CSV row counts verified |
| Archive | 293 files; top-level metadata and its live log intentionally excluded from their own inventory |
| Local objects | 30 MAT files explicitly retained on the owner machine; omitted objects were not independently checked |
| Case identity | All 11 case manifest hashes and source snapshots match the completed run |

Independent reviews checked artifact integrity, exact test names, and research
outcomes. Application identities, payloads and latency were reconstructed from
48,207 research protocol rows. Physical counts and drop-reason buckets were
checked against 33,919 research PHY rows. No truncated traces or unbalanced
application/receiver accounting were found.

The original ZIP, selected metadata/CSVs and actual comparison outputs are
preserved in `evidence/tranche-4-r2025a-accepted/`. The
[structured acceptance record](../evidence/tranche-4-portable-acceptance.json)
contains their identities and detailed results. The exact candidate manifest
used by the owner is retained as
[`tranche-4-validated-candidate.json`](../evidence/tranche-4-validated-candidate.json).
The prior 330/331 run remains historical evidence in the
[repair record](tranche-4-r2025a-repair.md).

## First actual shared MATLAB/ns-3 comparison

Each case generated and delivered three 64-byte application payloads in each
simulator. Generation identities/times, DSCP, payload sizes and delivery status
match; all five comparator commands exited 0 with
`--require-application-equality`. Across the cases this covers 15 applications
and 960 delivered payload bytes per simulator, using identical canonical CSV
bytes and the pinned ns-3 reference `486d9e01…`.

| Shared case | Delivered, each simulator | Mean latency MATLAB / ns-3 (s) | OTA transmissions MATLAB / ns-3 |
| --- | ---: | ---: | ---: |
| two_node_8 | 3/3 | 0.735300 / 0.839300 | 65 / 66 |
| two_node_128 | 3/3 | 0.569500 / 0.630167 | 65 / 66 |
| line_3_8 | 3/3 | 1.315233 / 1.419233 | 127 / 123 |
| high_rate_500 | 3/3 | 0.590880 / 0.655880 | 119 / 120 |
| high_rate_1000 | 3/3 | 0.590040 / 0.655040 | 119 / 120 |

This establishes the declared application comparison for five small cases,
not exact PHY/MAC/NWK trace equivalence. MATLAB's mean latency is 60.667–104 ms
shorter; OTA counts also differ. Their precise causal attribution remains a
backlog item. The comparator deliberately reports latency diagnostically.
No protocol behavior was changed to force these measurements to agree.
The 500/1000-kbps rows are separate extensions. Shared profiles remain explicit
current-send-only/current-fine-free-slot/production-pairwise16.

The owner metadata correctly says comparison had not run: these Python
comparisons were executed after receiving the ZIP. The source references were
already archived from actual runs; no new ns-3 rebuild or simulation was needed.

## Research outcomes

| Research case | Generated / delivered / dropped | Outcome |
| --- | ---: | --- |
| Two-node | 5 / 5 / 0 | One-hop delivery |
| Four-node line | 5 / 5 / 0 | Three-hop delivery |
| Hidden-node | 16 / 16 / 0 | Both sources delivered; eight DATA retransmissions |
| Six-node mesh | 15 / 15 / 0 | One-, two- and three-hop deliveries; DSCP 0/8/16 retained |
| Route recovery | 5 / 5 / 0 | Eventual delivery after administrative blackout and scheduled rediscovery |
| Leaf without transit | 5 / 0 / 5 | Five intended `transit_disabled` drops at node 2 |

All six end with zero application/physical pending, DATA/resend/DACK ownership,
NWK custody/waiting and pending controls. Queue drops/admission rejections,
DATA HOP failures and omitted traces are zero. Together with the shared cases,
the new exports contain 66 generated, 61 delivered and five intended policy
drops, with zero pending applications.

Control retries do sometimes exhaust. Hidden-node has one HOP and one terminal
NWK control failure. Mesh has eleven HOP control failures/twelve failed targets,
handled by eleven NWK residual retries with no terminal NWK control failure.
Recovery has five HOP control failures, four NWK residual retries and one
terminal NWK control failure. Drained ownership does not mean every control
exchange succeeded.

Recovery is a diagnostic stress case: receive blackout at 405–540 seconds,
scheduled rediscovery beginning at 576 seconds, first delivery at 585.940
seconds. Mean application latency is 68.9193 seconds and maximum is 135.9404
seconds. Its 60-second freshness setting causes 24 neighbor deactivations and
103 route changes, including activity outside the blackout. These results
demonstrate eventual delivery, not stable convergence or autonomous rediscovery.

## Readiness and remaining work

The portable implementation and evidence are ready for a Tranche 4 PR. This
local acceptance update does not publish, approve or merge a PR.

R2026a portable execution, six native tests, the 6000-second workload and seed
sweeps remain separate gates. These light, synthetic seed-128 experiments do
not certify saturation behavior or the historical campus dataset. Complete
native packet transport, full ACK-feedback adaptation, historical generator
equivalence and OPNET aggregates remain deferred. PHY/ECC and documented queue,
retry, security and RNG differences remain unchanged.

The next bounded work should expand the long-run/seed evidence and examine the
measured timing/control residuals before treating these layouts as performance
benchmarks. Battery, supervisory behavior, BBN routing, GUI, Simulink and
waveform-level work remain outside this baseline tranche.
