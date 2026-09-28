# MAC history repair readiness

This is a validation-harness repair, not a production protocol change. `replayCancelWindow` now uses indexed scalar iteration, including a correct zero-match no-op. The adapter generator, generated adapter, diff and provenance remain consistent. The new runner first executes cancellation-boundary regression, then history only; previously accepted slot/HOP groups are not repeated.

All accepted production core files, common-input tapes and native reference bytes must match the original issued kit. Native fidelity receipts remain the original executed proof. Full package and runtime hashes are refreshed for this explicitly identified repaired package, preserving the parent identities in repair_provenance.json. Neither oracle values nor tolerances are changed.

MATLAB execution of the repair is pending. Use run_mac_history_recheck from the extracted macfix folder and return out_mh_*.zip.
