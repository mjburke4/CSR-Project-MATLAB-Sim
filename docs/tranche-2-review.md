# Tranche 2 independent integration review

## Owner runtime follow-up

The initial static review below missed creation-time value capture in the MAC
and HOP test fixtures. The owner R2025a run passed all 15 integrated MAC/HOP
scenario/custody methods, but failed 24 unit methods because observers returned
empty logs and mutable input readers retained initial settings. Named nested
getters now share callback state. The repair also fixes NSDP, route-availability
and SYNC controls; assertions and protocol implementations are preserved.
The lead reviewed both specialist edits and audited the remaining anonymous
callbacks. Production callbacks read mutable handle objects or intentionally
capture per-event inputs. Runtime acceptance remains pending the corrected run.
See [recorded result and repair](tranche-2-r2025a-fixture-repair.md).

## Initial candidate static/source review

Reviewed against current ns-3 main
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`: MAC/HOP source and regressions,
logical packet layouts, the PHY state bridge, MATLAB MAC/HOP layers, the
integrated scenario runner, configuration, exports and prepared tests.

The architecture has coherent ownership: PHY owns signals/acquisition; MAC
owns access, duty timing, reservations, concatenation and ACK repetition; HOP
owns DATA retries and flow capacity. The scenario runner supplies explicit
paths and application custody. Release-specific wireless APIs remain in their
adapter package. Anonymous callbacks capture each node/index when created,
and no newly reviewed portable path requires an R2026a-only class.

The important integration boundaries are explicit:

- Physical start precedes HOP's sent indication and retry clock. ACKs receive
  the emitting radio's configured power before entering MAC. OTA observations
  have unique physical identities independent of HOP/application sequences.
- Receiver acquisition, interference and ECC retain the Tranche 1 engine.
  Decoded addressed members pass to HOP while still Track, so feedback can
  enter MAC before its Search preparation. Overheard frames update MAC state
  without becoming application deliveries.
- Application delivery and sender feedback completion are distinct. Missing
  ACKs do not reclassify a delivered application as lost. DACK releases NSDP
  while retaining the sender's HOP capacity until its hold expires.
- The fixed-path application ledger tracks furthest accepted custody. A
  DACK-marked retransmission may reassess feedback without adding a duplicate
  forwarding row or moving custody backward from a later relay.
- Queue admission refusals, terminal source queue losses, HOP failures,
  unconfirmed transfers and receiver-signal observations have separate counts.
  Bounded tracing does not own scheduling or random draws.

Review findings addressed during integration included the relay custody
regression on a repeated DACK-marked packet; an incorrect test expectation for
unconfirmed feedback after permanent ACK loss; local ACK power normalization;
and visibility of pending HOP/forwarding custody at scenario completion.
The integrated runner also repairs provisional timeout loss when a still-in-flight
frame actually establishes later relay custody or final application delivery;
separate late-reception counters retain that evidence. MAC dequeue now requests
a forwarding-queue scan, allowing other peers to use newly available MAC space.

The declared differences remain material to later comparisons: fixed paths;
configured rate/power instead of adaptive HOP link control; security envelope
sizing without authentication; safe overload rollback and retry-clock pause
while queued; a strict 16-total-member aggregate cap; a forwarding queue bound
that includes submitted custody; and optional post-PHY erasures for controlled
reliability tests. Raw PHY trace success describes decoder success before an
injected erasure. Aggregate receiver-delivery counters include those erasures.
These differences must remain in the parity ledger and handoff.

Original ns-3 workflow execution is reference-side evidence. Static MATLAB
review and lint do not establish MATLAB test success. The portable candidate
still requires the owner's `run_tranche2_validation` execution on R2025a;
R2026a/native integration is a separate validation boundary. No autonomous
routing, OPNET aggregate agreement, full native packet transport, or complete
end-to-end ns-3 numerical parity is certified by this review.

**Disposition:** ready as an integrated implementation candidate for owner-run
MATLAB validation. No remaining structural blocker was found in the reviewed
portable MAC/HOP/PHY integration. This is a static/source review gate, not runtime
acceptance of Tranche 2. Source-specific numerical and stochastic agreement
remain unmeasured until MATLAB scenario outputs are available.
