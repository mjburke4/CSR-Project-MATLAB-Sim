# Tranche 2 PHY/MAC bridge

The PHY keeps ownership of signals, acquisition, Track and half-duplex Tx. MAC
owns wake/sleep, channel access, post-transmit waiting and ACK preparation. The
bridge adds no duplicate duty-cycle scheduler and requires no MATLAB toolbox.

```matlab
engine = csr.phy.SignalEngine(config, scheduler, streams, ...
    onReceive, onTrace, onState);
engine.state(nodeId)                        % Search / Idle / Track / Tx
engine.hasSync(nodeId)                      % admitted active preamble exists
engine.setReceiverState(nodeId, 'Search')  % MAC wakes receiver
engine.setReceiverState(nodeId, 'Idle')    % MAC sleeps receiver
```

`onState(nodeId,state)` is optional and fires synchronously only when a state
actually changes. The receiver starts in Search without a constructor callback.
Root integration creates the MACs, then initializes their duty state. A callback
may inspect state/SYNC, enqueue work, schedule events or enter Idle/Search. PHY
transition bookkeeping and acquisition scheduling finish before notification;
the enclosing transition performs no subsequent state assignment.

With this callback installed, decoded reception is delivered to MAC/HOP while
the receiver is still Track, after the ended signal has been removed from PHY
bookkeeping. ACK enqueue therefore precedes Track-to-Search notification and
can immediately activate transmit preparation. A successful receive returns
to Search at physical completion; a rejected tracked receive retains the
source 28 ns fallback. A newer MAC state change during the receive callback
supersedes either automatic return; a later change also supersedes the fallback.
Standalone T1 consumers that omit `onState` retain their existing receive
callback ordering (Search before successful completion delivery).

`hasSync` reflects admitted preambles, including preambles rejected during a
previous Track epoch. Weak or unmatched-channel signals do not enter the SYNC
table and cannot cancel another signal's acquisition when their preamble would
have expired. SYNC presence expires when its scheduled preamble event executes,
preserving scheduler order at exact-time boundaries. MAC must separately query
state; SYNC presence does not imply the receiver is awake or acquired.

Aggregate `Segments` remain opaque to PHY. The outer frame's wire size, rate,
preamble and power determine one physical transmission; MAC/HOP interprets the
unchanged segments returned by the completion callback.

Behavioral reference: ns-3 main
`486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b`,
`model/csr-net-device.h`: `UpdateSyncPresence`, `ScheduleAcquisition`,
`SleepReceiver`, `EndReceivePreamble`, `DeliverTrackedSignal`,
`EndReceiveSignal`, `ReturnToSearchAfterReceive` and
`ReturnRejectedReceiveToSearch`; `model/csr-mac-core.h`: `SetReceiveState`.
The MATLAB cleanup-before-delivery detail is an intentional callback-safety
choice; delivered frame processing still precedes the observable Search
transition as in ns-3.

Nine tests in `tests/TestPhyMacBridge.m` cover receive/state ordering,
callback-directed sleep after successful or rejected reception, T1 ordering preservation, admitted SYNC lifetime,
waking into an existing preamble, the 28 ns rejection fallback, superseding
that fallback, and opaque aggregate transport. MISS_HIT static lint passed for
the two MATLAB files. These new tests have not been executed in MATLAB here.
