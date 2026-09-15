# Tranche 13: controlled loss and relay-link recovery

This milestone uses the same 4 → 5 → 1 chain to exercise continued application demand during DATA loss, feedback loss and a short relay-link interruption. It preserves all 259 source files recorded in the verified Tranche 12 return, including 135 MATLAB files.

For an existing repaired Tranche 12 installation, extract `t13up.zip` directly into your working package folder (the `csr11` folder used for the successful Tranche 12 rerun), replacing matching files. Do not add a subfolder. For a fresh installation, extract `csr13.zip` into a short folder such as `C:\CSR\csr13`.

In MATLAB, make the package folder current and run:

```matlab
clear functions
report = run_tranche13_validation;
```

Upload the new `t13.zip` whose path the runner prints. Results use short folders under `results/t13`. Upload the evidence even if tests fail or comparison differences are reported. The runner retains completed tests and attempts to package partial diagnostic failures.

| Case | Controlled intervention |
| --- | --- |
| `ok` | Successful addressed transport baseline |
| `data` | Lose the first DATA-containing receiver group on each forward hop |
| `ack` | Lose the first ACK/DACK-containing receiver group on each reverse hop |
| `out` | Lose groups transmitted across either relay link from 8 through just before 9.5 seconds |

Each source has 20 applications due at zero, then one new application each second from 1 through 28: 48 per source, 96 per case. A finite source driver queries the real NWK admission state every 20 ms before 40 seconds. Each case ends at 64 simulated seconds, allowing retries and DACK-held capacity to resolve while retaining ongoing demand. No queue is manually cleared, and the horizon is fixed in the input plan.

The runner executes 88 MATLAB tests: 16 new loss tests and all 72 tests retained from Tranche 12. The primary four-case diagnostic has 264 structural checks. It does not run the 6,000-second campus benchmark. The loss test class repeats the four cases to validate their outputs. Simulated seconds are not laptop wall-clock seconds; progress messages identify the current case and test class. A laptop runtime estimate is not yet measured.

Loss decisions apply to all segments addressed to the chosen receiver within the emitted aggregate. Dropped groups do not reach the receiver's MAC/HOP, and the test does not synthesize feedback. The outage affects transport around node 5; node 5 continues its timers, local traffic and queued work. This is not a node reboot or routing reconvergence experiment.

Radio settings remain fixed at nominal 128 kbps and +33 dBm, with preconditioned neighbors and selected routes. RF errors, collisions, half-duplex receive loss, neighbor authentication, adaptive radio selection and full production ApplicationGenerator parity remain outside scope. Bootstrap controls stay excluded and are reported separately.

Strict trace equality is a separate measurement. The known 28-nanosecond NWK startup offset and intermediate DACK callback ordering are retained. ACK/DACK bitmaps are preserved as exact 64-bit integers. No tolerance, radio parameter or production policy is adjusted to fit native outputs.

The executed native reference delivered 96/96 applications in each case (384/384 overall), with all final MAC, HOP and NWK work drained. DATA loss and the blackout each caused two DATA retransmissions. The ACK-loss case recovered through later cumulative feedback without a DATA retransmission. Blocked demand overlapped DACK-held capacity and admissions resumed as capacity became available. These are native results; MATLAB results are pending.

The configured blackout covers both directions of both relay links, but the actual lost frames in this run were two DATA frames on 5 → 1. Selected loss groups were single-segment groups; separate native self-tests verify that mixed-kind companion segments share a receiver-group loss decision.

Native reference execution, independent review and Python evidence-checker tests are performed before delivery. MATLAB execution of this new tranche must occur on your laptop and will be assessed from the returned archive. Python checks validate evidence and loss-policy accounting; the MATLAB simulator and its 88 runtime tests execute in MATLAB. See `docs/tranche-13-spec.md` for shared inputs and `UPDATE_T13.md` for source preservation, verification and the next decision.
