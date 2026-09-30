Node 8 partial common-input prefix audit, 2026-09-30

Run both commands from the evidence workspace root:
  python node8_return2/node8_queue/audit_prefix.py
  python node8_return2/node8_queue/audit_capacity.py

The MATLAB replay stopped at 895.115 s on a node-4 physical-TX context
divergence. These checks compare only [0,895.115), never a complete
1,200-second population. No simulations are invoked and no model files
are changed.

Result:
  Node 8 NWK arrivals: 269, identity/order/time exact.
  Node 8 HOP handoffs: 231, identity/order/peer/sequence exact.
  Node 8 custody releases: 229, identity/order/time/reason exact, with the
    documented MATLAB retry_exhausted to native no_ack reason mapping.
  Node 8 observable post-event HOP capacities: all 453 exact in identity,
    order, pending count/limit and neighbor outstanding/threshold.
  Node 8 DACK events preserving capacity: all 193 exact.
  Node 8 application attempts: all 29,756 admission/NSDP/queue snapshots exact.
  Native candidate queue checks: 34,686 internally consistent.
  MATLAB receive-NSDP checks: 152 internally consistent.
  The first local source 8 handoff is MATLAB 28 ns earlier at 300 s,
    previously known; the other 230 handoff times match at nanosecond
    reporting precision. All 32 ACK and 190 DACK-expiry times match.
  Ordered waiting and custody snapshots match at 400, 600, 675 and the
    exclusive 895.115-s cutoff. Final waiting 38 = 23 relay source-7 + 15 local source-8,
    custody 40 = 24 relay source-7 + 16 local source-8. Two live HOP owners and three DACK holds
    remain in MATLAB.

All six sources' accepted identities/timestamps/order (1,582) and final
delivery identities/timestamps/order (1,229) match native. There are 353
admitted applications unresolved at the cutoff. Source 7 has 172 admitted,
20 delivered and 152 unresolved; source 8 has 117 admitted,28 delivered and 89
unresolved. Their delivered mean latencies are 474.504011086 s and
459.909418228857 s, respectively, identical in the two models.

Interpretation: the observed node 8 bottleneck is reproduced under common
input in this prefix. No new node 8 semantic mismatch is demonstrated.
This does not establish autonomous-network +/-20% parity or validate the
unexecuted 895.115--1200-s interval.

The audit does not directly observe every MATLAB rejected NWK pump
candidate or reconstruct every surviving physical copy. Raw app_drop
events are provisional ownership events, not proven final losses.
Complete input hashes and detailed checks are in prefix_audit.json and
capacity_audit.json. observer_decoder.py is a byte-identical copy of the
accepted offline observer decoder (its hash is bound in prefix_audit.json).
