# Seed-132 queued DATA retry test

Restart MATLAB, extract this ZIP to a short folder such as `C:\work\autocase`, and set Current Folder to the extracted `autocase` folder. Run:

```matlab
report = run_autonomous_tests;
```

Send back the ZIP printed at the end, including if a diagnostic stop occurs. No ns-3 command is needed.

This batch keeps all 74 previously passed component checks, reuses the existing 16-test queued-retry suite, and adds two captured queue-order checks: 92 checks in total. The new `O_native_retry` network case uses the existing `native-provisional` DATA retry option over 0–330 seconds. All seven nodes, random-input fixtures, comparison guards, and previous source corrections are retained.

N reached 324.753 seconds with 4,202 matched draws and 769 verified physical transmissions. The earlier queue difference occurred at 318.498 seconds: ns-3 admitted a second DATA retry while its first copy was waiting in MAC. MATLAB's selected `actual-tx` policy waited for that retry to transmit. This eventually selected a newer application instead of the older retry. The existing alternate option implements the native provisional timing; no HOP code or queue priority is changed.

The accepted default remains `actual-tx`. A prior seed-128 experiment found increased terminal loss and did not promote the alternate policy. This batch tests the identified mechanism under common native inputs; it does not approve a default change or establish long-run parity.

The accepted natural A capture is reused only after its unchanged source, hashes, runtime, configuration and three exact prefix gates pass; otherwise A runs again. The root `configuration.json` records that baseline. O's actual configuration and the verified one-field selection are saved inside `O_native_retry/configuration.json` and `policy_selection.json`.

O and the additional tests have not been executed here in MATLAB. Static review is not a runtime pass. This lean package retains all runtime inputs and compact prior evidence; original N/M manifests, original runner text and omitted-history provenance are preserved in `ref/issued`. Return the result ZIP even if the diagnostic stops before 330 seconds.
