# Seed-132 existing-evidence replay anchors

`source5_first16.csv` records the 16 source-5→gateway-1 applications generated at
300.00–300.30 s and delivered in both native and fixed MATLAB. It contains the
audited attempt/packet identities, native event indexes, positive native HOP
admission capacity snapshots, HOP admission and first physical DATA TX times in
integer nanoseconds. `node4_ack_history.csv` records native node-2 DATA
receptions and the five node-5 ACK attempts at receiver 4 in 301.5–303.3 s,
plus fixed MATLAB's first ACK and the distinct node-2 interfering signal.
The latter is **node 2→8 ACK**, while native's node-2 signal is **DATA to 4**.
Rows are historical observations, not a common-input comparison.

Unknown inputs are intentionally empty: native aggregate members; full
receive state, track candidate and competing signal intervals at signal
start; native/Matlab random draw transcript; native failed capacity probes;
native ACK queue depths; fixed detailed HOP/global/per-peer capacity and ACK
queue snapshots for 300–330 s. In particular, `prior_stage` with zero bit
errors does not distinguish missed wake, unsuccessful acquisition, or rejection
while another signal was tracked. The available native `hop_admission` records
capture successful transfer snapshots only. The returned fixed MATLAB service
observer includes 90–100 s and 600–675 s but excludes 300–330 s.

All times are rounded from stored decimal seconds to integer nanoseconds.
Native sequence 14 and fixed sequence 16 are different ACK histories. Replaying
native TX times into fixed MATLAB must first supply the missing receiver state,
waveform/aggregate children, and random inputs; forcing the observed receive
outcomes would only check downstream bookkeeping. For the queue case, inject the
same initial 16 local arrivals, the same relay DATA receptions and ACK child
jobs, and the same route/priority/window state; compare HOP admission order,
capacity release and first DATA TX. A distinct receiver fixture should replay
the five ACK attempts and node-2 competitors from the same receiver startup
state, with native's final successful ACK as a positive control.

`provenance.json` lists SHA256 hashes of every input. Regenerate with
`python3 two_case_next/source5_replay/fixtures/make_fixtures.py` from the
workspace root. The generator asserts the 16-row and native eight-signal
expected scopes; it does not modify simulation files.
