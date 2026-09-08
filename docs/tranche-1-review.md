# Tranche 1 independent engineering review

## Runtime gate follow-up

The independent reviewer checked the owner-reported R2025a 25.1.0.2943329
output against the current tests and acceptance criteria: all 72 portable
tests passed and all nine scenarios satisfy the gate. **Accept portable
Tranche 1 on owner execution evidence.** Exports and runtime source hashes
were not independently inspected; this is not a blocker. The 400 checked
original C++ vectors support sampled calculation parity; full network
comparisons and R2026a/native gates remain outstanding. See
[acceptance record](tranche-1-r2025a-acceptance.md).

## Original implementation review (before owner runtime validation)

Reviewed 2026-09-08 against current CSR ns-3 source
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.

**Disposition: suitable for a portable MATLAB runtime handoff. The review
corrections below are present in the final candidate. No default-scenario
structural blocker was found by source and static review. This is not MATLAB
runtime acceptance.**

The review covered scenario validation and flow overrides, packet sizing,
transmission and receive accounting, the shared signal lifecycle, propagation,
modulation tables, interval errors, ECC, deterministic scheduling and RNG,
export, portable/native isolation, and the prepared validation tests. The
reviewer did not execute MATLAB R2025a or R2026a. The owner's previously passed
24-test R2025a T0 run does not validate the newly added T1 implementation.

## Findings and corrections

| Finding | Consequence | Verified correction or disposition |
|---|---|---|
| Node IDs were concatenated before numeric normalization | Mixed integer/double ID fields could coerce or truncate the endpoint list before duplicate and membership checks | Each validated node ID is now converted to double before concatenation |
| Standalone error allocation accepted integer signal start times | Adding fractional header timing to an integer start could round before the calculations used doubles | `signalStartSec` is now converted to double immediately after validation |
| Closure delegates are function handles in an otherwise JSON-exportable configuration | A supported delegate scenario could run successfully but fail JSON export | MAT results retain the callable; recursive JSON conversion records a callback description explicitly marked non-executable |
| Capability reporting still said the wireless adapter was unimplemented | The report obscured the new candidate adapter's actual scope | Reporting now distinguishes the implemented candidate, runtime validation pending, and full native packet transport not integrated |
| Native tests lacked an event exactly at the simulation horizon | A backend could differ on inclusive-horizon behavior without this prepared test exposing it | Added a native test for an event at the horizon, a same-time event it creates, and retained future work; keep the missed-event guard |
| The PHY fixture inherited T0 propagation speed 299792458 m/s while ns-3 uses 300000000 m/s | Small unrecorded receive timing difference | T1 PHY fixtures now specify 300000000 m/s and their prepared timing checks use it; T0 remains unchanged |

These findings do not justify another architecture tranche or an OPNET
investigation. The integration owner owns the implementation corrections and
final verification record. Only the new native horizon test and this review
document were edited by the independent reviewer.

## Behavioral and architectural assessment

- The CSR core remains independent of release-specific MATLAB classes.
  Optional subclasses of `wnet.Node` are confined to the adapter package, and
  the portable test runner explicitly excludes native test subfolders.
- The signal engine distributes a physical transmission to every other node.
  Intended application delivery, successful overhearing, receiver-level
  attempts and failures, and unfinished work are counted separately. A
  successful overheard packet cannot increase application delivery or goodput.
- Transmissions are FIFO-serialized per source for this tranche. Receiver
  Search/Track handling, preamble eligibility, half duplex and overlap are
  present; MAC slots, reservations, queues, ACK/DACK and retry ownership remain
  an explicit T2 integration boundary. Autonomous routing remains T3.
- Propagation uses the source minimum-gain path selection, transmitter/receiver
  passband overlap, antenna gains, linear-watt noise, and separate closure
  decision. These are network-level abstractions with appropriate scope.
- Error allocation preserves source-specific per-interval truncation and the
  final interval's realized BER. The inverse binomial CDF includes the source
  complement rule for probabilities above one half. ECC protects the fixed
  header and payload/FCS, excludes the preamble, applies an inclusive error
  limit, and does not rescue an earlier receiver rejection.
- Same-rate spread-spectrum interference retains receiver-global JSR history.
  High-rate payload jamming has separate per-signal interval-local state.
  Different-rate interference is removed using contributor identity when its
  signal ends. This follows the current ns-3 implementation rather than an
  unrelated aggregate PER approximation.
- A collision flag alone does not force packet loss in the default source
  model. Likewise the supplied DQPSK low-SNR values above 0.5 and residual
  PHY/ECC attribution uncertainty are preserved deliberately. The port should
  not silently change these merely to make an OPNET aggregate look closer.
- Configuration, bounded traces and pending-work accounting support useful
  controlled experiments. Trace truncation and disabled logging must remain
  observational only; they must not change RNG draws or protocol decisions.

## Native scope and remaining gates

The optional `wireless-clock` backend uses an actual native node to drive the
CSR event heap. CSR continues to own RF propagation and delivery on this
backend. A separate native packet/channel lifecycle probe exercises actual
native packet distribution. The two must not be described as an integrated
native CSR transport or as completed native PHY parity.

The portable suite contains algorithm, source-vector, signal-state and
integrated-scenario checks. They are meaningful tests of behavior, but their
presence is not evidence that they pass in MATLAB. Source C++ BER-vector
execution and the three recorded native ns-3 smoke workflows validate the
reference side only. Full MATLAB/ns-3 differential results require execution
on both sides with equivalent configurations.

Run `run_tranche1_validation` on the available R2025a installation first.
Separately run `validate_native` on R2026a with the required toolbox. In
particular, the exact-horizon native test may expose a framework event-ordering
constraint; a failure must remain visible rather than being hidden by a final
portable execution of missed events. Statistical comparison across simulators
must use ensembles or deterministic fixtures, not expect identical stochastic
packet outcomes merely from equal numeric seeds.

The remaining substantial work is the planned MAC/HOP reliability integration,
followed by autonomous routing and equivalent scenario comparisons. Missing
OPNET event exports and low-impact numerical differences do not block this
portable T1 runtime handoff.
