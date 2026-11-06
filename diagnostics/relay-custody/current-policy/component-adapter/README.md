# Current-policy preflight and matched-component adapter

This is a **runtime-unvalidated candidate** for Windows MATLAB R2026a Update 5. Static integrity checks and independent source review passed. The new loader, constructor/writer preflight and relocated execution path have not run. It is an additive, opt-in component adapter, not a full6000 runner or validation of a relocated full-network path.

Existing root entrypoints, historical node8case and production model/timing behavior are unchanged. Scientific configuration is deliberately **not distributed**: execution requires an authorized external private configuration file, supplied through a private hash-bound plan. The adapter never copies that file into its package or output, never exports its contents or exact configuration hash, and never substitutes scientific values.

## Package contents

- `frozen/`: exact bytes of the previously executed MATLAB model/data namespaces and four bounded writer/observer helpers, with the effective TerminalSimulation and ReceiverTimer overrides. No stale configure_case, seed-specific qualifier or full-run driver is installed.
- `observer/`: the exact two read-only NWK/HOP overlays used in the accepted component execution. They take precedence from the first constructor onward. Loaded classes are never swapped.
- `fixture/`: the exact previously executed MATLAB congestion and HOP-boundary harnesses and runner. Their scripted MAC feedback and synthetic setup are distinct from natural full-network behavior.
- `adapter/`: new loader, constructor/writer preflight and tiny explicit writer plan. These new paths remain runtime-unvalidated.
- `SOURCE_MANIFEST.json`: a new relative inventory and effective symbol map. `PROVENANCE.json` identifies prior evidence by hashes. Original full-run manifests remain separate; prior snapshot execution does not validate this new package.

No scientific configuration, private native implementation, native headers, original private manifests, raw traces, machine/account paths, ownership tokens or private file identifiers are included. Configuration data must not be added to this directory, committed as examples, embedded in scripts, or included in public result attachments.

## Consumer setup

Use a fresh checkout and a reviewed externally supervised Windows job. A normal GUI or already loaded model session must fail safely. The loader does not clear classes, reset global paths or terminate processes during its freshness check.

1. Fetch the exact repository commit into a fresh workspace with Git line-ending conversion disabled (`core.autocrlf=false`). Use this component-adapter directory as the package root. Verify the published package-manifest SHA-256 and run `python tools/validate_package.py` here. If Python is unavailable, the controller must independently verify every manifest file before execution.
2. Select the already authorized private scientific configuration outside the package and output directories. Compute its exact byte SHA-256 locally. Do not upload or copy it into the public package. It must satisfy the exact source validator and current-policy fixture assertions; no sample dataset or silent fallback is supplied.
3. The controller creates a separate empty output directory, a private execution plan and a sanitized owned-job receipt outside package/output. Keep the private configuration path/hash and raw ownership tokens private. Bind the plan's exact bytes by SHA-256. Launch a fresh owned MATLAB `-batch` engine, add only this package's adapter directory, and call `run_current_policy_adapter(planPath, planSHA256)`.
4. The controller enforces one owned attempt, asynchronous wall/memory limits, bounded controller logs and owned-job closure. The adapter checks the local binding receipt, deadline and unchanged external configuration hash between bounded stages. It does not establish or independently verify engine creation, a Windows job or asynchronous termination. Preserve `engine_creation_independently_verified: false`.
5. Recommended initial scope: `preflight-and-matched`, at most 300 seconds wall time, 3 GiB memory and 64 MiB output. No protected system query is required. Failure of any guard is a failed attempt, not a partial pass. Retain bounded failure artifacts privately for review.
6. Retrieve ADAPTER_RESULT.json, SOURCE_RESOLUTION.json, the three preflight writer files and COMPONENT.json when present, plus a sanitized controller launch/closure receipt. Compare COMPONENT.json independently with an authorized reference using the reviewed comparator. Execution success alone is not a cross-engine comparison pass. Review any artifacts for disclosure separately before publishing them.

