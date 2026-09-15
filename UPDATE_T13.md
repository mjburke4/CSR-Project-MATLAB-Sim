# Tranche 13 handoff

This milestone tests controlled DATA and ACK/DACK loss and relay-link recovery under continued application demand on the fixed 4 → 5 → 1 chain. It adds a diagnostic around the existing production MATLAB NWK/HOP/MAC layers. All 259 sources recorded in the successful Tranche 12 return, including 135 MATLAB files, are unchanged. Previous tranche runners remain available in the full package and after applying the update.

## Run

Follow `START_T13.md`. Apply `t13up.zip` directly over the repaired Tranche 12 installation used for your successful rerun, or use `csr13.zip` for a complete installation in `C:\CSR\csr13`. The update contains files at the package root, not an extra enclosing directory. Run `clear functions`, then `report = run_tranche13_validation;`. Return the printed `t13.zip`, including if a failure occurs.

The runner selects 88 MATLAB tests (16 new, 72 retained), four 64-second primary cases and 264 structural checks. The new test class repeats the four cases. Short results paths are under `results/t13`. MATLAB R2025a execution remains pending; static parsing and Python checks do not establish a MATLAB runtime pass.

## Implementation

| File | Purpose |
| --- | --- |
| `+csr/+validation/lossContract.m` | Finite offers through real admission state, controlled receiver-group loss, identity/custody/queue checks and trace export |
| `tests/TestLossContract.m` | 16 MATLAB runtime tests, including exact full-width ACK/DACK bitmaps |
| `run_tranche13_validation.m` | Selected regression suite, source/reference stability checks and partial-failure evidence packaging |
| `scenarios/loss/` | Shared cases, demand, raw contention draws and loss semantics |
| `scripts/ns3/tranche13_loss.cc` | Actual native NWK/HOP/MAC fixture using the unchanged earlier diagnostic hooks |
| `scripts/run_tranche13_ns3_reference.py` | Build, execute, verify and preserve native references |
| `scripts/analyze_tranche13_return.py` | Independently reconstruct and compare the returned MATLAB evidence |
| `evidence/tranche-13-gate/` | Preparation checks and independent review |

Loss is chosen at actual TX start for the whole addressed receiver group and applied on arrival. Dropped groups cause no receive bookkeeping, HOP ingress or fabricated feedback. Node 5 keeps running during the blackout. Each source starts with 20 applications and receives one new application per second through 28 seconds; admission polls continue before 40 seconds. Queues drain through the fixed 64-second stop without manual clearing. The finite offer driver is synthetic and queries the real NWK admission gate; it is not the production ApplicationGenerator.

## Native result and limits

The pinned CSR source is `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`; the ns-3 engine is `6b5cd24ea80713ce16d88575869aedd6f432bdae`. Current native main was checked for this tranche. No new OPNET execution was performed.

| Measurement | Executed native result |
| --- | --- |
| Application deliveries | 384/384, 96 in every case |
| HOP terminal custody outcomes | 556 ACK + 20 DACK, zero exhausted retries |
| Final queues and custody | Empty MAC ACK/DATA, HOP resends/DACK holds and NWK waiting/custody |
| DATA retransmissions | Two in `data`, zero in `ack`, two in `out` |
| Preserved native observations | 9,962 events; 1,475 draws; 1,592 transport segments |
| Native negative/group/boundary checks | 25/25 passed |
| Clean versus disabled-hook control checkpoints | 255/255 byte-identical |
| Closed native artifact hashes | 47/47 independently verified |
| Python evidence-checker tests | 44/44 passed on native references and deliberately corrupted inputs |
| MATLAB static parsing | All three new MATLAB files parsed successfully; runtime execution pending |

Blocked source-4 demand overlaps DACK-held capacity, then admissions resume as holds clear. Terminal custody success is distinct from delivery at the gateway. Native DACK terminal normalization is documented and preserves the original raw trace: the native `false` flag means not directly ACKed, while the DACK transfers custody.

The ACK-loss case recovers through subsequent cumulative feedback; it does not exercise DATA retransmission after ACK loss. The blackout policy is bidirectional, but the observed losses in that interval are two singleton DATA groups on 5 → 1. Actual selected losses do not exercise mixed-kind groups; separate native self-tests cover that grouping behavior.

This diagnostic fixes routes, neighbors, nominal rate (128 kbps), power (+33 dBm) and transport behavior. It does not establish RF/collision, adaptive radio, discovery, route reconvergence, node reboot, production traffic-generator or 6,000-second campus parity. The PHY/ECC baseline is unchanged. Existing 28-nanosecond startup and intermediate DACK callback-order residuals remain visible; no clock or tolerance change is introduced.

## Next decision

First inspect the returned MATLAB archive for structural integrity, per-case delivery, loss-policy decisions, retransmission/feedback sequences and admission recovery. Structural failures require repair; small timing or intermediate-state differences remain explicitly measured. After this comparison, choose a further fault case only if it addresses a concrete remaining gap, such as an ACK-loss interval long enough to force DATA retransmission or an outage that actually exercises both link directions. Full network and campus parity remain separate milestones.

This is a portable candidate for owner execution. It is not a MATLAB acceptance record or a published Git branch.
