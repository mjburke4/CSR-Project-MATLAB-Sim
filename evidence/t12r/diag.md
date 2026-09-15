# Tranche 12 return diagnosis

All four relay cases stop at the first DATA ingress because the fixture registered `NsdpCount` while the current `networks` cell entry was empty. The anonymous function captures that incomplete cell value. Assigning the NWK handle later does not repair the captured value. This is a fixture construction defect, not an observed production network algorithm failure.

The adjacent `RouteAvailable` callback has the same latent defect. Route both through nested functions that look up the live `networks` entry at invocation. `CanSendData` currently captures an already constructed HOP handle and is safe in this construction order; routing it through a nested function makes all layer lookups consistent. The remaining fixture callbacks already use nested functions or capture existing handles/immutable payloads appropriately. No equivalent issue was found in the clock fixture.

The uploaded R2025a run records 244 relay observations, 10 draws, zero deliveries, and 63 failed checkpoints. Its 2,649 relay mismatches arise from aborted trajectories, so they cannot establish relay numerical parity. The clock component passes all 72 checks with the three deliberately expected continuous-clock row differences.

The existing MATLAB integration tests are meaningful regression coverage: they exercise both callbacks through real HOP DATA reception, live NWK custody, 120 deliveries and 180 release callbacks. Nine of the twelve relay tests fail in this upload. Retain these requirements and rerun the existing 72-test runner after the repair. Do not loosen comparisons, regenerate native references, or change production MATLAB sources.

Review scope: source inspection and actual returned evidence only. No MATLAB runtime was available to this reviewer. Original `csr12` tree remained untouched.
