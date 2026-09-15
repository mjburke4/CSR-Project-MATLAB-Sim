# Tranche 10 mesh repair: independent review

Disposition: **no blocking findings in the reviewed repair; ready for owner MATLAB diagnostic execution.** This is a static review gate, not MATLAB execution or full Tranche 10 acceptance. The matching JSON file binds the five reviewed files by SHA-256.

The original source was read from `restore/csr10.zip`, the supplied Tranche 10 package at archive commit `87d0d69ed7f23496f711816bb0f048548366ac7c`. The review covered `Neighbors.m`, `EventScheduler.m`, their two test classes, and the new `run_tranche10_mesh.m`. Repository files were not edited by this reviewer.

## Correction and behavior scope

`Neighbors.evaluate` now compares each retry against the same absolute deadline used when re-arming it. All three demonstrated paths—key request, key update send, and overheard check—are corrected. `scheduleRetryAt` also removes the unnecessary subtract/add round trip from an existing absolute deadline. The retry policy, delay doubling, discovery reset behavior, in-flight control ownership, successful-admission gates, and stale/generation guards remain intact. Freshness, HOP retry timing, MAC slotting, PHY/ECC, and the mesh factory/configuration are unchanged.

The before-deadline branches only call `scheduleRetryAt` when `now < deadline`; therefore the private helper is not reached with a past deadline through those branches. Relative-delay callers still compute `Now+delay` once before entering it. The repair resolves the contradictory due test at exact completion, rather than imposing an arbitrary extra delay or changing the event budget.

The original arithmetic counterexample is decisive for the delivered source defect. Its occurrence in Mike's failed mesh remains unconfirmed because the uploaded log contains neither simulation time nor callback identity. The isolated mesh diagnostic is the appropriate next execution gate.

## Event-limit diagnostics

The scheduler change only enriches the existing `csr:sim:EventLimitExceeded` message with `Now`, next event time, and the last/next callback descriptions. `callback` is guaranteed to have been assigned before this error branch: the constructor requires `MaxEvents >= 1`, and the counter only advances after assigning a callback. Canceled events do not invalidate that fact. `func2str` formats existing handles without running them or consuming protocol randomness.

The pending event is still present when the exception is raised; ordering, clock state, callback count, and later continuation are unchanged. The new scheduler test checks these properties using two advancing events and then resumes the remaining work. Existing same-time-loop and callback-failure tests remain in place.

## Tests reviewed

The focused runner selects 25 neighbor tests and seven scheduler tests, for 32 tests total. Five neighbor tests and one scheduler test are new. The new neighbor tests cover all three exact-deadline defects, small fractional configured backoffs, just-before-deadline checks, future doubled-backoff scheduling, retained control completion ownership, and failed-discovery sequence preservation. Their event caps are low enough for old-code livelocks to fail promptly.

The fixture constants used to assert a rounded-down elapsed time (`started=11.013`, delays `5`, `0.1`, `0.2`, and `10`) were independently checked with IEEE-754 arithmetic. Their claimed rounding direction is correct. The tests use existing public methods and established local harness conventions; no private-field mutation or special MATLAB toolbox is introduced.

No MATLAB or Octave runtime was available. Tests were read and their assumptions checked, but this reviewer did not execute them. Root owns Python and static MATLAB validation results.

## Focused runner and failure capture

`run_tranche10_mesh` uses the original 900-second, seed-128 research mesh and its 2,000,000-event cap. Its report explicitly sets `DiagnosticOnly=true`, `FullAcceptanceGateExecuted=false`, and `NumericalParityEstablished=false`. It constructs a normal portable `NetworkSimulation` and invokes its existing run method once. It adds no simulation callback, observer, RNG stream, or periodic polling.

The runner uses existing provenance and export APIs, records its MATLAB version/release, binds source hashes before execution, checks source stability after success or failure, and preserves source/config/test logs plus a stopped-state snapshot. Accessed simulation, node, MAC, HOP, and NWK properties/methods have public getters in the reviewed classes. Capture failures are recorded without replacing the original simulation exception. Packaging excludes local MAT objects consistently with existing tranche evidence conventions; the original exception is rethrown after an attempted `mesh.zip` creation.

The output layout is short (`results/m10/r.../raw`). It does not rerun completed retained cases or campus during this diagnostic. Full Tranche 10 acceptance still requires the complete runner after the mesh issue is resolved.

## Handoff notes

- The `which` guard catches CSR path shadowing but cannot independently prove that MATLAB refreshed every class already loaded in an existing session. Use a fresh MATLAB session when loading the repaired package, or clear old objects/classes before running it.
- If another error occurs, the resulting `mesh.zip` should contain the original exception and current state. A packaging failure leaves partial files and prints their directory; the original simulation failure remains the one rethrown.
- No event-limit increase, radio-parameter change, or numerical parity claim is justified by this review.

Direct byte comparison with the original archive found zero changes across all two MAC, seven PHY, and three HOP MATLAB source files. The five reviewed file hashes are recorded in `final-review.json`; later edits require rechecking the affected finding.
