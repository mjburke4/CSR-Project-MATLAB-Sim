# Native reference binding for the current 6,000-second batch

**Reuse the existing seed-131 and seed-132 native references. No new native simulation is needed.** Both references completed the original 6,000-second campus scenario with the pinned native source/engine, original historical profiles, autonomous discovery, real PHY and complete admission accounting. Their compressed and decompressed traces and application/path ledgers were independently verified during the long-run review.

The current MATLAB candidate's scenario importer supports those exact native CSVs. This is a static source/input binding review; **MATLAB import and the new full runs have not executed here**.

## Exact input choice

The new batch directly imports each original seed-specific native `scenario.csv` with:

```matlab
cfg = csr.scenario.importNs3(scenarioFile, struct( ...
    'HistoricalBenchmark',true,'FlowLimit',0,'Backend','portable'));
```

The imported seed is **131 or 132**, with **no subsequent seed override**. The prior T25 MATLAB workflow imported the original seed-128 benchmark and changed only `Config.Seed`. Reversing only the native CSV's run-row seed token reproduces the exact original seed-128 SHA-256 in both cases. All other scenario bytes, including geometry and traffic, are identical.

| Input | SHA-256 |
|---|---|
| Seed 131 | `e10d210590c80cb839442b7847ee6c7e8b8c21d043da5fe5dcf1f2abb402ca7a` |
| Seed 132 | `fa45217f8631f34d203580842d8a1a12cb18c53a3efbe0b702b2e17aaeb30d48` |
| Original seed 128, reconstructed by reversing that token | `90b143d93c13c6c2761bc5f2875ccc3fff98f85af6f2550370e435df2aaabcfc` |

Direct import changes provenance fields (`SharedScenario.SourcePath`, CSV hash and imported-seed history) and omits the catalog's `Benchmark` metadata unless reconstructed. These differences should be reported accurately; they do not change the scenario's behavioral inputs. The simulation source does not use `Benchmark` or `SharedScenario` metadata to make protocol decisions.

The invariant experiment is seven nodes `[1 2 3 4 5 7 8]`, gateway 1, and six fixed flows from `[2 3 4 5 7 8]` to 1. Each flow attempts traffic from 300 s every 0.02 s, strictly before 6,000 s: **285,000 attempts per source, 1,710,000 per case**. Configured packet size is 200 bytes, corresponding to 185 application payload bytes after the original 15-byte exclusion; DSCP is zero and ACK is required. The historical profile tuple is `legacy-send-only-no-dscp` / `hist-2014-next-tslot-modulo-probe` / `hist-adb97c54-bare`.

Preserve current autonomous defaults, continuous timing, real CSR PHY, `actual-tx` DATA retry policy, gateway startup at 10 s, no observer and no post-stop drain. Do not carry manual/mature-route initialization from the short replay harness into this batch. The original evidence budgets are 1,500,000 protocol records, 1,500,000 PHY records, 100,000 admission-prefix records and 12,000,000 scheduler events. Complete admission counters remain required; 1,610,000 omitted admission-prefix records are expected, while protocol/PHY truncation must be detected.

## Current candidate identity

The 96 MATLAB source files are byte-identical to `integration_next/candidate` and `routing_work/grfix/candidate`, and match the issued ACK/NWK fixture's source binding. Their deterministic source-tree digest is:

`fcf84980619b6902660eb9192b4d71f3f912cafd8fb74074fc752560372d1b4e`

The digest hashes sorted UTF-8 records of `file-SHA256`, two spaces, POSIX relative path and newline, for `.m` files only. All three data assets, including the BER table, match the returned T25 source/reference pins; their hashes are recorded separately in `native_binding.json`.

Against the returned original T25 source inventory, **93 files are unchanged**, two discovery validation helpers are added, and **one production file changes: `+csr/+hop/Layer.m`**. That verified grouped-routing correction finishes successful ROUTING ownership while retaining an already queued routing retry, including single-target routing. The old HOP hash is `67323b4106738c2d1fdfafebf1f408719f878513aa898fb9cf754e446d87d9f7`; the current hash is `21d4a56d782fde35d45f102c137b6c78c3bf4cdc05593d15fb9a7db8f26c2649`. Short replay harness revisions made no further production change.

The unchanged historical `run_tranche25_validation` should not be reused as the new runner: its identity checks require the old unchanged baseline and full historical reference/catalog package. Also, `integration_v2/candidate` contains `+csr` and `data`, but lacks the catalog/plan/CSV dependencies required by `benchmarkSuite` and `tranche25Suite`. Direct import avoids those missing suite dependencies. The new runner should bind the current candidate and record the newly authorized **15% descriptive target**, leaving the historical 10% plan unchanged.

## Reference metrics and small staged evidence

| Seed | Attempts | Admitted | Unique delivered | Duplicate delivery events | Unresolved outcomes |
|---|---:|---:|---:|---:|---:|
| 131 | 1,710,000 | 12,630 | 12,261 | 0 | 369 |
| 132 | 1,710,000 | 12,460 | 11,794 | 4 | 666 |

`native_binding.json` contains the exact per-source counts and mean delivered/source-NWK/relay-NWK/combined-service values. Native terminal drops remain unobservable as a complete application outcome; unresolved means admitted without observed final delivery, not a live-queue count.

The new analysis reference is the **canonical raw-verified `applications.csv`** for each seed, rather than the legacy `native-applications.json` summary. Those two canonical ledgers total 5,801,029 bytes uncompressed; their paths, hashes and suggested targets are listed in the JSON. They support admitted/unfinished and scheduled-identity matching without shipping native simulation traces.

Small supporting files total **49,495 bytes** across both seeds: `scenario.csv`, original `manifest.json`, `app-admission-diagnostics.csv`, `seed-recipe.json`, `ns3-run.log`, and the verified `accounting.json`. The legacy native summary JSONs remain hash-bound source evidence for this review; they are not substituted for the canonical analysis ledger. Do not copy the large compressed native traces into the owner kit. Original manifests may retain hashes of those external large artifacts; the new package should explicitly bind its staged subset rather than claim all original files are bundled.

For seed 131, native sources 2, 7 and 8 admit and deliver zero applications. Relative percentage error and conditional latency are therefore undefined for those populations; missing values are not zero-delay or zero-error passes. Unique application deliveries and duplicate delivery events remain separate, and equal seed numbers do not imply common random streams. Reference reuse enables the new comparison; it does not establish that the current candidate meets the 15% target.
