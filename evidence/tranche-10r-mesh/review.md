# Tranche 10 mesh return: focused pass

The repaired six-node mesh completed on the owner's MATLAB R2025a
25.1.0.2943329. All 32 focused tests passed, including the fractional retry
regressions. The simulation reached 900 seconds at seed 128 with the original
2,000,000-event cap. Mesh execution took 125.3328103 wall seconds.

| Measurement | Returned result |
| --- | ---: |
| Generated / delivered applications | 15 / 15 |
| Application drops / pending | 0 / 0 |
| Delivered application bytes | 960 |
| Mean application latency | 1.458726 s |
| DATA retransmissions / acknowledged DATA hops | 0 / 30 |
| OTA transmissions | 1,155 |
| Protocol / PHY trace rows | 19,016 / 20,324 |
| Omitted protocol / PHY rows | 0 / 0 |

The independent audit verified all 225 source hashes, including 124 MATLAB
files, against the delivered `csr10r.zip`. It also verified the complete
20-member owner archive: 19 outer and 13 inner hash/size records, 12 CSV row
counts, and all 32 actual test identities/outcomes. The separate accounting
review passed 77 checks of packet identities, configured traffic, endpoints,
bytes, latency, receiver outcomes and final custody.

All application, HOP and NWK custody/control queues are empty at stop. Eight
scheduler events remain after the finite horizon; the earliest is at
900.0680000000219 seconds. These are future callbacks, not eight undelivered
packets. There are physical receive failures and control retries in this
network model; zero application drops does not mean an error-free radio link.

The complete mesh configuration equals the accepted Tranche 7 configuration.
That run also delivered 15/15, with mean latency 1.5384593333 seconds and 1,183
OTA transmissions. The new values are descriptive results for one seed across
several tranches. They neither isolate the retry correction nor measure
closeness to ns-3.

## Next execution

From the same existing `csr10r` folder in MATLAB, run:

```matlab
report = run_tranche10_validation;
```

No replacement source download or additional code change is needed. Use the
default full gate: 550 portable tests, 534 contract checkpoints, 29 retained
cases, 18 sweeps, six diagnostics, two observer controls and the 6,000-second
campus benchmark. Upload the printed `tranche10_evidence.zip` path afterward.
Earlier cases must be validated against this repaired source as part of that
gate. Campus remains the long-running part.

This review records a successful focused diagnostic, not full Tranche 10
acceptance or numerical parity. The original aborted run did not retain the
failing callback, so its precise cause cannot be proved retrospectively. The
retry regression tests and formerly failing mesh now pass on the repaired
source. No MATLAB, Octave or ns-3 simulation was run by the reviewers; these
are audits of the owner's returned execution.

## Provenance

- Owner archive: `mesh.zip`, SHA-256
  `553559bd4baaaad56ef36be18d34b084f28e2eb5e2b4b56cd11c98c610d10a34`.
- Delivered repair: `csr10r.zip`, SHA-256
  `df3ad517708fccc9e4c85d8e38c3492b97aff8d2d5236b3f05249da3cd15b900`.
- Owner source snapshot SHA-256:
  `9be444b0fb1ffbfe818cab86502a287b19e3da83467d210ef426ec3b19e183da`.

`accounting.json` and `independent/audit.json` contain the detailed results.
The Python files preserve the review procedures and original workspace input
locations. `manifest.json` binds the files in this review bundle; `mesh.zip`
is copied without modifying its bytes.
