# Tranche 23 return review

T23 is accepted as a completed controlled diagnostic. No MATLAB rerun is
required. Exact cross-engine custody agreement did not pass; the difference is
retained as an engineering finding. No production behavior is changed.

## Owner run

- MATLAB R2025a, version 25.1.0.2943329; portable backend.
- 79 of 79 focused tests passed; zero failures or incomplete tests.
- Seven cases and 123 checkpoints completed in 72.141 seconds.
- All 18 common milestones and 81 assertions passed.
- The exact issued candidate, 404 source bindings and 293 reference bindings
  were verified. All 390 accepted T22 sources, including 178 MATLAB files,
  remain unchanged. Initial and final inventories match.

The result status `completed-differences-review-required` correctly describes
the completed experiment. The two differing checkpoints are not two failed
MATLAB test methods.

## Confirmed difference

| Situation after replaying the DACKed packet | MATLAB relay custody | ns-3 relay custody | MATLAB waiting | ns-3 waiting |
|---|---:|---:|---:|---:|
| Continued relay congestion | 17 | 18 | 16 | 17 |
| After three downstream ACK releases | 14 | 15 | 12 | 13 |

121 of 123 state checkpoints agree. Only `nsdp_relay`, `nwk_waiting` and
`nwk_owned` differ at the two rows shown above.

All 91 captured feedback records agree in ACK/DACK kind, HOP sequence and ACK
and DACK bitmaps. Their timestamps agree within the declared 1 ns tolerance.
The complete feedback tables have two differing rows because those rows also
record custody counts; these are observation fields, not different feedback
control bits. The largest decimal time differences are 1e-15 seconds for state
checkpoints and 3e-17 seconds for feedback records.

## Why it happens

In both implementations, HOP passes a DACK-marked replay back to NWK for
reassessment. The pinned native NWK code queues another relay custody entry and
increments the flow's NSDP count. MATLAB's `Seen(SourceId,Id)` check accepts the
repeated application without adding another owner. Its pending queue also
checks the application identity, so merely removing the Seen check would not
provide a complete or safe implementation of native duplicate ownership.

The controlled replay uses the same pre-enqueue pressure in both engines.
That is why both still emit DACK under continued pressure and ACK after the
three releases, even though their post-enqueue custody counts differ.

This establishes a real ownership/accounting difference under the tested
conditions. It does not establish which behavior is preferable, what OPNET
would do, or how much of the campus delivery or delay gap it explains. The
cases stop before measuring subsequent service of the extra native entry.

## Engineering decision

Keep the current default while measuring the consequence. The next useful
step is an offline census in the already completed campus traces: identify
same-application relay enqueues following DACK-marked retries, count simultaneous
owners, and follow their downstream service and release. Begin with node 8,
source 7 and seeds 129/130. The earlier T21 review notes that historical native
seed 128 lacks equivalent detailed custody events; do not treat missing
observations as zero.

If the archived lineage is sufficient, this can establish whether the extra
owners are common and consume material capacity without another MATLAB run.
If lineage is insufficient, use a bounded observer/replay experiment that
follows each custody instance through transmission and completion. A behavior
change would then require its own focused regression and matched performance
experiment. Do not change PHY/ECC or tune admission thresholds from this result.

The working +/-10% campus goal remains open for the previously identified flow
and delay exceptions. T23 supplies mechanism evidence, not a new campus result
or numerical-parity acceptance.

## Provenance and scope

Owner archive SHA256:
`569cf1bbd7ca31e90518128d32dfd7a51c2f94b15e1ec5c5131aa1d5a426804c`

Issued T23 update SHA256:
`933fe4b6d09253786e38fbb43091ea62702bb01264ef9147a029cea45b71db64`

Issued candidate SHA256:
`b40afd3755ceb47576ea2c9854b4af15a14cebcf87024331e67bf53e069f0818`

Native model pin:
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`

The review checks owner-returned evidence and its cryptographic bindings; it
does not independently attest the MATLAB process. No MATLAB or native
simulation was executed during this return review. The experiment uses
controlled decoded arrivals and callbacks, with a declared one-microsecond
settling interval. It does not test real PHY, security ingress, same-tick
callback ordering, or full-campus performance.
