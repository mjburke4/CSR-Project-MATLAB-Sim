# Population and route-admission return evidence

The report is `autonomous_fifth/Autonomous_Population_Routing_Review_2026-09-25.md`.
The owner kit is `autonomous-population-routing-tests.zip`; its exact content
is also included under `autonomous_fifth/kit/autocase`.

Included: complete owner return and extracted files, the issued E/F kit,
the new G/H kit, native observations/fixtures, independent audits and reviews,
source transformation proofs, component evidence and static validation.
E/F and their eight component checks are actual owner MATLAB executions;
new G/H and their new component checks remain pending owner execution.

From the extraction root, Python-only audits include:

    python3 autonomous_fifth/audit_return.py
    python3 autonomous_fifth/review/audit_prefix.py
    python3 autonomous_fifth/matlab/audit_population.py
    python3 autonomous_fifth/native/analyze_population.py

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

`autonomous_fifth/EVIDENCE_CONTENT_SHA256.json` binds each member except
itself. The separate package receipt records final archive hashes.
