# Discovery lifecycle return evidence

The report is `autonomous_ninth/Autonomous_Discovery_Lifecycle_Review_2026-09-28.md`.
The owner kit is `autonomous-discovery-lifecycle-tests.zip`; its exact content
is also included under `autonomous_ninth/kit/autocase`.

Included: complete owner return and extracted files, the issued K kit,
the new L lifecycle correction kit, native observations/fixtures, independent audits and reviews,
source transformation proofs, component evidence and static validation.
K and its 53 component checks are actual owner MATLAB executions;
new L and its lifecycle component checks remain pending owner execution.

From the extraction root, Python-only audits include:

    python3 autonomous_ninth/audit_return.py
    python3 autonomous_ninth/review/audit_prefix.py
    python3 autonomous_ninth/receiver/audit_key_update_order.py

Native source and existing capture audits describe their exact scope.
Rebuilding the native simulator requires the pinned engine/CSR build recorded in
`autonomous/native_env/build.json`; selected relevant source headers are
included, while full repositories, libraries and compiled probes are excluded.
No new native simulation was run for this review. Existing results and
original capture excerpts are inspectable without rebuilding that environment.
Kit-generation scripts may refer to earlier workspace inputs; the final kit
and exact reversible transformations are included.

Historical absolute paths in provenance identify originating environments,
not instructions to load another MATLAB copy. Use the owner ZIP README.
No owner-side ns-3 command is required.

`autonomous_ninth/EVIDENCE_CONTENT_SHA256.json` binds each member except
itself. The separate package receipt records final archive hashes.
