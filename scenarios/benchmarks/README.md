# Campus benchmark inputs

`catalog.json` identifies the runnable cases, exact CSV hashes, atomic historical
application/MAC/HOP profile, complete duration, seed, and aggregate bucket width.
The default cases are:

| Case | Duration / bucket width | Stimulus | Comparison |
| --- | --- | --- | --- |
| `campus_multihop_6000` | 6,000 s / 60 s | Original seven-node campus topology; six 200-byte source flows start at 300 s and attempt every 0.02 s | MATLAB/ns-3 application aggregates and the original archived OPNET output |
| `two_node_admission_1200` | 1,200 s / 12 s | Synthetic two-node topology, 1,200 m separation; one 600-byte flow starts at 300 s and attempts every 0.02 s | MATLAB/ns-3 admission, application aggregates and latency |
| `three_node_contention_360` | 360 s / 3.6 s | Synthetic gateway at the origin and sources at ±1,200 m; two 600-byte flows start at 300 s and attempt every 0.002 s | MATLAB/ns-3 contention, admission and application aggregates |

The last two cases reuse the source-backed campus profile and radio settings.
They are new diagnostic stimuli, not reconstructions of the historical OPNET
latency or visible-node experiments. Their recipe files define each changed
field and bind the unchanged parent CSV. They do not assert that the source
nodes are physically hidden from one another.

All three cases use `legacy-send-only-no-dscp`,
`hist-2014-next-tslot-modulo-probe`, and `hist-adb97c54-bare` together. The
historical executable digest binds that behavior tuple. Radio bounds remain
8–128 kbit/s and −36 to +33 dBm, with 12 dB link margin, 1 m antenna height,
400 MHz carrier and ECC threshold 0.1. PHY/ECC behavior is preserved.

`flow_limit=0` means unlimited **admitted** packets. Attempts blocked by source
discovery, topology, gateway-route, destination or NSDP gates are counted
separately. An attempted generation is not an admitted application packet.

The original campus CSV SHA-256 is
`90b143d93c13c6c2761bc5f2875ccc3fff98f85af6f2550370e435df2aaabcfc`.
It exactly reproduces the prior ns-3 publication input. Original `.nt.m`, DES
environment, `.ov`, probe definition and compressed archived executable bytes
are preserved under `evidence/tranche-7-benchmark-inputs`, with the enclosing
archive and individual file hashes. The executable is evidence and is not run.

`hidden_symmetrical_60000.csv` is retained as a deferred canonical input. Its
100 m gateway antenna height differs from the 1 m source antennas, and the
full case entails approximately 149.25 million generation attempts. It is
outside the runnable catalog until those capabilities and execution cost are
handled. No shortened run is represented as its historical OPNET result.

To regenerate the ns-3 reference evidence from the clean pinned source and a
compatible preserved build:

```sh
python3 scripts/run_tranche7_ns3_reference.py \
  --source /path/to/CSR-Project-NS3-part2 \
  --ns3-build /path/to/ns3/build \
  --output /path/to/new-reference-output
```

The command verifies original input bytes and reproduces every runnable CSV,
then compiles the standalone scenario runner. It does not rebuild the ns-3
engine, execute MATLAB or rerun OPNET. It preserves the complete event traces
as gzip files, producer metadata, per-source aggregate CSVs, and normalized
sidecars for the benchmark comparator. A completed zero-tolerance OPNET
comparison may report numerical differences; extraction, execution,
correlation, size and provenance failures remain errors.
