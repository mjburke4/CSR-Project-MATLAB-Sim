# Tranche 4 application comparison

`scripts/compare_matlab_ns3.py` compares completed MATLAB and ns-3 runs of the
same canonical fixed-flow scenario. It reports application generation,
delivery and latency by flow and packet. It does **not** certify equivalent
PHY/MAC/NWK timing, adaptive rates, routing-control counts, security, RNG
streams or OPNET results.

The five source reference cases are under
`evidence/tranche-4-ns3-reference/`. Their canonical inputs are under
`scenarios/shared/`. The 500 and 1000 kbit/s cases are separately named
extensions, excluded from an 8 kbit/s campus baseline.

## Run a comparison

After `run_tranche4_validation` has actually completed in MATLAB, pass one
shared case output directory and its matching reference manifest:

```text
python scripts/compare_matlab_ns3.py --matlab PATH_TO_RUN/shared/two_node_8 --ns3 evidence/tranche-4-ns3-reference/two_node_8/manifest.json --output results/comparison/two_node_8
```

Replace `PATH_TO_RUN` with the returned `report.EvidenceDirectory` (under
`results/tranche4_validation/` by default). The `--matlab` directory must contain
`case_manifest.json`. Python 3.10 or later
is required; there are no third-party dependencies. The tool writes:

| File | Contents |
| --- | --- |
| `comparison.json` | Input manifest hashes, source/scenario/profile identity, evidence status, differences and limitations |
| `applications.csv` | Source/destination ordinal, both runtime IDs, payload/DSCP, generation time, delivery state and latency difference |
| `flows.csv` | Generation/delivery counts, delivery ratios, delivered payload bytes and mean latency |

Exit code 0 means the supplied evidence is valid. Application differences are
reported with status `application_differences`; this is not a parity pass.
With `--require-application-equality`, those differences return exit code 1.
Malformed, incomplete or inconsistent evidence returns exit code 2 in either
mode and writes an `invalid_evidence` report. An invalid run replaces previous
comparison CSVs with headers only so stale successful tables are not reused.

The optional equality gate checks the generated applications and their final
observed delivery set. It includes payload, DSCP and generation time. It does
not require equal latency: the two runtimes have different random streams and
documented protocol approximations. Every latency difference remains visible.
Even `application_match` always carries `full_protocol_parity: false`.

## Identity and byte accounting

MATLAB uses its `PacketId` to associate `app_generate`, `app_receive` and
`app_drop` records. ns-3 uses the application observation tag carried in
`sequence` on `app_send` and `nwk_delivery`. These are independent runtime
identities; a MATLAB ID is never equated with an ns-3 sequence number or a HOP
sequence number. IDs are parsed as integers without a floating-point
conversion, including values above 2^53.

After joining within each runtime, the comparator orders generations within
each `(source, final destination)` pair by time and assigns an ordinal. Ties
preserve recorded generation order. Reordered deliveries therefore remain
attached to the correct generated application. Each generation must fit a
shared flow schedule and payload/DSCP tuple. The generation-time tolerance is
one microsecond to allow decimal export precision; it is not a latency
tolerance.

For these source fixtures:

| Representation | Bytes for a 64-byte application payload |
| --- | ---: |
| MATLAB `ApplicationBytes` | 64 |
| ns-3 `app_send` / `nwk_delivery` `size_bytes` | 71 |
| Canonical scenario `flow_packet_bytes` | 79 |

The comparator subtracts 7 from ns-3 NWK application observations and 15 from
the configured scenario packet size. It never applies these offsets to PHY
frames, routing controls or aggregates.

MATLAB drops are evaluated chronologically. A late final delivery reverses an
earlier application drop; a late `relay_accept` can restore pending custody.
The computed final states must agree with the MATLAB summary. Absence of an
ns-3 delivery is labeled `not_observed_delivered`; it is not interpreted as
a terminal ns-3 application drop.

## Required evidence contract

The MATLAB manifest schema is `csr-matlab-research-case-v1`; the ns-3 schema
is `csr-matlab-ns3-reference-case-v1`. Both require:

- `status: completed`, `execution_completed: true` and
  `source_files_stable: true`.
- `scenario_sha256`, `ns3_source_commit`, `flow_limit`,
  `application_profile`, `mac_profile`, `hop_security_profile` and
  `run_options`. These fields must agree across runtimes. The source pin is
  exactly `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.
- A `files` array of relative `path` and raw-byte `sha256` entries. Every
  listed file must exist and hash correctly. Trace entries require
  `row_count`, excluding the header. Other CSV row counts are checked when
  present. Paths cannot escape the case directory.
- A hash-bound copy named `scenario.csv` whose actual hash matches the
  declared scenario identity.

MATLAB additionally requires `protocol_trace.csv` and `summary.json`.
`Statistics.Generated`, `Received`, `Dropped`, `Pending` and
`ApplicationBytesReceived` must match the reconstructed applications.
`OmittedTraceRecords` and `OmittedPhyTraceRecords` must both be zero.
`Config.SharedScenario` must agree with the manifest's hash, source pin,
profiles, flow limit and run options; `Metadata.SourceCommit` and
`Config.DurationSeconds` are checked as well.

ns-3 additionally requires `trace.csv` and `app_diagnostics.csv`. Trace rows
must use `csr-differential-trace-v1` and contiguous `event_index` values starting
at zero. The application diagnostics must identify the same scenario, profile
and flows; admitted counts must agree with observed sends. The recorded
observation totals and execution exit code are checked when present. The
bundled reference manifests contain both.

The explicit runtime options for this controlled comparison are:

```json
{
  "opnetAppGating": false,
  "stochasticSyncThreshold": false,
  "dutyCycling": true,
  "opnetAlignedDutyCycle": true,
  "gatewayDiscovery": true
}
```

The importer currently creates fixed-flow, current-profile cases. These
settings do not recreate legacy application generators or establish historical
no-DSCP equivalence. Shared source hashes keep the high-rate cases distinct.

Hashes and row counts bind the supplied artifacts to their manifests; they do
not independently prove where the run executed. Completed-run provenance is
provided by each runtime's exporter. The comparator does not manufacture a
MATLAB result from an ns-3 trace or rerun either simulator. Consistent differences
in generated counts or deliveries remain diagnostics; truncated files,
unknown delivery IDs, duplicate generation/delivery IDs, malformed schemas,
nonfinite or backward times, wrong payloads and inconsistent summaries fail.

## Tool regression tests

```text
python -m unittest discover -s scripts/tests -p test_compare_matlab_ns3.py -v
```

These tests use clearly synthetic Python fixtures to exercise identity,
reordered delivery, uint64 IDs, late custody recovery, different outcomes and
evidence rejection. They are comparator tests, not MATLAB execution evidence.
