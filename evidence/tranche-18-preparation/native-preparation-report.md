# Tranche 18 native diagnostic preparation

Completed 21 native executions: ten observer-on/off pairs and a pristine-source control for `m128`. All canonical protocol/admission bytes and derived aggregate bytes match their controls. Every service event drawn from the canonical trace matches its shared fields, including ingress and egress.

CSR source: `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. Engine: `6b5cd24ea80713ce16d88575869aedd6f432bdae`. The nine required debug modules were rebuilt; no MATLAB, OPNET, or full native engine unit suite was executed.

| Case | Attempts | Admitted | Delivered | Unmatched sends | DACK completions | No-ACK completions | Retry submissions |
|---|---:|---:|---:|---:|---:|---:|---:|
| r128 | 15000 | 278 | 248 | 30 | 183 | 2 | 17 |
| l128 | 15000 | 589 | 573 | 16 | 0 | 0 | 0 |
| m128 | 30000 | 391 | 335 | 56 | 154 | 0 | 14 |
| r129 | 15000 | 292 | 252 | 40 | 183 | 0 | 17 |
| l129 | 15000 | 596 | 580 | 16 | 0 | 0 | 0 |
| m129 | 30000 | 388 | 327 | 61 | 143 | 0 | 18 |
| r130 | 15000 | 287 | 249 | 38 | 178 | 0 | 35 |
| l130 | 15000 | 603 | 587 | 16 | 0 | 0 | 0 |
| m130 | 30000 | 398 | 338 | 60 | 148 | 0 | 28 |
| p128 | 180000 | 1606 | 1245 | 361 | 521 | 156 | 617 |

DACK and no-ACK columns count HOP custody events; they are not end-to-end application-loss counts. Retry submissions are separate from actual radio transmissions. Unmatched sends remain unclassified at the finite stop.

The reduced relay cases preserve `4 → 5 → 1`; local cases originate at node 5. Each observed forwarding edge and source cohort is recorded in the JSON report. Independent mutation checks cover exact controls, stage membership, source/runner bindings, canonical schema and lineage, missing events, and compiled ACK/DACK classification (21 passed).

Curated native evidence: 189 files, 61,181,484 bytes. Suite manifest SHA-256: `9e8e15dc026a4bbfcff93d1a39f095a91aebe761a46a94ce0a372583a8017250`.

Failed scratch pilots are excluded. The final isolated run has complete output and source/binary/overlay stability bindings. Native versus MATLAB results are descriptive across independent RNG streams; this does not establish full numerical parity.

Independent final reference review passed all ten cases: 1,239,816 canonical trace rows and 2,565,316 service observations verified; all 21 focused mutation tests passed. No remaining blocker was found within this evidence-integrity scope.
