# Tranche 0 independent review

Reviewed 2026-09-08 against ns-3 main
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.

**Disposition: implementation ready for MATLAB runtime validation.** No remaining
blocking defect was identified in the scoped static review after the fixes below.
Neither MATLAB R2025a nor R2026a was available; this review does not establish
that the scenario or tests execute successfully.

## Findings resolved before delivery

| Finding | Resolution observed |
| --- | --- |
| The tests called nonexistent `matlab.unittest.TestCase.verifyHeight` | Replaced with `verifyEqual(height(...), expected)` |
| A one-record trace can contain an empty character field, making default scalar `struct2table` conversion invalid | Trace and node conversion explicitly use `AsArray=true`; a singleton trace and empty-scenario regression was added |
| Accepted integer storage types could affect arithmetic through integer saturation | Scenario numeric fields are normalized to doubles before simulation arithmetic |

The relevant MATLAB API contracts were checked against the official
[verification methods](https://www.mathworks.com/help/matlab/ref/matlab.unittest.qualifications.verifiable-class.html)
and [structure conversion](https://www.mathworks.com/help/matlab/ref/struct2table.html)
documentation. These documentation checks are not MATLAB execution.

## Architectural and behavioral checks

- Scheduler review covered heap growth, stable equal-time insertion order,
  callback-inserted events, cancellation, finite horizons, callback failures,
  reentrant execution rejection, and bounded zero-time loops. The corresponding
  tests exercise behavioral outcomes. Anonymous callbacks capture the intended
  flow, packet, and test-loop values; no shared loop-index closure defect was found.
- Per-node/per-subsystem streams own their state independently of the global RNG.
  The documented integer seed mapping remains within `uint64` arithmetic bounds.
  No claim of identical ns-3 random draws or statistical stream independence is made.
- Current rate intervals and the 500-kbit/s DPSK versus 1-Mbit/s DQPSK distinction
  agree with `model/csr-phy-model.h`. Airtime agrees with the S0/payload accounting
  in `model/csr-net-device.h`. The bare DATA envelope's 17 MAC, 8 HOP, and 7 NWK
  bytes agree with `model/csr-opnet-packet-model.cc`.
- Statistics distinguish generated, transmitted, received, dropped, and pending
  packets. Horizon-limited packets remain pending. Goodput uses the configured
  observation duration, and latency is packet weighted. Truncating or disabling
  tracing does not alter the event or RNG path.
- MAT, CSV, and JSON export paths are present. `table(TestResult)` followed by
  `writetable` is a documented MATLAB export pattern; detailed test diagnostics
  remain in the MAT file and validation diary. File export still needs actual
  runtime verification.
- Core files use MATLAB constructs available before R2025a. No core class inherits
  from `wnet.Node`, and symbol discovery reports availability without claiming
  toolbox licensing or adapter execution.

## Scope and remaining gate

The delivered scenario is controlled direct transport with source-backed timing
and bare-envelope size accounting. It does not implement receiver acquisition,
path loss, BER/ECC, collision handling, MAC/HOP reliability, autonomous routing,
or a native wireless simulator adapter. FIFO serialization is foundation behavior,
not a claim of CSR MAC parity. These omissions belong to the planned subsequent
tranches and should remain visible in the parity ledger.

Run `run_validation` on each available MATLAB release and preserve its generated
evidence. Run the optional wireless scheduler probe separately in a fresh session;
success there validates only that probe. Do not declare the executable tranche
accepted, cross-release compatibility tested, or MATLAB/ns-3 scenario parity
achieved until the corresponding runtime evidence exists.
