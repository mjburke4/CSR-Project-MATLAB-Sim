# Restore the native capture environment

The native environment was recovered by cloning the two public repositories at their original pinned commits. A missing local executable does not require the MATLAB user to install or run ns-3.

## Rebuild in a fresh Linux workspace

Prerequisites: Python with pip, Git, GCC 13.3 with its standard C++ development libraries, and network access to GitHub and PyPI. The restore script installs CMake 3.31.10 and Ninja 1.13.2 under the selected directory. It does not install a simulator on the MATLAB user's machine.

```bash
python3 restore_native.py --root /absolute/path/native_restore --jobs 2
```

The script clones the repositories, checks out detached pinned commits, verifies both Git tree hashes and clean tracked files, creates `engine/contrib/csr` as a link to the CSR checkout, configures the original Debug profile, and builds all nine required modules. It verifies every shared library is ELF with exported symbols and resolved relocations, then writes `build.json`. Existing checkouts with different or modified tracked sources are rejected.

During this restoration, three generated object files were empty after a four-job build, causing unresolved symbols at link time. Only those generated files were removed and rebuilt with two jobs; tracked sources were unchanged. The script detects empty generated objects, records the recovery, and retries at two jobs. Other build errors are not suppressed.

| Repository | Commit | Git tree |
| --- | --- | --- |
| `mjburke4/CSR-Project-NS3-part2` | `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` | `b611b233fb369569b98f0914ece24d029ccc2f42` |
| `nsnam/ns-3-dev-git` | `6b5cd24ea80713ce16d88575869aedd6f432bdae` | `f30343185fb057e3a9cdd54f496cca0cef49ae23` |

Profile: Debug, assertions and logging enabled; modules CSR, spectrum, buildings, propagation, mobility, antenna, network, stats and core. Optional GSL, SQLite, Eigen, GTK3, visualizer, tests, examples, precompiled headers and ccache are disabled. Warnings are not treated as errors. The complete configure/build arguments and actual compiler versions are recorded in `build.json`.

## Run the existing capture kit

After successful restoration, the paths required by the kit are:

```bash
python3 /absolute/path/two_case_next/run_two_native.py \
  --native-source-repo /absolute/path/native_restore/csr \
  --engine-repo /absolute/path/native_restore/engine \
  --engine-build /absolute/path/native_restore/engine/build \
  --out /absolute/path/new_native_capture_output
```

The output directory must be new. The capture drivers preserve the original exact-prefix gates. A successful environment build alone does not establish a verified capture or network parity. Native capture generation and comparison are maintained by the assistant; the user's handoff remains one MATLAB runner and its returned results ZIP.
