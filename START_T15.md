# Tranche 15: transport timing under continued traffic

Extract `t15up.zip` directly into the package folder where you successfully ran the repaired Tranche 14, replacing matching files. Keep that folder current in MATLAB. The update adds this experiment and preserves the reviewed simulation sources; it does not require an extra nested folder.

```matlab
clear functions
report = run_tranche15_validation;
```

Upload the new **`t15.zip`** at the path printed by the runner, including if a case or test fails. Outputs stay under short `results/t15/r...` folders. Policy folders are `timing/c` and `timing/n`; per-case observations use `c1` through `c4`.

The runner first runs eight transport-time tests, then runs the same four 64-second loss/recovery cases under two policies, for 528 structural checks. It finishes with the retained 109-test MATLAB suite: **117 tests total**. Allow several minutes; total runtime is an estimate until your run completes. This does not run the 6,000-second campus benchmark.

Both policies use real NWK admission/custody, HOP reliability and MAC queue service, with controlled addressed-group loss on the fixed 4 → 5 → 1 chain. They share all offers and prescribed contention draws. The experiment changes only how the new fixture computes transport arrival timestamps. It leaves the global scheduler, startup phase, production radio policy and PHY/ECC unchanged.

The reviewer will compare delivery, retries, ACK overhead, capacity release and latency, and verify that the continuous branch reproduces the accepted Tranche 13 observations. A successful run is evidence for that bounded experiment; it does not by itself establish full-network parity or authorize a production timing change.

See `docs/tranche-15-spec.md` for the experiment and `docs/release-roadmap.md` for the three-milestone release target.
