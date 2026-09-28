# Missing neighbor-control diagnosis

The actual owner run passed native import, accepted natural reuse and all seven KEY_REQUEST preflight checks. Both coupled cases C and D stopped at 12.402 seconds, after consuming 40 native random draws and checking six physical transmissions. The next node-5 transmission contains exactly the first three native children:

| Child | MATLAB C/D | Native |
|---|---:|---:|
| ACK, HOP sequence 1 | 25 bytes | 25 bytes |
| ACK, HOP sequence 3 | 25 bytes | 25 bytes |
| Discovery check, HOP sequence 3, discovery sequence 1 | 16 bytes | 16 bytes |
| Overheard check, HOP sequence 4 | absent | 16 bytes |
| Total | 66 bytes | 82 bytes |

This is a control-generation mismatch, not a MAC packing rejection or an inferred packet-size discrepancy. The actual MAC assembly retains all three available children. The missing owner was never created in either MATLAB run.

## Exact cause

At 12.314891086 seconds, node 5 receives a gateway aggregate. Its first member ACKs node 5's KEY_UPDATE. That completion permits the pending Discovery response, setting `DiscoveryCheckActive=true` and the generic MATLAB `CheckActive=true`. The next member is a recently satisfied KEY_REQUEST and produces no fresh key update. The following member is a received Overheard check. A Message response is correctly suppressed while the Discovery proof is active.

Native then evaluates neighbor admission and creates its own Overheard proof because both key directions are complete and no Overheard has yet been sent. Native's Overheard eligibility depends on `!overheardValid || now-overheardWhen >= overheardDelay`; it does not exclude an active Discovery or Message proof. MATLAB adds `~entry.CheckActive` to that predicate and to its deadline-reschedule branch. The active Discovery response therefore suppresses the otherwise eligible Overheard proof. This first occurrence is first-proof eligibility (`OverheardValid=false`), not floating-point deadline equality.

Candidate E removes only the extra exclusion from the Overheard send predicate. The original not-yet-due rescheduling branch remains unchanged to avoid adding cancellation/reinsertion and timer-order changes. Existing key, stale/active, pending-discovery, retry/backoff and completion gates remain. It retains D's nanosecond receiver callbacks and synchronous no-ACK KEY_REQUEST admission in isolated classes. The original model files are unchanged.

## Adjacent flag ownership

Source inspection also shows a second reachable suppression path. MATLAB `sendCheck` sets generic `CheckActive` for every subtype, while native `EnsureCheckMessage` sets `checkMessageActive` only when starting a Message proof. Native `SendNeighborCheck` does not set that flag for Overheard, Verify or NoPath. With no pending Discovery, both key directions completed and an outgoing Overheard proof, a later received Overheard should start a Message proof; E retains the original generic flag and can suppress it.

Candidate F retains E and narrows flag setting to Message subtype only. It leaves an existing true Message flag unchanged when another subtype is sent. All current completion/failure/reset behavior remains unchanged, including clearing the flag for any completed proof, as native also does. No new per-owner flag lifecycle is introduced. Public API checks exercise these separate branches and existing gates; this is still not a claim of complete neighbor lifecycle equivalence.

## What the previous tests established

The timing option advanced both cases beyond the original 183-versus-184 PHY bit-count stop without relaxing any bit/BER guard. D removed the earlier rounded-nanosecond MAC request-time discrepancy: its first-time-difference field is empty through this stop; C first requests node 3's MAC draw 4.691923 ms late. The later packet transmissions nevertheless coincide through the current boundary. The common next mismatch is therefore independent of the original immediate-KEY_REQUEST scheduling correction.

E and F will be run independently in one command, retaining C/D as historical actual owner results. A semantic stop in E must not suppress F. All seven nodes start from time zero, and strict per-request/packet context guards, endogenous traffic/receiver/feedback behavior and partial evidence preservation remain in force. Neither local match nor case completion establishes the 15% full-network accounting/latency target.

## Reproduction and limits

`autonomous_fourth/matlab/audit_missing_child.py` reconstructs the actual ordered children and relevant node-5 event chronology from both owner returns, checks exact equality to the first three native children, and identifies the missing fourth child. Its artifacts are `missing_child_summary.json` and `node5_control_chronology.csv`. Native source and captured log evidence independently confirm the trigger sequence.

No MATLAB runtime is available in the preparation environment. Original A and C/D results are actual owner evidence. New E/F network cases and the neighbor-condition preflight remain pending owner execution. No production-default source file is changed by this kit.

The unchanged not-yet-due retry-reschedule path can become reachable when F leaves the Message flag clear. Exact native timer identity or equal-time callback order is not established by these bounded predicate/flag changes.
