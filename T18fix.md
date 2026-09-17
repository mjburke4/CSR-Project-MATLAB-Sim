# Tranche 18 path-check repair

Extract every file from `t18fix.zip` over the same installation where you
already applied `t18up.zip`. Accept file replacements. This is a small patch;
it requires the original T18 update and does not replace that full update.

Start a fresh MATLAB session in that installation root and rerun:

```matlab
clear functions
report = run_tranche18_validation;
```

Return the new printed `t18.zip`. The failed attempt completed no tests or
simulations, so there is no completed simulation work to repeat.

The original T18 scenario loader rejected valid filenames such as
`scenarios/t18/inputs/r128.recipe.json`: its regular expression disallowed
the dot before `recipe`. The repaired loader requires the exact shipped
scenario, recipe and native-reference paths for each case. File containment
and hash checks remain in place.

The returned R2025a evidence matched all 346 issued source hashes and all
731 reference hashes. The installation's folder name did not cause this
failure. The repaired candidate updates its verification hashes and preserves
the original failure, candidate and source under
`evidence/tranche-18-path-fix`.

Only the T18 scenario-loader path predicate changes. All 313 accepted T17
source files remain byte-identical. Workloads, native evidence, PHY/ECC,
timing and the 186-test gate are unchanged. The original preparation reports
describe the superseded candidate; the repair verification is recorded in
`evidence/tranche-18-path-fix/verification.json`.

MATLAB execution of this repair remains pending. Static analysis and
independent review do not establish MATLAB runtime success.
