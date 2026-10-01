> This is the provenance description of the full native capture retained by the analyst. This MATLAB owner kit contains only the random draws, transmission signatures and receipt needed to run the MATLAB cases. Paths such as `run/` and `fixture/receiver_history.csv` below refer to that separate native evidence archive; no native command is required from you.

# Seed-132 autonomous native capture

The 0–330-second native capture passes exact comparison of **48,919 rows and
all 30 canonical fields** against the accepted original prefix. The new
observers do not alter production algorithms, scheduling or random draws.

`fixture/random_draws.csv` has **4,430 native random samples** from all seven
configured nodes (1, 2, 3, 4, 5, 7, 8), beginning at simulation time zero.
`fixture/receiver_history.csv` has **70,441 receiver and timer observations**.
`run/observations.tsv` retains all **110,182** detailed observations, including
receive decisions, interference intervals, HOP/NWK admission and MAC queues.
`receipt.json` records the prefix gate, counts, source pins and file hashes.

`fixture/tx_signatures.csv` contains all **1,495 transmitted children in 811
physical transmissions**. It retains actual serialized packets after MAC
header updates, full ACK/DACK bitmaps, grouped destination sequences, network
source/destination, ordered aggregation, rate/power/preamble and wire lengths.
The PHY replay must validate that semantic transmission before reusing a
native receiver draw. Matching sender plus transmission ordinal alone does
not establish matching packet content. Capture-local `frame_id` is diagnostic
only. Use the 16-character hexadecimal ACK/DACK bitmap fields for exact MATLAB
`uint64` conversion; automatic decimal-to-double import loses upper bits.

DATA signatures join native application admission, HOP admission and TX to
retain the original flow index, **attempt ordinal**, and generation time.
Native flow indices are zero-based; MATLAB flow indices are one-based.
`application_bytes` is the 185-byte application content after excluding the
7-byte compatibility NWK header from the 192-byte compatibility payload.
Native application sequence/UID is recorded for provenance and must not be
compared directly with MATLAB's application ID.

The 115 ROUTING children include 98 actual ARL sections and 17 legacy
REQUEST envelopes. For REQUESTs only, `routing_section_hex` normalizes the
native metadata to its semantically equivalent six-byte routing prefix plus
REQUEST opcode `03`; `routing_section_origin` explicitly labels that case.
Other legacy encodings are rejected by the normalizer rather than silently
translated. The untouched actual payload and complete packet hex are retained.
SNMP fields include source, destination, command, signed value and node list.

These are new passive observations of the previously accepted simulation,
not a new network-performance result. MATLAB has not yet executed the new
fully coupled test.

## Random-input contract

| Purpose | Value supplied | Matching context |
|---|---|---|
| `mac_slot` | Returned inclusive integer sample | Node, per-purpose ordinal, time, inclusive low/high bounds, active/reported count, reservation state |
| `sync_threshold` | Actual sampled threshold in dB | Receiver, per-purpose ordinal, time, physical TX identity, mean and variance |
| `phy_binomial` | Consumed uniform sample on [0,1] | Receiver, per-purpose ordinal, physical TX identity, interval ordinal/bounds, header/payload component, tested bits and probability |

Each `(node,purpose)` ordinal begins at 1 and has no gaps. Values retain 17
significant decimal digits. `time_ns` and all interval bounds are native
integer nanoseconds. A physical TX identity is `(transmitting node << 32) |
per-node-transmission ordinal`; the MATLAB side must map its endogenous TX to
that semantic identity. Native numeric IDs must not be confused with a global
MATLAB packet ID.

The SYNC value is already the sampled threshold. Do not apply the normal mean
or standard deviation again. The MAC value is the returned integer, not an
underlying uniform random sample. For the PHY source-binomial sampler,
zero-bit and probability-0/probability-1 calls consume no random value and
therefore have no random row. Node 7 consumes zero PHY-binomial uniforms in
this capture; this is observed behavior, not missing capture data.

For this pinned scenario, fixed application destinations and fixed intervals
consume no application RNG; NWK/HOP do not draw random values. OPNET-aligned
duty cycling does not draw a wake phase. The configured historical MAC profile
uses the captured inclusive integer site; the active interval-error PHY path
uses the captured binomial site. Other profile branches and the alternate
whole-packet PER path are outside this scenario.

## Receiver diagnostics and limitations

The observer adds callback-entry/exit snapshots for the existing device wake,
sleep, acquisition, post-TX and receive-completion boundaries, with the native
calling cause. Snapshots include receiver state, SYNC presence, tracked signal,
active-signal count, transmit preparation, post-TX wait, force-awake deadline,
reservation counter and ACK/DATA queue depths. Existing timer schedule/cancel
sites record native event UID, pending state and deadline. MAC state/SYNC
changes and the original canonical MAC slot/holdoff records are retained.

These receiver states are **reference outputs**, not injected inputs for the
new coupled MATLAB test. Event UIDs are native-only diagnostics; compare
causes, deadlines and resulting states across engines. Timer firing is
identified by callback entry; not every native timer has a separate UID-bound
fire row. Device timer instrumentation does not claim a new complete trace of
all private MAC slot and holdoff timer internals. Some outer PHY entry points
retain the `unscoped` cause label; their explicit event names and signal IDs
identify the receive operation.

MAC and device observations share one monotonically increasing ordinal.
The detailed TSV has gaps because interleaved MAC-input-log rows use the same
counter. This preserves cross-layer observation order without scheduling new
events. The prior observer's extra t=300 snapshot event was removed.

## Reproduction

The pinned CSR and ns-3 source/build live under `autonomous/native_env/`.
From the project workspace root:

```sh
python3 autonomous/native_capture/build_capture.py
python3 autonomous/native_capture/run_capture.py
```

The build script creates an isolated header overlay and verifies source pins,
clean tracked source trees, critical source hashes and the existing native
driver hash. The runner executes the seed-132 scenario and invokes
`normalize.py`. Normalization refuses to issue fixtures unless the original
30-field canonical prefix is identical. Baseline source is not modified.

The package includes the byte-identical native driver under `vendor/`, the
accepted scenario and compressed original prefix under `fixture/`, and the
restored native build identity in `native-build.json`. Actual compile and run
commands are recorded separately. Those commands retain the input paths used
when executed; the reproduction scripts use the identical bundled files.
