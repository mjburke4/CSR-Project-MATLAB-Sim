# Native seed-132 receiver feedback audit

The original ns-3 trace closes the node 2 → node 8 ACK/DACK question at the logical HOP level. All **1,245** accepted node-2 DATA receptions from node 8 select the feedback required by the receiver's pre-reception, per-original-flow NSDP count. Each is subsequently completed at node 8 with the same ACK/DACK class. There are **300 ACKs and 945 DACKs**, with no decision mismatch, no missing logical completion, and no duplicate DATA receptions in this link's observed population.

The trace has 4,991,634 consecutively numbered events. Its compressed SHA-256 is `3da17e3397756f8890964d571932a44f7c94573b4d38eac9387342588883a4ef`. The script checks that hash before reading. State reconstruction from each enqueue and NSDP release has zero continuity errors; every receiver before/after count agrees. Filtered CSVs retain original `event_index`, not a substituted row number.

## Accounting by original source

| Source | Node-8 admissions to node 2 | Node-2 receipts | ACK | DACK | No-reception no-ACK exhaustion |
|---|---:|---:|---:|---:|---:|
| 7 | 775 | 759 | 114 | 645 | 16 |
| 8 | 496 | 486 | 186 | 300 | 10 |
| Total | 1,271 | 1,245 | 300 | 945 | 26 |

Every observed receipt is first, non-local and ACKable. All ACK decisions have pre-NSDP ≤15; all DACK decisions have pre-NSDP ≥16. The threshold concerns the original `(source,destination)` flow, not total node-2 custody or all traffic received from neighbor 8. NSDP includes HOP-submitted custody until release; NWK forwarding alone does not decrement it. This is the same condition in the current MATLAB `receiveData` implementation. This audit covers the observed first-reception branch, not unobserved duplicate/no-route/custody-refusal behavior.

Native receipt-to-logical-completion delay is small: ACK mean 0.3092 s (maximum 1.56248 s), DACK mean 0.3111 s (maximum 1.96548 s). Sender DACK capacity holding after completion is separate and is not included in these feedback times.

The current MATLAB counterpart has 1,132 receipts, **139 ACKs and 993 DACKs**, each also reaching the corresponding logical completion. Thus the 139-versus-300 ACK difference originates in the population/state of receiver decisions, not attrition between generated feedback decisions and eventual sender completions. This does not imply every individual physical feedback transmission succeeds; cumulative feedback may recover an earlier lost control frame.

## Receiver state and service differ

| Original flow at node 2 | ns-3 mean NSDP at arrival | MATLAB mean NSDP at arrival | ns-3 maximum | MATLAB maximum |
|---|---:|---:|---:|---:|
| Source 7 | 25.1594 | 75.9089 | 52 | 163 |
| Source 8 | 16.8992 | 19.7602 | 38 | 37 |

Source-7 first DACK occurs at 346.850815346 s in ns-3 versus 346.330815346 s in MATLAB. The later pressure is very different: ns-3's longest consecutive DACK run has 302 receipts from 346.85–2456.15 s; MATLAB's has 665 receipts from 420.52–4485.74 s. Therefore first-DACK threshold behavior alone does not explain the persistent source-7 backlog.

Source-8 first DACK is 349.918815346 s in ns-3 versus 331.367815346 s in MATLAB. Its first DATA arrival at node 2 is 316.963815346 s in ns-3 versus 301.381275346 s in MATLAB. Source-7 first arrival is 331.588815346 s in ns-3 versus 330.626815346 s in MATLAB. A 0–330 s capture contains the first source-8 timing divergence but ends before either source-7 receipt or either engine's first DACK.

The first 300–400 s service allocation at node 2 already differs:

| Original source | ns-3 NWK → HOP admissions | MATLAB NWK → HOP admissions |
|---|---:|---:|
| 2 | 31 | 29 |
| 7 | 0 | 6 |
| 8 | 0 | 17 |

In ns-3, the first forwarded source-8 packet is at 423.689293688 s; the first forwarded source-7 packet is at 430.638293660 s. MATLAB's earlier relayed service does not guarantee better longrun latency: its subsequent source-7 arrival pressure is much larger. The useful next attribution is arrival composition versus node-2 downstream service over the sustained divergence, retaining actual FIFO order and ACK/DACK-owned capacity history. Do not claim that matching seed numbers imply matched packet trajectories.

## Reproduction

Run from any working directory:

```text
python3 next_feedback/native_receiver/analyze.py
python3 next_feedback/native_receiver/derive_service.py
```

The script path determines the root. The original compressed trace must exist at `next_feedback/native_archive/evidence/tranche-25-ns3-reference/s132/ns3-trace.csv.gz`. `analyze.py` streams it and keeps 31,219 relevant rows; it does not load the 1.16 GB raw trace into memory. `derive_service.py` reads the filtered result, adds the matching 100-second service bins and flow summaries. `link_8_2_application_outcomes.csv` joins source/destination/application sequence/HOP sequence only within ns-3. MATLAB packet IDs cannot be joined directly to native application sequences.

The native longrun PHY schema exposes aggregate-front identity, not every logical child or bitmap bit. `edge_physical_front_events.csv` therefore supports exact front-frame observations but not an invented complete child-level feedback ledger. Logical per-application completions supply the receiver-to-sender closure used above.
