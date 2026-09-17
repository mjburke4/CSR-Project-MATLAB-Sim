# T21 native trace diagnosis

This read-only diagnosis reuses the accepted full 6,000-second native campus traces for seeds 128, 129 and 130. No simulator was run and no CSR source was changed. These scripts require Python 3 and its standard library. From the workspace layout used for the analysis:

```bash
python3 t21-work/native/analyze_native.py --source-root csr20 --out t21-work/native
python3 t21-work/native/join_outcomes.py --source-root csr20 --out t21-work/native
python3 t21-work/native/audit_native.py --source-root csr20 --out t21-work/native
```

`--source-root` points to the accepted T20 installation. `--out` selects the analysis output directory. The first command reads about 3 GB of uncompressed trace bytes as a stream; allow several minutes. The input files are bound to accepted T20 candidate SHA-256 `ba4cedf3551a0bc1fe31385108e1f33011d1c97211bba993b6061a2de31389c1`, then their compressed and uncompressed hashes are checked. No intermediate uncompressed trace is written.

The first command emits per-seed summary JSON, 300-second flow counts, protocol-event counts, time-weighted NSDP and shared queue occupancy, gateway-route changes, HOP completion episodes, and small raw-event examples. The second joins completion identities to actual unique application delivery and independently follows HOP capacity through DACK expiry. The third checks hashes, saved application metrics, occupancy conservation and complete/pending capacity accounting.

NSDP is per original source/destination at each node. It is not a shared node-wide pool. The NWK queue and downstream HOP service are shared. `nwk_queue_wait_s` measures enqueue to HOP admission, on episodes submitted before stop. Pending waits are censored at stop and listed separately. `hop_admission_to_nsdp_release_completion_s` ends at feedback/completion and excludes delayed DACK capacity hold; use `capacity_retention_completed` from the outcome-join JSON when comparing actual occupied HOP capacity. A DACK can release NSDP while retaining HOP capacity until expiry.

The seed-128 archive is a historical reduced trace and lacks the full admission/custody events. Its application counts, first-delivery delays, and route-change observations remain useful; omitted state is unavailable rather than zero. Native duplicate deliveries are retained as delivery events and excluded from unique delivered-application totals. All event bins are [start,end); every retained trace ends strictly before 6,000 seconds.

Failed `nwk_admission` counts are repeated pump attempts, not distinct packets. Native `no_ack` HOP completions cannot be equated with end-to-end loss: a downstream receiver can retain and deliver a packet after the sender stops retrying. All joins are within a simulator/seed; application sequence counters are not matched across simulators.
