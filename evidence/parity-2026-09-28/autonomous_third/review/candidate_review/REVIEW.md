# Review of the bounded C/D candidate kit

No blocking issue was found in the candidate's source boundary, ownership handling or case driver. The frozen kit preserves all 99 original model artifacts and all four packaged native-reference files byte for byte. This is a diagnostic candidate; its MATLAB preflight and both network cases still require the owner's runtime result.

## Candidate scope and receive-state correspondence

`ac.InlineKeyNwk` is an exact copy of the original NWK layer with class/constructor renaming and one 18-line insertion in `queueControl`. The insertion acts only on the newly appended, unacknowledged `KEY_REQUEST` when ordinary scheduling is enabled. Existing replacement, cancellation, capacity rejection, control-ID assignment, wire-byte construction and owner creation run first. The candidate does not call the general control/application pump or alter routing, retries, MAC scheduling or PHY code.

The insertion addresses the captured ordering mismatch at its origin: a received DISCOVER invokes NWK while the receiver remains in Track. Inline admission places its KEY_REQUEST into the existing HOP/MAC path before the unchanged Track-to-Search callback. The original MAC already starts preparation on that transition when a packet is pending. This preserves the MAC rule that native's captured receive-completion path also follows, instead of introducing a generic enqueue-preparation rule.

`ac.InlineKeySimulation` changes only its class/constructor names and the NWK constructor selected for each node. Inverse transformation checks recover both original source files exactly.

## Ownership, capacity and callbacks

The new owner is marked submitted before `SendControl` can reenter NWK. The callback uses the same radio-options helper and `AckRequired=false`. After callback return, the candidate finds the owner again by control ID, so synchronous completion cannot cause stale-index access or resurrect a removed owner. A rejected send resets submission only if that same owner remains and falls through to the original wake/retry path. A successful send avoids scheduling a new general pump; already-scheduled work is unaffected.

The reviewer supplied seven bounded checks through public NWK APIs: original deferral, immediate candidate submission, no flushing of unrelated control/application owners, submitted-owner cancellation and replacement at capacity one, capacity rejection before submission, rejected-send fallback with the same owner, and synchronous completion without resurrection. These checks use isolated callback probes and no private hooks, PHY/MAC model, random variates or network simulation. They are included in the owner preflight, but static review is not a claim that MATLAB executed or passed them.

## Case isolation and accepted evidence

Case C uses the original simulation and the existing nanosecond receiver-callback option. Case D uses that same option plus the isolated NWK candidate. Each gets fresh simulation/provider objects. The driver invokes D after C returns, including a semantic diagnostic stop in C; it does not require C to reach 330 seconds.

The accepted-A reuse function and natural provider/helper files remain unchanged. A runs through the original simulator, with the original configuration and source-hash gates. Neither candidate class is substituted into A. Both C and D retain the existing exact semantic draw/bit/transmission guards and report their own callback timing, partial traces and stop reason.

`check_candidate_boundary.py` reproduces the static boundary review; `candidate_boundary_review.json` binds the reviewed sources and helper hashes. The final MATLAB syntax/archive checks are separate packaging checks. Neither preparation-state parity, continuation beyond the previous bit mismatch nor ±15% network parity has yet been demonstrated by this kit.
