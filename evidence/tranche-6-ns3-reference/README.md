# Tranche 6 pinned ns-3 outage observations

These are actual runs of the CSR implementation at
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. The standalone observation fixture was
freshly compiled against the preserved ns-3 engine and shared libraries.
`build.json` records the compiler command, executable hash, source/header/library
hashes and fixture-source hashes. The engine was not rebuilt and MATLAB was not
executed by this utility.

| Freshness timeout | Seed 128 delivered | Seed 129 delivered | Seed 130 delivered | Total |
| --- | ---: | ---: | ---: | ---: |
| 60 seconds | 5/5 | 4/5 | 5/5 | 14/15 |
| 180 seconds | 2/5 | 2/5 | 2/5 | 6/15 |
| 300 seconds | 2/5 | 2/5 | 2/5 | 6/15 |

The nine cases generated 45 applications and delivered 26 unique applications,
with no duplicate application deliveries. All 19 undelivered applications have
an observed local HOP `no_ack` completion; none has an unclassified terminal
trace. The generic HOP-to-NWK link-failure callback was never invoked. All
observed NWK queues, HOP pending-DATA counts, HOP retry queues and MAC queues were
empty at 900 seconds. These aggregate observations do not establish a general
proof of global packet ownership, so the compact CSV reports global `dropped`
and `pending` as `unknown` alongside the exact observed categories.

For 180/300-second freshness, the first three applications, generated at
450/486/522 seconds, exhaust source HOP retries during the blackout; the last
two are delivered after restoration. The 60-second/seed-129 exception also
loses its first application at a local no-ACK completion (459.325000028 s).
The largest observed delivered delay is 135.655212667 seconds. This supports
the conclusion that the longer-freshness outage failure exists in the pinned
source as well as accepted Tranche 5 MATLAB. It does not establish numerical
parity between the implementations.

The shared stimuli are a three-node line (0/3800/7600 m; antenna height 1 m),
400 MHz real CSR PHY, 8–128 kbps adaptive link control, five 64-byte application
payloads from node 3 to node 1 at 450/486/522/558/594 s, manual per-node discovery
at 10/45/80, 315/320/325 and 576/581/586 s, and relay-2 ineligibility in
[405,540) s. Ineligibility suppresses decoded protocol receipt when either the
source or receiver is relay 2. Radios and protocol timers continue running.
Each `scenario.json` contains the exact contract.

There are explicit coupling differences. The available ns-3 MAC callback runs
after successful PHY decoding and MAC last-heard/pathloss/reservation updates;
MATLAB applies the administrative gate before MAC bookkeeping. Source ns-3 uses
its actual security state while MATLAB uses behavioral security with size-only
envelopes. Equal seed identities do not produce equal random draws across the
implementations. No PHY error hook, manual route installation or security-gate
bypass was used.

`case_summary.csv` is the compact comparison input. `summary.csv` adds physical
counts and final aggregate queues. Each case retains per-application outcomes,
five-second queue/admission snapshots, event counts, a focused event timeline,
the full canonical packet trace, and the source runtime log. Large text files
are losslessly gzip-compressed; manifests hash every file and the uncompressed
canonical trace. The seven focused Python tests exercise stimulus validation,
blackout boundaries, duplicate delivery and attribution of local failures when
delivery occurs later.

Final file verification detected an unexpected truncation of the last case's
`snapshots.csv` after its complete hash was recorded. The affected case was
rerun with the same executable and inputs in a separate directory. Its full
trace and snapshot hashes reproduced the original recorded hashes exactly; the
snapshot was then restored byte-for-byte. The cause remains undetermined.
`integrity_recovery.json` and `integrity-observed-snapshots.csv.gz` preserve that
event. All original case manifests and outcome observations remain unchanged.

To reproduce the nine cases from the repository root:

```bash
python scripts/run_tranche6_ns3_reference.py \
  --source /path/to/clean/pinned/CSR-Project-NS3-part2 \
  --ns3-build /path/to/preserved/ns3/build \
  --output /path/to/new/evidence-directory
```
