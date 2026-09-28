# Independent audit of the C/D owner return

The inline KEY_REQUEST candidate has a measurable, source-consistent effect: it restores the initial MAC preparation order and removes a one-slot delay in the first transmissions from nodes 3 and 5. The earlier PHY bit-count mismatch also passes in both returned cases. Both cases then reach the same separate aggregation mismatch at 12.402 seconds. No further network simulation was run for this audit.

## Unconditional comparison with native

The audit includes every native random request and physical transmission through the actual stop timestamp; it does not count only the requests that MATLAB happened to make.

| Through 12.402 seconds | C: callback timing only | D: timing plus inline KEY_REQUEST |
|---|---:|---:|
| Matched random-request contexts | 40/40 | 40/40 |
| Missing/extra request identities | 0/0 | 0/0 |
| Positions differing in global request order | 4 | 0 |
| Request times differing after rounding to ns | 13 | 0 |
| Differing recorded interval/component ns fields | 16 | 0 |
| Successful physical-TX context checks | 6 | 6 |
| Physical-TX attempts matching native order | 7/7 | 7/7 |
| Physical-TX attempt times differing from native | 2 | 0 |

Each case makes 11 MAC, 17 synchronization and 12 PHY random requests. Values and the declared semantic request fields were independently checked against the original fixture. D matches their global ordering and all rounded request/interval/component times. This is a bounded random-request and transmission-context result, not a comparison of every receiver-history field or a network-performance parity result.

## What D changes

C admits the first KEY_REQUEST only after PHY has returned from Track to Search. Nodes 3 and 5 then wait until the existing 11.505-second slot callback to start preparation. D admits the same request before the unchanged Track-to-Search callback, which immediately prepares the already-queued packet.

| Event | Native | C | D |
|---|---:|---:|---:|
| Node 3 initial preparation | 11.500308077 s | 11.505 s | 11.500308077 s |
| Node 5 initial preparation | 11.500311086 s | 11.505 s | 11.500311086 s |
| Node 5 first KEY_REQUEST transmission | 11.635 s | 11.648 s | 11.635 s |
| Node 3 first KEY_REQUEST transmission | 11.973 s | 11.986 s | 11.973 s |

The first preparation delays in C are 4.691923 and 4.688914 ms; each causes a 13-ms transmission delay. In D, the resulting gateway KEY_UPDATE requests are also generated 13 ms earlier. C's later common opportunities bring the remaining transmission times back into agreement.

C and D generate the same ordered ten neighbor-control requests, with identical semantic payloads. All 36 emitted PHY signal-end decisions also match between the cases after removing only their `TimeSeconds` fields, including receiver/frame identities, success flags, reasons and error counts. Thus D corrects the observed admission/timing mismatch without changing these bounded receive outcomes. Its seven public-API ownership/admission preflight checks passed in the owner return.

## What the timing option resolves

Both C and D request node 4's first payload-error sample with **183 bits**, at 11.500323527 seconds, using the same BER and captured uniform as native. The previous 184-versus-183 failure is therefore resolved at this observed case. All twelve PHY sample contexts reached by each case pass their strict bit-count and probability checks; no one-bit allowance was introduced. This does not establish every later PHY boundary without further execution.

## The remaining stop

Both cases stop before admitting node 5's third physical transmission at 12.402 seconds. MATLAB attempts three children totaling 66 wire bytes; native has four children totaling 82 bytes. The guards reject child count, total wire bytes and ordered child count. The first-divergence record alone leaves its actual child list empty because the parent-count check returns early, so that record alone cannot identify which control is absent.

The identical stop in C and D separates this aggregation/control-generation mismatch from the initial KEY_REQUEST timing correction. The existing child, admission and completion histories should determine the missing 16-byte control before changing aggregation rules or relaxing the physical-transmission guard. No inference about the 6,000-second source populations or the ±15% target follows from a run that stops before application generation begins.

Reproduction: `python autonomous_fourth/review/audit_cases.py`. The resulting `cd_audit.json`, `global_random_comparison.csv`, `global_tx_comparison.csv` and `control_request_comparison.csv` preserve the counts, unconditional comparisons, callback order and input hashes. The kit and model were read only.
