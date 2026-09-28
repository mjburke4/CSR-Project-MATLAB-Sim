# Seed-132 source-5 bounded replay

This directory contains two independently gated source-5 checks for the
300–330 s interval. Neither requires rerunning the 6,000-second campus case.

The first check is executable once MATLAB is available. The native 0–675 s
prefix already contains the first 16 source-5 application offers, 20 actual
DATA TX indications, 16 HOP ACK completions, and all 16 positive admission
capacity snapshots. `build_native_capacity_fixture.py` extracts the exact
native event indexes into `fixtures/capacity_events.csv` and a separate
`fixtures/native_admission_reference.csv`. Native input trace and selected
packet-table SHA256s are in `fixtures/capacity_manifest.json`. Run:

```matlab
addpath('/path/to/grouped-routing-fix/candidate');
addpath('/path/to/two_case_next/source5_replay');
report = run_source5_capacity_replay('/path/to/two_case_next/source5_replay/fixtures', ...
    '/path/to/output/source5-capacity-actual-tx', 'actual-tx');
```

The runner exercises the actual production `csr.hop.Layer`: the first 16
local applications enter a test-owned NWK FIFO, `hop.canSend` and `hop.send`
decide capacity, source TX indications call `hop.notifySent`, and completion
inputs call `hop.receive`. HOP's scheduled +TIC wake prompts the next FIFO
scan. Its oracle compares **each** native HOP admission's integer-nanosecond
time, source packet identity, global pending before/after, neighbor
outstanding before/after, and per-peer threshold. `report.json` contains
the first difference. For HOP retry-policy diagnosis, optionally run a
second time with `'native-provisional'` into a different output directory;
the accepted autonomous MATLAB default remains `'actual-tx'`.

The boundary deliberately supplies native actual send and ACK/DACK times.
It is a conditional capacity test, not an NWK, receiver, MAC or physical
reception replay. Native HOP sequences are normalized by source application
identity because controls before 300 s were not run in this fixture. If
admission or threshold order differs with the common boundary input, inspect
the first mismatch before changing code. Passing it would not establish
parity of arrival times, ACK scheduling or relay competing traffic.

The second check is prepared for the **new** native 0–330 s capture. It
reuses a **bundled** copy of the previously validated
`mac_adapter/matlab/run_mac_history.m` and `mac_replay.MacLayer` adapter.
`mac_adapter/binding.json` pins both adapter hashes and the current production
MAC Layer source hash (`d2e1b9e0…`). The small adapter has no dependency on
the old 112 MB history tree:

```matlab
report = run_source5_mac_replay('/path/to/two_case_next/source5_replay/mac_adapter', ...
    '/path/to/new_native_source5_capture', '/path/to/output/source5-mac', ...
    '/path/to/grouped-routing-fix/candidate');
```

The native capture must supply unchanged `frames.csv`, `inputs.csv`,
`draws.csv`, `tx_frames.csv`, a `profile.json` with node 5 and natural warmup
`[0,330)`, and independent native `reference/{tx.csv,draws.csv,fidelity.json}`.
`fidelity.json` must attest exact-prefix source identity before MATLAB can
compare all TX and raw draw consumption. Missing files, unproved fidelity,
draw exhaustion, draw support differences or an output mismatch fail closed.
The accepted adapter replays receiver state as an external input; its pass is
**conditional MAC scheduling**, not an independent receiver-rule pass.

`fixtures/source5_first16.csv` and `fixtures/node4_ack_history.csv` are
historical anchors for the capture, not same-input outcomes. The former's
source/provenance files are documented in `fixtures/README.md`. Native ACK
aggregates do not expose all children in the old trace. The new capture
needs ordered `tx_frames.csv` children and node-4 receiver/PHY state plus
node-5 HOP/NWK state in `source5_native.tsv`. A complete NWK rule replay
would also require its 300-s queue, route and HOP owner state (or all prior
inputs from time zero). This runner leaves the full NWK/receiver parity gate
open rather than creating state from the autonomous MATLAB history.

Offline check (run from workspace root):

```bash
python3 two_case_next/source5_replay/audit_source5_replay.py
```

It verifies native fixture hashes/counts and identity of production MAC
sources. It does not execute MATLAB or promote a conditional result to
full-network parity.
