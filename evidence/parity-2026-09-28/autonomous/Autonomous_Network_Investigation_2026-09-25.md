# Why the autonomous seed-132 networks diverge

25 September 2026 · Native = ns-3 C++ reference · Network target remains ±15%

**The offered traffic is the same. Different transmission and reception histories release custody at different times, which changes the admitted traffic and then feeds back into contention.** The first observed RF timing difference occurs during gateway discovery, long before application traffic starts. By 300 seconds, the two autonomous networks already have different receiver states and neighbor-freshness histories.

The evidence does not yet establish a new production algorithm defect. It does establish why equal numeric seeds cannot be treated as identical inputs, and it identifies specific causal chains that the next coupled test must resolve.

## 1. The application generators are offering the same load

The scenario CSVs are byte-identical. Six sources—2, 3, 4, 5, 7 and 8—attempt destination 1 every 20 ms from 300 seconds, strictly before 6,000 seconds. Each makes 285,000 attempts. The fixed destinations consume no traffic random draws.

The audit checked all **1,710,000 native attempt records**, all **100,000 exported MATLAB attempt records**, and both complete admitted-application ledgers. Every checked attempt and admitted application lies on the same integer-nanosecond 20 ms grid. The MATLAB admission-detail table ends at 633.32 seconds because of its configured export budget; complete aggregate counters and admitted-packet records remain available.

Both engines admit each source's first 16 packets at 300.00–300.30 seconds. Thereafter, the generator only creates a packet when that source/destination pair has fewer than 16 applications in custody. All suppressed attempts in this seed-132 run are attributed to this custody limit; the full counters report no discovery, topology, gateway-route or destination blocks.

In [300,330), **226 of 9,000 attempt outcomes differ**. Each differing decision is explained by a custody count of 15 in the admitting engine versus 16 in the blocking engine. The admission rule itself has no observed mismatch.

The native first NWK-to-HOP callback is 28 ns after packet generation. That is separate from the offered schedule: both engines generate their first admitted packets at exactly 300 seconds. It does not explain the second-scale feedback differences below.

## 2. The first admission difference has a complete event chain

Source 7's first differing attempt is at **300.56 seconds**. The native network has already received its first ACK and released custody; MATLAB has not yet transmitted its first packet.

| First source-7 packet | Corrected MATLAB, s | ns-3, s |
|---|---:|---:|
| Generated | 300.000000 | 300.000000 |
| DATA transmission begins | 301.496000 | 300.092000 |
| Node 8 accepts DATA | 301.740812 | 300.336812 |
| ACK releases source custody | 302.029292 | 300.547292 |
| First replacement application admitted | 302.040000 | 300.560000 |

The native release explicitly reduces custody from 16 to 15. At the common 300.56-second attempt, ns-3 therefore admits a new application and MATLAB suppresses it. This is a difference in the state supplied to the same gate.

Source 8 initially benefits in MATLAB instead: its first release is at **302.679295 seconds**, permitting a new admission at **302.68**. Native releases its corresponding first application at **317.291295 seconds**, permitting admission at **317.30**. As established in the preceding review, native node 8 sends 34 feedback transmissions to node 7 before its own DATA at 316.719 seconds. The accepted earlier MATLAB conditional MAC replay already reproduces that scheduling sequence.

These different admissions subsequently change the traffic competing for service. The relationship runs in both directions: service changes custody, custody changes admissions, and admissions change later service.

## 3. Receiver histories diverge during discovery

The first gateway DISCOVER transmission occurs at **10.452 seconds in MATLAB versus 10.465 seconds in ns-3**. Both prepare at 10.01 seconds, expire holdoff at 10.31, and use a 13 ms slot period with the first eligible countdown at 10.322 seconds.

Native's first raw slot draw is directly captured as **11** on support [0,31]. MATLAB's observed transmit time uniquely implies an initial slot of **10**, given the matching countdown rules and absence of preceding RF or neighbors. That MATLAB draw is an inference from timing, not a directly exported random value. The difference is one slot; it is not evidence of a different slot-duration rule.

The earliest subsequent differences at the path receivers include MATLAB tracking a control signal while native proceeds to its periodic sleep deadline:

| Receiver | First unmatched MATLAB Track, s | Incoming transmitter |
|---|---:|---:|
| 4 | 19.766642 | 5 |
| 2 | 41.502630 | 4 |
| 8 | 56.322645 | 2 |
| 7 | 61.262642 | 8 |

Those comparisons locate different autonomous RF histories. The ordinary MATLAB trace does not preserve every `mac_state` label; Track is independently supported by `phy_track` events. Matching earlier event timestamps alone is not a proof that every hidden state matched.

At application startup, the accumulated control history has changed receiver availability:

| Node at 300 s | MATLAB state inferred from transition cause | Native directly captured state |
|---|---|---|
| 2 | Idle | Search |
| 4 | Search | Idle |
| 7 | Search | Search |
| 8 | Search | Search |

For example, native node 2 last left tracking at 298.080095 seconds after traffic from node 8; MATLAB node 2 last followed its periodic sleep transition at 299.3729 seconds. Conversely, MATLAB node 4 was in its post-transmission Search history after a control transmission ending at 297.40854 seconds, while native node 4 followed periodic sleep at 299.3729 seconds. These differences are supported by earlier control exchanges, without requiring a different sleep rule.

Neighbor freshness also matters. Before MATLAB node 8 transmits its own DATA at 300.144 seconds, its last successful reception from node 2 was at 268.730555 seconds—about **31.41 seconds earlier**. It therefore uses a long preamble. Native has a much more recent reception before its own DATA transmission and uses a short preamble. The relevant native freshness threshold with a local active-node count of three is 20 seconds, from the same implemented `15.5 + 1.5 × active_count` rule. That count includes the node itself. The different preambles are consistent with different histories, rather than proving different preamble-selection logic.

