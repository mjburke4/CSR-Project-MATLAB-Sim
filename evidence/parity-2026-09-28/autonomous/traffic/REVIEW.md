# Seed-132 autonomous traffic audit — 25 September 2026

## Finding

The two networks have identical offered traffic. Their **admitted application traffic diverges because feedback releases source custody at different times**. This is a feedback-controlled offered-load experiment: the nominal generator tries every 20 ms, but creates an application only when its original source/destination custody count (NSDP) is below 16. Counts called “generated” in the application ledger are these admitted packets, not all generator interrupts.

No source generator rule mismatch remains in the examined evidence. The first differing decision is explained by different input state. The remaining cause lies earlier in the autonomous MAC/receiver history that produces those feedback times.

## What was checked

- Original seed-132 scenario CSV is byte-identical to the CSV in the corrected MATLAB owner return.
- Sources 2, 3, 4, 5, 7, and 8 all attempt destination 1 at `300 + 0.02*k` seconds, for `k=0…284999`. Each source makes exactly **285,000 attempts** before the 6,000-second stop.
- Every original native `app_admission` row was reread: **1,710,000 rows**, with zero timing errors at integer-nanosecond resolution. All native admission decisions agree with the recorded NSDP `<16` test and the complete generated-application ledger.
- Every exported MATLAB admission row was checked: **100,000 rows**, through 633.32 seconds, with zero timing errors at integer-nanosecond resolution and zero NSDP-rule violations. Its admission-detail export is truncated by the configured budget; its full counters and complete admitted-application ledger are retained. Every admitted application in that full ledger lies on the same 20 ms grid.
- All source counters in both engines report **zero discovery, topology, gateway-route, or destination blocks** over this seed-132 run. Every suppressed attempt is `nsdp_full`.
- Source start, interval, fixed destination, DSCP 0 and configured size 200 bytes agree. Native carries 192 NWK bytes; MATLAB reports 185 application-payload bytes. The seven-byte NWK header explains those different accounting sizes. Both code paths subtract the historical eight-byte source-model exclusion from the configured packet size.
- In the paired complete interval `[300,330)`, there are **9,000 attempts**. Exactly **226 admission outcomes differ**. Each difference is NSDP 15 versus 16; the other 8,774 decisions and NSDP counts agree.
- All sources admit their initial 16 attempts at 300.00–300.30 seconds in both engines.

The native source's initial NWK-to-HOP handoff occurs **28 ns after application generation**. MATLAB's initial handoff is at the same represented time as generation. This does **not** offset the application attempts: those occur at exactly 300 seconds in both. The first MAC preparation is at 300.001 seconds in both. The 28 ns difference is a separate internal scheduling detail, not an explanation for the later second-scale admission difference demonstrated here.

## First differing source decisions

| Source | First differing attempt, s | MATLAB NSDP / decision | ns-3 NSDP / decision |
|---|---:|---|---|
| 7 | 300.56 | 16 / suppressed | 15 / admitted |
| 4 | 301.62 | 15 / admitted | 16 / suppressed |
| 3 | 302.06 | 15 / admitted | 16 / suppressed |
| 2 | 302.20 | 16 / suppressed | 15 / admitted |
| 8 | 302.68 | 15 / admitted | 16 / suppressed |
| 5 | 304.98 | 16 / suppressed | 15 / admitted |

For source 7, the first replacement packet appears earlier in ns-3 because its first transfer completes earlier:

| Event for first source-7 packet | MATLAB, s | ns-3, s |
|---|---:|---:|
| Application generation | 300.000000000 | 300.000000000 |
| DATA transmission begins | 301.496000000 | 300.092000000 |
| Node 8 accepts DATA | 301.740812441945 | 300.336812442 |
| ACK releases source-7 custody | 302.029292441945 | 300.547292442 |
| Next admitted generator attempt | 302.040000000 | 300.560000000 |

The native release explicitly records `count_before=16;count_after=15`. At the following common attempt at 300.56 seconds, native observes NSDP 15 and creates a replacement; MATLAB still observes NSDP 16 and suppresses that attempt. There is no need to invent a different application arrival process to explain this first mismatch.

Source 8 has the opposite early advantage. MATLAB first releases its own initial application at **302.679295345563 seconds**, allowing admission at **302.68**. Native's first corresponding release is **317.291295346 seconds**, allowing admission at **317.30**. The prior MAC-history review already established that native node 8 sends 34 feedback transmissions to source 7 before its own first DATA transmission. MATLAB's accepted common-input replay reproduces that native sequence; repeating that replay would not diagnose the autonomous inputs.

The source/destination NSDP count must not be confused with the node's total NWK queue. For example, at source 8's first differing attempt, MATLAB has NSDP 15 and total NWK queue 16; native has NSDP 16 and total NWK queue 19. Relayed source-7 traffic contributes to the total queue, but uses a different NSDP key.