## Private plan and receipt

The plan has exactly these fields:

- schema: `csr-component-execution-plan-v1`
- mode: `preflight-only` or `preflight-and-matched`
- execution_id: a nonsecret local run label, 1–80 alphanumeric, underscore or hyphen characters
- package_manifest_sha256 and source_manifest_sha256: exact published manifest hashes
- scientific_configuration_path and scientific_configuration_sha256: authorized external private file and its locally computed byte hash
- output_root and ownership_receipt_path: explicit absolute consumer-local paths
- deadline_utc: UTC `yyyy-MM-ddTHH:mm:ss.SSSZ`
- max_wall_seconds: integer 1–300
- memory_limit_bytes: positive integer at most 3221225472, enforced externally
- output_cap_bytes: integer 20971520–67108864

The receipt has schema `csr-owned-component-receipt-v1`, matching execution_id, plan_sha256, package_manifest_sha256, deadline_utc and the three limits; job_owned and local_job_binding_verified are true, and engine_creation_independently_verified is false. Attestations must come from the controller's locally verified job binding. The adapter neither manufactures nor writes this receipt. The controller produces it after its launch/binding checks and before adapter entry; no additional independent PID or creation-time query is required. Plan, receipt and configuration bytes must remain unchanged during execution.

The loader reads at most 1 MiB of configuration JSON and calls the exact validator. JSON-unobservable vector orientation/type normalization is permitted; re-encoded values and fields must match. The constructor helper then checks idempotent normalized configuration. The external file is checked before and after work, including before each stage. No model, policy, duration, trace cap, memory setting or scientific value is adjusted to make a run pass.

## Bounds and failure behavior

Constructor preflight uses a 16,384-byte logical reservation: four 4,096-byte accounting units, not a measured physical allocation size. Directory/filesystem metadata is outside this estimate. Successful preflight creates only random_requests.digest.json (≤2,048 bytes), synthetic.digest.json (≤2,048 bytes) and synthetic.jsonl (≤512 bytes). first_divergence.json has a 2,048-byte reservation but must stay absent. Zero random records/raw bytes are allowed. This constructor-only plan must never be reused for traffic execution.

The exact component harness caps its main scheduler at 10,000 events and 5,000 rows, its boundary scheduler at 1,000 events and 1,000 rows, and serialized output at 16 MiB. The loader caps its source-resolution report at 256 KiB and result at 128 KiB, uses create-new writes, rejects unexpected output files and forbids reparse paths. Output checks use logical lengths and the stated reservation estimate. External supervision supplies asynchronous enforcement; callbacks alone cannot interrupt a constructor or allocation. A constructor failure before returning its object relies on exact-source destructors and outer owned-process cleanup, not a guaranteed helper-level cleanup claim.

## Prior evidence and remaining work

The accepted prior main fixture matched 25 checkpoints, 34 ordered common events and 299 checks. That result applies to its recorded execution, not this new loader or writer preflight. Raw MATLAB/native timestamps are not rounded into equality. The separate HOP edge remains unequal: MATLAB queues a retry just before ACK, cancels it and ends with clean-ACK streak 0; native registers equal-time ACK first, emits no retry and ends with streak 1. Both end with no owners or credit. This is not an established cause of the campus gap or full-network equivalence. Unsent LastTx is MATLAB Inf versus native zero sentinel, both unconfirmed and timer-ineligible. Third-ACK reset ordering is source-supported, not isolated by the main fixture's final streak 0.

A reusable full6000 entrypoint remains separate work: explicit scenario/seed and policy inputs, compatible traffic writer/retention and aggregate export contracts, bounded supervision, and validation of that full-run path. `ac.TerminalSimulation.run` is deliberately unsupported here because full-run support helpers are not installed. Exact prior full6000 evidence remains attached to its original snapshot. Another full6000 realization is not required to validate this bounded adapter's present contract.
