# Tranche 2 validation

The acceptance target is a complete application → HOP → MAC → PHY exchange,
including loss recovery and relay custody. Generated MATLAB tests are not
execution evidence. R2025a and R2026a runtime results must be recorded separately.

Current source-side result: **17/17 original ns-3 workflows passed** against CSR
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` in ns-3 engine
`6b5cd24ea80713ce16d88575869aedd6f432bdae`. This is actual native C++ execution.
The Tranche 2 MATLAB suite contains **145 portable test methods**, including
the original 72, and has **not** run in this workspace. The five native adapter
methods remain separately gated. MISS_HIT 0.9.44 static lint passed for all 54
MATLAB files using its MATLAB 2022a syntax profile; that is not runtime or
toolbox compatibility validation.

From a fresh MATLAB session in this repository:

```matlab
run_tranche2_validation
```

The runner executes every portable test before exporting the named MAC/HOP
scenarios to `results/tranche2_validation/`. Native wireless integration remains
a separate `validate_native` gate; a missing Wireless Network Toolbox does not
prevent the portable MAC/HOP validation.

## Integrated acceptance cases

| Case | Required observable behavior |
| --- | --- |
| Reliable link | Application packets arrive once; positive feedback releases HOP custody. |
| Lost ACK | Sender retries; receiver suppresses duplicate application delivery and repeats feedback. |
| Lost DATA | Sender retains custody and retries through the actual MAC/PHY path. |
| DACK | Relay accepts custody and can deliver onward while sender capacity remains held for the source's 20-second interval. |
| Contention | Multiple contenders use channel access and maintain packet accounting. |
| Relay | A fixed two-hop path forwards traffic and completes both link transactions. Autonomous route discovery belongs to Tranche 3. |
| Queue pressure | Bounded queues produce explicit admission/drop outcomes with no stranded application accounting. |
| 500/1000 kbps | High-rate DATA shares the same operational control/reliability path. |
| Reproducibility | Repeated seed/configuration reproduces traces and statistics while leaving global RNG unchanged. |
| Finite horizon | Work outstanding at the stop time remains pending, rather than appearing as loss. |
| Bounded traces | Reduced trace capacity preserves protocol outcomes and reports omitted records. |

`Collisions` retains Tranche 1's definition: completed receiver-signal
observations with a nonzero collision count. It is not a count of unique medium
collisions and does not by itself imply packet loss. Application delivery and
physical observations must remain separately accounted because one transmission
can be overheard by multiple radios or retransmitted without a new application
delivery.

`AcksReceived` and `DacksReceived` count HOP transactions completed by positive
or deferred feedback; repeated copies of an already-processed cumulative bitmap
do not create new completions. `UnconfirmedHopTransfers` counts failed feedback
after the application was delivered or custody moved onward. It is a cumulative
diagnostic, not current pending work. The permanent-ACK-loss test therefore
requires a nonzero unconfirmed count alongside one delivery and zero application
drops. Per-node HOP statistics retain the separate pending/resend/DACK-hold counts.
Completed scenario tests require those three counts and forwarding custody to
drain to zero; the summary CSV exports the HOP pending counts explicitly.

Loss fixtures erase selected successful PHY receptions before MAC/HOP handling.
`FaultDrops` records those deliberate receive erasures; they do not claim a
source-exact stochastic channel model. Ordinary fixtures have no scripted loss.
`PhyTrace.Success` describes decoding before these erasures, while aggregate
`PhysicalReceived` / `PhysicalDropped` reflect the decision after erasure.

Custody regression cases also cover MAC dequeue waking another peer's queued
work, a repeated DACK-marked packet reaching a four-node path after custody
has moved onward, and an oversized last transmission arriving after its sender's
final timeout. The event trace can retain an earlier `app_drop` followed by a
late `app_receive`; final statistics reverse that provisional loss and record
`LateDeliveries`. First-time late relay custody similarly increments
`LateCustodyRecoveries`. Actual application identity is delivered at most once.

## Source-side reference execution

`scripts/run_tranche2_ns3_reference.py` builds and executes unchanged original
MAC/HOP smoke workflows using the source repository and an already configured
ns-3 engine:

```sh
python3 scripts/run_tranche2_ns3_reference.py \
  --source-dir ../ns3-source --engine-dir ../ns3-engine-t1
```

The manifest `evidence/tranche-2-ns3-workflows.json` records source/engine commit
IDs, source/binary/log SHA-256 hashes, executable return codes and original PASS
lines. The selected workflows cover queue limits, feedback coalescing, cumulative
ACK windows, DSCP retries, DACK hold, actual MAC sent-time ownership,
concatenation, preamble selection, reservations, slots, receive contention,
overhearing, link control, no-route relay custody, relay holdoff, and queue
observation, plus original OPNET envelope serialization. These are source-side
references; their success does not certify the
MATLAB implementation or statistically establish full-network parity.

## Failure triage

- **Structural:** duplicates at the application, premature custody release,
  stranded queues, impossible reception, or completed-scenario accounting gaps
  block acceptance.
- **Numerical:** timing, throughput, or aggregate control overhead differences
  require attribution; a small difference does not automatically block a working
  subsystem.
- **Stochastic:** equal numeric seeds do not synchronize MATLAB and ns-3 random
  streams. Use controlled loss fixtures for exact structural checks and repeated
  independent runs for aggregate comparisons.
- **Known source uncertainty:** retain explicit parity entries. In particular,
  source queue-overflow accounting can retain a pending count larger than its
  bounded resend queue; intentionally corrected accounting must be identified.

No new OPNET execution is required. Existing source and aggregate evidence can
inform later comparisons; packet-level OPNET exports remain unavailable.
