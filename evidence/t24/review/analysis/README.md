# T24 native custody census

This is offline analysis of the accepted, full 6000-second native campus traces
for seeds 129 and 130. It does not execute MATLAB or ns-3, modify production
behavior, or create a new parity result. Python 3 standard-library modules are
the only dependencies.

Run the two stages in order. `SOURCE_ROOT` is a source/evidence installation
containing `evidence/tranche-20-ns3-reference/s129` and `s130` with the accepted
trace, scenario, and aggregate provenance files. Use a fresh output directory.

```sh
python3 custody_census.py --source-root SOURCE_ROOT --output OUTPUT
python3 service_lineage.py --source-root SOURCE_ROOT --census-dir OUTPUT
```

Both scripts pin the exact compressed trace hashes. The census additionally
checks the uncompressed trace hash and byte length against the accepted
aggregate provenance, complete event ordering, and all available NSDP, queue,
and HOP capacity snapshots for the recorded lifecycle transitions. The scripts
fail on a broken join, unmatched release, conservation failure, or changed
input. Failed NWK admission polls are not counted as separate owners or service.

Application identity is `(source, destination, application sequence)`, scoped
by retaining node. HOP sequence is a separate field. An owner instance begins
at a NWK enqueue and releases NSDP at its matching ACK, DACK or no-ACK completion.
The six flows have DSCP zero, which is checked before using FIFO order to join
identical application owners from NWK enqueue to forwarding. Forwarding and
HOP admission are joined by application, neighbor, and identical event time.
HOP completion uses its active neighbor/HOP-sequence lifetime and must also
match the application identity. Each completion joins the preceding synchronous
flow NSDP release. DACK retains HOP capacity until the later capacity-release
event, independently of the earlier NSDP release.

All occupancy areas use 300–6000 seconds. Open lifetimes are right-censored at
6000 seconds. A repeated instance is every later enqueue of an application at
one node; it can exist after an earlier instance completes. Simultaneous extra
ownership is a different measure: integrate `max(live instances - 1, 0)` for
each application. Both measures are preserved rather than conflated.

The census writes per-flow JSON/CSV summaries, every owner lifetime as CSV,
compact node 8 event extracts, and assertion counts. The lineage stage writes
all rare repeated-owner event records, exact upstream admission-owner joins,
and service summaries. Service means NWK forwards, HOP admissions, and held
HOP capacity. It is **not airtime or a physical transmission count**: native
`tx_start` metadata identifies only the leading member of an aggregate.

These measurements do not show the delivery counterfactual if repeated owners
were suppressed. Final unique delivery cannot be assigned to a specific copy
using this telemetry alone. Seed 128 lacks the detailed native custody events
and is unavailable for this census, rather than counted as having zero repeats.
