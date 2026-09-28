# Bounded review of the inline KEY_REQUEST candidate

Static review supports testing `ac.InlineKeyNwk` through
`ac.InlineKeySimulation` as an isolated diagnostic candidate. It is not a
production acceptance or a completed MATLAB execution.

The source-native boundary is specific: `CsrNetLayer::SendKeyRequest`
immediately invokes `CsrHopLayer::SendKeyRequest`. HOP allocates the no-ACK
request, cancels the older queued request for that neighbor, and calls MAC
enqueue in the same call stack. NWK then schedules its admission retry. There
is no intervening generic NWK control/data pump. The earlier confirmed
receive callback has empty queues and succeeds in placing this request into
MAC before returning from Track to Search.

The candidate changes that dispatch boundary only. It first executes the
original replacement and NWK control-capacity checks, creates the same owner,
then submits only the newly created nonreliable KEY_REQUEST through the
existing HOP callback. It uses the existing radio-options calculation and
does not directly alter MAC state, scheduling, packet construction or random
draws. It marks the owner submitted before the callback and looks up the
owner again afterward, accommodating a synchronous completion that removes
it. Reliable controls and other control types keep their prior path.

The successful branch does not call `pump`, `pumpControls`, or materialize
routing. Returning before the former KEY_REQUEST-triggered wake is deliberate:
it also avoids that wake's former opportunistic scan of other queued work.
Generic pump implementations and other wake sources are unchanged.

If immediate MAC admission fails, the candidate restores `Submitted=false`
when the owner still exists and executes the original scheduled-wake path.
That preserves the baseline fallback mechanism, but the candidate has now
made an additional immediate attempt. The fallback may process unrelated
owners through the baseline pump. **It is not established as equivalent to
native full-queue rejection, replacement, or retry behavior.** Those cases
remain outside the current empty-queue/successful-enqueue evidence. They must
not be included in an acceptance claim based solely on the proposed short
test.

The reviewer independently reversed every edit listed in
`candidate_transform.json` and recovered each baseline source byte-for-byte;
source and target hashes also matched. `InlineKeySimulation` differs only in
its class/constructor names and construction of the alternate NWK class.
The alternate class is selected only for `D_inline_key`; `C_timing` uses the
baseline network implementation with the same existing receiver timing option.

No code was edited and no network was run during this review. This review
checks candidate scope and correspondence to the confirmed native call
ordering; it does not validate MATLAB runtime behavior, later event order,
or whole-network parity.
