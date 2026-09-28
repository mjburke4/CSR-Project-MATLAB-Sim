# Existing MATLAB execution already covers the proposed MAC cases

The September 23 R2025a owner return, `out_mh_20260923_121427.zip`, contains actual node-8 and node-2 MAC replay outputs for 0–665 seconds. Its full-window comparisons passed, including the startup and 300–330-second interval now under investigation.

An independent offline recheck against the subsequently captured global 0–330-second native tape confirms:

| Check | Native reference | Existing MATLAB output | Result |
|---|---:|---:|---|
| Node 8, all TX events in 0–330 s | 98 | 98 | Exact |
| Node 8, TX events in 300–330 s | 50 | 50 | Exact |
| Node 2, all TX events in 0–330 s | 110 | 110 | Exact |
| Node 2, TX events in 300–330 s | 50 | 50 | Exact |
| Node 8 first source-8 DATA transmission | 316.719 s | 316.719 s | Exact |
| Node 8 ACK/DACK transmissions to 7 before that DATA | 34 | 34 | Exact |
| Node 2 first DATA transmission toward 4 | 301.639 s | 301.639 s | Exact |
| Node 2 frame 619 first transmission | 319.215 s | 319.215 s | Exact |
| Node 2 ACK transmissions to 8 while frame 619 waits | 5 | 5 | Exact |

Every TX comparison includes time, consumed and next slot, bytes, rate, power, preamble, duration, and ordered aggregate frame membership. The three focused checks also verify the actual prior replay applied the corresponding enqueue and reproduce the complete preceding TX sequence.

Frame identifiers are capture-local. The older capture numbers the focused frames 172, 170, and 238; the newer global capture numbers them 444, 439, and 619. The script establishes a **192-frame bijection** independently from ordered enqueues and identical frame fields, including complete packet bytes. Only identifiers and observer event-order counters require translation. This prevents treating two unrelated frames with the same integer as the same packet.

The proposed new two-node MAC replay is therefore redundant. This finding establishes conditional MAC behavior under the same recorded queue, receiver-state, cancellation, and draw inputs. It does not establish autonomous receiver duty-cycle, PHY reception, HOP feedback generation, or whole-network parity.

Run the offline recheck from the restored analysis workspace with:

```bash
python3 next_feedback/prior_acceptance/check_prior_actual_service.py
```

The script reads the recovered owner ZIP and both native fixture versions, emits `prior_actual_service_assertions.json` plus the mapped actual TX prefixes, and asserts that every check passes. No new simulation or production-source change is involved.