## Full-run traffic mix

Each row below has the same 285,000 offered attempts in both engines. All unadmitted attempts are NSDP blocks.

| Source | MATLAB admitted, 6,000 s | ns-3 admitted, 6,000 s | MATLAB admitted, 300–330 s | ns-3 admitted, 300–330 s |
|---|---:|---:|---:|---:|
| 2 | 400 | 569 | 29 | 36 |
| 3 | 8,522 | 8,600 | 60 | 58 |
| 4 | 596 | 498 | 24 | 19 |
| 5 | 1,745 | 1,462 | 26 | 35 |
| 7 | 1,133 | 819 | 37 | 37 |
| 8 | 239 | 512 | 31 | 30 |

Source 7's larger full-run admitted population in MATLAB and source 8's smaller population are consequences of the evolving closed-loop service/custody history. The early source-7 advantage reverses over the long run: both admit 37 packets in the first 30 seconds, despite different exact attempt times. **The early race cannot by itself be declared the cause of the entire 6,000-second latency gap.** The provided 100-second admission cohorts retain that evolution for subsequent analysis.

## Random-input ownership

These fixed-destination, fixed-interval flows consume **no traffic RNG draws**. Changing or aligning the traffic stream would not fix this case.

The relevant MAC and receiver random histories are not aligned by the common numeric seed:

- MATLAB `RandomStreams.m` explicitly assigns cached, per-node/per-subsystem `mt19937ar` streams using its own seed mapping. `+csr/+mac/Layer.m` obtains the node's cached `mac` stream and uses `randi` for slot selection.
- The recovered native capture implementation's `CsrMacCore::PickTxSlot` creates a fresh `UniformRandomVariable` for each selection. There is no explicit `SetStream` in that selection path. The device's `AssignStreams` pins only its device uniform and SYNC-normal random variables; the capture runner assigns those two streams per node and sets seed 132/run 1.
- The recovered ns-3 engine source confirms that the default `Stream` attribute is `-1`, which allocates the next global automatic stream index. `RngSeedManager::GetNextStreamIndex` increments that index. This makes the effect of native random-variable creation order explicit; it is not merely assumed from the absence of `SetStream` in MAC code.
- Consequently, neither raw draw values nor consumption/allocation history are equivalent across engines. In native, MAC random-variable creation occurs as the network evolves. MATLAB's MAC stream belongs to the node across successive calls. This is evidence of different random-input ownership, **not evidence that either uses an incorrect slot distribution**.
- The short native capture records its actual draws; the corrected MATLAB long-run export does not retain the full draw, ordinal, and reservation-state history. Existing evidence cannot separate every autonomous scheduling divergence into random realization versus a state-transition mismatch.

## Next useful boundary

Keep the deterministic offered-attempt schedule and the real NSDP admission gate. Align or record **MAC slot selection and receiver randomness**, then let DATA reception, ACK/DACK generation, receiver availability, and custody release evolve through the coupled network. Replaying already-decided admission outcomes or forcing receiver availability would bypass the mechanism just identified. Exact observed random draw values and their call context are required to distinguish differing input realization from differing behavior on the same inputs.

This offline traffic audit executes no simulation and changes no production behavior. Parallel work may prepare the new coupled capture separately; no claim of full network parity is made by this audit.

## Reproduction and files

Run from the recovered workspace:

```text
python3 autonomous/traffic/audit_traffic.py
```

The script reopens the original compressed native trace, not a newly simulated trace. `input_manifest.json` records its required input paths and SHA-256 values. `summary.json` records machine-readable checks and limitations. `paired_attempts_300_330.csv` contains every paired attempt with NSDP, queue size, decision and engine-local packet ID; IDs are not joined across engines. `first_admission_difference.csv`, `source_accounting.csv`, and `admission_100s_cohorts.csv` provide compact views. The two early-service CSVs preserve engine-specific event fields and IDs; their timestamps are not falsely normalized to one floating-point clock.

Source anchors: MATLAB `ApplicationGenerator.m` method `attempt`; `NetworkSimulation.m` method `generate`; `RandomStreams.m`; MAC `Layer.m` constructor and `pickSlot`; recovered native `capture.cc` function `SendFlowPacket` and stream setup; `csr-nwk-layer.h` methods `GetNsdpCount` and `CanAdmitApplicationPacket`; `csr-mac-core.h` method `PickTxSlot`; `csr-net-device.h` method `AssignStreams`. The native source is the recovered observer-instrumented capture tree; the full-run decision/timing claims above are independently checked against the original 6,000-second raw trace.

The random stream allocation source anchors are `autonomous/native_env/engine/src/core/model/random-variable-stream.cc` (`GetTypeId`, `SetStream`) and `rng-seed-manager.cc` (`GetNextStreamIndex`). These sources were restored by the parallel native-environment task; inspecting them did not execute a new network case in this audit.
