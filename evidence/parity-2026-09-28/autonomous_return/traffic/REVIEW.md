# Returned seed-132 natural capture: traffic, custody and actual random samples

The new capture directly records the different MAC samples that precede the different traffic histories. It also closes every observed source-admission decision against actual source custody changes. **No new source-generator or custody-release behavior mismatch is demonstrated.** The common-input case stopped in the harness at 10.01 seconds before consuming any reference sample, so it supplies no equal-input network comparison yet.

## Natural capture fidelity

An independent read of the returned CSV cells confirms the natural prefix exactly reproduces the corrected 6,000-second MATLAB return in `[0,330)`:

| Table | Rows | Independent result |
|---|---:|---|
| Protocol | 12,200 | All CSV cells identical |
| PHY | 12,198 | All CSV cells identical |
| Application attempts | 9,000 | All CSV cells identical |

These are actual owner-run results, not a static expectation. The new passive information can therefore explain the already reviewed natural trajectory without replacing it with a different run.

## Measured random-input differences

The following pairs are aligned by the named event and its time, **not by equal draw ordinal**:

| Request | MATLAB integer | Native integer | MATLAB ordinal | Native ordinal |
|---|---:|---:|---:|---:|
| Gateway 1 initial slot request, 10.01 s | 10 | 11 | 1 | 1 |
| Node 7 initial application slot request, 300.001 s | 19 | 6 | 40 | 45 |
| Node 8 initial application slot request, 300.001 s | 10 | 18 | 70 | 56 |

For each pair, the captured profile, inclusive bounds `[0,31]`, local active-node count, MAC state (`search`), and own reservation slot/counter agree. Node 7 reports two locally active nodes and node 8 reports three. Node 1's reported population differs, but this pinned historical profile uses the local count, not the reported count. Matching these selected request fields is not a claim that the entire network state is equal.

MATLAB's prepared slots at 300.001 seconds are also directly recorded as 19 for node 7 and 10 for node 8; these are not inferred by back-calculating transmission time. The receiver investigation handles the intervening state and timer details.

The ordinals show that startup has already changed draw consumption. Before 300 seconds, node 7 has consumed 39 MATLAB MAC draws versus 44 native draws; node 8 has consumed 69 versus 55. The native/MATLAB stream-ownership difference identified in source code is thus relevant to actual recorded inputs: MATLAB retains its independently seeded per-node MAC stream, while native creates automatically allocated random-variable streams for successive slot selections. Equal numeric seed 132 does not specify an equal sample sequence. The fixed traffic generator itself consumes no random samples.

These observations establish different actual stochastic inputs. They do not establish that either implementation uses an incorrect slot distribution, nor that randomness accounts for every later difference.

## Source admission closes against actual custody callbacks

The service trace preserves application attempts and source-local custody releases in one callback order. Starting from zero source custody at 300 seconds, the audit increments the original source's NSDP count on admitted application creation and decrements it on the matching source-local release callback. For **all 9,000 attempts**, the reconstructed count equals the directly observed admission NSDP value, and admission occurs exactly when the count is below 16. No discovery, topology or destination gate blocks these attempts.

| Source | Attempts | Applications admitted | Source custody releases | Source-owned at 330 s |
|---|---:|---:|---:|---:|
| 2 | 1,500 | 29 | 13 | 16 |
| 3 | 1,500 | 60 | 44 | 16 |
| 4 | 1,500 | 24 | 8 | 16 |
| 5 | 1,500 | 26 | 10 | 16 |
| 7 | 1,500 | 37 | 21 | 16 |
| 8 | 1,500 | 31 | 15 | 16 |

“Source-owned” refers to original source custody; it does not include copies held by downstream relays or represent total unresolved traffic. Every source makes its attempts on the common 20 ms grid. The remaining attempts are suppressed by NSDP 16 and create no application packet.

The first differing application decisions remain source 7 at 300.56 seconds and source 8 at 302.68 seconds. Across `[300,330)`, 226 of the 9,000 paired decisions differ; each is explained by the different observed custody count.

## Initial transfers with verified application identity

The transfer join requires DATA kind, original application source, original flow/attempt, generation at 300 seconds, and the correct directed HOP link. Engine-local packet IDs, control sequence numbers and physical aggregate IDs are not interchangeable. The final joins are independently checked against the returned ordered DATA children and native enriched transmission signatures.

| Event | MATLAB source 7→8, s | Native source 7→8, s | MATLAB source 8→2, s | Native source 8→2, s |
|---|---:|---:|---:|---:|
| First original-source DATA transmission | 301.496 | 300.092 | 300.144 | 316.719 |
| Receiver accepts that DATA | 301.740812441945 | 300.336812442 | 301.381275345563 | 316.963815346 |
| Feedback releases original source custody | 302.029292441945 | 300.547292442 | 302.679295345563 | 317.291295346 |
| Next replacement application admitted | 302.04 | 300.56 | 302.68 | 317.30 |

For source 7, the native ACK releases one of the initial 16 applications before the 300.56-second attempt. MATLAB still holds all 16 then, and first admits a replacement at 302.04. Source 8 has the opposite initial advantage. This is the measured feedback loop from service timing to admitted traffic; it does not require a different externally offered traffic schedule.

The own-source HOP sequences are MATLAB/native 12/11 for source 7 and 13/14 for source 8. Their difference reflects preceding control histories and must not be treated as evidence that the paired applications are different. Conversely, a matching sequence number without kind, link and application lineage can identify the wrong control or relayed packet.

## Action and limits

Retain the accepted natural capture. The actionable issue in this return is the case-B harness failure: `MATLAB:string:CannotConvertMissingElementToChar` in `Streams.take` at the first MAC request. Its random-request file has **zero rows**. Therefore no native sample was consumed, no shared-input network result was produced, and no protocol mismatch can be inferred from that failure. Repair and resume the common-input case using the already accepted natural evidence and native tape; a new natural run is unnecessary unless the repair changes the natural execution path.

The natural results justify following the measured MAC/receiver/custody loop. They do not justify changing traffic intervals, bypassing source admission, altering random distributions to fit one seed, or declaring the entire 6,000-second latency gap explained. The ±15% full-network target remains a separate acceptance question.

## Artifacts

`audit_return.py` reproduces this read-only audit. `summary.json` records checks and results; `input_manifest.json` hashes the source evidence. CSV outputs retain all paired attempts, source custody transitions/releases, per-source counts, selected matching request contexts with different samples, all-node RNG usage counts, and the correctly joined initial DATA transfer/lineage records. No kit source was edited by this audit.
