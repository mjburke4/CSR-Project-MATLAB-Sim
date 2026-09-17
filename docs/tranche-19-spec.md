# Tranche 19: queued retry expiration and campus admissions

The practical target is agreement within a few percent, rather than exact stochastic numerical equality. T19 uses a descriptive ±5% band for total and per-source admitted/delivered applications. Structural correctness, ownership accounting and regression remain required. A number outside the band is a measured residual, not a failed simulation.

T17 already delivers within 0.48% of native ns-3 in total, while source 4 is 16.95% low and source 5 is 20.09% high. T18 did not establish a local-DATA priority defect. Its full-campus prefix shows the opposite source 5 difference, and existing full-run evidence shows repeated changes in direction. Therefore T19 retains the original 6,000-second campus history.

## Experiment

Two fresh MATLAB runs use the original seven nodes, six offered flows, geometry, waveform/PHY/ECC, real interference, autonomous routing, seed 128 and continuous timing. Application traffic begins at 300 seconds and continues at the original offered interval. Each simulation stops at 6000 seconds; there is no queue drain or artificial late-window restart.

- `a128`: existing `actual-tx` policy. A queued retry waits for actual MAC transmission before its next retry deadline becomes active.
- `p128`: experimental `native-provisional` DATA policy. Initial transmission still requires actual confirmation. A queued retransmission retains confirmation and a provisional timestamp; existing global retry scans can process or expire it before that retry transmits. Native-inspired unmatched-DATA sent fallback scans are included as documented in the policy audit.

The experimental option concerns DATA timing. CONTROL retry confirmation, MATLAB terminal cancellation and transactional overload remain their accepted implementations; this is not a claim of complete native HOP equivalence. The default remains `actual-tx`.

Identical MATLAB input and seed permit a within-engine policy intervention. Changed event history can change subsequent random-number consumption, so this is not packet-by-packet common-random-number coupling. One full seed establishes only the observed effect. A further full-seed confirmation is appropriate if a worthwhile improvement appears.

## Evidence and comparisons

Full portable tests include deterministic retry-clock/capacity cases and all retained top-level test classes. The two campus cases retain complete protocol and PHY exports. The existing 100,000-row admission prefix is intentionally bounded; total/per-flow attempted, admitted and blocked counters and all admitted-application identities cover the full run. Late blocked-reason timelines cannot be inferred from the missing attempt tail.

The reviewer reconstructs DATA capacity from ordered HOP admission, ACK, failure, DACK and DACK-expiry events, and NWK custody/NSDP from enqueue and release events. It checks nonnegative ownership and endpoint agreement. These are event-derived states; they do not expose unobserved queue scans. DATA retries, actual transmissions and terminal-before-transmission outcomes remain distinct.

The default run must reproduce the accepted T17 core raw traces and statistics. Per-source admissions/deliveries, finite-stop outcomes, delay and retry overhead are compared between policies and with the exact pinned native campus evidence. Whole-run and 300-second timeline windows reveal changes over time; the retained historical aggregate exports use their original 60-second buckets. Numerical improvement must not be claimed from the total alone, or by hiding other flows, terminal loss, or pending custody.

## Provenance and runtime

Native main was inspected and remains `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`, with engine `6b5cd24ea80713ce16d88575869aedd6f432bdae`. The existing native full-campus reference remains applicable; this preparation does not execute a new native simulation. The repaired T18 owner return and acceptance are preserved in `evidence/t18`.

Each completed MATLAB stage is sealed independently. Reuse requires the same candidate, source files, reference files, MATLAB runtime and output bytes. A partial simulation is never resumed. Tests, default and experimental cases can run separately.

Based on the owner's T17 run, allow roughly 2–2.5 hours for the pair, plus tests/export overhead; system load and experimental behavior can change runtime. MATLAB is not available in the preparation environment. Python checks and MATLAB static analysis are preparation evidence only; owner MATLAB runtime validation remains pending.

## Decision after return

Adopt a retry-policy change only if a localized mechanism is confirmed and the full-campus comparison shows useful per-flow progress without material custody/reliability regression. If the effect is small, inconsistent or harmful, retain the accepted policy and record the remaining difference as a practical parity exception. PHY/ECC, battery, supervisory behavior and BBN routing are outside T19.
