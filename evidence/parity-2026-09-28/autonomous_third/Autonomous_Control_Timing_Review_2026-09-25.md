# Seed-132 autonomous control and callback timing review

The returned run exposed a concrete control-admission ordering mismatch: MATLAB defers a new KEY_REQUEST until after the receiver leaves Track; native ns-3 queues it before that transition. This makes native MAC preparation start earlier at nodes 3 and 5. A separate receiver-clock difference explains the guarded 184-versus-183 payload-bit stop, but does not establish a packet-delivery difference in this occurrence.

One MATLAB batch is ready to distinguish these causes. It tests the existing nanosecond receiver-callback option by itself, then tests that option with an isolated KEY_REQUEST correction. The accepted natural run is reused when its existing gates pass. Neither new case has been executed in MATLAB here, and the full-network target remains **±15%**.

## What the actual return establishes

Input: `out_auto_20260925_131150.zip`, SHA-256 `8b3b7c85d89bd2b39db19d1e4657b6fee03ec48c234b235a3af4dca0c7cc030b`. The archive has 27 members and identifies MATLAB R2025a, version 25.1.0.2943329, PCWIN64. Its source manifest matches all 134 files of the issued repair kit.

| Check | Actual result |
|---|---|
| Native fixture import and malformed-input preflight | Passed in MATLAB |
| Accepted natural case A | Reused; runtime, configuration, source and exact trace gates passed |
| Rechecked natural rows | 12,200 protocol; 12,198 PHY; 9,000 application attempts |
| Common-input case B | Stopped at 11.500323527005154 s on node 4 payload bit count |
| Random inputs | Six per-node/purpose matches, then one rejected request |
| Verified physical transmissions | First gateway DISCOVER, at 10.465 s |

The six matching requests are **not an identical global event prefix**. Native has nine requests through the stopping time; MATLAB has seven. Native already requested MAC reservation draws for nodes 3 and 5. MATLAB had not requested those draws. The provider deliberately matches by node, purpose and ordinal, leaving event timing endogenous.

## Earlier KEY_REQUEST ordering mismatch

Both implementations receive the same first gateway DISCOVER at nodes 3 and 5. Their queue insertion order differs:

| Stage | Native ns-3 | Returned MATLAB |
|---|---|---|
| Discovery accepted | Receiver is Track | Receiver is Track |
| NWK generates KEY_REQUEST | Direct HOP/MAC admission during receive callback | Schedules a separate, same-time NWK pump |
| Receiver returns to Search | KEY_REQUEST is already queued; preparation starts | Queue is still empty; preparation remains inactive |
| Deferred pump | Not required for this admission | Enqueues KEY_REQUEST in Search, with next slot already scheduled |

Native starts preparation at 11.500308077 s for node 3 with reservation counter **27**, and 11.500311086 s for node 5 with counter **10**. In MATLAB, each ends with one queued packet, preparation inactive and counter −1. The next slot is scheduled for 11.505 s. The returned run stops before that slot, so its eventual transmission or delivery effect is not measured.

The source boundary is MATLAB `csr.nwk.Layer.queueControl` → `wake`, which defers the pump. Native `CsrNetLayer::SendKeyRequest` directly calls HOP. Existing MATLAB MAC already starts preparation on Track→Search when a packet is present. The candidate therefore changes NWK admission rather than generic MAC scheduling.

The D-only classes submit just the newly created no-ACK KEY_REQUEST after existing replacement and capacity checks. They preserve radio options, set ownership before the callback, and find the owner again after synchronous completion. They do not pump other controls, DATA or reliable routing. The original 99 model files remain byte-identical. A failed immediate admission falls back to the original deferred wake path; that fallback is not established as native-equivalent under full queues or other competing owners. The motivating observed case has an empty queue and successful admission.

## Separate PHY callback-clock difference

Both engines retain the same continuous physical signal geometry. Native closes receive intervals using its nanosecond callback clock; the returned MATLAB case uses the continuous signal end.

