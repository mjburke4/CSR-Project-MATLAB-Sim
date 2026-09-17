# Tranche 16: receiver timing across seeds and real network workloads

Tranche 15 completed its focused MATLAB R2025a diagnostic: 117 tests, eight paired loss cases and 528 structural checks passed. In its DATA-loss case, the local nanosecond transport fixture removed five extra transmissions, four extra feedback envelopes, seven random draws and eight blocked admission polls. A constant 28 ns offset and explicit DACK observation/classification differences remained. That result supports a broader experiment; it does not establish a default timing policy for the network simulator.

## Experiment

Run the existing two-node admission workload for 1200 simulated seconds and the existing three-node contention workload for 360 seconds at seeds 128, 129 and 130. Run each workload with continuous receiver timing and the optional nanosecond receiver timing policy: six unchanged inputs, twelve simulations and 9360 simulated seconds in total. Each continuous/nanosecond pair shares the same configuration and seed.

These are the real NetworkSimulation workloads with autonomous discovery/admission, learned routing, application generation, MAC/HOP/NWK processing and the CSR packet-level PHY. No neighbor, route, delivery or queue state is installed to obtain a desired outcome. The original native reference runs are reused with their exact scenario and artifact bindings. Independent MATLAB and native random streams make aggregate and paired outcome comparisons appropriate; this is not a packet-by-packet native replay.

The original workload horizons and continued traffic are retained. Outstanding application and protocol work at the horizon is measured as pending, rather than forced to drain or treated as unexplained loss. Neither universal delivery nor improved performance is a prerequisite for a structurally complete experiment.

## Timing policy and default behavior

The new option is explicitly injected into the simulator constructor. Existing calls without a timing object retain the continuous implementation. The candidate changes two existing integration files, NetworkSimulation and SignalEngine, and adds a TransportTiming helper. The reviewed Tranche 15 installation is preserved separately.

Continuous observations preserve the SignalEngine's original expression order: `tx + propagation`, `tx + propagation + preamble`, and `tx + propagation + duration`. This order differs from the controlled Tranche 15 fixture and must not be silently replaced by that fixture's expression.

The optional nanosecond policy rounds the actual TX time, propagation delay, preamble duration and aggregate duration individually to nearest integer nanoseconds, adds the relevant integer components, then divides once by 1e9 for each scheduled receive start/preamble-end/end callback. Every component and sum must be exactly representable within `flintmax`; negative/nonfinite inputs, an arrival preceding actual TX, invalid ordering or exhausted audit capacity fail explicitly before SignalEngine state/event mutation. The policy does not clamp an invalid time to hide it.

Physical signal start/end/preamble fields and PHY/header/ECC formulas remain unchanged. Receive processing observes actual callback time in the optional policy. Transmit completion, MAC opportunities, acquisition timers, scheduler behavior, startup phase and random-number algorithms remain unchanged. This is an experimental receiver callback policy, not a universal emulation of ns-3 Time or a global nanosecond clock.

## Observations and gates

The runner exports the actual configuration, application/admission accounting, protocol/PHY observations, aggregate performance, ACK rate/power decisions and a bounded receiver timing audit for every run. Detailed ACK-service observation uses the declared early-traffic window [300, 320) seconds; full-run traffic and receiver timing accounting remain available separately. Timing audit operands, physical targets, scheduled targets and shifts preserve binary64 values with full-precision decimal and hexadecimal exports, and retain exact aggregate transmission identities.

Structural checks require complete cases, consistent actual input identities, valid application/physical accounting, bounded pending state, finite summary measures, no silent trace omission and valid timing arithmetic. Numeric comparisons remain visible whether they improve, worsen or stay unchanged. Paired changes in delivery, latency, admission wait, retries, ACK overhead, DACK-held capacity and final pending work determine the next decision.

The return checker validates the ZIP inventory and hashes, all executed MATLAB test names/results, candidate/source/reference identities, the two-file integration change allowlist, full-precision timing records and the native reference bindings. Existing selected MATLAB regressions remain part of the owner run. Python reviews the returned evidence; it does not replace MATLAB simulation or runtime tests.

## Completion and next gate

Preparation and static checks do not establish MATLAB execution. The owner runs `report = run_tranche16_validation;` and returns `t16.zip`, including partial evidence if a failure occurs. Run folders and case names remain short, and progress includes completed pairs and observed elapsed time.

The candidate does not claim campus-network, routing-reconvergence, PHY/ECC or OPNET parity. Following review of these multi-seed results, the planned release gate is the unchanged 6000-second campus benchmark plus full regression. Promote any default timing change only when those outcomes and retained regressions support it.
