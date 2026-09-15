# Independent Tranche 10 integrity audit

PASS

- 854/854 closed-inventory SHA-256 and size checks; 855 safe ZIP members and passing CRC.
- 225 source hashes match immutable csr10r.zip, including 124 MATLAB files; 332 reference hashes/sizes match and both lists are stable start to finish.
- 550/550 unique named MATLAB tests match the immutable source methods in 46 test classes.
- 279 MAC + 154 receiver + 101 ACK = 534 passing checkpoints independently compared with pinned native reference rows.
- 29 retained, 18 sweeps, 6 diagnostics, 2 controls and campus6000 all completed.
- Both observer controls reproduce all 12 listed files byte-for-byte, with identical configuration and statistics; observers report zero scheduled events and zero RNG draws.
- Campus: 12,484 generated = 11,825 delivered + 402 dropped + 257 pending at 6,000 seconds. 1,710,000 admission attempts have complete aggregate counts; 100,000 trace rows retained and 1,610,000 trace rows omitted.
- No MATLAB/ns-3 execution was performed by this auditor. No numerical-parity conclusion from these structural checks.

Blockers: none.
