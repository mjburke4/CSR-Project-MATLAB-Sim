# September 24–28 analysis checkpoint

This snapshot preserves analysis source, reports, validation receipts and selected derived tables under their original workspace-relative paths. It includes the corrected 6,000-second review, the source-132 receiver/feedback investigation and autonomous A–L return analyses, together with the preparation/review of pending M.

Start with:

- `return6000/review/accounting/REVIEW.md` for current seeds 131/132 accounting and the open ±15% result.
- `next_feedback/deliverables/Seed132_Feedback_Investigation_2026-09-25.md` for receiver decisions, custody pressure and reuse of the already accepted conditional MAC test.
- `autonomous_tenth/Autonomous_Discovery_Membership_Review_2026-09-28.md` and `autonomous_tenth/review/l_audit.json` for the latest actual L return and pending M correction.

L passed 61 component checks and matched the first 2,729 random requests plus 487 physical transmissions in unconditional order and rounded-nanosecond time. Its strict event prefix ends at 112.775012442 seconds; an extra discovery handoff then leads to a guard stop at 116.415 seconds. M and its five additional checks have only source review and static syntax validation. Neither is a 330-second or 6,000-second network acceptance result.

`PUBLICATION_FILES.json` binds copied source/results and lists large derived tables omitted from this compact snapshot. Original ZIPs, full owner ordered/protocol/PHY traces, native engine/build trees and repeated kit histories are not duplicated. Original issued manifests remain historical provenance; they describe their full original archives, not this selected publication tree.

**Reproduction requires the documented inputs.** The analysis scripts retain their original paths and are not silently rewritten to run against different data. Restore original archives at the locations named by each script, report and input manifest before executing a full audit. In particular, current autonomous prefix audits need that return's complete `data/ordered_events.jsonl`/`random_requests.jsonl` and the original issued kit path; native state reconstructions also require the omitted receiver history or full captured observations. Model preparation scripts need the pinned external native checkout/build. Hashes and original archive identities are retained in the per-investigation manifests.

Runnable standalone MATLAB snapshots are published separately under `diagnostics`; this evidence directory does not replace those bundles or install a model. Historical code versions live outside the active autonomous MATLAB binding root to avoid function-name collisions. No new MATLAB/ns-3 simulation ran during publication.
