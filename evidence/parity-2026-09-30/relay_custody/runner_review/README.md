# Relay-custody runner review

`run_node8_tests.m` retains one full seed-132 common-input network from 0 through
1,200 seconds. The 17 prior preflight groups and new `relay_custody` group execute
first, with a separate full-fixture import gate. The existing full network,
partial-export, omission, population and exact timestamp checks are unchanged.

The runner explicitly records changed candidate behavior. Its independent
allowlist compares every one of the 167 historical model/candidate files against
the accepted v2 manifest, requires the six approved existing files to change,
and requires all other files to retain their accepted hashes. Only the two
listed new focused-test files can be added under `model/` or `+ac/`.
`manifest_requirements.json` defines the metadata the final current manifest must
carry. The full current manifest must still hash every packaged artifact.

The historical 330-second natural tables are checked for archived integrity and
are labelled reference only. They are never copied to a new `A_natural` result,
reported as current acceptance, or used to claim unchanged model behavior. No
new 330-second natural network is launched.

Source binding resolves active top-level MATLAB files, `model/` and `+ac/` code.
Archived MATLAB source elsewhere remains hash-protected without being resolved
as an active package. The existing queued-retry test remains a required active
dependency.

`audit_runner.py` parses the runner with tree-sitter MATLAB and verifies that 13
network/export/timing/helper functions remain byte-identical to the accepted
runner. `runner_static.json` records its result and exact file hashes. This is a
static check, not MATLAB execution. Independent final dependency and manifest
reviews remain required before publication.
