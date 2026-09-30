Seed 132 common-input native capture, [0, 1200) seconds
=================================================

The capture runs all seven original nodes autonomously from time zero, with the
original scenario, driver and existing nine native libraries. It is not a replay
of receiver state or feedback. Only two passive observation cutoff constants
were extended 400→1200 seconds. No protocol code, scheduling or RNG call changed.

Validation
----------
All 896,568 canonical rows and all 30 fields match the independent original
6,000-second native seed132 reference exactly. This includes all 270,000 offered
applications. No captured canonical or observer row reaches the exclusive 1200 s
endpoint. The full reference hash is checked before normalizing.

The extended fixture retains every field/ordinal of the accepted 400 s prefix:
7,904 random rows; 2,201 transmitted children;113,739 receiver-history rows;
203,629 full observer rows; and the complete 2,222,101-byte raw MAC prefix.

Two independent native executions produce byte-identical canonical, admission,
MAC and receiver observation files. Timestamped stdout differs only in the
literal output-directory path in its final summary. Executable+ all 9 libraries
pass ELF and ldd-r checks. All 9 library hashes equal the previous validated run.

Full 1200 fixture: 50,375 consumed random draws; 8,742 physical transmissions;
10,306 transmitted children; 624,708 receiver-history observations.

Existing all-node NWK/HOP observations are sufficient for node 8: local and
relay enqueue identity, ordered queue depths, admission reason/NSDP/capacity,
HOP admission, custody and capacity release, DACK holds, and queue scan callbacks.
No extra model observer hooks were introduced. See independent node 8 observer
review for queue reconstruction and the limits of NWK timestamp comparisons.

Important distinction
---------------------
These are native capture gates, not a new MATLAB result or an autonomous 20%
parity claim. The MATLAB fixture consumes only the RNG values and compares
transmissions as outputs. Receiver history and feedback are reference evidence,
never inputs. Strict common-input comparisons remain exact; 20% applies only to
the agreed autonomous population metrics.

Reproduction from the evidence archive
--------------------------------------
Extract preserving node8_1200/native and recovered/native_origin paths. Work in
a disposable copy because run_capture.py writes run files and receipts.

1. Expand any *.csv.gz or *.tsv.gz reference archived instead of its raw peer,
   preserving identical uncompressed bytes. New canonical raw path is
   s132_1200/run/ns3-trace.csv ; its stored compressed copy is
   s132_1200/fixture/native_s132_prefix_0_1200.csv.gz. Expand the archived raw
   run log/mac log/admission/observation gzip files into s132_1200/run. Expand
   receiver_history.csv.gz in the fixture directory. Do the same for prior 400
   files when the packager stored them compressed.
2. Original full reference must exist at
   recovered/native_origin/evidence/tranche-25-ns3-reference/s132/ns3-trace.csv.gz
   SHA256 3da17e3397756f8890964d571932a44f7c94573b4d38eac9387342588883a4ef.
3. To recheck existing evidence, run:
   python node8_1200/native/normalize.py 132 1200
   python node8_1200/native/verify_400_prefix.py
   normalize.py requires the captured source/build receipts and recreates its
   pre-finalization receipt; do this in the disposable copy, not the sealed set.
4. To repeat native execution without compiling, verify native-capture-runtime
   against native-runtime.json;extract that tar.gz into native/runtime. Copy
   runtime/bin/autonomous-capture to native/build/autonomous-capture. Run:
   python node8_1200/native/run_capture.py
   python node8_1200/native/run_capture.py repeat
   python node8_1200/native/normalize.py 132 1200
   python node8_1200/native/verify_400_prefix.py
   verify_repeat.py verifies both raw runs against the recorded repetition
   receipt; filesystem path changes alter stdout hashes and require a new
   repetition receipt with exactly the same allowed path-only normalization.
5. To rebuild only the capture driver, clone nsnam/ns-3-dev-git and checkout
   6b5cd24ea80713ce16d88575869aedd6f432bdae into native/engine. Configure with the
   recorded configure_command.json after remapping paths (CMake 3.31.10, Ninja,
   GCC 13.3.0);this only generates matching public headers. The source CSR pin is
   486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b. prepare_capture.py copies the prior
   validated headers+driver and applies only the two cutoff constants. Execute
   build/compile-command.json with paths remapped, using the archived libraries.
   New debug path bytes may change executable SHA; repeat every semantic gate.

Seals bind issued fixture bytes. Reproduction receipts in a different filesystem
must be kept distinct; never overwrite the sealed original evidence in place.
