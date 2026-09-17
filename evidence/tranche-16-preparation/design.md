# T16 receiver transport timing source/design review

Review scope: immutable csr15 MATLAB source and pinned native `t14n/native/ns/model/csr-net-device.h` at the current source pin supplied by root. No MATLAB execution claimed.

## Smallest representative experiment

Reuse full T8 input/recipe files for two-node admission (1200 s) and three-node contention (360 s), seeds 128, 129, 130, paired unchanged continuous and optional nanosecond receiver transport. Twelve runs / 9360 simulated seconds. Preserve 300 s startup/discovery, historical generator, adaptive rates/powers, actual SignalEngine/PHY, complete scenario identity, RNG mapping, and native reference bindings. Do not inject routes, receive-success decisions or prescribed packets. Existing per-seed native results are suitable aggregate references; do not claim packet identity replay across native and MATLAB stochastic streams.

Accepted T10 owner runtimes: c128 89.17 s, c129 70.24 s, c130 67.59 s, a129 145.45 s. Paired network simulation extrapolates to roughly 22 minutes; exports and focused regression may make 25–35 minutes. State this as an estimate, not a runtime guarantee.

## Narrow production seam

Inject an optional typed `csr.sim.TransportTiming` as NetworkSimulation third argument and SignalEngine seventh argument. Empty means no changed arithmetic, trace fields, callbacks, RNG, or event insertion. Explicit continuous observes the existing expressions with identical arithmetic: start = tx + propagation; end = tx + propagation + duration; preamble end = tx + propagation + preamble duration. Avoid reusing the old validation helper for continuous timing because its operand order is tx + duration + propagation.

Leave TX/finishTx/TxUntil, MAC completion, global scheduler, acquisition and rejected-receiver return timers unchanged. Quantizing only PHY TX end can move it across the separate MAC completion and cause a new TransmitterBusy failure.

Native source preserves continuous physical RxSignal startSec/endSec/preambleEndSec, schedules receive begin using integer-native propagation delay, sets intervalStartSec to actual callback Now, then schedules preamble/end via integer-native max(0, physicalTarget - Now). MATLAB Model.allocateErrors derives continuous header/payload boundaries from physical StartSec and floors allocated bits. Preserve those physical fields and formulas when investigating callback quantization; use separate scheduled targets. Never silently change header split/PHY/ECC numerical model to make callbacks align.

Any nanosecond policy must explicitly define zero/subnanosecond propagation at off-grid TX times (rounded absolute start may precede actual TX). Fail before transmission state/RNG mutation or use an explicitly named, recorded causal adjustment; never silently schedule in the past. Validate safe integer component/sum bound and positivity/order before state mutation.

## Gate requirements

Structural: completed case membership, config/source/reference identity, exact default-vs-explicit-continuous observations, physical attempts partition into received/dropped/pending, application generated partition into received/dropped/pending, finite nonnegative integer counters, no negative intervals, no duplicate terminal identities, bounded/no omitted required traces. Historical continued traffic can leave custody and in-flight work at the horizon; no invented all-delivered or all-queues-drained requirement.

Report paired seed metrics: generated/received/pending/dropped, aggregate DATA/control transmissions, ACK/DACK actual feedback transmissions, latency, goodput, retry totals, blocked admission, route/neighbor state, RF collisions/physical drop reason counts, ACK rate/power decisions. Compare both policies with same native case profile/seed and report differences without claiming aligned RNG streams. Promotion is a later owner-reviewed decision; default stays continuous.

MATLAB tests: invalid injection/mode/time bounds; unchanged default vs explicit continuous all old fields/traces/callback order; integer component arithmetic and fullprecision export; causality failure or declared adjustment before mutation; same-time FIFO receive insertion; preamble/end monotonicity; signal interval and physical header references retained; colocated/subnanosecond propagation; half duplex/no double delivery; interfering same-rate and different-rate signals including exact non-overlap endpoint; occluded completion behavior; observer limits fail explicitly; actual small NetworkSimulation discovery/PHY execution with current defaults.
