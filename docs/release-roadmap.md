# Working roadmap to a useful MATLAB parity release

The target is **three remaining milestones, including Tranche 15**. This is an engineering estimate, not a promise that no further defects will be found. Repair cycles are warranted for functional failures or misleading evidence, not merely to eliminate every floating-point difference.

| Milestone | Work | Completion decision |
| --- | --- | --- |
| 15 — Transport timing under continued traffic | Pair continuous and local nanosecond transport across no-loss, first-DATA loss, first-feedback loss and relay-link blackout cases, with identical inputs and prescribed draws. Measure delivery, retries, ACK overhead, custody and admission-capacity release. | Owner MATLAB completes both policies and retained regression tests; evidence checker verifies baseline reproduction and identifies whether the timing policy improves the actual service outcomes. |
| 16 — Supported change and representative network tests | Adopt a timing change only if Tranche 15 supports it. Exercise smaller representative networks across multiple seeds, covering admission, relaying, congestion, routing and ACK behavior. | No unexplained loss or stuck custody; repeatable input/seed provenance; behaviorally important residuals measured and explained. If the experimental timing policy has no useful benefit, retain the current implementation and move on. |
| 17 — Campus and release checkpoint | Run the canonical 6,000-second campus benchmark and complete MATLAB regression, with the corresponding pinned ns-3 reference and historical OPNET aggregates where applicable. Publish the reviewed source and evidence. | A reproducible, usable MATLAB baseline with characterized delivery, latency, retry, queue and control-overhead differences. Record remaining limitations and freeze the release. |

Perfect OPNET or packet-by-packet stochastic identity is not the release goal. Large unexplained functional discrepancies remain work; small characterized numerical/stochastic differences can remain in the ledger. A regression failure can add a repair cycle before the relevant checkpoint closes.

Battery/energy, supervisory logic and BBN routing remain excluded. LoRa PHY, directional antenna/terrain models, RF sensing and LPD research are subsequent research extensions, not prerequisites for finishing this port. Existing PHY/ECC behavior remains preserved under the owner's instruction.

The reviewed Tranche 14 checkpoint is ready for repository publication separately from Tranche 15, whose new MATLAB execution remains pending. As of this preparation, remote MATLAB main still ends at merged Tranche 5; publishing the validated checkpoint therefore includes the local Tranches 6–14 history and evidence, with explicit distinctions between broad acceptance and focused diagnostics.
