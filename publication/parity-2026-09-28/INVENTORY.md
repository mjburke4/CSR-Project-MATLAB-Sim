# September 28 publication inventory

Baseline repository main: `6bfbb3ceaa39c3a7457027384a4bf6498313194e` (merged PR 11). This review inspected local work and prepared staging copies; it did not edit, commit, push or open a PR in the repository.

## Canonical source checkpoints

| Local checkpoint | Role | Actual validation |
|---|---|---|
| `next_feedback/mac_kit/macfix` | Corrected historical conditional MAC wrapper and fixed native-input replay | Actual R2025a history return accepted; later audit verifies the node-2/node-8 0–330 prefix. Supplied receiver history is not autonomous parity. |
| `next_feedback/short_kit/two_case_next` | Seed-131/source-5 bounded common-input short tests | Actual returned reconstruction/capacity/MAC results retained. Receiver rule gates remained explicitly open despite matching outcomes. |
| `return6000/kit/csr6000` | Corrected uninstrumented model and 6,000-second accounting runner | Both seeds 131/132 completed in R2025a; 26,526 accounting checks passed. Only 2/9 defined cells pass both ±15% metrics. |
| `autonomous_tenth/kit/autocase` | Latest isolated M autonomous diagnostic, containing all prior candidate/helper classes | Latest actual L passes 61 components and a 3,216-event strict prefix. M plus five new checks is pending MATLAB execution; static parsing/source reviews pass. |

All 99 files in historical macfix/core equal main production. The short-test and corrected 6,000-second models differ from main in exactly one file, `+csr/+hop/Layer.m`. `production_hop_proof.json` binds the actual 6,000-second source provenance and exact SHA; `grouped_routing_cleanup.diff` shows the sole behavioral change: an exact ACK completes ROUTING HOP ownership without cancelling the remaining queued structured ROUTING frame. All other production bytes match. This correction can be published at production root independently of the still-isolated autonomous candidates.

The autonomous `model/` is a validation copy of the corrected model, with observer/RNG/export seams described by `source_transform.json`. “99 unchanged model files” refers to continuity across autonomous kits. It does not mean the validation copy can replace production `+csr`. Its later behavioral corrections live in explicit `+ac` copies. No automatic production promotion of those copies is supported by this snapshot.

## Staged publication

- `stage/macfix`: 226 original selected files, 12.30 MB, including every runtime-bound file and all source. About 97.65 MB of large native trace/log files are omitted with hashes. The original full-package manifest is preserved, and current `PACKAGE_FILES.json` is regenerated. Offline package generation and verification pass; RUN_FILES remains byte-identical.
- `stage/two_case_next`: all 303 source/input/reference files, 30.69 MB; no compiled native binaries.
- `stage/csr6000`: all 126 source/input/reference files, 8.26 MB.
- `stage/autocase`: separately prepared by the kit builder; latest M source and all runtime dependencies retained, with a new publication manifest and original issued manifest preserved. Heavy historical captures are omitted explicitly.
- `stage/legacy_autonomous_sources`: all ten issued manifests plus the ten earlier MATLAB source versions not present in latest M. These are nine old runners and the initial Streams import implementation, totaling 190,610 source bytes. Keep this directory outside the active hash-bound MATLAB kit to prevent name collisions.
- `stage/evidence`: 786 copied analysis/report/provenance/table files, 34.29 MB before publication metadata. Original relative paths are preserved. Full raw returns, native build trees and repeated kit copies are excluded; README and manifest identify restoration requirements and six omitted large derived tables.

The ten autonomous kits contain 1,276 repeated MATLAB file copies but only 161 unique contents totaling 2.52 MB. Latest M contains 151 of those contents; the separate ten-file legacy supplement preserves every earlier MATLAB source generation. Copying all historical kits would instead duplicate hundreds of megabytes of accumulated captures. Original manifests and return SHA identities preserve their lineage without asserting that compact snapshots contain every original file.

The abandoned feedback replay under `next_feedback/kit/fbtest` is marked `DO_NOT_RUN` and superseded by reuse of existing accepted MAC evidence. It is not a canonical executable checkpoint and is intentionally excluded from active publication.

## Validation boundary

Latest actual L matched 2,729 random requests and 487 successful TX contexts in unconditional global order and rounded-nanosecond time, ending at 112.775012442 seconds. At 116.340299163 it generated an extra discovery handoff, then stopped before emitting the rejected TX at 116.415. Its two final MAC requests consumed per-source native 300-second samples early; they are not part of the strict prefix. Applications begin at 300 seconds, so this is not a current traffic or 6,000-second parity result.

M removes the unintended current-route merge during scan advancement; local completion and received DONE population remain. Its five new public checks and network case are unexecuted. All new publication actions were copying, hashing, metadata generation and offline package verification. No new MATLAB/ns-3 simulation ran.

`source_vs_main.csv`, `autonomous_stage_inventory.json`, `legacy_unique_source_versions.json`, `staging_receipt.json` and `production_hop_proof.json` contain the machine-readable inventory. `macfix-package-check.zip` is a temporary packaging verification output, not a repository deliverable.
