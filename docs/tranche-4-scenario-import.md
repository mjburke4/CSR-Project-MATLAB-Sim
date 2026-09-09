# Shared ns-3 scenario importer

`csr.scenario.importNs3(path, options)` reads the frozen ns-3 runner's
`csr-opnet-scenario-v1` CSV into the portable autonomous MATLAB network stack.
The initial contract supports explicit `current-send-only`,
`current-fine-free-slot`, and `production-pairwise16` run profiles. The deprecated
ACK-envelope alias may be empty or agree with that security profile. Legacy
application generators and archived MAC/security tuples fail explicitly.

```matlab
config = csr.scenario.importNs3('scenarios/shared/two_node_8.csv', ...
    struct('FlowLimit',3,'Backend','portable'));
result = csr.runScenario(config);
```

`FlowLimit` is a positive integer cap applied independently to every fixed flow;
its default is 3. `Backend` is `portable` by default or `wireless-clock` for the
optional adapter. Unknown options are errors. Importing does not execute or
validate the optional backend.

## Exact shared input and mapping

The importer records the exact raw CSV SHA-256, canonical path, frozen source
commit `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, profiles and run options in
`config.SharedScenario`. These identify the imported input; they do not assert
that MATLAB and ns-3 have equivalent network output or identical random draws.
The standard MATLAB JVM computes SHA-256 without normalizing the source bytes.
The shared synthetic fixtures use the explicit original-source label
`synthetic-shared-scenario-v1`; this is retained as `OriginalSourceLabel`, with
`OriginalSourceSHA256` empty. It is not represented as an OPNET archive digest.

| Canonical field | MATLAB mapping |
| --- | --- |
| `duration_s`, `seed` | `DurationSeconds`, `Seed`; source seed range 1–4294944442 |
| `node_id`, `node_type` | Node ID and capability ordinary=0, routable=1, gateway=2 |
| Ordinary node | Transit forwarding disabled |
| `x_m`, `y_m`, `height_m` | Position `[x y height]`; antenna TX/RX heights preserved |
| Fixed `min/max_speed_kbps` | Radio rate and NWK local INFO minimum/maximum |
| Fixed `min/max_power_dbm`, `link_margin_db` | Radio power and NWK INFO in tenths of a dB |
| `ecc_threshold` | Receiver ECC fraction in [0,1] |
| `rx/tx_frequency_hz` | Radio receive/transmit base frequency |
| `flow_packet_bytes` | Application payload = configured bytes − 8-byte br_app exclusion − 7-byte NWK header |
| `flow_dscp` | DSCP integer 0–7 |
| `coordinate_scale_m_per_unit` | Provenance only: `x_m`/`y_m` are already meters |

Node construction is sorted by ID, as in the reference. Flow order follows the
CSV. The importer accepts fixed rates 8, 16, 32, 64, 128, 500 and 1000 kbps;
the last two are explicitly marked as high-rate extensions. Every node must
have the same fixed rate, fixed power, margin and height because the current
MATLAB NWK configuration has one shared local INFO template. Power and margin
must be exactly representable in tenths of a dB. Uniform height preserves the
reference's horizontal link distances while MATLAB uses 3-D coordinates.

The channel uses real CSR packet-level PHY: OPNET three-path propagation,
Earth line-of-sight closure, 1-MHz transmit/receive bandwidth, source noise and
antenna defaults, and deterministic SYNC threshold. No closure delegate, fixed
path, receive-erasure rule or preloaded route table is introduced. Gateway
startup discovery begins at 10 seconds for 30 seconds; duty cycling is aligned
to first wake at 0.988 seconds. Adaptive link control is disabled for this fixed
operating-point comparison. Security remains the accepted production envelope
and admission behavior model, without cryptographic execution.

## Matching reference execution

The ns-3 runner must use the same CSV and `--flowLimit=N`, with:

```text
--opnetAppGating=0 --stochasticSyncThreshold=0
--dutyCycling=1 --opnetAlignedDutyCycle=1 --gatewayDiscovery=1
```

The CSV duration supplies the stop time; a reference `--stop` override is not
part of this importer contract. Disabling application gating makes the fixed
offered schedule explicit; it does not reproduce the historical br_app
discovery/route/NSDP admission gate or its dynamic destination selection.

Only sends before the stop time are counted, up to the cap. A repeated send
exactly at stop is excluded because ns-3's previously scheduled stop event wins.
A first send exactly at stop is rejected: the source creates that event before
the stop event, so it has different ordering from a repeated send. A start
after stop yields zero packets. Times must fit exact nanoseconds within the
portable integer range. Timing comparisons still need a numerical tolerance
because MATLAB schedules double seconds while ns-3 stores integer nanoseconds.

## Rejected inputs and validation boundary

Unknown populated fields, populated fields on the wrong row type, unknown row
records, missing/duplicate run rows, duplicate node IDs/names, invalid endpoints,
malformed numbers/CSV, TMM terrain, forced reservations, dynamic flows, adaptive
rate/power ranges and historical profiles fail before simulation. Unknown empty
columns are harmless. CSV text remains text throughout parsing; quoted commas,
escaped quotes and CRLF input are supported without table type or shape inference.
The frozen ns-3 line parser does not consistently accept CRLF; the reference
bridge therefore requires LF input, as supplied by all committed shared cases.
Changing line endings changes the raw scenario hash and requires a new reference
execution before comparison.
Decimal integer fields cannot contain leading zeroes, hex, exponent or decimal
point syntax, avoiding the reference's base-0 unsigned parser ambiguity.

`TestNs3ScenarioImport` covers configuration mapping, raw provenance, packet
byte exclusion, stop boundaries, text/shape handling, explicit high-rate labels
and unsupported-input rejection. MATLAB execution remains an owner runtime gate;
static checks alone do not establish an R2025a/R2026a pass.
