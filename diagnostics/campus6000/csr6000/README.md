# Corrected MATLAB: two full 6,000-second cases

This batch runs seeds **131 and 132** using the corrected MATLAB model and the
original ns-3 scenarios. The practical comparison target is **±15%**. Here,
“native” means the ns-3 C++ reference implementation.

## Run

1. Extract the entire ZIP into a new, short local folder, such as `C:\csr6000`.
2. Start a fresh MATLAB session and set **Current Folder** to the extracted
   `csr6000` folder containing `run_6000_batch.m`.
3. Run this one command:

```matlab
report = run_6000_batch;
```

Both cases run automatically, one after the other. No Python, ns-3 installation,
Parallel Computing Toolbox, or extra downloads are required on your computer.
Use MATLAB R2025a or later with its standard Java support.

Return **`out_6000_*.zip`**, whose full path is printed at the end. Send the ZIP
even if a case or comparison fails. The output folder also contains the raw
evidence and local MAT results; you do not need to upload those separately.

This is a several-hour batch. The original seed-131 and seed-132 owner runs took
about 1 hour 47 minutes and 3 hours 3 minutes respectively. The corrected run and
your computer can take a different amount of time. The console can stay quiet
during a case because the existing simulation runs without progress events.
Keep the computer awake and allow space for the full traces and local MAT files.

## Interrupted or failed run

Keep the extracted folder and its `out_6000` subfolder. Running the same command
again reuses a completed case only after verifying its sealed evidence, exact
input/code identity and MATLAB runtime. An unfinished simulation starts from
time zero in a new attempt folder; its earlier partial files are preserved.
A packaging failure does not invalidate a previously sealed completed case.

Only run one invocation against a given output folder. The operating-system lock
releases when MATLAB exits; a remaining `batch.lock` file is harmless. If the
runner reports another active process, let that process finish or close it before
retrying. To deliberately start a separate batch while preserving the original
results, use a new output folder:

```matlab
report = run_6000_batch('out_6000_retry');
```

That optional command starts a separate batch. For ordinary interruption recovery
or a handled failure, the original command is sufficient. Do not edit or delete
individual files in a completed case.

## What is measured

- Source attempts, admissions, delivery, recorded terminal drops and applications
  still pending at the 6,000-second stop.
- Per-source delivery counts and delivered latency against the ns-3 references,
  with the ±15% target and explicit undefined comparisons where a reference mean
  does not exist.
- Delivery within 60, 300, 600 and 1,200 seconds of generation, using equal
  observation windows and retaining unsuccessful traffic in the denominators.
- Full protocol and PHY traces for discovery, causal queue/admission/receipt
  analysis, and investigation of any consequential residual after return.

The full application-attempt counters remain complete. The raw attempted-admission
trace retains its original 100,000-row prefix; its omissions are explicit. All
admitted applications are retained in the application ledger and protocol trace.
Protocol/PHY omissions invalidate capture completeness rather than silently
allowing an incomplete comparison. Native undelivered applications keep their
unresolved-fate classification.

The MATLAB production files are byte-identical to the grouped-routing-corrected
candidate used in the successful September 24 integration return. This harness
does not tune retries, timers, queues or PHY behavior. It uses real PHY,
autonomous discovery/routing, continuous timing, the default `actual-tx` policy,
and no post-stop drain or externally supplied traffic/ACK history.

`completed` means the case executed and its evidence passed the structural
checks. It does not mean every ±15% comparison passed. The two cases refresh
these two histories only; they do not establish five-seed or statistical
equivalence. The returned traces support the subsequent independent latency
phase review; a full native per-application retry-only split remains unavailable.

## Preparation status

The kit includes the model, both scenarios, the verified ns-3 application ledgers,
source/input hashes, a reporting preflight and case checkpoints. Native reference
runs and the previous MATLAB component runs already exist. This new batch runner
has been reviewed and checked statically; execution in MATLAB awaits your run.
See `READY.json`, `plan.json` and `review/` for the precise provenance and checks.
