# Seed 132 discovery scan membership: native audit

The extra node 3 SNMP request is caused by adding newly learned routes to the scan table during advancement. Native ns-3 advances only entries registered by discovery lifecycle inputs. MATLAB L additionally merges its current reachable routes every time `advanceScan` runs.

| Time (s) | Native and returned L evidence |
|---|---|
|25.385728077|Node 3 receives START from 1; native registers 1 complete.|
|40.385728077|Local discovery completion snapshots `[5,1]`; native adds 5 and hands off to 5.|
|56.340299163|DONE from 5 advertises `[4,3,1]`; native adds 4 and hands off to 4.|
|65.832808077–96.268879163|Node 3 learns routes to 2, 8 and 7. No native discovery-table registration follows.|
|116.340299163|The target 4 watchdog fires. Native has no remaining needed entry. L re-reads routes and requests newest destination 7.|
|116.415|L tries to transmit the extra START for 7 via 5; strict TX signature gate stops.|

Native node 3's next physical transmission with ordinal 86 is DATA at 300.365 s. The earlier reported MAC ordinal 102 difference, 116.350 versus 300.001 s, is the extra traffic consuming a future ordinal. It is not evidence of a 183.651-second watchdog delay error. The corresponding watchdog fires at the same nanosecond in both traces.

The full accepted 0–330 s capture contains 34 discovery-table insertions, 28 handoffs and 17 watchdog callbacks. Every insertion coincides with an allowed registration boundary; every handoff selects the first already registered needed entry. Node 3's complete registered order remains `[1,5,4]`; destination 7 is never registered in this native capture. The table state is reconstructed from logged operations and source-defined idle START marking, not sampled private state.

The source caller inventory is complete: `EnsureDiscoveryEntry` is called by idle START marking, received DONE and local lifecycle completion. `NoteDestinationCreated` updates a separate newest-first routing destination list and does not register scans. `CollectKnownDiscoveryNodes` snapshots at most 10 reachable destinations; only local completion consumes that snapshot to populate the table. Its other caller is a read-only public getter. The 10-node limit applies per completion snapshot, not to the total table.

The isolated M candidate removes one executable line: the eager reachable-route merge inside `advanceScan`. Completion and DONE merges, idle START marking, ordering, mark-before-send behavior, watchdog generation/deadlines and L's reliable KEY_UPDATE fix are preserved. The simulation changes only its class identity and NWK binding. All 26 reversible transforms and 99 unchanged model files are checked by `review_candidate.py`; the final runner and manifest hashes are bound in `candidate_scope_review.json`.

All 7 delivered native DONE reports match the pending target. Broader DONE interruption policy and requester-capacity differences remain unexercised and are outside this correction. No native network or component simulation was rerun, and MATLAB M has not been executed here. This evidence establishes the cause of the extra control traffic; it does not establish global callback-order or 15% network-performance parity.

Reproduce the read-only audit from the shared workspace with:

```sh
python autonomous_tenth/native/audit_membership.py
python autonomous_tenth/native/review_candidate.py
python autonomous_tenth/native/finalize_receipt.py
```

The audit requires the accepted native fixture/log and the L owner return identified by hashes in `evidence_receipt.json`; no native binary is needed. `source_path_proof.json` preserves the relevant native code and complete caller inventory for review without the native checkout.
