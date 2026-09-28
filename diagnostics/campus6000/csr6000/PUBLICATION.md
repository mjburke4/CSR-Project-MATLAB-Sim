# Published corrected 6,000-second checkpoint

All 126 original files are preserved, including the 99-file model, both native reference ledgers, the runner and its original manifests. The model differs from September 23 repository main only in the validated grouped-routing retry cleanup in `+csr/+hop/Layer.m`.

This exact model ran seeds 131 and 132 to 6,000 seconds under MATLAB R2025a. Independent verification bound all 99 model artifacts and both returned cases; 26,526 accounting checks passed. Numerical consistency is not network acceptance: at the ±15% target, both delivered count and delivered-only latency passed only 2 of 9 defined seed/source cells; three additional cells had zero native deliveries and undefined relative errors.

The original runner remains `report = run_6000_batch;`. This publication does not commission another long run. The active diagnostic continuation is the separate autonomous M candidate, which has not yet run in MATLAB. Its receiver, routing and lifecycle changes are not silently promoted into this historical model.

`publication_source_manifest.json` records source identities. Full raw-trace auditing additionally needs the separately preserved `out_6000_20260924_152302.zip`, SHA-256 `a3f7fd6fc09a5b0505c6a759a5c025390151bef484e7e15c9818e51a3f4f1484`. Publication ran no new simulation.
