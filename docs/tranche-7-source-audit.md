# Tranche 7 source and benchmark audit

Current source `mjburke4/CSR-Project-NS3-part2/main` was rechecked on
2026-09-10 at `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, tree
`b611b233fb369569b98f0914ece24d029ccc2f42`. The retained ns-3 engine is
`6b5cd24ea80713ce16d88575869aedd6f432bdae`. Original campus inputs came from
`CSR project examples(3).zip`, SHA-256
`5ae5a14ba36918e19d274a9f2385eb00dd9b63de518b72b728fc373a29be5b73`.

The canonical campus CSV hash is
`90b143d93c13c6c2761bc5f2875ccc3fff98f85af6f2550370e435df2aaabcfc`.
The archived vector output hash is
`b643bee5c1d0260581a0135c0add5c87441bd98f70f66388fac0bf95096c39ee`.
Original inputs and compressed executables have individual hashes and
archive-member mappings in `evidence/tranche-7-benchmark-inputs/manifest.json`.

## Bounded implementation contracts

| Contract | Pinned source mechanism | MATLAB implementation |
| --- | --- | --- |
| Campus input | `utils/import-opnet-scenario.py` and original network/experiment files | Explicit historical importer preserves seven IDs, six flows, 6,000 s, seed 128, coordinates and radio limits |
| Generator | `examples/csr-opnet-scenario-runner.cc` application interrupt and admission code | Pre-admission interrupts; discovery, raw topology, destination/gateway, then local source/destination NSDP count below 16 |
| Gateway cache | First successful gateway capability scan retained per flow, even if NSDP blocks that attempt | `ApplicationGenerator` stores the selected gateway without subsequent route revalidation |
| Dynamic destinations | Raw route/neighbor candidates after discovery and topology gates | Stable source IDs, traffic RNG draw only when a candidate selection occurs |
| Timing | Integer nanosecond ns-3 scheduling; recursively posted stop-time interrupts excluded | Exact nanosecond input validation, rounded tick scheduling, admitted caps separate from attempt limits |
| Campus slot selector | `hist-2014-next-tslot-modulo-probe` in `model/csr-mac-core.h` | Local qualified population, coarse range, inclusive initial draw, direct-counter modulo probing |
| Active population | `CsrNwkLayer::GetActiveNodeCount` counts persistent peers with `lastHeardSec >= 0`, plus self | Read-only persistent qualified-neighbor observation, including expired entries; excludes passive-only peers |
| Historical envelopes | `hist-adb97c54-bare` executable-bound DATA/ACK path in HOP/NWK headers | Atomic bare DATA/ACK size profile; production control/security lifecycle remains modeled |
| Statistics | `utils/aggregate-ns3-trace.py` and `utils/extract-opnet-ov.py` | Eight common application series; exact bucket identity, size convention and missing values |

The campus executable SHA-256 is
`adb97c54f7566439f1404e972d3d777a3bca613e2a965bf12f03353fb009d9af`.
Its application profile is `legacy-send-only-no-dscp`. Configured packet
size 200 excludes the legacy eight-byte application wrapper and seven-byte
NWK header before payload creation. Thus payload=185, common measured
network packet=192 and bare DATA over air=217 bytes. Bare cumulative ACK/DACK
is 41 bytes and exact ACK is 25 bytes. Control layouts and real cryptography
are not inferred from these DATA/ACK sizes.

Uniform campus limits remain **8–128 kbps, −36–33 dBm and 12 dB margin**, with
400 MHz, one-meter antennas and ECC threshold 0.1. The importer enables the
existing adaptive MATLAB link policy; it does not clamp the workload to
8 kbps or change the validated physical equations to fit old measurements.

## Actual reference observations

Fresh campus raw trace hash
`b5d4a7fd8da818c8581a73bef52ab8f98ced815f821745350e8f95c7c7f02722`
and aggregate hash
`d0b37516ba57ce76fc5692ce295dc4bed65e0654e9849a9e5b087d164f8870b1`
match the earlier publication byte for byte. The standalone runner was
recompiled using verified source headers and preserved engine libraries.
A missing build symlink was restored only after the 48 preserved build
inputs matched their recorded hashes. A damaged packaged two-node gzip was
replaced from the same execution identity and verified uncompressed hash;
the recovery record and final inventories preserve that distinction.

| Campus common measure | ns-3 | Archived OPNET | Relative difference |
| --- | ---: | ---: | ---: |
| Mean sent rate (packets/s) | 2.06950 | 2.01200 | +2.86% |
| Mean received rate (packets/s) | 1.96150 | 1.9016667 | +3.15% |
| Mean of populated bucket delay means (s) | 103.18101 | 112.748 | −8.49% |

The delay row is a mean of populated bucket means, not the packet-weighted
global delay. The exact comparison has 800 aligned identities, 780 numeric
points and 641 unequal numeric values; 20 OPNET points are authoritative
missing samples. Compare exit 1 records these expected residuals. Extraction,
execution and ns-3 aggregation each completed successfully.

## Known model differences retained

MATLAB's HOP reverse ACK/DACK builder currently copies the received data
rate and uses the node's configured transmit power. Current ns-3
`SendAck`/`SendDack` calls `ApplyLinkControl` separately for the reverse peer.
MATLAB NWK DATA/control selection uses local fixed S0 plus pathloss and NWK
failure observations; source HOP uses advertised peer S0 and HOP failure
state. Matching radio limits does not establish matching feedback control.
This candidate does not silently fill in that larger policy implementation.

Separate RNG implementations also prevent equal seeds from implying equal
packet histories. Retained queue/custody and retry-timing differences are
listed in `parity-ledger.csv`. T6 ordinary DATA exhaustion has no generic
route invalidation/requeue policy in either source; its qualified outage
acceptance remains unchanged. Stop-time undelivered packets and pending
controls must retain their observed classifications.

The historical selectors and envelope sizes are tested components, not a
claim of complete historical executable emulation. MATLAB runtime evidence,
full campus outcome comparison, R2026a and native execution remain pending.
PHY/ECC and BER data stay byte-identical to the T6 baseline. Battery,
supervisory behavior and BBN routing stay outside the project baseline.
