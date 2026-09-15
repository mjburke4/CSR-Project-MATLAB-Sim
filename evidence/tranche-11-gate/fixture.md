# Independent Tranche 11 fixture review

**Passed for MATLAB handoff. No open implementation blockers remain. MATLAB execution and cross-simulator matching are still pending.**

The final native reference contains 1,756 semantic events and 133 raw contention draws across four 8-second cases. Independently checked event identities confirm all 32 declared applications delivered and all 32 corresponding HOP capacity releases completed. Each release callback sees capacity cleared before resend removal. All final pending counts are zero. The native Track case contains the two prescribed receiver transitions and no gateway transmission during that interval.

All 255 ACK/receiver checkpoints are byte-identical between clean native headers and the overlay with hooks disabled. The closed reference artifact manifest was rehashed. All 225 accepted Tranche 10 source entries, including 124 MATLAB files, remain byte-identical.

The implementation preserves raw integer selection before the existing occupancy probe, source-computed airtime, actual MAC queue/sent boundaries, real HOP feedback generation, and actual capacity release plus delayed queue wake. MATLAB uses validation-only stream method dispatch, and its aggregate ingress callback now matches native ordering and one MAC update per recipient. Neither implementation prewarms the gateway slot timer.

Three review findings were resolved: native usage schema now includes supplied count; native reported-active initial state is explicitly three; MATLAB aggregate transport callbacks now use the native grouping. Exact hashes of reviewed files and detailed checks are in final-review.json.

Both comparisons retain full ordered trajectories and unmatched suffixes; a shifted or extra event cannot pass as a common prefix. The finite application driver exercises real HOP admission. It does not exercise production NWK admission or real RF loss, collision, half-duplex rejection, or adaptive radio selection. Fixed radio and successful addressed delivery are declared fixture inputs.

The Track interval affects preparation and reservation probing, but ends before the ordinary first ACK transmission; it should not be described as proving ACK-ready holdover under an already-expired holdoff. No additional scenario is needed for this bounded handoff.
