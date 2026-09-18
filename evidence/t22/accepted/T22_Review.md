# Tranche 22 return review

**Accepted for the controlled HOP adaptive-window contract. No MATLAB rerun or production correction is needed.**

| Check | Verified result |
|---|---|
| Owner runtime | MATLAB R2025a, 25.1.0.2943329; portable backend |
| Elapsed run time | 56.610 seconds |
| Focused tests | 89/89 passed; zero failed or incomplete |
| Controlled cases | 9/9 completed |
| MATLAB/native checkpoints | 364/364 matched in every discrete state |
| Independent milestones | 38 milestones, 142 integer assertions passed |
| Source and references | 390 source and 157 reference bindings verified |
| Accepted T20 baseline | All 376 files, including 175 MATLAB files, unchanged |

The issued return checker and two independent reviews agree. The integrity audit passed all 49 checks. Direct comparisons checked 5,460 state/counter values, plus 728 step and peer identifiers, without importing the issued checker. Recorded action times satisfy the declared 1 ns tolerance. Their largest difference, 2×10⁻¹⁵ seconds, is a numeric representation difference, not measured physical timing precision.

The cases verify clean-ACK window growth, growth before a retried-ACK reset, ordinary and doubled DACK capacity holds, final-failure reduction and its zero floor, neighbor/global admission limits, grouped feedback and repeated-feedback handling, and a reduced seed-130 startup sequence. The final-failure case intentionally finishes by admitting a new packet to demonstrate reopened capacity; its retained owner is accounted for.

This establishes matching behavior for the prescribed HOP inputs. No adaptive-window update defect was exposed. Keep the production implementation, `actual-tx` retry policy, continuous timing, and PHY/ECC unchanged.

T22 injects feedback and controls transmit callbacks. It does not reproduce receiver feedback generation, radio contention, security ingress, or the full campus workload. There is no new campus delivery or delay measurement, and no fresh full portable regression. The existing ±10% campus screen remains unchanged: network delivery is within the band for all three seeds, while per-flow delivery and mean delay each meet it in 13/18 comparisons. Those results do not establish statistical equivalence.

The next useful bounded test is **receiver congestion → ACK/DACK generation**. Apply identical relay arrivals, local application attempts, and downstream capacity releases through the actual NWK/HOP objects at node 8. Compare the resulting custody counts and feedback, including the pre-enqueue congestion boundary, duplicate reassessment, and separate local/relay admission. Let ownership counts arise naturally from admissions and releases. This would test how feedback is produced, complementing T22's test of how a sender responds to it. A new campus run or threshold tuning is not justified by this passing result alone.

The package preserves the original owner ZIP, issued update, returned records, frozen native references and contract, checker output, independent audits, and updated parity ledger. Historical candidate/handoff files retain their original pending wording; this review records the completed outcome. No simulator was executed by the reviewers, and no T22 repository publication was performed in this review.

Original return SHA-256: `37863a70ef46c2889b3f945bcc2d3cfbe548115f1c349136488cc56357a9f6af`.
