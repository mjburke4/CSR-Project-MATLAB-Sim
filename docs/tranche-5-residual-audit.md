# Tranche 5 audit of accepted timing and recovery residuals

The accepted seed-128 evidence does **not** justify a protocol timing or
PHY/ECC correction. All 15 application latency differences are already present
at the final radio transmission start; the subsequent final-envelope transit
durations agree. The next useful gate is repeated-seed evidence, preserving
the current protocol and the diagnostic recovery configuration.

This is a retrospective analysis of the actual accepted R2025a run at
`6fdf23835dec2f702ef0d7012776bbc30790b307`, with the five retained ns-3 runs
at `486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`. It is not new MATLAB or ns-3
execution. The [machine-readable audit](../evidence/tranche-5-residual-audit.json)
records the archive, per-case manifests, diagnostic code and source hashes.
MATLAB source hashes are read from the published equivalent `ec1b3fa65f7d…`,
whose Git tree is checked against the publication record's validated tree.
The JSON retains both identities. Subsequent Tranche 5 edits cannot silently
redefine the source associated with these results, and a fresh complete
GitHub clone need not contain the original local-only commit object.

## Timing localization

The diagnostic first verifies the original evidence ZIP against its accepted
SHA-256, then reruns the strict application comparator for every shared case.
Within MATLAB, it joins each application to its last `hop_sent` toward the
final destination, then to that sender's same-time physical `tx_start`.
Within ns-3, it joins `nwk_delivery` to its preceding same-time `rx_accept`
and then to the latest matching physical header's `tx_start`. Ambiguous or
missing matches fail. This preserves the different application IDs and HOP
sequences and correctly handles ACK-headed relay aggregates.

All 15 final-hop transit durations agree within 0.335 nanoseconds in the
exported decimal values (the diagnostic tolerance is 1 microsecond). All
delivery differences are integer multiples of the common 13-ms slot.

| Shared case | MATLAB minus ns-3 latency, packets 1 / 2 / 3 (slots) | Same final-envelope transit time, packet 2 (ms) |
| --- | --- | ---: |
| two_node_8 | −9 / −10 / −5 | 126.480333 |
| two_node_128 | −7 / −4 / −3 | 25.680333 |
| line_3_8 | −19 / −4 / −1 | 173.413333 |
| high_rate_500 | +3 / −9 / −9 | 21.060333 |
| high_rate_1000 | +3 / −9 / −9 | 20.220333 |

For example, the second 8-kbit/s application is generated at 135 s in both
runtimes. Both prepare at 135.005 s. MATLAB transmits at 135.187 s and delivers
at 135.313480333 s. ns-3 transmits at 135.317 s and delivers at
135.443480333 s. The 130-ms delivery gap is entirely the 10-slot difference
before transmission; final transit is identical.

The original statement that MATLAB's *mean* latency was 60–104 ms shorter is
correct. It is not evidence of a fixed missing delay: MATLAB is faster for
13 applications and slower by three slots for the first application in each
high-rate case. Both runtimes also use the same long first-packet envelope
durations in these fixtures. A blanket latency offset or airtime correction
would damage those observed agreements.

The source comparison supports the following narrower conclusion:

- MATLAB `csr.mac.Layer.pickSlot` and ns-3 `CsrMacCore::PickTxSlot` both draw
  a free-slot ordinal in `[1, range]`, scan physical entries 0–253, skip
  occupied neighbor reservation counters and apply the same fallback.
- Both countdown implementations re-arm the 13-ms timer first and decrement
  the sender only in Search without SYNC after holdoff; transmission requires
  counter −1. The inspected ordering does not expose a fixed off-by-one gap.
- MATLAB caches a per-node MAC `mt19937ar` stream. ns-3 constructs a
  `UniformRandomVariable` for slot selection. The generators, stream ownership
  and preceding control histories differ. Equal numeric seeds do not pair
  their reservation draws.

