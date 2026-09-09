# Tranche 4 research scenarios

`csr.scenario.researchNetwork(name)` constructs a synthetic research scenario
for the existing autonomous MATLAB CSR stack. These layouts are not imported
OPNET campus scenarios. The factory supplies configuration and hypotheses;
MATLAB execution and measured results are separate evidence.

| Name | Nodes / layout | Default seconds | Application workload |
| --- | --- | ---: | --- |
| `two_node` | Two nodes, 100 m separation | 300 | Five packets to gateway |
| `line_4` | Four nodes, 3.8 km spacing | 600 | Five packets from far endpoint |
| `hidden_node` | Gateway between sources at +/-3.8 km | 600 | Eight packets per source, simultaneous application start |
| `mesh_6` | 3 by 2 rectangle, 3.8 km spacing | 900 | Three flows, five packets each, DSCP 0/8/16 in current profile |
| `route_recovery` | Three-node line, relay receive blackout | 900 | Five packets spanning the blackout and recovery |
| `leaf_no_transit` | Three-node line, middle node refuses transit | 600 | Five packets from far endpoint |
| `high_rate_500` | Two nodes, 100 m separation | 300 | Five packets, fixed 500-kbps extension |
| `high_rate_1000` | Two nodes, 100 m separation | 300 | Five packets, fixed 1000-kbps extension |
| `long_run_6000` | Four-node line, 3.8 km spacing | 6000 | 160 packets, every 30 s from 600 through 5370 s |

The optional scalar options struct accepts exactly `Seed`, `DurationSeconds`
and `ApplicationProfile`. Duration can extend each fixture from its listed
default through 6000 seconds; `long_run_6000` stays exactly 6000 seconds. That
named workload requires explicit selection and an explicit runner opt-in. Any
ordinary fixture explicitly extended to 6000 seconds also carries
`Research.LongRunOptIn=true`, while preserving its original packet count. Seed changes
the simulator's owned random streams and leaves the process-wide MATLAB RNG
alone. The factory itself draws no random numbers.

```matlab
config = csr.scenario.researchNetwork('mesh_6', ...
    struct('Seed',981,'ApplicationProfile','legacy-send-only-no-dscp'));
result = csr.runScenario(config);
```

## RF assumptions and experiment controls

Every radio uses `OPNET_THREE_PATH` propagation, `EARTH_LINE_OF_SIGHT` closure,
400-MHz base frequency with a 1-MHz bandwidth, 1-m transmit/receive antenna
heights, 0-dB antenna gains, and the source noise and stochastic synchronization
threshold defaults. The ordinary NWK range remains 8 through 128 kbps and 0
through 30 dBm; the initial radio power is 30 dBm. Source path-loss-based link
control subsequently chooses rate and power from those operating limits. The two high-rate
fixtures fix the selected rate and use 30 dBm. They remain separate extension
experiments, including when a named legacy application profile is selected.

At 1-m antenna heights the implemented Earth-horizon closure is approximately
7.14 km. A 3.8-km adjacent link is geometrically visible; a 7.6-km two-spacing
link is closed. The modeled adjacent-link path loss is approximately 143.2 dB,
so 30-dBm transmission gives approximately -6.2-dB SNR against the configured
noise floor, around 4.8 dB above the mean synchronization threshold. Those are
configuration link-budget calculations, not measured reliability. The retained
model uses Euclidean node separation and radio antenna heights in its geometric
closure calculation; it is not a terrain, diffraction or environmental survey.

The hidden-node fixture therefore supplies the geometric conditions for two
mutually hidden senders. Application starts are simultaneous, but independent
MAC slots can avoid overlap. Collision count, capture, BER/ECC outcomes, actual
admitted neighbors and selected routes must be measured; the fixture does not
force successful reception, a prescribed route or a collision count.

All scenarios use explicit per-node discovery requests staggered at
`10 + 35*(node_index-1)` seconds. This avoids depending on the retained legacy
SNMP START message being forwarded across multiple hops: it is not forwarded
by this baseline. Discovery requests create protocol activity, and install no
neighbors or routes. Admission, routing records, ACKs and applications traverse
the CSR MAC/HOP and PHY. No closure delegate or general receive-erasure fault
rule is installed. Default freshness monitoring remains off, as in Tranche 3,
except in `route_recovery`.

`route_recovery` is explicitly an administrative receive-blackout experiment.
The relay is disabled at 45% and restored at 60% of simulation duration through
the existing `LinkEvents` interface. Those events erase receives at completion
while protocol timers continue; they do not move the radio or alter its RF
power. Additional per-node discovery requests occur around 35% and 64% of the
duration. Neighbor freshness is enabled with a 60-second timeout and 5-second
inspection period. The eligible receive calculations still use the CSR PHY.
This distinction is recorded in `config.Research.AdministrativeReceiveBlackout`.

`leaf_no_transit` gives the middle node capability 0 and disables its transit
policy while leaving its radio present. An admitted relay may acknowledge HOP
receipt before policy rejection. Whether admission occurs in a particular run
remains an RF outcome. The fixture has no alternate geometric path.

## Profiles, duration and evidence

`current-send-only` preserves the workload's configured DSCP values. Both
`legacy-send-only-no-dscp` and `legacy-send-to-from-no-dscp` set every application
DSCP to zero. These selectors do not claim implementation of the historical
application generators or historical gateway cache behavior.

Short workloads start after a convergence allowance and finish with at least
90 seconds of drain time. These are experimental allowances, not assertions
that all control queues become idle by the stop time. The 6000-second workload
has a 600-second warmup and 630-second final drain allowance. It is synthetic
and does not certify the 6000-second historical campus reference.

Trace storage is bounded at 100,000 protocol and 100,000 PHY records per short
run, and 200,000 each for `long_run_6000`. MaxEvents is 2,000,000 and 5,000,000,
respectively. Omitted trace counters and unfinished custody must be reported
when assessing a run. A completed simulation alone does not certify delivery,
queue drainage, trace completeness, or numerical MATLAB/ns-3 parity.

`TestResearchScenarios` checks configuration normalization, native PHY
selection, geometric link hypotheses, experiment timing, profile separation,
reproducibility of configuration construction, and rejection of unsupported
options. These tests create no claim of MATLAB runtime execution in a workspace
without MATLAB. Run the research suite and inspect its saved results on the
R2025a work machine and R2026a home machine before accepting new outcome claims.
