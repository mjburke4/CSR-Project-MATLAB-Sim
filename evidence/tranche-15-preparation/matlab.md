# Tranche15 MATLAB implementation

Added a paired local transport experiment for the four accepted controlled DATA/ACK-loss and relay-link-blackout cases, keeping all original source inputs and production callbacks unchanged. Each mode retains the original six output tables and264 functional checks; both modes total eight cases and528 checks.

Continuous mode preserves `(tx+duration)+propagation`. Nanosecond mode applies separate component rounding, an exactly representable integer sum, then division by1e9. It changes addressed aggregate ingress only, with no global clock or startup-phase changes. The helper rejects invalid components, inexact-range sums and selected arrivals before TX. This policy is tested in the bounded64-second fixture and is not a universal implementation of native Time conversion.

Timing records preserve actual TX operands, both policy results, selected result, exact hexadecimal and17-digit decimal encodings, and actual emitted envelope bytes/segment count/preamble/rate/power. Precision records preserve every original semantic event identity and exact scheduler time. All eight tables use explicit scalar string/numeric/uint64 schemas; each case is saved under c1 through c4 before aggregation.

Eight independent MATLAB tests cover the owner-observed one-ULP pattern, component-rounding distinction, true before/tie/after ordering, unchanged scheduler insertion order, zero and64-second boundaries, exact-integer bound and rejected inputs. The focused suite now has117 methods. MISS_HIT parsed all four new MATLAB files successfully. MATLAB execution remains pending on the owner's machine.

Legacy release events retain app_id0, so release metrics must be limited to actual callback counts/time series and NSDP/custody state; no per-identity release latency is claimed. Whole-trajectory native comparisons retain the original1ns tolerance for compatibility; exact precision comparisons remain separate.
