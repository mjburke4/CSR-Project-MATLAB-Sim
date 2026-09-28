# Control and callback timing evidence

The report is `autonomous_third/Autonomous_Control_Timing_Review_2026-09-25.md`.
The separately issued owner kit is `autonomous-control-timing-tests.zip`.
Its entire content is also included at `autonomous_third/kit/autocase`.

Included: complete returned ZIP and extracted files, the previously issued
repair kit, original native observation/trace capture and fixtures, independent
reviews, arithmetic calculations, candidate transforms, and static validation.
The new C/D cases and public-NWK preflight have not been run in MATLAB here.

From the extraction root, Python-only audit commands are:

    python3 autonomous_third/audit_return.py
    python3 autonomous_third/review/review_bit_boundary.py
    python3 autonomous_third/matlab/analyze_clock_boundary.py

The native arithmetic probe source, results and exact build command are
included. Recompiling `autonomous_third/native/run_arithmetic_checks.py`
requires restoring the pinned ns-3 engine build and CSR module recorded in
`autonomous/native_env/build.json`. Selected relevant source headers are
included for inspection, but the full repositories, libraries and compiled
probe are intentionally excluded. The script performs arithmetic checks,
not a new network simulation. The existing output CSVs can be inspected
without that build. Kit-generation scripts retain prior workspace inputs;
the final kit and exact reversible candidate transformations are included.

Historical absolute paths in provenance identify the originating environment;
they do not direct MATLAB to load those code copies. The owner ZIP README is
the run instruction. No ns-3 execution is required from the owner.

`autonomous_third/EVIDENCE_CONTENT_SHA256.json` binds every archive member
except itself. The separate package receipt identifies final archive hashes.
