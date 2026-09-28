# MATLAB/ns-3 parity checkpoint — 28 September 2026

This checkpoint publishes the work following the September 23 diagnostic-source update. It includes the validated grouped-routing retry cleanup, the completed two-seed 6,000-second comparison, short capture/replay tooling, and the latest autonomous common-input investigation. The practical target is now **±15%**, and full-network parity remains open.

## Production correction

The only production-source change is `+csr/+hop/Layer.m`. Completing a grouped ROUTING control removes its resend owner without also cancelling the queued MAC routing retry. Other grouped controls retain their existing cancellation behavior. This is the previously confirmed cleanup mismatch, not a newly designed retry policy.

The corrected file has SHA-256 `21d4a56d782fde35d45f102c137b6c78c3bf4cdc05593d15fb9a7db8f26c2649`. It is bound to the actual MATLAB R2025a seed-131 and seed-132 6,000-second returns. All other production model files are unchanged. The source proof and exact patch are under `publication/parity-2026-09-28/`.

## Executable checkpoints

Use a fresh MATLAB session and select the indicated folder as Current Folder. Keep the repository in a short local path, such as `C:\csr-matlab`. Do not add every diagnostic folder recursively to the MATLAB path; the checkpoints intentionally contain isolated model versions.

| Folder | MATLAB command | Current status |
|---|---|---|
| `diagnostics/autonomous-discovery-membership/autocase` | `report = run_autonomous_tests;` | Latest continuation M; execution pending. Retains 61 previously passed checks and adds five membership checks. |
| `diagnostics/campus6000/csr6000` | `report = run_6000_batch;` | Both corrected 6,000-second cases completed in the existing owner return. No publication rerun is needed. |
| `diagnostics/two-case-short/two_case_next` | See its README for the short capture/replay entry points. | Preserved short-test source, fixtures, corrected model and review records. |
| `diagnostics/mac-history/macfix` | See its README and publication note. | Preserved executable MAC-history batch and runtime fixtures. Large archival native captures are omitted explicitly. |

The latest autonomous checkpoint is self-contained for its MATLAB runner. Its code and required fixtures are byte-identical to the issued M kit. Large historical CSV/JSONL observations that the runner does not use are excluded, and the publication manifest is regenerated to describe the files actually present. The original issued manifest, omitted-file identities and packaging explanation are retained in `autocase/PUBLICATION.json`, `PUBLICATION.md` and `ref/issued/M_FILES.json`. This is a packaging change, not additional MATLAB validation.

Earlier autonomous source versions and their original issued manifests are preserved under `publication/parity-2026-09-28/legacy-autonomous-sources`. The new replay classes and instrumented model copies remain isolated under their diagnostic folders. They are not promoted into the production model.

## What is validated

The latest returned autonomous case, L, ran on MATLAB R2025a `25.1.0.2943329`, PCWIN64. All **61 component checks passed**. Its first **2,729 random requests and 487 transmission contexts** match the native fixture in guarded context, unconditional order and rounded-nanosecond time, ending at **112.775012442 seconds**. Both prior lifecycle mismatches cleared. The run then stopped at **116.415 seconds** on an extra SNMP discovery request from node 3 to node 7.

M removes the source-confirmed cause: scan advancement must not add every newly learned route to discovery membership. Local discovery completion and received DONE reports remain the legitimate population boundaries. M and its five added component checks await owner MATLAB execution. All **151 MATLAB files** in the issued M kit passed static parsing; those source bytes are preserved here. No MATLAB or network simulation was run for publication.

The source-confirmed autonomous corrections include response admission ordering, MAC population publication, route admission, control wire accounting, relative receiver timer targets, requester lifecycle and discovery membership. The narrow exception for trace-only outer broadcast DISCOVER identifiers remains documented; the replay does not claim byte-for-byte packet identity or universal internal-state equality.

## Full-network limits

The completed 6,000-second seed-131/132 accounting covers **3,420,000 scheduled attempts per simulator**. Corrected MATLAB delivered **23,698** applications versus **24,055** in ns-3 (−1.48%). Raw delivered mean latency is **135.156 s versus 64.497 s** (+109.56%). Standardizing the comparable source cells to native delivered-source weights gives **96.177 s versus 64.497 s** (+49.12%); it excludes MATLAB deliveries from seed-131 sources with no native delivered population and is not a parity gate.

Only **2 of 9 defined source/seed cells** pass both delivery and delivered-mean-latency comparisons at ±15%. Three additional cells have no native deliveries, making relative errors undefined. MATLAB retains 760 known drops and 614 model-pending applications; native has 1,035 admitted applications with unresolved final fate. The different source mix and unfinished populations remain part of the comparison, not discarded observations.

Receiver-feedback analysis found the same audited custody-threshold rule and reproduced the early native feedback sequence under common inputs. Autonomous histories still differ, motivating the current startup investigation. These results do not justify claiming full-network parity from aggregate delivered counts alone.

## Publication and historical records

The base is main commit `6bfbb3ceaa39c3a7457027384a4bf6498313194e` (merged PR #11). Existing repository files and historical evidence are retained. Original handoff text and package manifests keep their historical wording; this document and the new parity-ledger rows describe current status. Large raw captures and original owner ZIPs remain identified by their recorded hashes and are not duplicated into Git.

The pinned reference remains `mjburke4/CSR-Project-NS3-part2` commit `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. The publication commit is a new identity linked to prior executions by exact file hashes. It is not itself claimed as an executed MATLAB revision. The branch is for review; no merge or auto-merge is performed.
