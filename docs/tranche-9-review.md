# Tranche 9 independent candidate review

**Gate decision: ready for candidate handoff, subject to the final package
integrity checks. Owner MATLAB R2025a execution and acceptance remain pending.**
No unresolved implementation blocker was found in the frozen code reviewed
here. This review does not establish a numerical improvement or full protocol
parity.

The independent reviewer inspected the production diff, passive MATLAB and
native observers, deterministic contracts, six-case runner, return verifier,
failure-sensitive tests, and supporting source/evidence records. Review and
verification were read-only; this report is the reviewer's sole repository
edit. No MATLAB or Octave execution, native simulation rerun, remote push,
pull request, or merge was performed by the reviewer.

## Source and behavioral scope

The reviewed base is accepted Tranche 8 commit
`d0f3c5657f9f2dcf678f32900020caf3696bf90a`. The recorded GitHub main recheck pins
ns-3 to `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b` and tree
`b611b233fb369569b98f0914ece24d029ccc2f42`.

An independent Git blob comparison found **965 of 971 inherited files byte
exact** to the base. The six intentionally changed existing files are:

| File | Reviewed purpose |
| --- | --- |
| `+csr/+mac/Layer.m` | Remove two queue-empty preparation resets. |
| `+csr/+sim/NetworkSimulation.m` | Add optional service observations and cancellation wrappers. |
| `+csr/+analysis/exportResults.m` | Export the service trace and its metadata. |
| `README.md` | Point to the new candidate and owner gate. |
| `docs/parity-ledger.csv` | Record the correction and remaining limits. |
| `evidence/source-baseline.json` | Advance candidate provenance while retaining accepted execution identities. |

The corresponding native cancellation methods only erase queued entries; they
preserve preparation and the live reservation. The MATLAB change now follows
that ownership. Actual Idle and other state transitions continue to use the
existing state machine. PHY/ECC, BER, HOP/NWK policy, radio selection, and all
earlier accepted evidence are preserved. The six selected case objects and
all twelve scenario/recipe hashes exactly match their accepted T8 parents.

## Contracts and passive observations

The MATLAB and native contracts use equivalent public-API inputs for the
properties they compare. Both use the historical modulo profile, range 2,
and neighbor counters leaving only slot 1 available at selection. Neither
uses the simulators' different forced-slot controls. Search, SYNC, Track,
replacement and cancellation timings agree at the declared checkpoints.

The HOP fixture checks capacity release before the NSDP callback, with resend
and MAC entries still present during that callback. It then checks completed
cleanup and one deferred network wake, including duplicate-ACK handling.
These are prescribed subsystem conditions, not RF-delivery or RNG equivalence
tests.

The reviewer independently verified **30 native-contract hash bindings**:
four output artifacts, the contract and runner sources, fifteen pinned CSR
headers, and nine preserved engine libraries. All **101 checkpoint rows
across six cases** report passing actual/expected values. The separate native
mutation record demonstrates twelve failures in the two cancellation cases
when the old resets are deliberately restored. That is a native sensitivity
check, not execution of old or corrected MATLAB.

The MATLAB observer and its hooks schedule no events, draw no randomness,
and mutate no packet or protocol queue. T9-only cancellation wrappers call
the original operation exactly once and read six side-effect-free public MAC
scalars before and after, only within the observation window. Pairing, read
counts and omissions are explicit. Existing callbacks and the inherited
full-run ACK correlation remain separately identifiable. All twenty observer
test methods were reviewed, including tests of both actual callback routes,
missing/mismatched pairs, window limits, caps and unchanged core results.
Their MATLAB execution remains an owner gate.

## Independent native evidence verification

The final service reference contained exactly **97 files**. A before/after
inventory and hash comparison confirmed that the review did not change them.
The final verifier passed six case identities, **24 gzip roundtrips**,
**12 observer-on/off file pairs**, and **24 accepted T8 file pairs**. The
overlay-generating scripts and observer headers match their captured build
inputs. Only standalone executables were compiled against preserved engine
libraries; no full engine rebuild is claimed.

Raw service validation reconstructed **182,429 windowed rows**, including
**101,000 application attempts** and **1,404 admitted application identities**
across the six cases. These counts cover `300 <= time < 320 s`, not the full
simulation durations.

The reviewer also independently joined the embedded early-findings records
to raw CSVs. In seed 129, ACK decision 52 is replaced by decision 54 before
any transmission of decision 52. Between the first queueing and first actual
ACK, the gateway has 189 observed slot ticks: 29 in Search without SYNC and
160 in Track, of which 154 have SYNC. The reported native cancellation retains
preparation and counter 4 across queue depth 1 to 0. These observations
support the documented native timeline. They do not prove that the correction
caused, or will eliminate, the MATLAB delivery residual.

The rejected preliminary output and unlisted raw duplicates remain described
in the recovery record without attributing a cause. Final declared reference
hashes and strict membership passed this review; package integrity is checked
again by the integration agent.

## Review findings resolved before handoff

1. The admission-order join initially allowed independent control IDs to
   collide with application IDs. It now joins only APP/DATA identities, with
   a deliberate control-ID collision regression.
2. Reference validation initially bound observer headers without binding the
   scripts that generate injected source. Both MATLAB preflight and Python
   review now verify the captured T9/T8/T7/T4 generator hashes against the
   candidate. MATLAB reads the original JSON property/hash pairs to avoid
   sanitization of long absolute-path keys.
3. Repeated compressed-original lookup initially aliased a manifest list in
   memory. It now constructs a new list, and a regression verifies that
   repeated lookups preserve the inventory. This issue did not write files.

The reviewer inspected the frozen **35/35 focused Python test** log, SHA256
`1fd9680a10289038c0013f7d37793a22cdf348a34fba9110f7dbded4cc3bb78c`,
and verified the integration log reporting **244/244 Python tests**. The
integration record separately captures the full suite, static analysis,
source stability and archive checks. Static analysis of 115 MATLAB files
and preparation of 514 MATLAB test methods do not establish MATLAB execution.

The owner gate remains: 101 matching contract checkpoints, all current portable
tests, six complete diagnostics, both observer-disabled controls, and verified
source/reference provenance. Before/after outcomes must be measured against
accepted T8 evidence. The campus benchmark, older sweeps, OPNET, and native
MATLAB adapters are outside this candidate run.
