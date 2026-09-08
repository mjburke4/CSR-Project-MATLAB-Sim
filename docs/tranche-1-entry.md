# Tranche 1 entry — integrated PHY, channel and traffic

Readiness checked 2026-09-08. A fresh read of remote ns-3 `main` resolved to
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, matching the inspected checkout.
Recheck before implementation if work resumes after this checkpoint.

The owner's MATLAB R2025a 25.1.0.2943329 rerun passed all 24 foundation tests
and completed the controlled scenario: six generated/transmitted/received,
zero dropped/pending, 384 application bytes, delivery ratio 1, mean latency
1.1138 s and goodput 307.2 bit/s. This satisfies the portable T0 runtime gate
on that installation. The supplied console transcript is the evidence; this
workspace did not execute MATLAB or inspect the generated result files.

## Working endpoint

Run a configured multi-node network through source-backed CSR propagation,
received power, modulation tables, interference, interval error allocation and
ECC. Include the 8-kbit/s baseline plus separately selected 500-kbit/s DPSK and
1-Mbit/s DQPSK cases. Retain the controlled channel for isolated regression
tests and label it explicitly. Reliable MAC/HOP and autonomous routing remain
subsequent tranche endpoints.

**Critical next change:** replace the destination-only
`Simulation.transmit` → `ControlledChannel.evaluate` path with physical signal
fanout to eligible peers and a per-receiver active-signal lifecycle. A peer
can contribute interference or observe a signal without being its application
destination. Track receive start, preamble end, interference changes and
receive completion; distinguish physical reception from application delivery.
A single independent packet-loss draw cannot express this source behavior.

## Source boundaries and parallel ownership

Reuse the detailed [source map](../evidence/source-map.md) and
[compatibility assessment](compatibility.md); no new architecture study is
needed before implementation.

| Workstream | Exact reference boundary in pinned ns-3 source | Deliverable |
|---|---|---|
| PHY/channel | `model/csr-phy-model.h`: `HasClosure`, `ComputeFrontEnd`, `CalculateBer`, `AllocateErrors`, `EvaluateEcc`, `EvaluateAllocatedRx`; `model/csr-opnet-ber-tables.{h,cc}` and `csr-opnet-ber-tables-data.inc` | Release-independent radio configuration and pure calculations, preserved table samples, interval errors and explicit acceptance/drop diagnostics |
| Signal integration | `model/csr-net-device.h`: `SendFramesToPeers`, `BeginReceiveSignal`, `EndReceivePreamble`, `CloseSignalInterval`, `CloseAllSignalIntervals` | Portable all-peer transport, bounded active signals, overlap accounting, receiver eligibility/acquisition boundary and final delivery callbacks |
| Traffic/packets | `csr-opnet-scenario-runner.cc`: `SendFlowPacket`; `model/csr-wire-format.h`, `csr-opnet-packet-model.cc`, `csr-opnet-envelope.h` | Extend existing scenario/packet structs with explicit radio/profile fields and traceable application versus physical byte counts; maintain periodic generator attempts |
| Native MATLAB adapter | R2026a `wnet.Node`/`wirelessPacket` contracts already recorded in `compatibility.md` | Optional adapter translating the same CSR core events/frames into native simulator scheduling and packet distribution; keep simulator IDs separate from CSR addresses |
| Differential/QA | `csr-phy-front-end-smoke.cc`, `csr-phy-ber-ecc-smoke.cc`, `csr-live-high-rate-dqpsk-smoke.cc` | Independent golden vectors, deterministic integrated fixtures, trace/counter reconciliation, then matched statistical comparisons |
| MAC/HOP preparation | Current MAC core/device receive states and HOP send/ACK ownership; `csr-mac-receive-contention-smoke.cc`, `csr-hop-mac-sent-time-smoke.cc`, `csr-ack-window-smoke.cc` | Prepare T2 state/queue/ACK contract and fixtures while PHY develops; define actual-TX completion, carrier/acquisition and receive callbacks with the integration owner |

