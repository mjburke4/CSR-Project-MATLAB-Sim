# Tranche 10: contention timing and campus regression

This candidate corrects two source-confirmed MAC timer differences and prepares
the next full campus comparison. It is based on accepted Tranche 9 publication
`386f669f369f90b18d1d553db85b017b0ca8c77c`; the executed R2025a baseline remains
`99fff0381fe9621ccd76fbdce41eac9aba5a9469`. The authoritative ns-3 main was
rechecked and remains `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.

## Changes and their purpose

1. An idle RTS must use a strictly future slot boundary. In binary floating
   point, `15 * 0.013` divided by `0.013` can fall just below 15, causing the old
   calculation to schedule the RTS at the current instant. The corrected MAC
   advances the grid index when the computed boundary is not in the future.
2. Repeated addition of the 13 ms slot period can move a nominal `.312` tick
   to `.31200000000000017`, changing its order relative to a receiver transition.
   The MAC now computes eligible slot ticks from one integer-nanosecond epoch
   and an integer tick index, matching native timer precision for this clock.
   Idle cancels the epoch; Search/Track/Tx retain it. Custom non-integral-ns
   periods and times outside the exact integer range retain the continuous
   scheduling path. The global scheduler, propagation and PHY clock are unchanged.

The idle RTS guard retains double grid products, and other timers retain their
existing representation. It guarantees a future boundary in the exercised
cases; it does not establish exact ordering for every idle-RTS/periodic-wake
tie. The recurring slot correction has the narrower tested epoch/FIFO scope.

The only existing simulator behavior file changed is `+csr/+mac/Layer.m`.
RNG streams, slot-selection policy, PHY/ECC, ACK rate/power selection, HOP
capacity release and canonical scenario inputs are unchanged.

## Evidence prepared here

The fresh native build uses the exact recorded engine commit
`6b5cd24ea80713ce16d88575869aedd6f432bdae`, GCC 13.3 and C++23 Debug. Its nine
modules, source/header hashes, commands and closed logs are bound in
`evidence/tranche-10-native-build.json`. These are freshly built libraries;
byte identity with historical libraries is not asserted. The unchanged
Tranche 9 native ACK contract reproduces all 101 accepted checkpoints byte for byte.

All six retained native diagnostics also reproduce the 24 accepted application
artifact pairs, 12 observer on/off pairs and all 182,429 Tranche 9 service rows
byte for byte with the fresh engine. A first output set was rejected for an
inventory/hash mismatch. A fresh isolated run passed, and its closed archive
passed all 125 output hash checks; the rejected-set record and recovery are
preserved in `evidence/tranche-10-native-compatibility.json`. The cause of the
first artifact failure remains unestablished. This is native-build compatibility,
not a Tranche 10 MATLAB result.

- MAC: **279 native checkpoints in 15 fixtures**. Coverage includes seven idle
  boundary arrivals, initial Search/SYNC/Track, busy intervals, both insertion
  orders of a simultaneous receiver transition, and an Idle restart. Receiver
  states and neighbor occupancy are prescribed; this is a subsystem contract.
- Receiver: **154 native checkpoints in four fixtures**. Fixed transmissions
  exercise acquisition before/at/after a periodic wake and cancellation by
  sleep followed by acquisition at the next wake. Source BER/ECC remains active;
  stochastic SYNC sampling is disabled explicitly. This is controlled RF timing.
- The matched MATLAB contracts and focused regression tests are prepared.
  **MATLAB and Octave have not been executed here.** Static/native checks do not
  establish owner portable acceptance or a numerical improvement.

See the source audits and `evidence/tranche-10-local-checks.json` for actual
checks, and `docs/tranche-10-review.md` for the independent gate.

## Owner milestone

Run `report = run_tranche10_validation;` in the new package. The default gate
executes all portable tests once, the three contract families, 29 retained
scenarios, 18 load/recovery sweeps, the same six Tranche 9 diagnostics, two
tracing controls, and the original 6,000-second campus case at seed 128.
It exports complete accounting, raw observations, source/reference hashes,
closed logs and `tranche10_evidence.zip` using short paths.

The campus test previously took approximately 72 minutes; the Tranche 9 small
gate took approximately 24 minutes. Allow roughly 1.5–2 hours for the combined
run, with machine-dependent variation. The runner announces campus start and
prints completion after the simulator returns. The new changes have no
measured runtime improvement yet.

The return reviewer compares small cases with accepted Tranche 9 and pinned
ns-3, retained cases/sweeps with accepted Tranche 7, and campus with accepted
Tranche 7, pinned ns-3 and archived OPNET aggregates. No new OPNET execution is
claimed. Bounded campus admission-trace omissions are reported while full
admission counters remain required.

## Remaining limits

The seed-129 initial slot draws still differ: MATLAB source nodes 2/3 choose
9/1 while ns-3 chooses 3/7. Identical seed numbers do not align their random
streams. Native and MATLAB early receiver acquisition follows the same rule;
the first sender and its start time differ. The timing fixes may change later
event sequences, but they do not by themselves resolve the 510-versus-353
source-2 delivery gap measured in Tranche 9.

After the owner run, inspect changed early events and campus per-flow results
before choosing another protocol correction. A matched exogenous contention
experiment or a wider seed study may be warranted if the gap persists.
Periodic-wake behavior inside an existing awake window, outage/retry limits,
unexercised relay/DACK link states and R2026a/native packet transport remain
separate investigations. No universal parity or worst-case bound is claimed.

No remote push, PR or merge is part of this handoff. Previous runner entry
points remain available in this package, but they execute the new MAC; retain
the accepted old package when reproducing its exact results.
