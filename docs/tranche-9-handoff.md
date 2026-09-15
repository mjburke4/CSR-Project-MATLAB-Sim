# Tranche 9: early ACK service and admission capacity

Owner execution at `99fff038` is now accepted for the bounded portable
correction and diagnostics: 514/514 tests and 101/101 contracts passed.
See [portable acceptance](tranche-9-portable-acceptance.md) for the measured
effects and unresolved numerical differences. The text below preserves the
original candidate handoff and its pre-execution expectations.

This candidate preserves a prepared MAC reservation when cancellation empties
the DATA/control queue, matching the pinned ns-3 behavior. It also adds
deterministic subsystem contracts and passive observations of the early
contention sequence. The effect on MATLAB application outcomes is **pending
owner execution**; this is not a numerical-parity or performance acceptance.

Base: Tranche 8 acceptance `d0f3c5657f9f2dcf678f32900020caf3696bf90a`.
The accepted MATLAB execution remains `89b62e729e588f396bb919afdff522f7e9419268`.
Authoritative ns-3 main was rechecked and remains
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, tree
`b611b233fb369569b98f0914ece24d029ccc2f42`.

## Source-confirmed correction

Both MATLAB `mac.cancel` and `mac.cancelControl` previously cleared
`PreparationActive` whenever the queues became empty. The corresponding
ns-3 cancellation methods remove queued entries and preserve preparation and
the live reservation. An arriving ACK can therefore use the already prepared
opportunity. The correction removes those two resets; normal MAC state
transitions still own the reservation lifecycle.

Six controlled MAC/HOP fixtures exercise cumulative ACK replacement, holdoff,
SYNC/Track interruptions, DATA/control cancellation followed by an ACK, and
capacity/NSDP/MAC cleanup before the delayed network wake. The fresh native
reference passes **101/101 checkpoints**. A scratch-only native mutation that
restores the old MATLAB resets fails **12 checkpoints**, all in the two
cancellation cases. This demonstrates that the tests detect the specific
defect. It is not execution of either MATLAB version.

The prescribed receiver conditions and neighbor occupancy remove slot-choice
ambiguity without using the simulators' non-equivalent forced-slot controls.
These are subsystem contracts, not radio simulations. See the
[source audit](tranche-9-source-audit.md) and
[native contract evidence](../evidence/tranche-9-contract-reference/manifest.json).

## What the native early trace now explains

At contention seed 129, gateway ACK decision 52 is queued at 301.401104 s.
The gateway prepares slot 28, then receives node 3's DATA through 302.493104 s.
As its countdown approaches the final slot, it begins receiving node 2's
duplicate DATA. That reception ends at 303.845104 s and replaces decision 52
with decision 54. The next slot, 303.849 s, transmits the feedback. The original
decision never transmits. The observed delay includes two receiver-busy
intervals and a reservation countdown; it is not residence time of one
unchanged ACK.

The same native window directly observes a node-3 queued retransmission being
canceled at 303.873544 s. Preparation and counter 4 survive queue depth 1 to 0,
and the next network handoff occurs 28 ns later. This shows that cancellation
is exercised in the outlier. It does not establish how much the MATLAB
correction changes the 157-packet node-2 delivery gap, nor does it make all
random contention paths identical between simulators.

The six fresh native cases reproduce **24 accepted Tranche 8 artifact pairs
byte for byte**: application/statistics traces, admission summaries, aggregates
and feedback observations. All six observer-on/off controls pass. The service
window is **300 <= time < 320 s**. The preliminary reference output failed a
closed-file integrity check and was rejected; the whole suite was regenerated
in isolation and verified before promotion. The
[recovery record](../evidence/tranche-9-ns3-recovery.json) preserves those facts.
Only standalone executables were compiled against verified preserved engine
libraries; no full ns-3 engine rebuild or OPNET execution is claimed.

## Candidate architecture and verification

| Area | Change |
| --- | --- |
| `+csr/+mac/Layer.m` | Preserve preparation across DATA/control queue cancellation. |
| `+csr/+sim/AckServiceDiagnostics.m` | Reuse full-run T8 feedback correlation and add ordered, bounded service observations. |
| `+csr/+sim/NetworkSimulation.m` | Tap existing events/admission callbacks and observe cancellation before/after through T9-only wrappers. |
| `+csr/+analysis/exportResults.m` | Export service CSV and completeness metadata. |
| `+csr/+validation/ackServiceContract.m` | Execute and compare the 101 matched native checkpoints. |
| `+csr/+scenario/ackServiceSuite.m`, `run_tranche9_validation.m` | Six unchanged T8 inputs, portable tests, contracts and two tracing controls. |
| New T9 Python tools | Reproduce native references; verify returned evidence, service traces and measured before/after outcomes. |

PHY/ECC, BER data, HOP/NWK policy, ACK radio selection and all earlier accepted
input/evidence artifacts remain unchanged. The observer performs no scheduled
event, random draw or packet mutation. Cancellation observations read public
MAC scalar state; unavailable identities remain explicitly unavailable.

The [local checks](../evidence/tranche-9-local-checks.json) record exact Python
test results, MATLAB static analysis, protected-source hashes, input/reference
checks and independent review. MATLAB and Octave are unavailable in this
workspace. Static analysis does not establish R2025a execution. R2026a/native
adapters remain separate from this portable handoff.

## Owner gate and remaining limits

Extract `csr9.zip` into a short folder such as `C:\csr9` and run:

```matlab
report = run_tranche9_validation;
```

Return the printed `tranche9_evidence.zip`. See the
[run instructions](tranche-9-validation.md) for case names, short paths and the
estimated runtime. The return reviewer must pass source/reference integrity,
all current portable tests, 101 contract checkpoints, six complete cases,
and both tracing controls. It then measures all six cases against their
accepted T8 outcomes and pinned ns-3 references. Numerical differences are
reported without an invented pass tolerance.

The 6,000-second campus benchmark is not rerun here. Its accepted T7 residuals,
the prior outage/retry limits, unexercised relay/DACK/link states, and different
random streams remain documented. If the returned small-case evidence supports
the correction, the next milestone is the single campus benchmark with retained
regression checks. Further policy changes require another observed mismatch.