Different reservation draws and histories are therefore a credible cause,
but **exact RNG attribution remains unproven**. MATLAB's current protocol CSV
drops the reservation fields emitted in the MAC callback, and its trace does
not record every reservation tick. Final-TX localization does not identify
every upstream cause, especially for a two-hop packet. It also does not prove
equivalent radio error outcomes or explain every OTA control-count difference.
If repeated-seed distributions expose a systematic gap, the next bounded
diagnostic should export selected/reused reservation counters and correlate
enqueue, prepare, holdoff, transmit, receive and relay events before any fix.

## Control failures and recovery

| Case | HOP control owners exhausted | Before first application | Observed context |
| --- | ---: | ---: | --- |
| hidden_node | 1 | 1 | KEY_UPDATE at 20.302 s; first application at 240 s |
| mesh_6 | 11 | 11 | ROUTING at 48.980–174.287 s; first application at 360 s |
| route_recovery | 5 | 3 | Three ROUTING failures during the relay blackout; two at 870.892 s |

The mesh failures precede offered application traffic; they cannot be called
DATA-load saturation failures. The accepted counter evidence records eleven
NWK residual retries and zero terminal NWK control failures in this case.
The hidden-node case has one terminal NWK control failure; recovery has one
terminal NWK control failure and four residual retries. An exhausted owner
and an unsuccessful final application are different observations.

MATLAB `Layer.controlResult` retains remaining active routing targets for a
bounded number of control cycles. ns-3's
`NoteOwnedRoutingControlFailure` marks the grouped owner ready and schedules
its residual retry after HOP releases its owner. MATLAB's finite cycle limit
is an existing declared difference. These results do not show that raising
the limit improves convergence, nor that the prior chosen bound is defective.
No retry policy was changed to remove these counters.

The accepted recovery configuration enables 60-second freshness checks every
5 seconds, while application traffic is silent until 450 s. Its relay receive
blackout lasts from 405 to 540 s. Eleven of the 24 neighbor deactivations occur
**before** the blackout: at 125, 195, 265 and 400 s. Four occur during the
blackout and nine after it. Thus much of the churn is independent of the
imposed link outage. The first large deactivation group at 125 s is 280 seconds
before that outage.

The source's freshness monitor uses `age > timeout`, as MATLAB does. This
timer can intentionally stale a quiet admitted neighbor. The research
fixture's aggressive timeout is an explicit stimulus, not a physical movement
or a source-default campus setting. Freshness-triggered inactivity and
subsequent control activity are therefore credible experimental causes of
the churn; the present CSV's generic `neighbor_failure` reason does not prove
the precise trigger of every deactivation.

Receive eligibility is restored at 540 s, but administrative rediscovery is
explicitly scheduled at 576, 581 and 586 s. The first application delivers at
585.940413 s, 45.940413 s after eligibility restoration and 9.940413 s after
the first rediscovery request. Its 135.940413-s application latency includes
the blackout, the deliberate post-blackout wait and convergence. It cannot
be interpreted as autonomous recovery time.

Keep this accepted stress fixture intact. Tranche 5 should report seed,
control retry totals, route changes, failure timing and restoration-relative
latency, while distinguishing complete delivery from stable convergence.
Any future quieter recovery benchmark should be a separately named experiment
with its changed freshness and rediscovery stimuli preserved in the manifest.

## Reproduction and actual checks

From a MATLAB repository Git checkout containing the published history, with
the pinned ns-3 Git source checkout available:

```text
python scripts/audit_tranche4_residuals.py --ns3-root ../CSR-Project-NS3-part2 --output evidence/tranche-5-residual-audit.json
python -m unittest discover -s scripts/tests -p test_audit_tranche4_residuals.py -v
```

The actual audit revalidated all five application comparisons and reconstructed
all 15 final envelopes. Five Python diagnostic tests passed: ACK-headed
aggregate association, latest retransmission selection, ambiguous MATLAB
envelope rejection, wrong ns-3 HOP identity rejection and modified-archive
rejection. Those synthetic tests validate the diagnostic, not MATLAB behavior.
The standalone MATLAB ZIP and its validation runner do not invoke this
retrospective Git-dependent engineering diagnostic.

No production simulator code, PHY/ECC tables or accepted evidence was changed
by this audit. Numerical timing parity, full ACK-feedback adaptation, native
packet transport and historical OPNET/campus validation remain separate work.