This has a direct effect on the first DATA race: MATLAB node 8's long transmission at 300.144 seconds puts nodes 7 and 2 into Track until approximately 301.381 seconds, postponing their countdowns. Native source 7 transmits first at 300.092 seconds and starts the feedback competition at node 8 instead.

A source review also found a narrow Idle-RTS scheduling edge: native can treat the current nominal periodic awake window as the next wake, while MATLAB computes the next cycle boundary. The relevant native 0–330-second enqueue history does not exercise the differing idle condition. This remains a separately documented candidate edge; it is not established as the cause of the observed startup or application discrepancy and does not justify a production fix here.

## 4. Equal seeds do not align the random inputs

MATLAB caches a separate `mt19937ar` stream for each node and subsystem. The native MAC creates a new `UniformRandomVariable` object at each slot-selection call, without explicitly assigning a stream in that path. Native's device stream assignment separately covers PHY uniform and SYNC-normal variables.

Consequently, seed 132 does not imply equal MAC samples, equal PHY samples, or equal cross-event stream allocation. The initial gateway slot difference is a concrete manifestation of different realized inputs. This does not show that either implementation uses the wrong probability distribution, and it does not prove that random sampling alone explains the full latency gap.

The earlier common-input MAC tests supply receiver availability and queue/cancellation histories. Those tests validate conditional service, but they cannot establish how the autonomous network generates those histories.

## 5. One combined test, with endogenous reception and feedback

The new test keeps all seven campus nodes, the original geometry and the original offered traffic. Nodes 1, 3 and 5 remain because they contribute discovery, interference, overhearing, neighbor counts and downstream service. The 7→8→2→4 path is the analysis focus, not a reduced topology.

Both cases start at time zero and stop at 330 seconds:

1. **Natural diagnostic:** retain MATLAB's own random streams, add passive observations, and compare the resulting protocol/PHY/application prefix against the existing corrected 6,000-second return. This checks that the diagnostic changes preserve the original behavior and exposes actual slot choices, receiver transitions and timer context.
2. **Coupled common-input case:** supply captured native MAC slot draws, SYNC-threshold values and PHY error uniforms. The network must generate its own transmissions, receiver availability, ACK/DACK decisions, cancellations, retries, admissions and custody releases. No receiver-state or successful-reception outcome is injected.

Draw requests must match their semantic context: node, subsystem, ordinal, bounds/profile, packet lineage, and relevant PHY component/interval properties. A mismatched request is a diagnostic stop, not permission to consume a different random value. Actual event times remain observed outputs; clock differences are recorded separately and do not become commands to force an event onto the native schedule.

The native extended capture has now reproduced the original 0–330-second canonical trace: **48,919 rows × all 30 fields match exactly**. Its extra observations include **928 MAC slot samples, 1,960 SYNC-threshold samples and 1,542 PHY error uniforms**, for 4,430 samples total. All seven nodes are covered; a node with no stochastic error interval legitimately has no PHY uniform request. The 928 MAC samples were also independently compared with the earlier accepted capture and all match.

The capture adds 70,441 receiver/timer-history rows. Its common observation order and timer causes support diagnosis, but native event IDs are local identities and are not compared directly with MATLAB scheduler IDs. The extra timer lifecycle records cover device timers; the receipt states that scope explicitly.

The reference also verifies ordered packet identities and behavioral control fields before PHY samples are supplied. Discovery fields are observed before native encryption; ciphertext alone is not treated as readable discovery content. Those additional passive records preserve the same exact canonical prefix. Cryptographic envelope bytes are diagnostic only because the MATLAB behavior/size model has no bit-for-bit counterpart.

MATLAB execution remains an owner validation step: local source checks and a valid native reference do not constitute a MATLAB pass. The runner preserves partial evidence if the coupled case stops on a mismatched request. A diagnostic stop identifies the next boundary to inspect; it is not itself proof of a production bug or a network-parity pass.

## 6. What this explains—and what remains open

The source generator configuration is not the cause of the different offered load: offered load matches. We have traced the first admitted-traffic difference to feedback timing and identified prior receiver-state/freshness differences arising during autonomous control traffic.

The initial advantage is not a full-run explanation. Both engines admit 37 source-7 applications during the first 30 seconds of traffic, despite different exact admission times. Over 6,000 seconds, MATLAB admits 1,133 source-7 applications versus 819 native, but only 239 source-8 applications versus 512 native. A short initial race alone cannot be asserted to explain that later source mix or the entire latency difference.

The coupled test is intended to distinguish a specific state-machine or timing mismatch under comparable inputs from different stochastic histories. Any proposed production correction must follow that evidence. The ±15% network acceptance target remains unmet and is not replaced by a short component or coupled-case pass.

## Evidence

The traffic and receiver audit directories contain their scripts, CSV event joins, input hashes and scope limitations. The previous feedback review remains the authority for the recovered 34-feedback conditional MAC acceptance. The new native-capture and MATLAB-kit validation records document execution and pending owner checks separately.

The owner package is `autonomous-seed132-tests.zip`. Extract it into a short local path, restart MATLAB, and set Current Folder to its `autocase` folder, which contains `run_autonomous_tests.m`. Run:

```matlab
report = run_autonomous_tests;
```

Return the printed `out_auto_YYYYMMDD_HHMMSS.zip`, including when a diagnostic divergence stops the coupled case. Both cases are launched by this command. The ns-3 reference has already been run; no ns-3 command is needed from the owner.
