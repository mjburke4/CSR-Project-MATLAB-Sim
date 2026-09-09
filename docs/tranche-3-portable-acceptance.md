# Tranche 3 portable acceptance

**Accepted on MATLAB R2025a:** the owner run of code commit
`ff7859af3900f1ab8c25263dbd2b5bc580e8488d` passed all 289 portable tests,
all eight autonomous network scenarios and the retained nine MAC/HOP scenarios.
The evidence-only acceptance update changes no MATLAB source or tests.

| Gate | Verified result |
|---|---|
| Runtime | MATLAB `25.1.0.2943329 (R2025a)`, portable backend |
| Portable suite | 289 passed, zero failed, zero incomplete; exact method-name set matches source |
| Test time | 104.6286431 seconds summed method time |
| Complete runner | 2026-09-09 13:34:48–13:39:21 UTC; 273 seconds |
| Source provenance | All 74 MATLAB file hashes match the accepted code; source stability confirmed by runner |
| Evidence linkage | Test CSV and validated candidate-manifest hashes match final runtime metadata |
| Tranche 3 scenarios | Eight expected rows, application and physical accounting balanced |
| Final ownership | Zero application, HOP, NWK and control backlogs in every T3 row |
| Admission pressure | Zero queue drops, admission rejections or control/backlog rejections in every T3 row |

## Scenario outcomes

| Scenario | Delivered/generated | Policy drops | Observed outcome |
|---|---:|---:|---|
| `autonomous` | 3/3 | 0 | Discovery/admission and two-hop forwarding completed |
| `no_route_custody` | 3/3 | 0 | Early queue depth reached three, then drained |
| `control_loss` | 3/3 | 0 | One injected routing-control erasure; seven control retransmissions; owners drained |
| `route_recovery` | 3/3 | 0 | Loss/readmission and five discovery completions; retained DATA delivered |
| `gateway` | 3/3 | 0 | Advertised gateway selected by routing |
| `leaf_no_transit` | 0/3 | 3 | Disabled-transit policy discarded all three after HOP receipt |
| `high_rate_500` | 3/3 | 0 | Separate 500 kbps extension fixture completed |
| `high_rate_1000` | 3/3 | 0 | Separate 1 Mbps extension fixture completed |

In total, 24 applications were generated, 21 delivered and three intentionally
discarded by the disabled-transit fixture; none remain pending. All eight rows
also report zero physical pending, resend depth, DACK holds, HOP failures and
unconfirmed transfers. Recovery permits bounded health controls at the finite
horizon, but this run happened to drain them too.

The prior nine MAC/HOP rows also meet their aggregate gates, including 18
intentional queue-pressure drops and zero final pending ownership. The completed
nested runner and passing test CSV confirm the portable regression gate was
not bypassed. Raw protocol traces and per-scenario config/MAT exports were not
supplied here; passing scenario tests support their trace-level assertions.
Physical receive drops and control-member transmission counts are different
from application loss and over-the-air aggregate counts.

## Preserved evidence

The [structured acceptance record](../evidence/tranche-3-portable-acceptance.json)
contains input hashes, exact class counts, scenario rows and scope limits.
Supplied test/scenario CSVs and final metadata are preserved byte-for-byte.
The runtime came from a ZIP without Git metadata, so identity is established
by its exact MATLAB file hashes and the original candidate-manifest hash.
That original manifest is preserved as
`evidence/tranche-3-validated-candidate.json`; the current candidate manifest
now points to acceptance. The accepted source commit remains `ff7859a`.

The test CSV is directly bound by SHA-256 in runtime metadata. The scenario
CSVs were supplied by the owner and are consistent with the completed runner;
they are hashed here but were not hashed by that runner. The earlier 215/286
and 287/289 runs remain historical evidence in the
[repair record](tranche-3-r2025a-repair.md).

No MATLAB execution took place in the engineering workspace. Earlier 12/12
preserved ns-3 workflow results remain source-side reference evidence; no new
source build or reference run was needed for this acceptance update.

## Scope and next work

This accepts the portable controlled-line PHY/MAC/HOP/NWK implementation with
behavioral admission, diagnostic receive erasures and administrative recovery
discovery. It retains the documented custody bounds, retry timing, modeled
security envelopes and other policy differences.

R2026a portable execution and six optional native tests remain separate gates.
Cryptographic protection, complete native CSR packet transport, historical
application-generator equivalence, full feedback-driven link adaptation,
equivalent MATLAB/ns-3 network comparisons and OPNET aggregate parity remain
outside this acceptance. The high rates remain separate extension fixtures.
Battery, supervisory behavior and BBN routing stay excluded.

The next engineering tranche is reusable research scenarios and MATLAB/ns-3
comparisons. Tranche 3 is ready to present as a portable implementation PR;
this acceptance update is committed locally and performs no push or PR creation.
