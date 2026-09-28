# Seed-131 discovery capture, 25–85 seconds

This native probe instruments the accepted ns-3 model while running the
canonical seed-131 scenario **from t=0 to t=85**. It writes detailed receiver
events only for the half-open [25,85) interval. The accepted MAC capture tape
runs from t=0 so prior queue/state/draw history is preserved. No application
traffic is scheduled before t=300 in this scenario.

The modified source is limited to the passive probe in `probe_sources/`:
`capture.cc`, `csr-net-device.h`, `csr-phy-model.h`, `mac-replay-hooks.h`, and
new `csr-discovery-capture.h`. `discovery-capture.patch` is an equivalent patch
against the frozen files. `apply_overlay.py` checks four baseline SHA-256 hashes,
copies the accepted overlay into a new output directory, and replaces only
these five files. The original native tree remains untouched.

Before running, supply Linux checkouts at exact commits
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` (native source) and
`6b5cd24ea80713ce16d88575869aedd6f432bdae` (ns-3 engine), plus the
matching debug engine build. `run_seed131_capture.py` verifies both commits,
the seed-131 scenario SHA-256
`e10d210590c80cb839442b7847ee6c7e8b8c21d043da5fe5dcf1f2abb402ca7a`,
the reference SHA, and all source guards before compilation. It then compiles
the overlay and runs only to 85 seconds. For a small reference use the
unfiltered original native `native_s131_prefix_0_85.csv.gz` from the companion
schema package; its SHA-256 is
`5b7ea32822f91e9404afd9ff25e31973c6c9f462e7360967bc0dcf5d8eab6bac`.

```bash
python3 run_seed131_capture.py \
  --base-native /path/to/accepted/macbatch/native \
  --native-source-repo /path/to/native/source/checkout \
  --engine-repo /path/to/ns3/engine/checkout \
  --engine-build /path/to/ns3/engine/build \
  --scenario /path/to/seed131/scenario.csv \
  --reference /path/to/native_s131_prefix_0_85.csv.gz \
  --output /path/to/new/seed131_capture_result
```

The output `capture.jsonl` uses `case_id=discovery131`, monotone `event_order`,
integer `time_ns`, `node`, `peer`, `frame_id`, `tx_id`, `layer`, `event`,
`reason`, `state_before`, `state_after`, and a detailed object. `tx_id` is a
unique physical signal identifier distinct from the MAC enqueue `frame_id`.
`tx_child` includes each ordered member's post-MAC header, structured
destination sequences, and raw wire bytes. `rx_begin` carries receiver state,
power/SNR, overlap IDs, and signal/preamble/end times. `sync_decision` carries
the actual sampled native normal threshold. `phy_uniform` records the exact
raw uniform for each nontrivial source binomial BER draw, scoped to receiver,
signal, interval, and header/payload component. Wake, sleep, preamble expiry,
acquisition scheduling/selection, receive outcome, and the explicit t=25
receiver state/active-signal snapshot are recorded. The original `Mr::` tape
grammar remains unchanged and includes all seven scenario nodes; the supplied
converter writes five existing MAC CSV tables under `mac_csv/`.

**Mandatory acceptance gate:** `receipt.json` reports
`verified_exact_native_prefix` only when every canonical ns-3 CSV row in
[0,85) matches the original native reference exactly, including order and
metadata, all seven receivers have empty active-signal sets at t=25, and
aggregate children are complete. The full original trace's parent SHA-256 is
`8daa3cea2bcfae1162c373b39110745fe8889066fdaab3bd22fbb0c685fe3878`.
On any mismatch, the script rejects the capture and preserves diagnostics.
The overlay has been statically checked and its patch applied byte-for-byte;
no native engine or executable is available in this workspace, so no run or
behavioral parity result is claimed yet.

All current outputs are observer evidence. They do not equate independent
native and MATLAB RNG histories or imply that seed-131's autonomous timing
difference is a production defect. The MATLAB replay still needs to consume
the common native receiver inputs and compare acquisition decisions before
any source-level behavior change is justified.
