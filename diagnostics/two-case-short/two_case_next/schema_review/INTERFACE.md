# Two bounded cases: evidence interface and gates

The two cases share the already accepted MAC history tape from
`repaired_kit/macbatch/native/mac-replay-hooks.h` and `convert_capture.py`.
Keep its five CSVs and field names unchanged:

| File | Key | Purpose |
| --- | --- | --- |
| `inputs.csv` | `(time_ns,event_order,node)` | External `enqueue`, `receiver_state`, `sync`, `active`, `reported`, `received`, `cancel_ack`, `cancel_type` callbacks. Columns: `time_ns,event_order,node,kind,peer,sequence,frame_id,value,value2,value3,ack_bitmap,dack_bitmap`. |
| `draws.csv` | `(node,ordinal)` | Observed MAC *integer slot* draw with `event_order,time_ns,node,ordinal,min,max,draw`. This is not a PHY draw. |
| `frames.csv` | `frame_id` | Post-MAC bytes and envelope of a queued frame; retain all fields in the existing converter. |
| `tx.csv` | `(time_ns,node)` | Physical TX parameters, full-frame IDs and duration. |
| `tx_frames.csv` | `(time_ns,node,child_index)` | Every child of a transmitted aggregate (source, destination, sequence, type, wire bytes, MAC frame ID). |

Supplemental case-specific receiver/capacity events can be JSONL or TSV and
should expose `time_ns` (integer ns), `event_order` (strictly increasing within
that stream), `case_id`, `node`, `layer`, `event`, `peer`, `frame_id`, `tx_id`,
`app_source`, `app_sequence`, `reason`, `state_before`, `state_after`, and
`detail`/`detail_json`. Add measured PHY threshold, receiver acquisition and
overlap, ACK depth, HOP pending and per-neighbor outstanding, NWK queue/NSDP,
and exact capacity release where applicable. An absent field is `null` in
JSONL or empty in TSV, and must be listed as `unavailable` in the manifest.
No value may be back-filled from another model's autonomous trajectory.

**Identity domains are distinct.** `frame_id` is the validation `FrameTag`
attached at MAC enqueue, `tx_id` is a physical signal ID, and
`(app_source,app_sequence)` is the source application identity. Native
`CsrNetDevice::SendFramesToPeers` and `Mr::Tx` retain all child headers; the
canonical differential trace records only the aggregate's head. A join must
use `(tx start time_ns, transmitting node, child_index)` plus an explicit
signal/aggregate association, never merely a common sequence number.

**Case A: discovery131.** Run the unmodified simulation from zero through
at least 85 s, recording all states from zero. Select 25–85 s decisions at
node 5 (4→5 acquisition) and node 2 (4→2 propagation); retain nodes 3 and 4
as competing signal/control producers. The seed-132 successful long 4→2
reception is a separate positive control. Need exact TX schedule, aggregate
children, receiver wake/Search/Track history, physical overlap, per-receiver
sync-threshold draws and any receiver PHY uniform draws. A single native
snapshot at 25 s without pending events/interference is inadequate.

**Case B: source5_132.** Run from zero through at least 330 s; select
300–330 s decisions. Capture node-4 ACK reception under node-2 interference,
node-5 relay arrivals and ACK queue, source-5 application identity, route,
NWK scan/NSDP, HOP global/per-neighbor capacity and release, MAC assembly,
and per-receiver random draws. A HOP object initialized at 300 s omits the
existing resend/flow-control/route state; such a fixture can test an isolated
boundary but cannot claim a native-state-equivalent queue replay.

The native overlay's `Mr::Active()` in `mac-replay-hooks.h` currently includes
only nodes 2/4/8, so each short case must expand its instrumentation nodes.
`Mr::Draw()` records only MAC integer draws; native
`CsrNetDevice::DrawSyncSnrThresholdDb` uses a receiver-local normal generator,
and `CsrPhyModel::AllocateErrors` consumes uniform draws. MATLAB
`csr.phy.SignalEngine.beginSignal` uses a separate `randn` stream and
`csr.phy.Model` a `rand` stream. Replaying the same numeric seed is not a
common-input receiver test. Reproduce the receiver values/ordering or mark
`phy_random_tape: unavailable` and the result conditional or pending.

The portable MATLAB `csr.phy.SignalEngine` can directly set only receiver
`Search`/`Idle`; `Track` and `Tx` arise through its own signal and TX callbacks.
For exact receiver comparison, feed all prior physical signals/duty edges and
do not force an observed native `Track` by mutating MATLAB internal state.
The earlier `run_mac_history.m` predicts MAC TX from recorded external inputs
and validates draw consumption; that *conditional MAC* scope remains useful.

The accepted native-history build script assumes a separate ns-3 build under
`startup131/environment/engine/build`; this current workspace has neither
that engine/library nor a `matlab` or `octave` executable. A complete
native-prefix fidelity gate must be run where the native engine is available:
compare canonical CSV rows exactly to the source native trace for the
half-open `[0,85)` or `[0,330)` prefix, including metadata and order. A
capture with the same seed but a different prefix cannot be used to assert
decision-rule mismatch. This environment can prepare and statically validate
an owner-runnable capture/replay package, and can run offline evidence checks.

`validate_two_case.py` checks hashes, manifest truthfulness, ordered tape,
capture prefix and draw usage. It accepts `capture_pending` and
`replay_pending` as honest prepared states and prints an explicit pending
verdict; `--require-complete` turns them into a failure for an acceptance gate.
The self-contained pending manifests bind the scenario, canonical native
reference prefix, and case's overlay *generator*. For a verified capture,
add `source_files.native_overlay` for the exact generated instrumented header
used by that build and `source_files.native_capture_source` for the runner;
both are hash checked. The generator alone never proves a native run.
Set `capture.observations_path` to the JSONL/TSV receiver-capacity event stream,
and `capture.mac_tape_paths` to all five converted CSVs. The validator checks
observer identities/order and declared counts against those actual files.
No short-case result can establish full 6,000-second network parity.

## Source anchors

- `repaired_kit/macbatch/native/{mac-replay-hooks.h,convert_capture.py,capture.cc,replay.cc,build_capture.py}`;
- `repaired_kit/macbatch/native/overlay/ns3/csr-net-device.h`, methods
  `SendFramesToPeers`, `BeginReceiveSignal`, `DrawSyncSnrThresholdDb`,
  `AcquireSignal`, `EndReceiveSignal`;
- `repaired_kit/macbatch/native/overlay/ns3/csr-nwk-layer.h`,
  `CheckNwkQueue` and its `nwk_admission` details;
- `repaired_kit/macbatch/native/overlay/ns3/csr-hop-layer.h`,
  `GetDataAdmissionSnapshot` and `GetPendingDataCount`;
- `routing_work/grfix/candidate/+csr/+phy/SignalEngine.m`, `beginSignal`;
- `routing_work/grfix/candidate/+csr/+validation/ReplayStreams.m`;
- `repaired_kit/macbatch/matlab/run_mac_history.m`.
