# Independent Tranche 10 gate review

**Approved for owner validation, with zero open blockers.** MATLAB/Octave have not been executed here, and this review does not grant portable acceptance or numerical parity.

The reviewed change is limited to the existing MAC layer's idle-RTS boundary guard and shared slot timer. The strict-future guard addresses the documented floating-point boundary error. The integer-nanosecond MAC epoch and tick index preserve timer phase and equal-time FIFO while retaining the previous continuous path for unsupported precision ranges. PHY/ECC, random streams, slot-selection policy, HOP/NWK production, canonical inputs and earlier runners remain unchanged.

| Check | Result |
| --- | --- |
| Independent native MAC fixture replay | 279/279, 15 cases, reference bytes identical |
| Independent native receiver fixture replay | 154/154, 4 cases, reference bytes identical |
| Fresh native libraries | All 9 hashes verified |
| Independent native compatibility archive | 125 output hashes, 126 safe members |
| Native compatibility comparisons | 24 accepted T8 pairs, 12 observer pairs, 6 T9 service traces / 182,429 rows identical |
| Independent Tranche 10 Python tests | 49/49 |
| Reviewed full Python suite | 303/303, source stable |
| Reviewed project MATLAB static lint | 123/123 files; no MATLAB execution |
| Accepted T7 accounting compatibility | 47/47 existing retained/sweep results pass the new helper |
| Tested source snapshot | All 222 tested files unchanged; candidate metadata is the sole addition (223 final) |

The independent review found and resolved schema/inventory integration errors, protocol-table `NodeId` handling, and the retained gateway's source-defined destination rewrite. The new runner now exports that gateway case with its full network tables and bounded custom accounting. Required protocol artifacts and configured endpoints are enforced. Current-send-only admission traces remain empty as the source specifies, with complete counters checked separately. The initial failures are preserved in the independent check records.

The default owner run prepares 544 portable tests, 534 contract checkpoints across three families, 29 retained scenarios, 18 sweeps, six small diagnostics, two observer controls, and the original campus workload for 6,000 simulated seconds at seed128. Skipping tests or campus yields diagnostic-only evidence. Short storage paths preserve scientific case identities in metadata. Returned source/configuration/test membership and artifacts are verified before comparison; numerical differences never receive automatic acceptance.

Remaining limits are explicit: idle-RTS grid products and other timers retain double arithmetic, so this is not a blanket event-order parity claim. Different initial random choices can preserve the seed129 delivery gap. Fixed receiver stimuli with stochastic SYNC disabled do not establish population equivalence. Archived OPNET aggregates are reused.

The machine-readable report records exact reviewed file hashes, all tested source hashes, checks and resolved findings. The candidate JSON was assembled after code tests and is the sole addition to the 222 tested files; it is included in the 223-file reviewed snapshot. Local-check metadata may be assembled after review only with final binding of these unchanged implementation and test files. No remote push, PR or merge is authorized by this gate.
