"""Arithmetic/FIFO counterfactual only; not MATLAB or a full CSR simulation."""
import hashlib
import heapq
import json
import math
from pathlib import Path


def shared_boundary(mode, insertion):
    queue = []
    next_id = 0
    state = "search"
    counter = 1
    holdoff = False
    tick_index = 0
    trace = []

    def add(time, kind):
        nonlocal next_id
        next_id += 1
        heapq.heappush(queue, (time, next_id, kind))

    add(.013, "tick")
    add(.300, "holdoff")
    if insertion == "early":
        add(.312, "track")
    else:
        add(.311, "insert_track")
    add(.399, "checkpoint")
    add(.400, "search")
    while queue:
        time, event_id, kind = heapq.heappop(queue)
        if kind == "tick":
            tick_index += 1
            next_time = (time + .013 if mode == "old_double_rearm"
                         else (tick_index + 1) * 13_000_000 / 1_000_000_000)
            add(next_time, "tick")  # Both implementations rearm first.
            if state == "search" and holdoff:
                counter -= 1
                if counter == -1:
                    return {"transmit_seconds": time,
                            "counter_during_track": frozen,
                            "boundary_events": trace}
        elif kind == "holdoff":
            holdoff = True
        elif kind == "track":
            state = "track"
        elif kind == "search":
            state = "search"
        elif kind == "insert_track":
            add(.312, "track")
        elif kind == "checkpoint":
            frozen = counter
        if .311 <= time < .313:
            trace.append({"time_seconds": time, "event_id": event_id,
                          "event": kind, "counter": counter, "state": state})
    raise AssertionError("No transmission")


if __name__ == "__main__":
    result = {
        "schema": "csr-tranche10-mac-arithmetic-counterfactual-v1",
        "scope": "Python binary-double arithmetic and stable event-heap replay of documented MAC timer operations; no MATLAB, Octave, native execution or full CSR/RF simulation.",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "boundary_cases": {}, "fifo_cases": {},
    }
    for multiplier in [15, 30, 51, 60]:
        now = multiplier * .013
        next_index = math.floor(now / .013) + 1
        old = next_index * .013
        corrected = (next_index + 1) * .013 if old <= now else old
        native = (multiplier + 1) * 13_000_000 / 1_000_000_000
        assert old == now
        assert corrected > now and abs(corrected - native) < 1e-12
        result["boundary_cases"][str(multiplier)] = {
            "now_seconds": now, "old_rts_seconds": old,
            "corrected_rts_seconds": corrected, "native_rts_seconds": native,
        }
    for insertion in ["early", "late"]:
        old = shared_boundary("old_double_rearm", insertion)
        corrected = shared_boundary("integer_nanosecond_grid", insertion)
        expected = .416 if insertion == "early" else .403
        assert abs(corrected["transmit_seconds"] - expected) < 1e-12
        assert old["counter_during_track"] == 1
        assert corrected["counter_during_track"] == (1 if insertion == "early" else 0)
        result["fifo_cases"][insertion] = {"old_double_rearm": old,
                                           "integer_nanosecond_grid": corrected}
    result["status"] = "passed"
    output = Path(__file__).with_suffix(".json")
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "output": str(output),
                      "boundary_cases": len(result["boundary_cases"]),
                      "fifo_cases": len(result["fifo_cases"])}))
