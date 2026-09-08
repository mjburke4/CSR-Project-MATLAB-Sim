# CSR MATLAB validation strategy

For the subsequent owner's R2025a runs (initial 20/24, corrected 24/24 passed)
and the accepted controlled scenario,
see [r2025a-validation-followup.md](r2025a-validation-followup.md).
The initial inspection evidence below retains its original scope.

Source baseline: `mjburke4/CSR-Project-NS3-part2` main commit
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, inspected 2026-09-08.
This is a development strategy; proposed MATLAB checks below are not execution results.
Machine-readable current and inherited evidence is in
[`../evidence/ns3-validation.json`](../evidence/ns3-validation.json).

## What has actually been checked

| Evidence | Result | Meaning |
| --- | --- | --- |
| Fresh Python utility suite | 289/289 passed, 8.219 s | Import, extraction, aggregation, trace/path/admission comparison, and workflow fixture tests |
| Fresh Python release classifier | 51/51 passed, 0.742 s | Release-evidence classification and integrity checks |
| Latest publication record, 2026-09-07 | 38/38 executable workflows; 39 build products | Historical ns-3 execution recorded by the source repository; not rerun here |
| Publication source hashes | All 9 listed source/document hashes match this checkout | Published selected MAC/HOP fixes and retained PHY evidence apply to these files |
| MATLAB R2025a / R2026a | Neither executed in this inspection | Runtime validation remains necessary on available MATLAB machines |
| Fresh ns-3 C++ simulation | Not executed in this inspection | Python workflow tests use fixtures or fake runners; they are not live protocol runs |

The current executable-search path exposes neither `matlab`, `octave`, nor an
`ns3` command. The inspected CSR repository is a module/program source checkout,
not the separate pinned ns-3 engine and build environment.

## First tranche: small checks that expose structural mistakes

The implemented acceptance fixture uses three nodes and six packets over
controlled direct links. Nodes 2 and 3 send three packets each to node 1,
starting at 0.1 and 1.4 s with 3-s intervals, stopping at 10 s. Each packet has
64 application bytes, bare envelope overhead, a long preamble, and nominal rate
key 8. This is a new MATLAB foundation fixture, not a recovered
OPNET result and not evidence that MAC/HOP or routing has already been ported.

| Check | Independent acceptance condition |
| --- | --- |
| Packet transfer | Six generated packets and six completed intended deliveries, 384 received application bytes, positive latency; no unexpected drops or duplicated deliveries |
| Multiple receivers (T1/T2) | Extend beyond T0 direct destinations to distinguish signal reception/overhearing from intended application delivery; not yet implemented |
| Time ordering | Receive completion follows transmit start by the modeled airtime plus propagation; event times never regress |
| Scheduler | Equal-time events preserve documented insertion ordering; canceled events do not fire; nested same-time work does not disappear; events beyond stop do not fire |
| Stop boundary | Explicitly document and test whether stop-time events execute; account separately for packets still in flight at stop |
| Scenario validation | Reject duplicate/invalid node IDs, broadcast as a concrete endpoint, invalid rates, impossible byte counts, negative/nonfinite timing, and missing destinations |
| RNG repeatability | A fresh run with the same config/seed reproduces outputs; optional tracing does not change draws or packet outcomes |
| RNG isolation | Adding an unrelated node or drawing from another subsystem's stream does not perturb an existing stream, if the selected stream architecture promises that property |
| Rate timing | Compare to current ns-3 independent golden constants; nominal keys must not be multiplied by 1,000 indiscriminately |
| Statistics | Trace-derived totals reconcile with result counters; generated/admitted/transmitted/received/delivered counters have separate definitions |
| Adapter contract | Repeat the same controlled scenario through each installed adapter and check counters/timing; an unavailable adapter reports unavailable rather than a test pass |

Do not call a counter check a reliability test before ACK/retry ownership exists.
Use direct transfer explicitly in this tranche. Stop declaring tranche completion
at “generated and statically reviewed” when no MATLAB runtime result is available;
label it implementation ready for runtime validation.

### Source-backed golden fixtures

`csr-phy-ber-ecc-smoke.cc::TestExactRates` contains these independent timing
vectors:

| Nominal rate key | Four-bit interval, s | Exact payload bit rate, bit/s |
| ---: | ---: | ---: |
| 8 | 0.000510 | 7843.137254901961 |
| 16 | 0.000254 | 15748.031496062993 |
| 32 | 0.000126 | 31746.031746031746 |
| 64 | 0.000062 | 64516.12903225806 |
| 128 | 0.000030 | 133333.33333333334 |
| 500 | 0.000008 | 500000 |
| 1000 | 0.000004 | 1000000 |

The current `model/csr-phy-model.h` uses DPSK for key 500 and DQPSK for key
1000. Tests must keep those modes distinct. Later PHY tests should bring over
BER table anchor values, processing gain, header/payload error allocation, and
inclusive ECC threshold boundaries from `csr-phy-ber-ecc-smoke.cc`, rather than
only testing monotonic behavior of the MATLAB implementation itself.

`csr-opnet-scenario-runner.cc::SendFlowPacket` defines the legacy imported-size
contract: configured bytes minus 8 gives total NWK bytes; subtract its seven-byte
NWK header to obtain payload bytes. Thus a configured 200-byte historical flow
has 192 total NWK bytes and 185 payload bytes. This adjustment belongs to the
historical scenario profile, not a universal deduction from a user-declared
payload size. Blocked application attempts create no packet identity and do not
count as generated traffic; the next attempt remains scheduled.

