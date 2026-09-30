# Unique-application accounting with relay custody occurrences

The repair queries registered NWK custody across every node before recording a
provisional application drop. A failed occurrence cannot drop the unique
application while any registered sibling remains. The older high-water
`CustodyNodeId`/`CustodyHopCount` fields remain diagnostic metadata; they are no
longer a single-owner authority for loss accounting. This matters when the last
remaining occurrence is at a lower hop or another node.

Every accepted relay enqueue counts in `RelayAccepted`, including an accepted
copy at the same hop and a later copy of an application already delivered.
`Received`, payload bytes, first-delivery latency and `app_receive` remain unique
by application identity. A new retained occurrence can reverse a provisional
drop once even if it does not increase the high-water hop count. A delivered
application cannot revert to pending or dropped.

This is not a physical-copy ledger. When every registered NWK occurrence has
been released, the raw application `Dropped` count remains provisional because
an orphan MAC copy may still arrive later. Such reception can recover the
application exactly as before. No scheduler event, random draw, protocol
feedback, frame byte or transmit time is added by the accounting query.

## Validation added

The three previously executed integrated accounting cases remain enabled.
The existing relay case now expects two retained relay occurrences for its two
fresh HOP receive sequences, while its exact HOP duplicate remains suppressed.
The final-destination case still expects NWK application deduplication.

A fourth `siblings` case drives public NWK release/terminal and HOP receive
boundaries using real `TerminalSimulation` objects and counters. It checks:

- First sibling failure leaves one retained occurrence and no unique drop.
- Repeating the old callback does not consume or drop its sibling.
- A lower-hop occurrence at another node prevents premature loss.
- Failure of that last lower-hop occurrence records one provisional drop.
- Same-hop later reception recovers that drop once; a stale old callback does
  not drop the new occurrence.
- Repeated sink delivery increments unique delivery, bytes and latency once.
- Accepted relay copies after delivery still count as retained occurrences;
  their later failures never undo unique delivery.

The synthetic NWK terminal calls in this accounting case intentionally do not
pretend to be actual HOP completions. The separate relay-custody component suite
checks the real HOP-to-NWK release order and ACK/DACK/expiry behavior.

Both active and production simulation accounting methods are byte-identical
from `delivered` through `recoverDrop`. Four changed MATLAB files parse without
syntax errors using tree-sitter-matlab. MATLAB is unavailable in this workspace;
the new runtime assertions have not been executed here. No runtime pass claim
is made.
