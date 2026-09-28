# Receiver timer arithmetic return evidence

The report is `autonomous_eighth/Autonomous_Receiver_Timer_Review_2026-09-28.md`.
The owner kit is `autonomous-receiver-timer-tests.zip`; its exact content
is also included under `autonomous_eighth/kit/autocase`.

Included: complete owner return and extracted files, the issued J kit,
the new K timer correction kit, native observations/fixtures, independent audits and reviews,
source transformation proofs, component evidence and static validation.
J and its 45 component checks are actual owner MATLAB executions;
new K and its timer component checks remain pending owner execution.

From the extraction root, Python-only audits include:

    python3 autonomous_eighth/audit_return.py
    python3 autonomous_eighth/review/audit_prefix.py
    python3 autonomous_eighth/native/audit_intervals.py
    python3 autonomous_eighth/receiver/audit_relative_timers.py

The native component probe sources/results describe their exact public-API
scope. Recompiling requires the pinned engine/CSR build recorded in
`autonomous/native_env/build.json`; selected relevant source headers are
included, while full repositories, libraries and compiled probes are excluded.
No long network simulation was run for this review. Existing results and
original capture excerpts are inspectable without rebuilding that environment.
Kit-generation scripts may refer to earlier workspace inputs; the final kit
and exact reversible transformations are included.

Historical absolute paths in provenance identify originating environments,
not instructions to load another MATLAB copy. Use the owner ZIP README.
No owner-side ns-3 command is required.

`autonomous_eighth/EVIDENCE_CONTENT_SHA256.json` binds each member except
itself. The separate package receipt records final archive hashes.
