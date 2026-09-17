# Independent T16 evidence-gate review

No remaining blocking findings in the reviewed gate and runner interface. This is a source/checker review; no MATLAB execution is claimed.

The gate preserves the complete 12-case workload/configuration identity, 192 structural check identities and 129 selected MATLAB tests. It independently reconstructs binary64 scheduled targets, joins actual PHY start/end observations at their legacy CSV precision, and keeps future completions pending. Preamble callback execution is not exported. Application, ACK/DACK rate/power, bounded service-window, native aggregate and hash provenance checks remain explicit.

Six issues found during review were corrected before handoff: Decimal/float boundaries; a JSON Boolean parser mismatch; using the incomplete T9 configuration archive for a128/a130; missing PHY callback joins; omitted retained ACK input/power checks; and an inexact planned test-count condition.

The 44 T16 Python tests passed independently. Separate checks against genuine accepted T9 a129/c129 exports reconstructed application outcomes and 2,081/402 actual feedback members. Native references and finite-stop pending/drop semantics are preserved; these checks do not establish new MATLAB execution or numerical parity.

Exact reviewed file hashes and scope are in `gate.json`.
