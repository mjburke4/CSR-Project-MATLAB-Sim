# Run Tranche 10 on MATLAB

Extract the prefix-free `csr10.zip` into a new short directory, preferably
`C:\csr10`. Do not unzip it over a running or accepted older package.
Open MATLAB R2025a in that directory and run:

```matlab
report = run_tranche10_validation;
```

The default run performs three deterministic contract families, all portable
unit tests once, 29 retained scenarios, 18 sweeps, six small diagnostics, two
tracing controls, and the full 6,000-second campus benchmark. Contracts and
regressions execute before campus. A failure stops the gate and preserves
partial evidence for diagnosis.

Allow roughly 1.5–2 hours on the laptop based on previous measured runs. The
campus workload alone previously took 72 minutes. Its simulated seconds are
not wall seconds; no progress callback or wall-time estimate changes the
simulation. Keep MATLAB running until the final upload message appears.

Results use `results\t10\r<short-id>` with compact case directories:

| Directory | Contents |
| --- | --- |
| `k\mac`, `k\rx`, `k\ack` | Matched timing and retained ACK contracts |
| `tests` | Portable test outcomes |
| `r\01` through `r\29` | Retained scenarios |
| `s\01` through `s\18` | Load/recovery sweeps |
| `b\c128` through `b\c132`, `b\a129` | Six unchanged diagnostics |
| `c\c129`, `c\a129` | Tracing-disabled controls |
| `b\campus` | Campus6000, seed128 |

Upload the **`tranche10_evidence.zip`** whose complete path is printed at the
end. The archive contains CSV, JSON and closed logs; larger MATLAB objects
remain on the laptop. Do not rename or edit internal files before uploading.
Full comparison and acceptance follow inspection of the returned archive.

For an explicitly shorter diagnostic run, omit campus:

```matlab
report = run_tranche10_validation([], struct('RunCampus', false));
```

This still runs tests, contracts, retained cases/sweeps and small diagnostics.
It produces **diagnostic-only evidence**, not the completed campus milestone.
`RunTests=false` is also diagnostic-only. Use the default command for the full
acceptance gate; neither option is needed for the normal handoff.

For an output path outside OneDrive while keeping the package elsewhere:

```matlab
report = run_tranche10_validation('C:\csr10r');
```

Older tranche commands remain available, but run them from their frozen
accepted packages when exact historical reproduction is needed. This package
includes the two Tranche 10 MAC timing corrections.
