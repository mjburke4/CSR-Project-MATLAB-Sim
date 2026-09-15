# Tranche 11 runner static review

Provisional static pass; no confirmed blocker in the reviewed runner. MATLAB is unavailable, so this is source review, not runtime evidence. The candidate and replay fixture were still being assembled and are explicit remaining dependencies.

All **225 accepted source files**, including **124 MATLAB files**, match the Tranche 10 accepted hashes. The new source snapshot includes the new runner, validation helpers, tests, scripts and shared replay inputs. The runner separately checks before/after source and reference inventories and exports those identities.

The four shared cases (`ab`, `ba`, `slow`, `track`) each run for eight simulated seconds. Their twelve case/node tapes each contain 128 unique contiguous ordinals with exact inclusive support 0–31 and valid draws. The swapped source tapes and slow gateway tape agree with the case definitions. The plan explicitly limits claims to real MAC/HOP with prescribed draws and controlled transport; it does not present this as RF or production NWK admission validation.

The runner writes replay observations before running focused MATLAB tests. An ordinary test assertion failure still produces test results, then a failure metadata record and `t11.zip`. Replay mismatch remains an observation and does not prevent packaging. Test identity comparison checks the full expected set and rejects duplicates. Full acceptance and numerical-parity flags stay false.

The metadata scalar struct, cell-valued string lists, struct arrays, table export, source hashing, `assertSuccess`, diary cleanup and `zip` call follow patterns present in accepted T10 runners. Short paths use `results/t11/rYYMMDD_HHMMSS_xxxx` and `t11.zip`; no long scenario names or repeated run-directory nesting are introduced.

The initial minor finding is resolved. The updated runner writes cumulative `tests.csv`, counters, `TestClassesCompleted` and metadata after each completed class. Earlier test outcomes now survive a later class discovery/load exception, with `TestsPassed` still false until the complete identity and outcome gate passes.

The fixed five test classes are `TestReplayStreams`, `TestReplayContract`, `TestContentionContract`, `TestAckServiceContract` and `TestRandomStreams`. Before handoff, bind these files and exact names, every reference those classes use, the accepted baseline snapshot and all shared replay/native inputs in the candidate. Check the final `replayContract` return-field schema and partial export behavior. Those artifacts did not yet exist and were not marked as defects.

The JSON review records exact hashes of the reviewed files. No source was edited during this review.
