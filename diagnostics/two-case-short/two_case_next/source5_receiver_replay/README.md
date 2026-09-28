# Seed-132 node-4 ACK receiver replay (300–330 s)

The original trace contains 299 physical TXs in this window, 255 node-4
receiver outcomes, and ten node-5→4 ACK attempts (six accepted, four rejected
before PHY delivery). The immutable fixture maps every TX to exactly one
node-4 physical outcome, where the TX is not from node 4. A pre-300 signal
gap is proven from the exact prefix. The fixture is observational: the source
trace alone lacks aggregate children, receiver state, and random draws.

After running **both** native cases with `run_two_native.py`, bind the verified
seed-132 capture in the same extracted two-case package:

```sh
python3 source5_receiver_replay/bind_capture.py \
  --capture /path/to/outputs/seed132 \
  --output /path/to/outputs/bound_node4
```

The binder rechecks every field of the original `[0,330)` native event prefix,
source/input hashes, all 299 TXs and aggregate children, all 255 node-4
physical decisions, child ACK reception/drop identity, node-4 actual state
transitions, exact empty PHY state and pending PHY timers at t=300, and each
named PHY draw/BER interval. It copies the actual native TX power into the
bound TX tape. Any missing or ambiguous input raises an error; it never fills
it from the MATLAB trajectory.

Then run in MATLAB R2025a or later, with `runtimeRoot` set to the existing
grouped-routing candidate tree containing `+csr`:

```matlab
addpath('/path/to/two_case_package/source5_receiver_replay');
report=run_source5_receiver_replay(runtimeRoot, ...
    '/path/to/outputs/bound_node4', ...
    '/path/to/outputs/source5_node4_receiver');
```

The validation-only receiver seam uses the source-bound production PHY code
with captured node-4 thresholds and uniform random draws substituted. It
replays every native physical TX and the one actual Idle→Search wake at
300.001 s. The 235 repeated refresh requests are retained as audit evidence,
not injected. The receiver derives its own Track and Tx state, contention,
acquisition, error intervals, and completion states. It compares all 211
state transitions, all 255 decisions, all PHY intervals, and the aggregate
physical outcome of every native-verified
node-4 ACK child. MATLAB child delivery is not run separately. The draw
sampler requires exact key, order, time, and full exhaustion. Native
`prior_stage` is a broad
category, so the report allows MATLAB's specific pre-delivery reasons within
that category. Native closure records its drop at TX start, while the MATLAB
PHY callback emits closure at physical completion; closure timing follows
those two documented conventions. Other timings are checked within 2 ns.

`bounded_outcome_alignment=true` applies only to the node-4 PHY receiver
boundary in this short window after the native capture and MATLAB replay
actually execute. `node4_receiver_rule_parity` stays false because the native
`prior_stage` label does not distinguish every sync, acquisition, and MAC
state rejection subtype. The test does not assert MAC service, HOP/NWK
capacity, or entire network behavior parity. An outcome mismatch or
unconsumed draw yields a failed result for review; no production file is
edited by this test.
