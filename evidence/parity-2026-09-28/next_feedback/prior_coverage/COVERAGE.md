# Previous short-test coverage relevant to node 2 → node 8 feedback

**The proposed node-2/node-8 MAC replay is already covered by the accepted September 23 owner run. Do not issue another MATLAB test.** We recovered its original issued fixture and actual returned MATLAB observations, verified all 160 runtime-bound file hashes, and matched the 0–330 s portion against the newer global tape: **4,075 input applications, 208 TXs, 241 draws and 192 complete frame records**, with no differences after explicitly mapping capture-local frame IDs. Adapter and scheduler bytes are identical; the driver's only difference is a result-label string. The current model differs only in HOP Layer, which this conditional MAC replay does not execute.

The two September 24 returns originally reviewed here contain source-5 and node-4 tests. They do not add a node-2 receiver/HOP or node-8 HOP-feedback integration test. That remaining boundary distinction must not be confused with a missing MAC scheduling test. Machine-readable reuse proof: `prior_acceptance_reuse.json`; reproduction: `compare_prior_acceptance.py`.

## Scope matrix

| Existing test | Observed coverage | Result and limit | Relevance to current investigation |
|---|---|---|---|
| September-23 accepted MAC history | Nodes 2/4/8 from natural startup through 665 s; distinct target gate 657–665 s | All 1,761 TXs and 2,018 draws matched. Independently reverified newer 0–330 node-2/8 tape against actual returned execution: 208 TXs and 241 draws match | Already includes node-8 first DATA waiting behind 34 feedback TXs to 7, and node-2 DATA waiting behind five feedback TXs to 8. No rerun needed. |
| Source-5 HOP capacity | First 16 source-5 offers; 20 actual DATA TX indications; supplied received-feedback times; production HOP with test-owned NWK FIFO | 16/16 admissions match, final 16 ACKed; no DACKs, no receiver replay or production NWK custody | Do not repeat this component test. It cannot establish node-8 DACK/ACK ownership behavior. |
| Source-5 MAC history | Seed 132, warmup 0–330 s, comparison 300–330 s; native queue, availability, receiver-state and draw inputs | 135/135 total TX schedule matches, including 35 target-window TX; exact draw comparison. MATLAB executes node 5 only | Passed conditional scheduling need not be rerun. Native staged global inputs can be reused for nodes 2/8. |
| Node-4 PHY replay | Seed 132, 300–330 s; 299 physical TX inputs; 255 receiver outcomes; 211 state transitions; 227 draws | 255 outcomes and 211 states match. Latest return has 306/306 keyed interval/effective-input matches, but 300/306 bit/error allocation matches; strict/full rule gates remain false | No node-2 DATA receiver or node-8 ACK reception replay. Its 10 ACK-child outcomes are inferred from aggregate PHY decisions, not separate MATLAB child callbacks. |
| Source-5 HOP+NWK integration | Seed 132, 300–330 s; public initialized mature routes, recorded DATA sends/receives, 32 ACK bitmap epochs | 26 admission identities, 20 ownership/custody releases and final 17 custody identities match. Semantic pass true; strict pass false: first admission −28 ns, 104 versus 69 scans, extra gate probes. No DACKs | Establishes the supplied-bitmap integration at node 5, not feedback generation/arrival on edge 2→8. Do not call this an unqualified whole-test pass. |
| Discovery PHY reconstruction | Seed 131, 25–85 s, receivers 2/5: 22 targets; seed-132 receiver-2 positive controls: 3 targets | 22/22 bound targets with 223 captured draws; 3/3 observational seed-132 controls lack native PHY draw tape | Receiver 2 appears, but only startup traffic from node 4 before application traffic. Not node2←8 DATA coverage. |
| Discovery-controller integration | Four bounded public-controller cases through 18 s | Three match; `after_empty_done` retains the accepted T27 derived-scope difference | Unrelated to node-8 feedback queue service. No reason to repeat. |

## Recovered edge evidence already available

`out_short_20260924_083651/replays/source5_mac/staging/` contains **global native** input records despite the node-5-only replay profile:

- `inputs/inputs.csv`: 17,881 records for nodes 1, 2, 3, 4, 5, 7 and 8, time 0 through 329.901295374 s.
- `inputs/frames.csv`: 734 frame records with source/destination, HOP sequence, ACK/DACK flags and bitmaps, wire representation, packet hex.
- `reference/tx.csv`: 811 actual TX records, with frame membership, start/duration, consumed/next slot, rate, power and preamble bits.
- `inputs/draws.csv` and `reference/draws.csv`: 928 native MAC draws.
- All five included files match the hashes recorded in the capture's fidelity manifest.

