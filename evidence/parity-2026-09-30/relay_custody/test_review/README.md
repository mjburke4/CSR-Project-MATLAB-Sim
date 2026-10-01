# Focused relay-copy custody checks

`ac.relayCustodyPreflight(config, folder)` attempts 22 independent component groups: the same 11 cases run against production `csr.nwk.Layer`/`csr.hop.Layer` and the replay candidate `ac.DiscoveryMembershipNwk`/`ac.TerminalHop`. Any failure blocks the single common-input network replay after writing all available public callback evidence.

New packaged dependencies are only `+ac/relayCustodyPreflight.m` and `+ac/RelayCustodyProbe.m`. They use existing public model APIs and MATLAB core functionality. There is no new test-framework dependency and no private-state mutation.

The cases cover:

- The observed NSDP transition 25→26→27: a synthetic source-7 application with local test ID 2873 repeats the same HOP sequence after DACK. Both accepted occurrences retain one application identity but receive different local custody tokens.
- ACK-marked incoming duplicates remain filtered by HOP.
- FIFO order source 7, source 7, source 8, with independent outgoing HOP sequence and custody identities.
- ACK `NsdpRelease` followed by `Terminal`, repeated ACKs, stale releases, and stale terminals cannot release the sibling occurrence.
- DACK releases one NWK occurrence once; its later hold expiration releases HOP capacity without releasing another NWK occurrence. Another incoming copy can be accepted after the earlier local occurrence was released.
- Actual HOP retry exhaustion releases only its failed occurrence. Late feedback and late sent callbacks cannot release a live sibling or recreate the old HOP owner.
- No-ACK outgoing sent completion reaches NWK `terminal` directly and releases only that occurrence.
- Out-of-order public release, wrong node, missing token, wrong application identity, and stale duplicate release do not remove siblings or schedule extra queue pumps.
- Each receiver overwrites upstream custody ownership; original application identity and traversal remain intact.
- A final sink invokes its unique-delivery callback once despite repeated incoming sequence and a later copy with a fresh incoming sequence.
- Queue capacity refusal leaves the incoming HOP sequence retryable after capacity release.
- A nested public send callback can release an old occurrence and admit a new occurrence before returning rejection; the old return cannot modify the new copy's submission state.

The captured-count case uses the normal HOP NSDP limit of 16. Two-copy edge cases use a valid, explicitly test-only limit of zero to obtain DACK-marked incoming copies without unrelated queue occupants. Components run on short independent schedulers; this is not a replay of captured MAC/PHY timing. Global unique-application statistics and provisional-drop recovery are exercised by the separate integrated accounting fixture.

`static_tests.py` generated `static_tests.json`: both new MATLAB files parse without errors. No MATLAB runtime is available here, so runtime success remains pending the user's R2025a preflight. The common-input replay remains the behavioral acceptance gate.