The PHY calculation and table work, adapter, and QA fixtures can proceed in
parallel. The integration owner must settle receiver-state ownership with the
MAC/HOP specialist early: do not implement competing acquisition state
machines. T1 needs enough receiver state to validate its PHY pipeline; slot
access, reservations, ACK/DACK and retries belong to cohesive T2 integration.

## Decisions to preserve

- Match the **retained current ns-3 PHY/ECC**, including its interval-boundary
  behavior; the reverted BER/Track experiment is not the baseline. Keep the
  unresolved OPNET attribution issue in the parity ledger.
- Use the source's minimum-gain propagation rule, band-overlap fraction and
  linear-watt noise arithmetic. Keep same-rate spread interference distinct
  from different-rate additive noise, and retain the documented high-rate
  jammer-as-noise extension.
- Preserve the seven exact bit rates and long/short airtime already implemented.
  The 500/1000 rate pair is explicit extended-profile behavior; no rate or
  security profile may be inferred from a topology name.
- Preserve exact BER table samples, including the recovered DQPSK low-SNR tail;
  carry forward the documented off-grid interpolation approximation. Convert
  the committed data reproducibly with source hashes instead of hand-copying it.
- Exclude preamble bits from error allocation, protect fixed header plus
  payload/FCS, and preserve inclusive ECC acceptance and earlier-rejection
  precedence. Do not replace interval allocation with an unrelated aggregate
  PER model or tune ECC to an OPNET aggregate.
- Declare `ApplicationPayloadBytes` separately from historical imported size:
  upstream `packetBytes=200` means 185 application bytes. Keep production
  security-envelope overhead and bare fixture profiles explicit; full security
  processing and NWK admission gates remain later work.
- Keep the portable backend available on both releases. R2025a's reported
  wireless symbols are absent on the tested installation. Native integration
  must be optional, with no `wnet.Node` dependency in CSR protocol classes.

## Runtime acceptance and remaining evidence

The prepared acceptance plan below is **not** a passed-test report.

1. Retain all 24 T0 regression tests and run new PHY/table/config tests on
   R2025a. Validate source-derived power, overlap, rate, BER, boundary error
   allocation and inclusive ECC vectors; test deterministic success/failure
   and explicit drop reasons.
2. Execute separated and overlapping multi-node transmissions, including
   non-destination interference, closure/band mismatch, both preambles and
   all supported rates. Reconcile generated, transmitted, physical-received,
   application-delivered, dropped and pending identities without double counts.
3. Repeat a scenario with the same config/seed and with tracing disabled;
   outcomes must be reproducible within the backend. Record source/MATLAB
   commits, release, configuration, profile, seed, runtime and trace limit.
4. Execute the native R2026a adapter's controlled timing/cancellation and
   packet-distribution fixtures, then the shared PHY scenario. Compare
   deterministic outcomes across backends; explicitly review same-time event
   ordering. An unavailable toolbox/adapter is recorded as untested, not passed.
5. Compare independent vectors with the pinned ns-3 fixtures first. Fresh
   executable ns-3/MATLAB differential results require both runtimes; inherited
   ns-3 publication results and source-derived constants are labeled separately.
   For stochastic tests compare matched ensembles, not packet identity from
   identical numeric seeds. Structural failures block acceptance; bounded
   numerical/stochastic issues enter the ledger.

R2026a execution, native simulator integration, real CSR PHY/BER/ECC in MATLAB,
MAC/HOP, routing, and executed MATLAB↔ns-3 comparisons remain untested or
unimplemented at this checkpoint. The T0 goodput and latency are controlled
fixture results, not CSR network-performance parity evidence. Missing legacy
OPNET packet traces do not block T1.

Portable T1 acceptance and native-adapter acceptance should be reported
separately if the required R2026a installation is unavailable; useful portable
development can continue without claiming completion of the native adapter.
The next integrated subsystem is T2 MAC/HOP reliability. No implementation,
commit, push, PR, merge or branch deletion was performed for this entry check.
