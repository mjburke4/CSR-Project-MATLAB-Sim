# Peer review: native CSV import repair and reuse of accepted case A

The returned case A is accepted evidence: 12,200 protocol rows, 12,198 PHY rows and 9,000 application-admission rows exactly match the original seed-132 prefix. Case B stopped at its first MAC request at 10.01 seconds because MATLAB could not convert a missing string to a character vector. The blank `component` cell is valid for a MAC draw. This exception is a harness import failure, not an observed network behavior difference.

## Import repair

The new `ac.Fixture` importer explicitly types text columns and normalizes missing text to empty strings before `Streams.take` or `TxSignature` converts them to character vectors. Numeric columns remain numeric, with missing required values rejected rather than replaced with zeros.

Required fields are checked within their proper scope: MAC bounds/state/population, SYNC mean/variance/TX identity, PHY interval/component/bits/probability, and relevant packet-kind/subtype fields. In particular, PHY components must be `header` or `payload`; an absent component is accepted only for MAC/SYNC rows. Empty discovery peer sets, grouped-target lists where not applicable, and SNMP node lists remain valid empty lists. NeighborCheck fields are required according to the existing `discovery` and `no_path` subtypes.

The full fixture inventory confirms the repaired type declarations cover all 4,430 random rows and 1,495 transmitted-child rows. No field designated numeric contains an unexpected nonnumeric nonblank value. The exact natural-prefix CSV comparison is unchanged; missing-value normalization is confined to the native fixture importer.

The new MATLAB import preflight exercises the original failing request, expecting node 1's first MAC value of 11 at 10.01 seconds. It also tests rejection of an empty required PHY component, empty MAC state, missing SYNC mean and empty routing section. It advances a separate empty scheduler and schedules or executes no network callbacks. This preflight still requires MATLAB execution; static review does not establish that the repaired common-input run has passed.

## Accepted-A reuse

The runner reuses the packaged accepted A only after checking its evidence hashes, unchanged natural source hashes, approved current provider hash, exact MATLAB version/release/computer triple, and configuration equality. The live configuration is JSON-roundtripped before comparison with the returned JSON. Only `SharedScenario.SourcePath` is canonicalized, because extracting the same kit into a different folder changes this metadata path. The input CSV remains hash-bound; its source digest and every behavioral configuration field still participate in equality. Source inspection found `SourcePath` is populated by the importer and is not read by the simulator. Both actual paths are recorded in the reuse receipt. The runner verifies the prior acceptance status and recomputes the same three exact prefix comparisons from the packaged returned tables.

Reuse is explicitly labeled `accepted_prior_run_reused`, with no new natural simulation claimed. A runtime or configuration difference triggers a fresh case A. The common-input case remains gated by an accepted natural prefix in either path.

Independent source review confirms that all 99 model artifacts still match both the original issued kit and the owner's returned provenance. Natural-mode helper files are unchanged. The only changes within `Streams.m` are in the native-only constructor import branch and native-only request matching method. Consequently, reusing A rests on actual prior MATLAB acceptance plus unchanged natural execution code; it does not assert new MATLAB execution of the repaired helper.

## Result and limits

No blocking issue was found in the bounded import repair or the reuse gate. The native reference, source schedules, MAC/NWK/HOP/PHY model code, and network acceptance target are unchanged. Repaired case B still needs its owner runtime result; no new protocol correction or ±15% parity result follows from this harness repair.

Supporting checks are in `repair_boundary_review.json`, `model_unchanged_review.json`, `typed_csv_schema_review.json`, and `native_csv_missing_inventory.json`. `check_repair_boundary.py` reproduces the static source/evidence boundary check. The boundary check was rerun against the builder's frozen repair, including the final configuration comparison; its receipt binds the reviewed helper, runner and reuse-proof hashes. MATLAB syntax checking and archive validation are separate packaging checks.
