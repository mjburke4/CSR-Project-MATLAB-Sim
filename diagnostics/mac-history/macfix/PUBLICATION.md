# Published historical MAC recheck

This folder preserves the executed September 23 MAC-history recheck source and every file in its original 160-entry `RUN_FILES.json`. All 99 bundled core files remain unchanged. This historical core intentionally predates the later grouped-routing cleanup; it must remain fixed for its accepted conditional replay.

The original README describes the status when this kit was issued. The actual R2025a return subsequently passed the repaired history replay. The September 25 review also verified the existing node-2/node-8 prefix, including node 8's 34 feedback transmissions before its first DATA. This is conditional MAC evidence with supplied receiver history, not autonomous network parity.

`run_mac_history_recheck` remains the historical entry point. It is not the current recommended autonomous investigation. Current work is the isolated M discovery-membership test, whose new component checks and network continuation are pending MATLAB execution.

This repository snapshot omits large native raw capture/replay traces and logs. It retains every MATLAB runtime input and all native preparation source. Their source identities and omitted-file hashes are recorded in `publication_source_manifest.json`. The original full-package manifest is preserved as `issued_provenance/original_PACKAGE_FILES.json`; the current `PACKAGE_FILES.json` binds the actual published tree. `RUN_FILES.json` is unchanged. Both `python verify_bundle.py` and `python package_bundle.py --output /path/to/macfix.zip` operate on this published tree.

No new simulation was performed during publication. Regenerating the native reference requires the pinned external native source/build and creates a separate evidence run.
