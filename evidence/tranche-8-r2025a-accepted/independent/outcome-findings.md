Tranche 8 independent outcome and ACK review

Independent reconstruction from the uploaded MATLAB protocol/application/feedback CSVs and the frozen ns-3 application/feedback traces confirms the reported outcomes. This audit imported no Tranche 8 reporting helpers. It found no contradictory application counts, delivered identities, sizes, or latency accounting. All MATLAB application rows match the raw protocol events; no duplicate application delivery events occur in either simulator.

Upload SHA-256: `bfc4f7f05f0800316b371df3ec316f309f14e3482ef259c3f9c7bd7eea025d77`. The findings JSON binds every consumed ns-3 trace and admission file.

Five seeds (128–132), two direct-to-gateway diagnostics

| Diagnostic | Simulator | Delivered mean ± sample SD | Delivered range | Pooled packet-weighted delay |
|---|---|---:|---:|---:|
| two_node_admission_1200 | matlab | 11332.4 ± 52.91 | 11249–11385 | 0.937928 s |
| two_node_admission_1200 | ns3 | 11338.4 ± 66.70 | 11227–11396 | 0.941006 s |
| three_node_contention_360 | matlab | 916.4 ± 22.88 | 894–948 | 1.684183 s |
| three_node_contention_360 | ns3 | 891.0 ± 41.29 | 822–920 | 1.736412 s |

Two-node pooled deliveries differ by −0.0529% (56,662 MATLAB versus 56,692 ns-3); pooled delay differs by −0.3271%. Contention pooled deliveries differ by +2.8507% (4,582 versus 4,455); pooled delay differs by −3.0079%. These are descriptive results for five seeds, not an equivalence test. Packet delays are summed over actual deliveries and divided by their count; means of populated bucket means are kept separate in JSON.

| Case | MATLAB admitted / delivered / dropped / pending | ns-3 admitted / delivered / unmatched | Delivery difference |
|---|---:|---:|---:|
| a128 | 11395 / 11385 / 0 / 10 | 11380 / 11364 / 16 | +21 (+0.185%) |
| c128 | 954 / 928 / 0 / 26 | 946 / 914 / 32 | +14 (+1.532%) |
| a129 | 11358 / 11354 / 0 / 4 | 11234 / 11227 / 7 | +127 (+1.131%) |
| c129 | 980 / 948 / 0 / 32 | 854 / 822 / 32 | +126 (+15.328%) |
| a130 | 11326 / 11315 / 0 / 11 | 11412 / 11396 / 16 | -81 (-0.711%) |
| c130 | 926 / 894 / 0 / 32 | 948 / 916 / 32 | -22 (-2.402%) |
| a131 | 11265 / 11249 / 0 / 16 | 11334 / 11330 / 4 | -81 (-0.715%) |
| c131 | 927 / 895 / 0 / 32 | 903 / 883 / 20 | +12 (+1.359%) |
| a132 | 11369 / 11359 / 0 / 10 | 11383 / 11375 / 8 | -16 (-0.141%) |
| c132 | 949 / 917 / 0 / 32 | 952 / 920 / 32 | -3 (-0.326%) |

ns-3 unmatched admitted sends do not have a source-certified terminal drop/pending partition. MATLAB has 0 explicit drops and 205 pending applications across these ten cases. Numerical seeds and packet IDs are simulator-specific.

Largest observed flow difference and where it develops

Contention seed 129, flow 2→1 is 510 MATLAB deliveries versus 353 ns-3 (+157, +44.4759%). MATLAB admits 526, with 0 drops and 16 pending; ns-3 admits 369 with 16 unmatched. Flow3→1 is 438 versus 469 deliveries. Both source 2 workloads attempt 30,000 sends; the +157 source 2 delivery difference exactly matches its admission difference, with the same 16 unmatched count at stop. Thus 17.10% from the earlier campus run was never a general worst-case bound.

Of the 157-packet source 2 gap, 117 (74.5%) is already present by 320 s: MATLAB delivers 152 packets during300–320s while ns-3 delivers 35. During 320–360s, the respective counts are 358 and 318.

| Source2 onset observation | MATLAB | ns-3 |
|---|---|---|
| First delivery |302.519104s; PacketId 1|301.401104s; event 520, identity (2, 1, 258)|
| First feedback selection |decision 48, HOP sequence 10, bitmap 1|decision 52, HOP sequence 11, bitmap 1|
| First actual ordinary ACK |302.549s; observation 232, decision 48, aggregate 123/member 2|303.849s; decision 54, aggregate 4294967327/member 1|
| First resumed source 2 admission |302.574s; PacketId 33|303.874s; event 543, identity (2, 1, 293)|
| Longest source 2 delivery silence |1.534s|4.08002s|

ns-3 first selection 52 has no actual-transmission record. Its first actual ACK uses later selection 54 at 303.845104 s, for the same HOP sequence 11/bitmap 1. The 2.447896 s first-delivery-to-first-ACK interval therefore must not be called the queue residence time of one unchanged ACK. In both simulators, new source 2 admission resumes about 25 ms after the first actual ACK. ns-3 source 2 delivery silences of 3.96302 s and 4.08002 s occur around 309–318s. This identifies an early contention/feedback service difference; it does not establish whether scheduler logic, random draws, collisions, or another mechanism caused it. Exact rows and 10-second per-flow buckets are preserved in the JSON.

ACK rate, power, and queue observations

| Observation across 10 cases | MATLAB | ns-3 |
|---|---:|---:|
| Feedback selections |61,543|61,472|
| Actual ACK members including repeats |12,438|12,460|
| Ordinary DATA-window selections |61,247|61,154|
| Ordinary DATA-window transmitted members |10,958|10,870|
| Exact-sequence control selections |296|318|
| Exact-sequence control transmitted members |1,480|1,590|
| Actual-versus-selected rate overrides |29|139|
| Power overrides |0|0|

Every ordinary DATA ACK selection and actual member uses rate key 128 at +33 dBm in both simulators. The rate key is the legacy 128-kbps label; the operational four-bit interval rate is 133,333.333 bps. No ordinary rate or power override occurs. All observed rate overrides are exact-sequence startup control ACKs, by 17.888 s MATLAB or 58.682 s ns-3, before application traffic begins at 300 s.

Control ACK behavior is measurably different: MATLAB selects key 8 for 151 control ACKs and key 128 for 145; ns-3 selects key 8 for 66 and key 128 for 252. MATLAB transmits 784 control members at key 8 and 696 at key 128; ns-3 transmits 469 at key 8 and 1,121 at key 128. MATLAB copies incoming frame rate while ns-3 applies its reverse-link control calculation. This known control-policy difference cannot be equated with proof that replacing the MATLAB rule will reduce delivery differences.

MATLAB observes 335 enqueues and 61,208 replacements, with no queue rejection or retained duplicate. All 12,438 actual members independently match their retained decision identities; repeats never exceed 5. These counters include cumulative ACK replacement and repeated transmission, so member counts are not per-packet ACK success rates. ns-3 observes selection before MAC admission; MATLAB observes after admission. The counts do not establish queue equivalence.

No DACK occurs. All source-observed peers are known with advertised S0 −103 dBm and HOP failure count 0; varied link margins, asymmetric paths, unknown-peer fallback and relay backpressure remain untested. The campus 6000 s run is not part of this return.

Recommendation: retain the current ACK radio policy and validated PHY/ECC. Next inspect the early contention seed 129 chain from DATA reception through ACK scheduling and admission-capacity release. Do not infer a campus explanation or overall numerical parity from these small direct-link runs.