On edge 8→2 there are **20 DATA frame records representing 18 HOP sequences**. On edge 2→8 there are 27 ACK frame records over the full warmup. During 300–330 s specifically there are **14 ACK enqueues, 24 physical TX records carrying those ACKs, and 24 node-8 `cancel_ack` callbacks from peer 2**, representing 13 distinct sequence/bitmap windows. **All these observed DACK bitmaps are zero.** More than one transmission of an ACK is normal capture behavior here and must not be counted as multiple ownership completions.

The edge-only extractions are `native_edge_inputs_0_330.csv`, `native_edge_frames_0_330.csv`, and `native_edge_tx_0_330.csv`. Full original staged files remain in the extracted return. Do not use an edge-only subset to replay a node: its other peers, receiver state, MAC draws and queue inputs are necessary competing context.

These files expose feedback enqueue, frame content, actual transmission, received-peer notices and ACK bitmap cancellation boundaries. They **do not expose node-2 receiver NSDP-before, first-versus-duplicate DATA reception, or node-8 HOP ownership decisions**. A generic `received` input contains peer and timing/PHY summary, not the received child's DATA identity. A `cancel_ack` callback is not itself proof of an ownership release.

## Provenance and recovery pointers

Both returns record exactly the same **96 candidate MATLAB source hashes**, and all 96 match the current 6,000-second kit's model files. Important identities:

| File | SHA-256 |
|---|---|
| `+csr/+hop/Layer.m` | `21d4a56d782fde35d45f102c137b6c78c3bf4cdc05593d15fb9a7db8f26c2649` |
| `+csr/+nwk/Layer.m` | `7ef09931c83c55697ce96b400ee1d90459a44af4c0527b396829d62ab9125300` |
| `+csr/+mac/Layer.m` | `d2e1b9e08c7e3d3ea60c88b61f3480f881e53c5963f48ae09822c4f04170e67b` |
| Short-return ZIP | `4dbc4265b3445dbf58ee4ad7f0086c9e1097a3c415ffd90bb7fe3327138aeea2` |
| Integration-return ZIP | `38a841bacf3f6095d3c5b8dbab388559de3fbf5cb2d55988b461e33109cb0882` |

Native fidelity binds source commit `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` and engine commit `6b5cd24ea80713ce16d88575869aedd6f432bdae`, with an exact 48,919-row original-trace prefix from 0–330 s. Source-capture observer SHA is `ab59b90647a72eaaa0dc2c173a14d6920635dd576719379e509aa07763e848b1`.

The manifest records these original paths/names, which are evidence-backed recovery search terms, **not a claim those archives are now available**:

- Kit directory `csr-short-tests-ready-v3/two_case_next`; native executable `two_case_next/native/seed132/source5-native-capture`.
- Native trace `two_case_next/native/seed132/capture/ns3-trace.csv`; input scenario `two_case_next/schema_review/scenario_s132.csv`.
- Kit directory `csr-integration-tests-v2/integration_next`; wrapper `run_next_tests.m`; integration source `ack_nwk_integration/run_ack_nwk_integration.m`.
- Receiver fixture manifest SHA `44e47e83d76472b93a24d8c945af7bc36dea04c568b0af001d4a201b7db26e99`; latest receiver capture manifest SHA `97a9a18949a5216c8c1d47fec94ce3820871a62ada9ade4cdfba26d526b9da06`.

The native fidelity manifest lists broader 300–330 s observer streams (`relay_rx`, `hop_feedback`, `mac_service`, `mac_tx_child`, `rx_child`, and receiver PHY/draw streams), but those original observer files are **not members of either returned ZIP**. Only counts are included, so they cannot prove node-2/8 coverage until recovered and read. Also absent are the manifest-listed `tx_raw.csv`, `tx_wire_hex.csv`, and `tx_frames.csv`.

## Next use

The older MAC-history acceptance **already covers** the proposed 0–330 node-2/8 test, including both identified feedback-priority waits. Do not repeat it. Investigate which autonomous receiver/queue/feedback inputs diverge first, then trace those inputs to their upstream cause. The conditional MAC result means the captured native input history is reproduced by the current MAC implementation; it does not make the independently generated MATLAB input history equivalent.

Reproduce the September-24 inventory with `python3 next_feedback/prior_coverage/audit_coverage.py`, and the prior-acceptance reuse proof with `python3 next_feedback/prior_coverage/compare_prior_acceptance.py`. Detailed source/adapter audit: `adapter_static_review.json` and `adapter_vs_production.diff`. No simulations or production edits were performed.
