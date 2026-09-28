# Source-5 returned replay audit

The returned MATLAB R2026a run independently matches the supplied native tapes at both tested boundaries. It does not establish autonomous network parity.

| Check | Verified result |
|---|---|
| Node-5 MAC TX, 0–330 s | 135/135 rows textually identical to native, including timing, slots, wire length, preamble, duration and frame IDs |
| Node-5 MAC TX, 300–330 s | 35/35 exact; remaining 100 TX are the startup history |
| Raw slot draws, 0–330 s | 153/153 exact timing, node, ordinal, support and value; zero unused |
| Raw slot draws, 300–330 s | 39/39 exact |
| Production-HOP first-16 admissions | 16/16 exact integer-nanosecond time, application identity and capacity snapshots |
| Supplied HOP boundaries | 52: 16 offers, 20 actual TX notifications and 16 ACK completions |
| Resulting HOP state | Four retransmissions, 16 acknowledgments, zero pending |

First-16 offer→admission waiting is reproduced exactly: **mean 9.977604171 s, median 11.001111114 s, maximum 17.761111114 s**. This supports the admission/capacity response under native service and feedback timing; it does not establish that MATLAB autonomously produces those upstream times.

The native source-5 observer records **856 repeated HOP gate evaluations**, of which 830 deny admission because of the per-neighbor capacity condition and 26 permit admission. Global capacity is available at all 856 evaluations. These are repeated probes, **not 856 unique applications**. The broader native target contains 35 local offers and two relay receptions, 26 admissions (25 local and one relay), and 20 HOP ACK completions (19 local and one relay). The first-16 fixture does not cover the full workload or production NWK state.

The MAC replay supplies receiver state, queue changes and ordered draws. The HOP replay supplies physical-transmission and ACK times and uses a test-owned FIFO. Those boundaries therefore remain conditional. No additional HOP admission or MAC scheduling fix is supported by these passes. The next causal check is the upstream ACK generation/reception and feedback-release sequence; production NWK with the full mixed workload can follow if a mismatch remains.

The returned `target_comparison.json` has an inherited “657–665 seconds” text label. Inspection of the profile and comparison selectors confirms the tested target was **300–330 seconds**. The root agent corrected the runner label dynamically and updated its binding for future runs; original returned results remain intact.

Source paths:

- Returned MAC: `/workspace/scratch/db3d3caa011d/short_results/20260923_174417/replays/source5_mac/replayed/node5/`
- Native MAC references: `/workspace/scratch/db3d3caa011d/two_case_next/native/seed132/reference/`
- Returned HOP: `/workspace/scratch/db3d3caa011d/short_results/20260923_174417/replays/source5_capacity/`
- HOP fixtures: `/workspace/scratch/db3d3caa011d/two_case_next/source5_replay/fixtures/`
- Native gate observer: `/workspace/scratch/db3d3caa011d/two_case_next/native/seed132/capture/source5_native.tsv`
- MAC comparison implementation: `/workspace/scratch/db3d3caa011d/two_case_next/source5_replay/mac_adapter/matlab/run_mac_history.m`
- HOP comparison implementation: `/workspace/scratch/db3d3caa011d/two_case_next/source5_replay/run_source5_capacity_replay.m`
