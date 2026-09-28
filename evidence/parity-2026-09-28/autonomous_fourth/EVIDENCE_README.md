# Neighbor-control return review evidence

The report is `autonomous_fourth/Autonomous_Neighbor_Control_Review_2026-09-25.md`.
The separately issued owner kit is `autonomous-neighbor-check-tests.zip`;
its exact content is also included under `autonomous_fourth/kit/autocase`.

Included: the complete owner ZIP and extracted return, the previously issued
C/D kit, the new E/F kit, native observations and fixtures, independent audits,
source reviews, static validation and the native component-probe evidence.
E/F and their new MATLAB preflight are pending owner execution. C/D and the
seven KEY_REQUEST checks are actual owner-executed results.

From the extraction root, Python-only audit commands are:

    python3 autonomous_fourth/audit_return.py
    python3 autonomous_fourth/review/audit_cases.py
    python3 autonomous_fourth/matlab/audit_missing_child.py

The native public-API probe source, log and build receipt are included. It
uses actual HOP key exchange/ACK and NWK callbacks with an unattached MAC;
it does not run a network or call Simulator::Run. Recompiling requires the
pinned engine/CSR build identified in autonomous/native_env/build.json.
Selected native source headers are included for inspection. Full repositories,
libraries and compiled probes are excluded. Recorded outputs are inspectable
without a native build. Kit-generation scripts retain prior workspace inputs;
the final kit and exact reversible candidate transformations are included.

Historical absolute paths in provenance identify the originating environment;
they are not instructions to load another MATLAB code copy. Use the owner
ZIP README to run. No ns-3 command is required from the owner.

`autonomous_fourth/EVIDENCE_CONTENT_SHA256.json` binds every member except
itself. The separate package receipt identifies the final archive hashes.
