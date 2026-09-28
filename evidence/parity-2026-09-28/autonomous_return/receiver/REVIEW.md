# Natural seed-132 receiver capture: direct evidence

The returned natural case reached 330 s and passed its exact corrected-baseline gate: 12,200 protocol rows, 12,198 PHY rows and 9,000 application-attempt rows matched, with no timing tolerance. The new passive observations therefore expose the same previously reviewed MATLAB trajectory. They confirm the earlier inferred initial slot, awake/asleep states and preamble-freshness explanation directly.

Case B stopped at 10.01 s because the harness attempted to convert a missing CSV text field to a character vector. It did not supply its first native draw. This return provides no completed coupled comparison and no new same-input production-defect finding.

## Direct slot evidence

At the first gateway discovery preparation, MATLAB draws **10** at 10.01 s; native draws **11**. Both use profile 4, local active count 1, support [0,31], Search state and expired reservation counter -1. The subsequent first discovery transmissions are 10.452 versus 10.465 s. The MATLAB draw was previously inferred; it is now explicitly recorded in `random_requests.jsonl`.

At application startup, all six source draws occur at 300.001 s. Local populations and draw bounds match, but the realized values and prior per-node draw counts differ:

| Source node | MATLAB draw | Native draw | Local active count, both |
|---|---:|---:|---:|
| 2 | 17 | 30 | 3 |
| 3 | 8 | 4 | 3 |
| 4 | 14 | 6 | 3 |
| 5 | 8 | 17 | 4 |
| 7 | 19 | 6 | 2 |
| 8 | 10 | 18 | 3 |

In particular, MATLAB node 8 has the smaller initial reservation; native node 7 has the smaller reservation. These are different draws from the same configured support, not evidence of a changed slot-range constant or probability law. The equal numeric scenario seed does not supply equal random realizations.

## Direct availability and timer ownership at 300 s

The first `mac_boundary/start_before` snapshot in each source's enqueue call occurs at exactly 300.000 s, before its first DATA is inserted. It records actual MAC state and post-TX timer ownership. The scheduler log independently resolves each timer ID to its deadline.

| Node | MATLAB state | MATLAB post-TX guard deadline | Native state | Native post-TX guard deadline |
|---|---|---:|---|---:|
| 2 | Idle | None active | Search | 303.836540 s |
| 4 | Search | 317.408540 s | Idle | None active |
| 7 | Search | 301.253080 s | Search | 316.671080 s |
| 8 | Search | 302.662080 s | Search | 318.080080 s |

The native states and active flags come from its directly recorded receiver boundary history before application startup; its timer lifecycle records supply the deadlines. Its older node-4 guard expired at 228.47554 s and is not counted as active at 300.

These records replace the prior inference based on unlabeled ordinary `mac_state` rows. Recent control transmissions—not a different base wake period—account for the different guard ownership. The node-7 and node-8 MATLAB guards are canceled when queued work activates preparation; the table describes state at the initial application arrival, not an uninterrupted future guard.

The first unmatched Track transitions during discovery are also now explicitly labeled Search→Track: node 4 at 19.766642444 s, node 2 at 41.502630 s, node 8 at 56.322645346 s and node 7 at 61.262642442 s. Those times match the earlier ordinary PHY evidence.

## The source-7 waiting mechanism is directly measured

MATLAB node 8 draws slot 10 while node 7 draws slot 19 at 300.001 s. Node 8 begins its own original-source-8 DATA at **300.144 s**, using a long preamble and 1.23726 s airtime. Its child metadata identifies original source 8, destination 1, generation 300 s, source attempt 1; the HOP transfer is 8→2, sequence 13.

Node 7 enters Track at **300.150642442 s** while hearing this frame. Its reservation counter is already **8**. The passive MAC snapshots show that counter remains 8 at **95 slot ticks from 300.157 through 301.379 s** while Track. After reception completes at 301.381272442 s, its countdown resumes and it transmits its own original-source-7 DATA at **301.496 s**. This frame is HOP 7→8, sequence 12, source attempt 1 generated at 300 s; it is not relayed source-8 traffic.

Node 8 accepts that source-7 DATA at 301.740812442 s. Its ACK transmission at 301.964 s reaches source 7 and completes feedback at **302.029292442 s**, so the next 20 ms source attempt admits a replacement at **302.04 s**. In native, the corresponding original-source-7 DATA starts at 300.092 s and feedback releases custody at 300.547292442 s, permitting the 300.56 s replacement.

Native first DATA identities were verified using the enriched transmission signatures, not aggregate observation IDs: original source 7/attempt 1 is HOP 7→8 sequence 11 at 300.092 s; original source 8/attempt 1 is HOP 8→2 sequence 14 at 316.719 s. Node 8's earlier forwarding of source-7 packets is a different population.

This establishes the immediate mechanism: different initial service order causes a long received transmission to pause another sender's countdown, delaying its first feedback and replacement admission. It does not establish that this one initial race explains the full 6,000-second source mix or latency difference.

## The long preamble is consistent with directly recorded freshness

At application startup, MATLAB node 8's neighbor entry for node 2 contains `LastHeardSeconds = 268.73055534556323`. Its local active count is 3, so the implemented freshness threshold is **15.5 + 1.5 × 3 = 20 s**. At the actual DATA TX at 300.144 s, that entry is **31.413444654 s old**, directly supporting the long preamble choice.

Native node 8 has different intervening received traffic and hears node 2 at 315.897815346 s before its own DATA at 316.719 s; that age is about 0.821 s, consistent with its short preamble. The two code paths are acting on different neighbor histories.

## Limits and reproducibility

- The natural-prefix gate validates this instrumentation/runtime combination against the previous corrected MATLAB result. It does not validate MATLAB against native.
- The common-input harness failure must be repaired and case B run before drawing a coupled conclusion. The successful natural case should be reused rather than unnecessarily repeated.
- No production behavior was changed and no simulation was run during this analysis. The ±15% network criterion remains unmet.
- Run `python3 autonomous_return/receiver/analyze_natural_receiver.py` to regenerate the bounded evidence. `input_manifest.csv` records the exact source traces and fixtures. Direct state snapshots, timer mappings, countdown CSV and lineage-specific native signatures are included in this directory.
