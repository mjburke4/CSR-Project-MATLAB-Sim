# Seed-132 source-5 bounded native capture

This case runs the original seed-132 scenario from **0 to 330 seconds** and
records the 300–330-second receiver/queue decision interval. It retains the
validated native MAC input format and adds a read-only observation stream.
Nothing in this directory is a network-layer or PHY behavior change.

Run on a host with the source-bound native CSR/ns-3 Debug checkout:

```sh
python3 source5_capture/run_bounded_capture.py \
  --source-model /path/to/csr/model \
  --engine-build /path/to/engine/build \
  --scenario schema_review/scenario_s132.csv \
  --reference-trace schema_review/native_s132_prefix_0_330.csv.gz \
  --out /path/to/source5_132_capture
```

Choose a new output path for each run; the runner rejects an existing output
directory so a failed attempt cannot expose a stale fidelity receipt.

Run from the extracted two-case package directory; `source5_capture` and
`schema_review` are siblings. The scenario SHA-256 must be
`fa45217f8631f34d203580842d8a1a12cb18c53a3efbe0b702b2e17aaeb30d48`.
The compact canonical reference SHA-256 must be
`6819889725eb891112b57dbc9f8e63c35af7e87fcf64f77c6dbe3f490d3c63a8`;
it contains every original trace row strictly before 330 s, with lineage to
full native trace SHA-256 `3da17e3397756f8890964d571932a44f7c94573b4d38eac9387342588883a4ef`.
The runner also accepts `--reference /path/to/original/t25/s132` in place of
the two direct reference arguments.

The generator compares five untouched native model header hashes, checks
the native source/engine Git commits if their Git metadata is present, and
creates an isolated header overlay. It compiles the previously validated
native capture driver against the owner's matching Debug engine. Changes
to tracked source files or a different commit stop the run; untracked build
artifacts are ignored. Without Git metadata, header hashes and the exact
canonical trace gate still bind the behavior. No source checkout is edited.

The runner first compares **all 30 canonical fields and event order for every
native row in [0,330) exactly** against the original reference. Any mismatch
stops the run before a `fidelity.json` pass is written. This gate checks the
autonomous path, including the setup history needed before the 300-s burst.

On success, `capture/mac-input.log` converts to the accepted format under
`inputs/{inputs,frames,draws,tx,tx_frames}.csv`. MAC inputs, packets and integer
draws cover all seven scenario nodes 1, 2, 3, 4, 5, 7 and 8 from t=0, including
node-3 DATA that contends at receiver 5. `inputs/profile.json` selects node 5
for 0–330-s replay with comparison window 300–330 s. The independent
`reference/tx.csv`, `reference/draws.csv` and `reference/fidelity.json` are
created **only after** prefix equality. `inputs/tx_wire_hex.csv` additionally
holds final transmitted child bytes, and `capture/source5_native.tsv` holds
the bounded receiver/queue records.

The TSV has named columns `time_ns,event_order,case_id,node,layer,event,peer,frame_id,tx_id,app_source,app_sequence,kind,outcome,reason,state_before,state_after,pending_data,peer_outstanding,peer_threshold,nwk_waiting,mac_ack_depth,mac_data_depth,detail_json`. `frame_id` is the passive MAC enqueue tag, `tx_id` is the PHY signal identity, and `(app_source,app_sequence)` identifies an application packet. `mac_tx_child` joins these identities at transmission by `tx_id,frame_id,child_index`; the companion `tx_frames.csv` binds `time_ns,node,child_index` to the same frame tag. An empty field means not observed for that record and is never fabricated from MATLAB.

Receiver records include arrival with prior signals/Track state, per-signal
normal SYNC threshold draw and decision, acquisition candidates/selection,
PHY interval binomial uniform draws, successful aggregate children and
node-4 ACK reception/drop. Node-5 records include local source submissions,
relay arrivals, NWK queue scans and selected route/NSDP/HOP gates, admitted
HOP owners, ACK/DACK/no-ACK completion and capacity release, and MAC TX plus
its ordered children. The native differential trace with `--admissionTrace=1`
retains full packet-level NWK/HOP feedback fields. This is a capture of
actual native random values and queue states; it does not initialize a
MATLAB receiver or HOP object at 300 s.

At exactly 300 s, `boundary_state` records node 4's MAC state, active RX
signal count/identities, tracked signal, receiver callbacks, SYNC presence,
queue depths, and both receiver draw counters. The runner requires an idle or
searching receiver with no active RX, tracked signal, pending acquisition,
pending completed RX, pending signal wake or SYNC flag. Scheduled periodic
wakes and MAC timers remain visible and are replayed from external native
history. Each `rx_error_interval` and `rx_binomial_draw` carries a 1-based
interval ordinal per `(receiver node, physical tx_id)` with observed interval
bounds in nanoseconds, noise/JSR/collision state, and header or payload
component bounds, tested bits, BER probability and the actual native uniform
draw. The runner also checks the expected **distinct physical signals**: six
node-5 ACKs accepted and four dropped at node 4, plus 32 node-3 DATA
aggregates accepted at node 5. It does not assume one packet per aggregate.

The supplied workspace has no native ns-3 build or MATLAB executable, so
generation, prior-converter regression, source-hash checks, and observer
schema/C++23 smoke tests were performed locally, but **this new capture has
not been compiled against ns-3 or run here**. The new receiver/capacity
replay result therefore remains pending until the owner runs the bounded
command and returns its output. The accepted previous MAC converter outputs
were reproduced byte-for-byte (six files) from the 665-s fixture log.
