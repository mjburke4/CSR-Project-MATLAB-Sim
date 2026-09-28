# Seed-131 discovery acquisition replay

`build_fixture.py` extracts all native physical TXs and MAC states in the
half-open `[25,85)` window, plus measured 4→5 and 4→2 decisions, from the
already validated native traces. It checks source packet airtime, propagation,
native receiver observation binding and absence of an on-air packet spanning
25 seconds. `fixture/manifest.json` pins each input by SHA-256. The seed-132
successful long 4→2 receptions are separate positive controls. No fixture
row is filled from an autonomous MATLAB trajectory.
Each TX power is reconstructed independently from native received power plus
path loss at its measured receiver: all 162 seed-131 TXs have 442 power
observations, and all 288 seed-132 TXs have 770; each resolves to 33 dBm.

From MATLAB R2025a or later, run this bounded history fixture against the
candidate tree containing `+csr`:

```matlab
runtimeRoot = '/path/to/grouped-routing-fix/candidate';
fixtureRoot = '/path/to/discovery_replay/fixture';
outputDir = '/path/to/results/discovery';
addpath('/path/to/discovery_replay');
report = run_discovery_replay(runtimeRoot,fixtureRoot,outputDir);
```

The v3 runner schedules **162 native seed-131 physical TXs** and **122 actual
Idle↔Search duty transitions** for checked receivers 2 and 5. It compares
412 independently generated receiver state transitions with the native
history. Repeated state requests and PHY completion transitions are retained
as audit evidence, not injected as commands. The PHY derives acquisition,
Track, Tx and completion states. It compares all six 4→5 KEY_REQUEST
decisions and all 16 short 4→2 decisions. The archived seed-132 control
replays 288 TXs and 65 actual duty transitions for receiver 2, comparing
207 state transitions and three accepted long node-4→2 decisions.

The bundled seed-131 capture supplies 223 sampled SYNC/PHY draws and verifies
all 8,710 original trace events before 85 seconds. The archived seed-132
controls lack a captured draw tape and remain observational. The report
separates `primary_result` from `control_result`.
`native_parity_gate_pass=false` **even if the observed decisions match**:
this receiver replay does not execute the full discovery protocol or network.
Native `prior_stage` is broader than MATLAB's receiver reason vocabulary;
compare success, arrival time, collision and error fields independently.

The prepared test seam accepts a supplemental **captured** seed-131 draw CSV
as fourth argument to the same MATLAB function. It must have precisely:

```text
time_ns,event_order,node,tx_id,interval_ordinal,purpose,value
```

`purpose` is `sync_threshold_db`, `header_uniform`, or `payload_uniform`.
The package already contains the bound tape. To regenerate it from the
captured native evidence:

```bash
python3 convert_capture_draws.py --capture /path/to/capture.jsonl \
  --mac-inputs /path/to/mac_csv/inputs.csv \
  --mac-tx /path/to/mac_csv/tx.csv \
  --fixture /path/to/discovery_replay/fixture \
  --output /path/to/phy_draws.csv
```

That converter verifies every physical TX time, node, sequence, size,
preamble and initial native receiver state against the immutable accepted
trace before mapping its native physical signal IDs into the replay tape. It
also verifies actual PHY TX power against each fixture's measured native
power and the accepted MAC TX export, then writes `tx_inputs.csv` with the
captured power used by the MATLAB runner. It
also writes `receiver_inputs.csv` from actual Idle↔Search duty transitions
for nodes 2 and 5, crosschecked against 122 captured wake/sleep observations.
`receiver_state_audit.csv` retains actual state transitions and
`receiver_request_audit.csv` retains raw request calls. When the fourth
argument is present, the MATLAB runner uses the external duty input tape
and compares its own state changes with the expected history. Place
the output CSV beside `capture.jsonl`; the MATLAB runner verifies its hash,
the actual TX-power input, and the accepted MAC TX power before replay.
For threshold rows `interval_ordinal=0` and `value` is the actual sampled
threshold in dB. Uniform values are in `[0,1]`, and the interval ordinal
starts at 1 per physical signal and receiver. `tx_id` maps to the native
`tx_start.event_index` in `fixture/s131/tx.csv`; join a new capture by
`(time_ns,transmitter)` and verify unique physical TX identity before use.
Filter the CSV to receivers 2 and 5, retaining **all** their threshold and
PHY uniform draws for **all** native signals in `[25,85)`, ordered by actual
capture execution. The sampler raises on a missing, duplicate, unused,
out-of-order, out-of-time, or out-of-range draw. The validation-only copied
`DiscoverySignalEngine` replaces two random call sites with the sampler;
the production engine and radio model remain unchanged. `build_seam.py`
pins the production `SignalEngine.m` SHA-256 and regenerates this copy.
`DiscoveryReplayAllocator.m` copies the source interval allocation arithmetic
but supplies purpose-labeled uniforms to the unchanged BER and binomial
methods. Seed 132 stays an observational physical control in this bounded
capture.

An exact common-input rule verdict additionally requires the new native
capture to prove original `[0,85)` prefix fidelity and complete physical
aggregate children, receiver state/acquisition and competing-signal inputs.
The current runner deliberately never sets its parity gate to true. Once
those capture and MATLAB outputs are returned, inspect any first mismatched
receiver decision before changing production behavior. A full NWK discovery
handoff cannot be replayed from the current native primary-only aggregate
trace: the child `SNMP_START` / `DISCOVER` membership and node-4 HOP/NWK
state remain unobserved. The capture contract and native overlay in the
two-case package collect those missing inputs for the follow-on handoff
decision check.
