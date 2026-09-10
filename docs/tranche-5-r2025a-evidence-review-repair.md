# Tranche 5 R2025a evidence analyzer repair

Review date: 2026-09-09. Validated MATLAB candidate: `536b288`.

The returned Tranche 5 evidence exposed a Python analyzer compatibility defect.
MATLAB's JSON encoder represented exact file sizes using exponent notation:
`2.485837E+6` for a 2,485,837-byte PHY trace and `1.01088E+6` for
1,010,880-byte protocol/combined traces in the retained mesh regression.
Python's JSON decoder loads those values as integral floats. The analyzer's
previous decimal-digit check rejected them before checking the actual file
size and hash. This was an analyzer failure, not a MATLAB execution failure.
Nine instances occur across the run inventory, retained regression inventory,
and mesh case manifest.

`scripts/analyze_research_sweep.py` now accepts native Python integers,
digit-only strings, and finite nonnegative integral floats strictly below
`2^53`. Floats at or beyond that boundary are rejected because distinct integer
values can have the same binary64 representation. Exact integer values and
digit strings retain all digits without conversion through float. Booleans,
negative values, fractions, nonfinite values, and decimal/exponent strings are
still rejected. File-size, SHA-256, row-count, source-snapshot, and exact-file-set
checks are unchanged.

Four new Python tests cover the exact returned numeric tokens, integer
precision boundaries, invalid values, and inventory size/hash rejection with
integral float counts. The focused analyzer suite passes 28/28 tests, and the
complete Python suite passes 75/75 tests. No MATLAB file or simulator behavior
was changed.

The repaired analyzer completed against the untouched returned evidence:

| Check | Result |
| --- | --- |
| Descriptive analysis | Completed for all 18 cases |
| Seeds | 128, 129, 130 |
| Hash-bound test CSV | 367 passed, 0 failed, 0 incomplete |
| Recorded source snapshots | 116 entries, initial and final equal |
| Native execution | Not requested / not run |
| Further serialization failures | None observed |

The 116 source snapshot entries include configuration and tooling files; this
is not a count of MATLAB sources. The analyzer checks internal evidence
consistency and descriptive statistics. It does not by itself establish a
tranche acceptance decision or MATLAB/ns-3 equivalence.

Input ZIP SHA-256:
`824cf0f5cb6a735ee896ebc5431be5c72f69d9d95135c8e03311238bd0ca75c1`.

Input `validation_metadata.json` SHA-256:
`bd0a46d92e0a57875db9d8d6c2d9102a9edaf92937300170a3d227938a39fdd0`.

Generated report SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `sweep_analysis.json` | `a53449ca77e354dab20200fbc6ec92b09e42b0c324d6b76d86e3095616818186` |
| `seed_observations.csv` | `8b2bc7b22a0e7074817494918b8134a92ec10fcbe8a0d44a0c1149abc28bc5c0` |
| `group_statistics.csv` | `49fe889c29f9b6c175f45af15783a609d6786631284321406f4fb191f158d301` |

Reproduction, with output outside the extracted evidence directory:

```sh
python -m unittest discover -s scripts/tests -v
python scripts/analyze_research_sweep.py --evidence EXTRACTED_RUN --output ANALYSIS_OUTPUT
```

No MATLAB rerun is needed for this Python-only reporting repair. The original
candidate and returned archive remain the MATLAB execution evidence.
