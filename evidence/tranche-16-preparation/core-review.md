# Independent T16 core review

No blocking defect was found by source inspection. MATLAB execution remains pending; this review ran no MATLAB or native simulation.

The default path preserves prior arithmetic, physical times, callback insertion and RNG use. Explicit continuous uses the actual SignalEngine operand order. The nanosecond experiment changes receiver callback targets while retaining physical fields and error-allocation formulas. Initial receive intervals begin at actual callback time, as in pinned native BeginReceiveSignal. Native relative-duration conversion and the declared T16 component conversion are deliberately distinguished; this is not a general ns-3 Time emulation.

Timing values, causal ordering and the complete observation budget are checked before observations, PHY state or scheduler events change. Exact nanosecond sums are guarded at flintmax, and FrameId stays uint64. The fixed numeric tables do not show the variable-length character-column concatenation problem seen in T14.

## Nonblocking scope note C1

`SignalEngine.transmit(frame, explicitDuration)` retains an older malformed-frame failure path: missing WirePayloadBytes can fail after Tx state changes. The T16 preflight claim should remain specific to timing inputs, causality and observation capacity. Valid production frame constructors are unaffected; broad frame-input hardening is outside this experiment.

## Test interpretation

The nine new tests cover meaningful arithmetic, ordering, failure-before-mutation, interference, half-duplex, identity and integration behavior. They remain prepared tests until the owner runs MATLAB. The 20-second integration test executes real stack and PHY logic using the existing routedNetwork closure delegate; it checks observational equivalence and actual physical activity, not completed routing or delivery.

Nanosecond tests do not directly assert error-allocation intervals on both sides of a sub-nanosecond physical endpoint. Static inspection confirms that existing physical-end bounds and native-style interval-start semantics remain intact. This is a coverage limit rather than a detected defect.
