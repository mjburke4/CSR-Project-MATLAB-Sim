Returned relay-custody preflight evidence audit

Run from the workspace root:
  python relay_return/provenance/audit_return.py

Input issued_v1_tests.zip is the preserved original issued repair kit. The root
relay-custody-repair-tests.zip now contains the subsequent test-fixture correction
and must not be substituted when auditing this return.

The returned owner run is MATLAB R2025a 25.1.0.2943329, PCWIN64. Its full issued
manifest matches the preserved original kit: all 496 sealed entries verify and
all 162 runtime-resolved source hashes match. The return ZIP passes CRC and its
extracted bytes are identical to the archive.

All 17 prior preflight groups passed; integrated accounting passed 4/4, including
the new sibling case. Custody tests completed 22/22 groups with 20 passing. The
only failures were the production and candidate versions of the queue-full test.

Both NWK implementations demonstrated accepted-copy counts 25, 26, 27 with two
distinct local custody IDs for the repeated application; FIFO source order 7, 7,
8; and three independent ACK releases draining custody to zero. Other successful
groups cover ACK duplicate filtering, DACK hold/release, retry failure, no-ACK
release, invalid/stale tokens, upstream-token replacement, unique final delivery,
and nested send rejection. Integrated accounting preserved pending status with
a surviving sibling, recorded provisional drop only after final registered-custody
loss, recovered on same-hop acceptance, and retained one delivered application,
185 bytes and 4.5 seconds latency after duplicate delivery and later relay arrival.

The requested seed-132 replay did not start: its import passed, but the runner
correctly stopped at prerequisite_failed. This return supplies component-test
evidence only, not new 1200-second or 6000-second network parity evidence.

Exact archive, manifest and source SHA-256 identities are in audit.json.
