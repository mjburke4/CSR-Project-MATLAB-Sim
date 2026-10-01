# MATLAB/ns-3 parity checkpoint — 30 September 2026

This PR preserves the work since merged PR #12 (`8c976d0`): the completed terminal-copy 6,000-second measurement, the seed-132 common-input replay and its confirmed relay-copy mismatch, and the current repair with focused custody tests. The engineering target is **±20% per-source delivered count and delivered mean latency**. Full-network parity remains open.

## Current runnable work

Keep the checkout at a short path, such as `C:\csr-matlab`. Restart MATLAB R2025a and select the indicated folder as Current Folder. These checkpoints contain isolated source versions; do not recursively add all diagnostic folders to the MATLAB path.

| Folder | Command | Status |
|---|---|---|
| `diagnostics/relay-custody/node8case` | `report = run_node8_tests;` | Current repair, revision 2. Runs component checks and the same seed-132 0–1,200-second replay. Latest MATLAB return is pending. |
| `diagnostics/terminal-campus6000/csr6000` | `report = run_6000_batch;` | Exact earlier candidate used for the completed seed-131/132 6,000-second runs. Preserved for reproduction; an unchanged rerun is not the next investigation. |

Both folders contain their complete issued file populations and original manifests. No runtime fixtures are stripped and no runner gate is weakened for publication. `TestQueuedRetryPolicy.m` is included in the current replay folder. The prior 330-second natural reference is historical evidence only; it is not current-model acceptance. The current replay uses native random inputs while MATLAB generates its own admission, routing, feedback and receiver states.

The repaired NWK and simulation classes are included in the current snapshot's `model/+csr` and `+ac` directories. Root `+csr` remains at the previous production checkpoint. This publishes the complete candidate for review without promoting the pending replay into the established root model.

## Confirmed mismatch and repair

The previous seed-132 run stopped at **895.115 seconds** on a transmission-content mismatch. Its cause occurred at **694.821813632 seconds**: node 4 received a DACK-marked retry of source 7, attempt 2873. Native ns-3 queued a second relay occurrence and advanced NSDP from 26 to 27. MATLAB suppressed it by application identity. The missing copy later changed FIFO admission at **894.464292500 seconds**.

The repair assigns each accepted copy a fresh receiver-local custody identifier. Enqueue, submission and release use that occurrence; a stale completion cannot remove a sibling. Original application identity is retained for unique final delivery, byte counts and latency. Unique provisional loss requires no registered NWK copies at any node; a later accepted copy can recover that status. Unregistered queued MAC copies may still survive, so provisional drops are not asserted to be final losses.

The focused suite contains 22 groups across the production and replay classes: DACK retries, NSDP 25→26→27, FIFO 7/7/8, distinct outgoing sequences, ACK/DACK/failure/no-ACK release, stale and foreign tokens, queue refusal/retry, nested callbacks, and final-delivery uniqueness. Integrated accounting also tests surviving copies at other nodes, last-copy failure and same-hop recovery.

## Actual validation and pending execution

All owner execution cited here used MATLAB R2025a **25.1.0.2943329, PCWIN64**.

- Before the repair, the 895.115-second replay passed all 17 existing preflight groups. All 34,260 observed random requests matched the compared contexts, values, order and integer-nanosecond times. The first 6,007 physical TX contexts matched; the next request triggered the stop. All 6,008 recorded TX requests matched source/order/time, including that rejected request. The existing exclusion of reported population remains explicit.
- Before that stop, both models admitted 1,582 and uniquely delivered 1,229 applications, leaving 353 unresolved. First-delivery identities and nanosecond times matched. This is a bounded prefix result, not full-network parity.
- The first relay-repair return passed **17/17 existing groups**, including **4/4 integrated accounting cases**, and **20/22 focused custody groups**. Both failures were the queue-full fixture: a constructor argument-count error replaced its requested queue limit of 1 with 512. The network did not start.
- Revision 2 corrects only the test-helper argument defaults and adds an effective-configuration assertion, with README/manifest updates. Its network-model code is identical to the returned relay candidate. Static source/package checks and independent review passed. The corrected MATLAB rerun remains pending.

The accepted-copy repair is therefore supported by the successful component boundaries, but has not yet cleared the 895.115-second network divergence. The 1,200-second replay remains subject to its strict context, time, population and omission checks. The ±20% engineering target does not relax those checks. No new MATLAB or ns-3 simulation was run for this publication, and no new native capture is required for the pending replay.

## Full 6,000-second status, before this relay repair

Across seeds 131 and 132, each simulator offered **3,420,000 applications**. MATLAB admitted 24,998 and uniquely delivered 23,720; ns-3 admitted 25,090 and uniquely delivered 24,055. MATLAB left 1,278 unresolved (769 raw provisional drops and 509 raw pending); ns-3 left 1,035 unresolved.

Delivered mean latency was **130.909 s versus 64.497 s** (+102.97%). Standardizing comparable source cells to native delivered-source weights gives **90.748 s versus 64.497 s**, a **+40.70%** gap. The source-weighted figure excludes cells with no native delivered population and does not remove their traffic from the accounting.

At the current ±20% threshold, **5 of 9 defined source/seed cells pass both metrics**. Three additional cells have zero native deliveries, so relative errors remain undefined. The historical full-run kit retains its issued ±15% report; `evidence/parity-2026-09-30/terminal6000_return/accounting/source_targets_20.csv` transparently regrades the same population at ±20%. No new measurement is implied. These results predate the relay-copy repair and cannot estimate its eventual effect.

## Evidence and publication boundaries

`evidence/parity-2026-09-30/` contains compact source-bound return records, source accounting and latency-phase analysis, the node-4 causal trace, independent checks, and the relay-return/fix review. Large raw owner archives and native build trees are identified by their recorded hashes rather than duplicated. Historical forensic Python scripts still require the original raw inputs and workspace layout; their saved audit results are not a claim that every script runs from this compact checkout alone.

`publication/parity-2026-09-30/` records source origins and snapshot identities. The repository's root `PACKAGE.json`, `evidence/source-baseline.json`, older checkpoint guides and historical handoffs describe earlier revisions. The current checkpoint guide and snapshot `FILES.json` manifests identify this publication. Existing files and evidence are retained.

The ns-3 reference pin remains `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. This is a publication of existing work, not a new behavior tranche. The next decision is based on the returned revision-2 replay: verify independent custody through the prior divergence, then reassess autonomous 6,000-second performance if the bounded replay passes. The PR is for review; no merge or auto-merge is performed.
