# Tranche 11 native control build

This is a fresh local build of unchanged pinned sources. It is the control
environment for the separate Tranche 11 replay fixture. No fixture hook is
included in this build record.

- CSR commit: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`.
- Engine commit: `6b5cd24ea80713ce16d88575869aedd6f432bdae`.
- CSR source: `ns/`.
- Engine source: `engine/`.
- Headers: `engine/build/include/`.
- Libraries: `engine/build/lib/`.
- Profile: C++23, Debug, assertions and logging enabled.

From a fresh `t11n/` directory beside `csr11/`, use:

```sh
python fetch.py
python -m pip install --target tools 'cmake==3.31.10' 'ninja==1.13.0'
python build.py
python verify.py
```

The checkout helper must be run in a fresh directory. It fetches both exact
commits and checks them out detached. The build helper copies only the 24
historically pinned CSR module files and checks every copied hash.

`verify.py` compiles and executes the unchanged six-case ACK contract, validates
all 101 checks, and requires byte identity with the stored T9 checkpoints.
It emits a build manifest, input hashes, exact commands, toolchain identities,
logs and smoke results under `csr11/evidence/tranche-11-native-build/`.

The first actual build completed successfully, but its directly redirected log
was retained only through step 53. A successful follow-up build completed the
retained objects and captured stdout after process exit. The accepted manifest
records both events and does not claim the follow-up had no work pending.
The reproduction helper now captures stdout after process exit as well.

The native build did not run MATLAB, the full ns-3 engine test suite, or the
historical statistical benchmarks. It establishes the local build environment
and the unchanged deterministic ACK reference only.
