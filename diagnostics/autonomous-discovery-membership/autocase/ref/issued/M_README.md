# Seed-132 discovery membership test — 0–330 seconds

The latest L run passed all 61 component checks and cleared both previous lifecycle mismatches. It matched 2,729 random requests and 487 transmission signatures before node 3 generated an extra SNMP_START for node 7. Native did not generate that control.

This kit runs one new case, **M_discovery_membership**. It removes one incorrect refresh that turns newly learned application routes into additional discovery work whenever a watchdog advances the scan.

## Run in MATLAB

1. Extract into a new short path, for example `C:\csr\autocase`. Do not overwrite an earlier kit.
2. Restart MATLAB to clear previously loaded CSR classes.
3. Set **Current Folder** to the extracted `autocase` folder containing `run_autonomous_tests.m`.
4. Run:

```matlab
report = run_autonomous_tests;
```

Return the printed **`out_auto_YYYYMMDD_HHMMSS.zip`**, including any diagnostic stop. No ns-3 command is required from you. All seven nodes start at zero; M runs until its first semantic difference or 330 seconds. L is preserved as actual history and is not rerun. No 6,000-second run is requested.

## What changes

The 116.340299163-second watchdog expires correctly in both implementations. Native advances its existing discovery entries, which are already complete. MATLAB additionally imports late routes for nodes 7, 8 and 2, then sends the extra START for node 7 through peer 5. The transmission guard stops it at 116.415 seconds.

M removes only the live-route import from scan advancement. Local discovery completion and received DONE reports continue to populate the discovery table. Routes remain available for application forwarding. Watchdog behavior, routing, L's key-update correction, K's receiver timers and strict comparison guards remain unchanged.

The correction lives in an isolated NWK copy and its simulation binding. All 99 original model files, prior candidate classes and native input fixtures remain byte-identical. The native ten-node completion-report limit remains a per-report limit; no global discovery-table cap is introduced.

## Tests and return evidence

The accepted natural A result is reused only after its exact source, returned-file hashes, runtime, configuration and three CSV-prefix gates pass. Compatible reuse is labeled `accepted_prior_run_reused`; a different runtime or configuration causes a fresh A run. A failed A gate prevents M.

All 61 existing component checks remain. Five new public checks reproduce the old extra control, verify corrected watchdog behavior, exercise transit DATA over the retained late route, and check legitimate insertion through DONE and a new local discovery completion. New checks and M remain pending MATLAB execution.

The same seven nodes, six source-offer schedules and native MAC/SYNC/PHY samples are used. Reception, contention, routing, admission and feedback remain endogenous. Time differences are recorded separately from semantic matching.

Return evidence includes protocol, PHY, admission, random-use and ordered state/timer records, plus the retained receiver-timing exports. `FILES.json` binds issued files; `candidate_transform.json` records reversible copies. `ref/history/L_discovery_lifecycle` stores the prior actual run and `DIAGNOSIS.md` explains the precise cause and limits.

No MATLAB runtime is available in the preparation environment. Earlier component passes and A–L results are actual owner returns. M does not yet establish the ±15% full-network accounting and latency target.
