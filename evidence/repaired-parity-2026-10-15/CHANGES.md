# Candidate mapping and validation scope

The production delta is copied byte-for-byte from the frozen executed candidate
into `diagnostics/relay-custody/node8case`; root `+csr` is unchanged. The complete
candidate manifest is `CURRENT_SOURCE_MANIFEST.json` in that diagnostic directory.
Some files differ in line endings as well as code. Existing Git attributes disable
text normalization for this directory, preserving tested bytes. Review semantic
changes with `git diff --ignore-space-at-eol` as well as the exact byte diff.

| Files | Purpose |
| --- | --- |
| `DiscoveryMembershipNwk.m` | Synchronous successful-control follow-up; explicit NWK-local DATA ownership and retry order while preserving HOP custody |
| `discoveryMembershipPreflight.m`, `RelayCustodyProbe.m` | Align public callback fixtures with separate queue scheduling ownership and ACK follow-up |
| `TerminalMac.m`, `NativePeriodicWake.m` | Preserve IdleRTS acquisition ownership; reproduce native periodic-wake arithmetic and genuine wake ownership |
| `ReceiverTimerSignalEngine.m` | Optional MAC-only receiver-state notification preserving active acquisition; existing radio calculations unchanged |
| `TerminalSimulation.m` | Wire MAC-only callback and bounded passive trace capture/export |
| `ReceiverTimer.m`, `TransportTiming.m` | Typed passive timing records and bounded export batches |
| `AckServiceDiagnostics.m`, `LinkDiagnostics.m` | Typed passive observer storage and bounded table slices |
| `PagedUtf16Column.m`, `TypedTraceBuffer.m` | Paged exact text and typed passive record storage; explicit omissions and export failure propagation |

The associated focused regressions are portable copies of the accepted public
component tests with repository-relative binding. They cover ACK follow-up,
queue ownership, wake arithmetic, retained acquisition, HOP boundary behavior,
and exact timing/trace snapshots and CSV formatting. Test-only synthetic radio
settings isolate component cases; they do not alter production PHY/ECC.

The old `run_node8_tests` manifest is deliberately not relabeled as current.
Its entrypoint now explains that it is historical and stops before starting a run.
The new component entrypoint is `repaired-tests/run_repaired_checks`.

The separately accepted complete 6000-second replay is documented in RESULTS.txt.
Its exact admitted/delivered/local-failure scope does not imply full ACK/DACK or
custody equality, and does not measure autonomous latency. The later autonomous
seed-131 result is documented separately in AUTONOMOUS_SEED131.txt: structural
acceptance passed, numerical parity failed, and seed 132 remains unlaunched due
to the disk-reserve gate. No production or portable harness change was required
for this evidence update. FOCUSED_TESTS.json retains the earlier component-run
receipt, whose autonomous pending field describes its original capture time.
