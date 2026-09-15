# Tranche 6 independent review

Review date: 2026-09-10. Disposition: **ready for candidate handoff and fresh
MATLAB validation**. No unresolved code or packaging blocker was found in the
reviewed scope. This is not MATLAB acceptance or a claim of improved recovery.

The review compared the candidate with merged Tranche 5 at
`243ed8610df807e47d3b0be36d4ce2eae0527898` and inspected the pinned ns-3 source
at `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, tree
`b611b233fb369569b98f0914ece24d029ccc2f42`. The reviewer did not implement the
behavior changes, alter reference evidence, or perform GitHub writes.

## Behavioral review

- Passive reception now updates radio observations without creating a NWK
  neighbor or extending its freshness deadline. Qualified Discover and first
  NeighborCheck/routing delivery remain the network-liveness boundaries.
  Existing HOP validation and replay filtering precede those callbacks.
- Each accepted routing section refreshes freshness before reassembly finishes;
  a malformed single-section message does not. Expiry still discards the peer's
  partial reassembly and learned transit information.
- Quiet-peer expiry retains failure count, key-send ownership, admission retry
  ownership, backoff histories and callback generation. It clears admission and
  routing transactions and schedules a coalesced chirp, matching the inspected
  source transition. Explicit `failNeighbor` retains its separate behavior.
- A valid in-flight NeighborCheck completion may readmit a peer after freshness
  expiry. The obsolete discovery-Verify sequence guard still prevents freshness
  renewal. A key ACK alone does not renew NWK liveness.
- Ordinary DATA retry exhaustion remains terminal for its local HOP owner.
  This tranche does not add automatic DATA requeue or a generic route-failure
  callback. The source inspection supports retaining this shared limitation.

The new deterministic MATLAB tests exercise real HOP/NWK objects behind an
explicit fake MAC. Their nested callbacks correctly share the initialized HOP
handle. The strict timeout and scheduled expiry assertions match the existing
scheduler contract. Static review cannot establish MATLAB runtime success.

The protected PHY, HOP, MAC, BER/data and shared-scenario files, plus the
research-network and sweep definitions, have no changes against the merged
baseline. Existing regression assertions remain in place.

## Evidence and reference review

The Tranche 6 wrapper retains the Tranche 5 runner and binds the candidate's
source snapshot to its nested regression. Its outer metadata identifies the
Tranche 6 baseline. The documentation correctly explains that nested T5-format
metadata describes the retained harness executing current candidate code.
Diagnostic subsets do not replace the default acceptance gate.

The comparator checks identical scenario configurations and application
identities, retains delivered/dropped/pending transitions, and computes paired
latency only for applications delivered in both runs. Its output explicitly
leaves acceptance and cross-simulator equivalence unestablished.

Direct independent checks performed during review:

| Check | Result |
| --- | --- |
| Tranche 6 Python comparator tests after provenance hardening | 16/16 passed; synthetic files only |
| Source-contract source/header/library/fixture/artifact hashes | 55/55 matched |
| Source-contract oracle rows | 45/45 passing checks across 11 cases |
| Outage suite, case, source, library, fixture and decompressed-trace hashes | 140/140 matched |
| Outage application identities and delivery events | 45 generated; 26 uniquely delivered; zero duplicate deliveries |
| Outage delivery totals by freshness timeout | 60 s: 14/15; 180 s: 6/15; 300 s: 6/15 |
| Stop-time observation completeness | All three nodes present at 900 s in all nine cases |
| Final per-case inventory membership | Exact file sets in all nine case directories |
| Protected-source diff and whitespace check | No protected changes; clean whitespace check |

The source contract uses direct ingress and public observation/test boundaries;
it does not exercise a physical channel. The separate outage fixture uses the
actual CSR PHY/MAC/HOP/NWK implementation with matched geometry, offered
applications, discovery stimuli and blackout times. Its receive gate runs
after source MAC bookkeeping, whereas MATLAB gates before that bookkeeping.
Actual source security, behavioral MATLAB security and random draws also
differ. These boundaries are stated in the launcher, manifests and handoff.
Local no-ACK completions are not mislabeled as proven global packet loss.

Both reference fixtures were freshly compiled against matching CSR headers
and preserved, hashed ns-3 shared libraries. A full ns-3 engine rebuild was
not performed or claimed.

## Review findings and disposition

1. **Nested provenance binding — fixed.** The initial return verifier could
   accept conflicting outer and nested reference/runtime identities. It now
   binds the nested source pin and runtime/release to the wrapper and checks
   the original accepted Tranche 5 code identity. Three rejection tests cover
   these cases; all 16 comparator tests passed on independent re-execution.
2. **Reference snapshot integrity — recovered and verified.** One final
   snapshot was found truncated after its original manifest was created. The
   fixture owner replayed the same preserved executable and inputs outside the
   candidate. Both the complete snapshot and full trace reproduced the original
   manifest hashes; only the exact original snapshot bytes were restored.
   The reviewer verified those hashes, the unchanged case manifest, executable
   identity and retained corrupt bytes against `integrity_recovery.json`.
   The cause remains undetermined and is recorded as such.
3. **Uninventoried raw copies — packaging condition closed.** Six extra raw
   trace/log files were found beside the canonical compressed artifacts. They
   were quarantined outside the candidate, preserving their bytes. The reviewer
   then confirmed exact membership of every per-case inventory. Canonical
   evidence hashes continue to match the original manifests.

No further behavior or test change is required by this review before owner
validation. Fresh R2025a execution of `run_tranche6_validation` and review of
its returned evidence remain necessary. The accepted Tranche 5 MATLAB results
cannot be carried forward to these behavior changes. Improved delivery,
autonomous convergence, native R2026a operation, the optional 6000-second gate
and full protocol timing parity remain unproven for this candidate.
