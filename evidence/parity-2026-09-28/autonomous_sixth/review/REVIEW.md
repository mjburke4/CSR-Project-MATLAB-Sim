# G/H returned-prefix audit

H clears the earlier routing-admission discrepancy and continues to 25.298 seconds. Its next transmission has the expected three controls, destinations, sequence numbers, routing sections and reservation slot; two REQUEST controls are each sized at 23 bytes instead of native's 16 bytes. The guard stops before this transmission occurs. This establishes a specific remaining wire-size mismatch, not a 15% performance-parity result.

| Returned case | Random values consumed | TX contexts verified | Rejected TX attempt | Unconditional merged order/time |
|---|---:|---:|---|---|
| G population | 97: 21 MAC, 44 SYNC, 32 PHY | 16 | Global 17 / node 1 TX7, 14.534 s: 8 children / 241 B versus 7 / 215 B | All 114 request/TX events match native order and rounded-ns times |
| H admission route | 276: 57 MAC, 125 SYNC, 94 PHY | 47 | Global 48 / node 1 TX18, 25.298 s: 77 B versus 63 B | All 324 request/TX events match native order and rounded-ns times |

The audit compares every request and physical-TX guard through each stopping event, including requests regardless of whether their context matched. It separately merges those two event types to check their relative order against native event order, rather than checking only individual streams. All supplied random values and controlling request fields match; recorded PHY interval and component nanosecond fields also match. The historical profile-4 `reported_nodes` diagnostic differs on 10 G requests and 19 H requests; the checked slot algorithm does not use that field. These existing diagnostic differences are recorded rather than described as identical state.

Earlier discrepancies are cleared within the observed prefix:

- Node 4's second PHY draw uses 183 payload bits and passes in both cases.
- Node 5's third TX at 12.402 s contains all four children totaling 82 bytes and passes in both cases.
- Node 1's eighth MAC request at 14.534 s now uses population 2 and consumes native value 13 in both cases. H later publishes population 3 at 18.724108077 s on a qualifying observation.
- At peer 3 admission, G enqueues the extra 26-byte grouped DELETE (`00000004000101000003`) at 14.400468077 s; H does not. H's node 1 TX7 consequently passes with the expected seven children and 215 bytes. The legitimate 65-byte routing snapshot remains in both cases.

At H's stopping TX, the first two children have identical normalized REQUEST sections (`00000006000103` and `00000007000103`) and exact destination/sequence pairs 3:7 and 5:9. Only their 23-versus-16-byte lengths differ. The third, 31-byte SNMP_START control matches. This is the first attempted physical TX containing these REQUEST sections; no earlier successful prefix transmission validates their size. The report does not infer subsequent airtime, reception or traffic outcomes after the guard stopped.

The returned provenance matches the issued manifest exactly: all 247 bound local files and 121 resolved MATLAB file hashes verify, including the source and candidate transform copies. The owner ran R2025a on PCWIN64. Import checks and all 29 component checks passed: 7 KEY_REQUEST, 8 neighbor-condition, 6 population and 8 route-admission. A was reused, not rerun; its 12,200 protocol, 12,198 PHY and 9,000 application-admission rows retain the accepted trace bytes and its exact prefix gate passed. The live configuration matches the accepted configuration after canonicalizing only the documented source-path metadata. Both service observers report no omitted rows and complete cancellation pairs through their diagnostic stops.

`audit_prefix.py` reproduces the assertions and writes `gh_audit.json` plus the four comparison CSVs. No new simulation or kit/model edit was performed for this audit. Agreement here covers the logged, guarded prefix; it does not show every internal callback or state is identical, complete the 330-second case, or establish autonomous 6,000-second network parity.
