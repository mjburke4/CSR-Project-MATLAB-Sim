# Seed-132 feedback signature test

Restart MATLAB, extract this ZIP to a short folder such as `C:\work\autocase`, and set MATLAB's Current Folder to the extracted `autocase` folder. Run:

```matlab
report = run_autonomous_tests;
```

Send back the ZIP whose path is printed at the end, including if a diagnostic stop occurs. No ns-3 command is needed.

This batch retains the 66 component checks already passed by the prior M owner run and adds eight feedback-signature checks. It then runs the new `N_feedback_identity` case over 0–330 seconds with all seven nodes and the same native random-input fixture. The accepted natural A capture is reused only after the unchanged source, file-hash, runtime, configuration and three exact prefix gates pass; otherwise it runs A again.

M reached 312.143 seconds with 3,518 matched random requests and 648 verified physical transmissions. Its next transmission differs only in the signature's type label: MATLAB calls the child DACK, while ns-3 writes outer ACK type with both ACK and DACK flags. N projects that label to the native wire representation and strictly checks both flags, their encoded bits, sequence, window, bitmaps, addresses, bytes and the existing remaining fields. Both original labels are recorded. It changes no NWK, HOP, MAC, PHY, timer, custody or routing behavior.

The new checks reconstruct the stopped frame, cover all 1,104 native feedback children, and verify negative mutations. The native corpus contains 21 mixed DACK windows, 163 ordinary window ACKs and 920 exact ACKs. Sibling cases not present in the capture are marked as synthetic component checks. N and the eight new checks have not yet been executed in MATLAB; static review is not runtime validation. A diagnostic stop is evidence, not a parity pass.

This is a self-contained lean continuation. It preserves every prior M model and helper byte, all runtime fixtures and accepted natural evidence. It omits old raw history CSV/JSONL files that are not runtime dependencies, while keeping their hashes and the original issued and published M manifests in `ref/issued`. `FILES.json` binds this N package; `PUBLICATION.json` explains the preserved M package and the new candidate files. The exact prior I divergence required by a retained component check is included.