| Quantity | MATLAB continuous callback | Native callback |
|---|---:|---:|
| Payload start (s) | 11.476863527005154 | Same |
| Interval end (s) | 11.500323527005154 | 11.500323527000001 |
| Duration × rate | 184.00000000000028 | 183.99999995958294 |
| Truncated payload bits | 184 | 183 |

The endpoint difference is **5.153 picoseconds**. The bit allocator's truncation rule agrees. The same captured BER and uniform yield **two payload errors for either bit count** in the native arithmetic probe. The matched header adds two errors in both cases. Node 4 was already Idle, untracked and rejected before this calculation; the MATLAB guard stopped before consuming the payload sample. This arithmetic counterfactual is not a completed MATLAB receive result.

The existing `csr.sim.TransportTiming('nanoseconds')` option has the relevant scope: quantize receiver arrival, preamble-end and receive-end callback targets while retaining continuous physical geometry. Independent calculations against the existing capture found:

- All 1,960 receiver-arrival targets, 1,658 observed preamble-end targets and 1,958 observed receive-end targets match. Two signals are unfinished at capture end and are not counted as matching receive outcomes.
- All 1,542 directly observed stochastic PHY sample bit counts match the existing division-based clock conversion under the captured native interval history.
- Reconstructed counts agree for all 4,070 native intervals, including those without a stochastic draw. This is fixed-history arithmetic, not a coupled-network run.

Native clock conversion and division by 1e9 differ by one binary64 ULP at two of 10,139 audited tick values, without changing any captured sample bit count. Multiplication by 1e-9 performs worse and is not substituted. No epsilon, copied bit count or relaxed semantic guard is introduced. The supported claim is bounded agreement on this capture, not universal binary64 clock equivalence.

## One batch to run

Use **`autonomous-control-timing-tests.zip`**. Extract into a new folder, restart MATLAB, and set Current Folder to the extracted `autocase` folder containing `run_autonomous_tests.m`. Run:

```matlab
report = run_autonomous_tests;
```

Return the printed **`out_auto_YYYYMMDD_HHMMSS.zip`**, including diagnostic stops. No ns-3 command is required from you.

| Case | Purpose |
|---|---|
| A | Reuse accepted natural capture after the same strict gates; rerun only if runtime or configuration differs |
| C | Common native inputs plus existing nanosecond receiver callbacks |
| D | Same as C plus isolated synchronous KEY_REQUEST admission |

C and D each start all seven nodes at zero and run to their first semantic mismatch or 330 s. A diagnostic stop in C does not prevent D. No new 6,000-second run is requested. The earlier B remains explicitly historical.

The runner preserves raw protocol, PHY, application-admission and ordered state/timer traces, random request accounting, first-divergence context and callback-timing records, including partial runs. Timing records describe scheduled targets, not proof of callback execution. Strict transmission, context and unused-input checks remain enabled.

On return, first check the seven public-NWK preflight assertions. Then compare C and D around the two missing native MAC requests: did D insert KEY_REQUEST while Track and reproduce counters 27 and 10? Check the node-4 payload request separately, and inspect the next global event divergence. Only subsequent end-to-end accounting and latency evidence can establish progress toward the 15% target.

## Validation and evidence

Preparation included independent native/source and runner reviews, exact reversal of the two candidate source transformations, model/native-fixture identity checks, MATLAB static syntax checks, and package/hash validation. The new preflight and C/D runtime outcomes remain pending MATLAB execution. The only new native execution was an arithmetic microprobe; no new network simulation was run.

`autonomous-control-timing-evidence.zip` contains the exact candidate kit, returned evidence, original native observations and fixture, reproducible audits, independent reviews and validation receipts. `EVIDENCE_README.md` explains dependencies for reproducing the native probe. Historical absolute paths in provenance identify the original environments; they are not instructions to load other copies of the code.