The existing `utils/testdata/csr-scenario-fixture.csv` is only a 0.1-s,
two-node initialization fixture with no traffic flows. Its corresponding
`opnet-trace-fixture.csv` is synthetic. Neither proves packet transfer or OPNET
event parity. The three-node reservation fixture is useful after MAC integration:
nodes 2 and 3 both reserve slot 5, control begins at 59.9 s, both send to node 1
at 60 s, and the run stops at 65 s. Preserve its explicit profile and collision
controls when implementing an equivalent controlled scenario.

## Gates for subsequent tranches

| Tranche | Required end-to-end evidence | Useful existing ns-3 references |
| --- | --- | --- |
| PHY/channel/traffic | Modeled receive power and propagation; deterministic forced success/failure; separated/overlapping signals; rate and ECC fixtures | `csr-phy-front-end-smoke.cc`, `csr-phy-ber-ecc-smoke.cc`, `csr-live-high-rate-dqpsk-smoke.cc` |
| MAC/HOP | ACK frees capacity; lost DATA/ACK invokes retries; retry exhaustion; DACK hold; bounded queues; controlled collision and overhearing | `csr-ack-window-smoke.cc`, `csr-hop-mac-sent-time-smoke.cc`, `csr-hop-dack-hold-smoke.cc`, `csr-mac-hop-queue-limit-smoke.cc`, `csr-mac-receive-contention-smoke.cc` |
| NWK/control | Autonomous discovery, loop-free multi-hop delivery, route loss/recovery and custody; control wire-format fixtures | `csr-nwk-arl-routing-stream-smoke.cc`, `csr-nwk-residual-routing-retry-smoke.cc`, `csr-hop-no-route-relay-smoke.cc` |
| Scenario integration | Shared topology/traffic/radio/profile inputs; results and traces with provenance; trace-derived counter consistency | `csr-opnet-scenario-runner.cc`, `utils/aggregate-ns3-trace.py`, path/admission analyzers |
| Parity/research | Controlled deterministic comparisons plus ensemble distributions; measured gaps recorded without changing tolerance after observing a failure | Trace and aggregate comparators; latest residual review |

Every meaningful run should record CSR MATLAB Git commit, reference ns-3 commit,
MATLAB release/toolbox versions, selected adapter, complete configuration/hash,
seed/stream scheme, stop/warmup times, elapsed runtime, and trace detail level.
This can begin as one small JSON manifest; the old release-certification harness
does not need to be recreated before this simulator becomes useful.

## Differential strategy and interpretation

1. Share scenario values and explicit application/MAC/security profiles. Import
   rectangular ns-3 scenario CSVs or map into a validated MATLAB config; do not
   manually create an approximately equivalent campus topology.
2. First compare deterministic controlled tests with unambiguous identities,
   packet sizes, paths, event order and known airtime. A new observation-only
   MATLAB packet key is acceptable; do not add serialized bytes for tracing.
3. Compare stochastic runs as distributions across independent replications.
   The same numeric seed in MATLAB and ns-3 does not pair their random draws.
   Report replication count, warmup/window, mean, uncertainty and effect size;
   increase replications when uncertainty prevents the intended conclusion.
4. Keep delivery ratio, packet-weighted mean latency, latency percentiles,
   goodput, retransmissions, queue drops, control traffic and PHY drop reasons
   distinct. Historical OPNET “mean of bucket delay means” is a separate metric.
5. Classify findings as structural failure, numerical difference, stochastic
   difference, or known ns-3/OPNET uncertainty. Structural failures block the
   relevant tranche. Record small differences and continue integrated work.

Before T2 is complete, missing MAC/HOP behavior is “not yet implemented,” not
a numerical tolerance. Before T3 is complete, configured direct destinations
are not autonomous route discovery. OPNET `.ov` evidence cannot prove same-time
packet ordering; no unavailable OPNET event trace is a baseline gate.

## Current inherited residuals and later campus baseline

The latest publication includes rejected-preamble acquisition and third-ACK
window-growth fixes. The proposed BER interval/Track experiment was explicitly
excluded; initially port the retained current PHY/ECC behavior.

The final published two-fix candidate's historical 6,000-s multihop run reports
2.06950 sent packets/s, 1.96150 received packets/s and 103.18101 s mean of bucket
delay means. Relative to OPNET these are +2.86%, +3.15% and -8.49%. All 800
application point identities aligned, 780 numeric points were compared, 641
were numerically unequal at zero tolerance, and 20 authoritative missing values
were preserved. All 11,769 internal ns-3 deliveries matched send identities and
sizes. These are useful reference values, not current MATLAB acceptance targets.

The canonical historical multihop configuration uses seven nodes
`[1,2,3,4,5,7,8]`, gateway 1, six fixed flows to gateway 1, seed 128, 6,000 s,
application `legacy-send-only-no-dscp`, MAC
`hist-2014-next-tslot-modulo-probe`, and security `hist-adb97c54-bare`.
Publication provenance contains hashes for the imported scenario and the
external `.ov`/`.pb.m` media. Those media are not included in this source
checkout. Recover the exact inputs when reaching scenario integration; their
absence does not block the direct-transfer foundation.

The 60,000-s hidden-node case was not rerun for the final two-fix publication.
The historical three-fix experiment's large ECC-drop discrepancy must not be
attributed quantitatively to the published candidate. Retain an unresolved
PHY/ECC-attribution entry; do not tune a multiplier or threshold to fit it.
Source-version/DSCP/security profiles must stay bound to the chosen scenario.

References in the pinned ns-3 repository: `docs/opnet-residual-review.md`,
`docs/opnet-residual-review.json`, `docs/opnet-scenario-differential-harness.md`,
`docs/opnet-phy-ber-ecc.md`, and `utils/release/README.md`. Older aggregate values
inside the long-running harness document are historical checkpoints; the
latest publication record takes precedence for the current baseline.
