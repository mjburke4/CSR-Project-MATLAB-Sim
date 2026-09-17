# T21 offline diagnostic package

Read **T21_Review.md** first. This package records completed analysis of the
accepted T20 results using the revised **±10% numerical target**. It is not an
installation overlay. **No MATLAB command or new simulation is required.**

The default, PHY/ECC, continuous timing, all 376 issued source bindings and all
98 bound references remain unchanged. T21 reused the accepted 716/716 MATLAB
tests; it did not execute new MATLAB tests. The numerical target change does
not alter the accepted T20 result or its historical ±5% report.

| Item | Contents |
| --- | --- |
| T21_Review.md | Findings, engineering disposition and next bounded question |
| diagnostic.json | Machine-readable outcome and bound result hashes |
| target/ | All seed/flow comparisons at both ±5% and ±10% |
| matlab/ | Verified ownership/service reconstruction and source-derived threshold replay |
| native/ | Streamed trace analysis, same-engine lineage and true capacity-release joins |
| source4/ | Admission/completion decomposition and original-source loss attribution |
| pinned-source/ | Exact pinned native HOP header inspected for this review |
| review/ | Independent mathematical, source, interval, lineage and final review checks |
| SHA256SUMS.json | Hash and size inventory of this package |

## Optional reproduction

All scripts use Python 3 and its standard library. Preserve this delivered
package as the record of the reviewed run; work on a copy when reproducing.

Extract a copy of this ZIP into a folder named `t21-work` beneath a workspace.
Use these neighboring inputs:

| Workspace path | Input |
| --- | --- |
| csr20/ | Exact accepted T20 installation, including its bundled references |
| t20-return-review/package/ | Extracted `t20review.zip` |
| t20-return-review/owner/ | Extracted `original-t20.zip` from that review |
| t20-return-review/analysis/ | Copy of the review package's `analysis/` |
| t20-return-review/independent-findings/ | Copy of the review package's identically named folder |
| upload/t20.zip | Unmodified `original-t20.zip`, renamed only |

The accepted T19 seed-128 archive is already bundled at
`csr20/evidence/t19/owner.zip`. The native traces for seeds 129/130 are bundled
in the original T20 update. Input hashes are in `input-provenance.json` and the
individual result JSON files.

Run from the workspace root:

```bash
python3 t21-work/compare_target.py --review-package t20-return-review/package --output t21-work/target
python3 t21-work/matlab/extract_matlab.py --workspace . --output t21-work/matlab
python3 t21-work/matlab/replay_flow_threshold.py --workspace . --output t21-work/matlab
python3 t21-work/native/analyze_native.py --source-root csr20 --out t21-work/native
python3 t21-work/native/join_outcomes.py --source-root csr20 --out t21-work/native
python3 t21-work/native/audit_native.py --source-root csr20 --out t21-work/native
python3 t21-work/source4/analyze_source4.py --workspace . --native-root t21-work/native --output t21-work/source4/source4.json
python3 t21-work/write_report.py
```

Native parsing streams about 3 GB of uncompressed trace data without writing
an uncompressed copy. Allow several minutes. Script execution timestamps and
elapsed times may change during reproduction; the numeric findings should
reproduce. Delivered independent-review hashes attest to the delivered run,
not a later rerun with changed files.

## Interpretation

The target is an engineering screen, not a statistical-equivalence claim.
Keep individual seeds visible alongside pooled ratios. Delays are conditioned
on the packets actually delivered; their populations differ between engines.
Detailed MATLAB admission-state observations stop at 633.32 seconds, although
application-generation traces and admission counters cover the whole run.
Historical native seed 128 lacks full custody telemetry. Missing observations
are not treated as zero, and no omitted blocking reasons are reconstructed.

NSDP is per original source/destination. DACK releases that ownership before
its later HOP capacity release. The reports preserve those separate endpoints,
finite-stop censoring, original-source identity and duplicate-delivery rules.
