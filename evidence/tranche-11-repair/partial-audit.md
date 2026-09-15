# Tranche 11 incomplete owner return audit

**Status: blocked by MATLAB execution failure; no acceptance or numerical parity claim.**

The authentic owner ZIP reports MATLAB R2025a (25.1.0.2943329), a failed execution lasting approximately 12 seconds, and zero test classes executed. All four replay cases report `MATLAB:cellfun:NotAScalarOutput`: “Non-scalar in Uniform output, at index 1, output 1.” No `tests.csv` was produced.

The strict return gate correctly rejects the ZIP as an incomplete Tranche 11 diagnostic. Independent partial inspection verifies its safe ZIP members and CRC, all **8 artifact hashes**, all **241 current source bindings**, all **78 reference bindings**, and all **225 accepted source files, including 124 MATLAB files**, unchanged. The candidate identity and input/native-reference bindings match the immutable issued candidate.

| Case | Recorded events | Recorded draws | Last recorded event (s) | Next unobserved native event |
| --- | ---: | ---: | ---: | --- |
| ab | 146 | 5 | 0.680 | tx_start, node 1, 0.698501 s |
| ba | 146 | 5 | 0.680 | tx_start, node 1, 0.698501 s |
| slow | 218 | 5 | 1.040 | tx_start, node 1, 1.049501 s |
| track | 152 | 5 | 0.700 | tx_start, node 1, 0.711501 s |

**All 662 recorded event rows and all 20 consumed-draw rows match their corresponding per-case native prefixes**, using the prescribed 1 ns event-time tolerance and exact comparison for all other fields. No behavioral disagreement is observed before truncation. Each case admits and delivers one application per source (two total), records no gateway ACK transmission, and records no capacity release or wake. The next native event in every case is the first gateway ACK transmission.

This prefix result does not validate the missing ACK/capacity-release chain or the remainder of any case. The full-array mismatch total is affected by the missing suffixes and shifted case boundaries and must not be read as a completed parity result.

Owner ZIP SHA-256: `0d5ef15fc3cc8b1ea00b84252ec6fc41bb5701425f231039afcc9a0e50c33282`.

This audit made no changes to the uploaded ZIP or immutable candidate. It does not execute MATLAB or fabricate a completed return.
