#!/usr/bin/env python3
"""Insert validation-only passive chronology into a pristine copied CSR model.

Call instrument_model(model_root) after copying the pinned production model and
before adding sampler seams. The generated MATLAB code calls
ac.Trace.record(time, kind, node, details). That sink must not schedule events,
draw randomness, or mutate protocol objects. This script never touches the
production source directory unless explicitly passed that directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PINS = {
    "+csr/+sim/EventScheduler.m": "0e1887cf9d1195a20ab8e4a24c7ff182a2e72303abfec67d34a61eaa1fa9585e",
    "+csr/+mac/Layer.m": "d2e1b9e08c7e3d3ea60c88b61f3480f881e53c5963f48ae09822c4f04170e67b",
    "+csr/+phy/SignalEngine.m": "289c764bac0de95fefa75812e1b5090dcdf1953e35960cf7f02c4e298f4e294e",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Inserter:
    """Only inserts code; reversing recorded edits proves base bytes survive."""

    def __init__(self, original: str):
        self.original = original
        self.text = original
        self.edits: list[tuple[str, str]] = []

    def after(self, anchor: str, addition: str) -> None:
        count = self.text.count(anchor)
        if count != 1:
            raise ValueError(f"Expected one anchor, got {count}: {anchor[:120]!r}")
        replacement = anchor + addition
        self.text = self.text.replace(anchor, replacement, 1)
        self.edits.append((anchor, replacement))

    def before(self, anchor: str, addition: str) -> None:
        count = self.text.count(anchor)
        if count != 1:
            raise ValueError(f"Expected one anchor, got {count}: {anchor[:120]!r}")
        replacement = addition + anchor
        self.text = self.text.replace(anchor, replacement, 1)
        self.edits.append((anchor, replacement))

    def finish(self) -> str:
        restored = self.text
        for anchor, replacement in reversed(self.edits):
            if restored.count(replacement) != 1:
                raise AssertionError("Inserted source region cannot be reversed uniquely")
            restored = restored.replace(replacement, anchor, 1)
        if restored != self.original:
            raise AssertionError("Observer transformation changed existing source bytes")
        return self.text


def scheduler(source: str) -> Inserter:
    p = Inserter(source)
    p.after(
        "            obj.Active(id) = true;\n",
        "            ac.Trace.record(obj.Now,'scheduler_schedule',0, ...\n"
        "                struct('EventId',id,'DeadlineSeconds',time, ...\n"
        "                'Callback',func2str(callback),'PendingCount',double(obj.Active.Count)));\n",
    )
    p.after(
        "            wasPending = isKey(obj.Active, id);\n",
        "            ac.Trace.record(obj.Now,'scheduler_cancel',0, ...\n"
        "                struct('EventId',id,'WasPending',wasPending));\n",
    )
    p.before(
        "                callback();\n",
        "                ac.Trace.record(obj.Now,'scheduler_fire',0, ...\n"
        "                    struct('EventId',id,'DeadlineSeconds',time, ...\n"
        "                    'Callback',func2str(callback),'ExecutedOrdinal',executed));\n",
    )
    p.after(
        "                callback();\n",
        "                ac.Trace.record(obj.Now,'scheduler_return',0, ...\n"
        "                    struct('EventId',id,'DeadlineSeconds',time, ...\n"
        "                    'Callback',func2str(callback)));\n",
    )
    return p


def mac(source: str) -> Inserter:
    p = Inserter(source)
    # These boundaries identify timer/state causes. slotTick records the
    # before/after reservation and SYNC gating without changing its dispatch.
    for name, args in [
        ("start", "obj"), ("schedulePending", "obj"),
        ("startSearchTiming", "obj"), ("holdoffExpired", "obj"),
        ("idleRts", "obj"), ("periodicWake", "obj"), ("sleep", "obj"),
        ("slotTick", "obj"), ("prepare", "obj, redrawZero"),
        ("transmit", "obj"), ("packingRetry", "obj"),
        ("finishTx", "obj"), ("postTxExpired", "obj"),
        ("cancelPostTxWait", "obj"), ("receiverChanged", "obj, state"),
    ]:
        p.after(
            f"        function {name}({args})\n",
            f"            obj.autonomousObserve('{name}_before');\n"
            f"            acMethodExit = onCleanup(@()obj.autonomousObserve('{name}_after')); %#ok<NASGU>\n",
        )
    p.after(
        "        function onStateChange(obj, previous, state)\n",
        "            ac.Trace.record(obj.Scheduler.Now,'mac_state_transition',obj.NodeId, ...\n"
        "                struct('Previous',previous,'Current',state));\n",
    )
    p.after(
        "        function cancelTimer(obj, name)\n",
        "            ac.Trace.record(obj.Scheduler.Now,'mac_cancel_timer',obj.NodeId, ...\n"
        "                struct('TimerName',name,'EventId',obj.(name)));\n",
    )
    p.before(
        "        function emit(obj, name, frame, details)\n",
        "        function autonomousObserve(obj,cause)\n"
        "            % Validation-only read-only snapshot; no callback/event/RNG ownership.\n"
        "            neighborIds=keys(obj.Neighbors);\n"
        "            neighbors=repmat(struct('PeerId',0,'ReservationCounter',0, ...\n"
        "                'LastHeardSeconds',0),1,numel(neighborIds));\n"
        "            for acIndex=1:numel(neighborIds)\n"
        "                acPeer=neighborIds{acIndex}; acNeighbor=obj.Neighbors(acPeer);\n"
        "                neighbors(acIndex)=struct('PeerId',acPeer, ...\n"
        "                    'ReservationCounter',acNeighbor.ReservationCounter, ...\n"
        "                    'LastHeardSeconds',acNeighbor.LastHeardSeconds);\n"
        "            end\n"
        "            details=struct('Cause',cause,'State',obj.State, ...\n"
        "                'DataQueueCount',obj.DataQueueCount,'AckQueueCount',obj.AckQueueCount, ...\n"
        "                'ReservationSlot',obj.ReservationSlot,'ReservationCounter',obj.ReservationCounter, ...\n"
        "                'LastAdvertisedReservation',obj.LastAdvertisedReservation, ...\n"
        "                'LastOpportunitySlot',obj.LastOpportunitySlot, ...\n"
        "                'PreparationActive',obj.PreparationActive,'HoldoffOver',obj.HoldoffOver, ...\n"
        "                'PostTxWaitActive',obj.PostTxWaitActive,'InReceiverUpdate',obj.InReceiverUpdate, ...\n"
        "                'ActiveNodes',obj.Config.ActiveNodes,'ReportedActiveNodes',obj.Config.ReportedActiveNodes, ...\n"
        "                'SlotProfile',obj.Config.SlotProfile,'Neighbors',neighbors, ...\n"
        "                'SlotEvent',obj.SlotEvent,'HoldoffEvent',obj.HoldoffEvent, ...\n"
        "                'IdleRtsEvent',obj.IdleRtsEvent,'FinishEvent',obj.FinishEvent, ...\n"
        "                'WakeEvent',obj.WakeEvent,'SleepEvent',obj.SleepEvent, ...\n"
        "                'PostTxEvent',obj.PostTxEvent,'PackingRetryEvent',obj.PackingRetryEvent);\n"
        "            ac.Trace.record(obj.Scheduler.Now,'mac_boundary',obj.NodeId,details);\n"
        "        end\n\n",
    )
    return p


def phy(source: str) -> Inserter:
    p = Inserter(source)
    for name, args in [
        ("finishTx", "obj,index"), ("cancelAcquisition", "obj,index"),
        ("scheduleAcquisition", "obj,index"), ("beginSignal", "obj,index,incoming"),
        ("endPreamble", "obj,index,id"), ("acquire", "obj,index"),
        ("finishOccluded", "obj,index,signal"), ("endSignal", "obj,index,id"),
        ("returnRejectedToSearch", "obj,index"), ("returnToSearch", "obj,index"),
    ]:
        p.after(
            f"        function {name}({args})\n",
            f"            obj.autonomousObserve(index,'{name}_before');\n"
            f"            acMethodExit = onCleanup(@()obj.autonomousObserve(index,'{name}_after')); %#ok<NASGU>\n",
        )
    p.after(
        "            value=char(value); index=obj.nodeIndex(nodeId);\n",
        "            ac.Trace.record(obj.Scheduler.Now,'phy_state_request',nodeId, ...\n"
        "                struct('Previous',obj.Receivers(index).State,'Requested',value));\n"
        "            obj.autonomousObserve(index,'setReceiverState_before');\n"
        "            acMethodExit = onCleanup(@()obj.autonomousObserve(index,'setReceiverState_after')); %#ok<NASGU>\n",
    )
    p.after(
        "        function notifyState(obj,index,previous)\n",
        "            ac.Trace.record(obj.Scheduler.Now,'phy_state_transition',obj.Receivers(index).Id, ...\n"
        "                struct('Previous',previous,'Current',obj.Receivers(index).State, ...\n"
        "                'Changed',~strcmp(previous,obj.Receivers(index).State)));\n",
    )
    p.before(
        "        function notifyState(obj,index,previous)\n",
        "        function autonomousObserve(obj,index,cause)\n"
        "            % Snapshot only scalar/struct state already owned by the PHY.\n"
        "            rx=obj.Receivers(index);\n"
        "            signals=repmat(struct('SignalId',0,'FrameId',uint64(0), ...\n"
        "                'SourceId',0,'StartSeconds',0,'PreambleEndSeconds',0, ...\n"
        "                'EndSeconds',0,'SyncEligible',false,'PreambleActive',false, ...\n"
        "                'Rejected',false,'HalfDuplex',false,'MissedByState',false),1,numel(rx.Signals));\n"
        "            syncPresent=false;\n"
        "            for acIndex=1:numel(rx.Signals)\n"
        "                s=rx.Signals{acIndex};\n"
        "                signals(acIndex)=struct('SignalId',s.Id,'FrameId',s.Frame.Id, ...\n"
        "                    'SourceId',s.Frame.SourceId,'StartSeconds',s.StartSec, ...\n"
        "                    'PreambleEndSeconds',s.PreambleEndSec,'EndSeconds',s.EndSec, ...\n"
        "                    'SyncEligible',s.SyncEligible,'PreambleActive',s.PreambleActive, ...\n"
        "                    'Rejected',s.Rejected,'HalfDuplex',s.HalfDuplex, ...\n"
        "                    'MissedByState',s.MissedByState);\n"
        "                syncPresent=syncPresent || (s.SyncEligible && s.PreambleActive);\n"
        "            end\n"
        "            details=struct('Cause',cause,'State',rx.State,'TrackedId',rx.TrackedId, ...\n"
        "                'AcquireEvent',rx.AcquireEvent,'TxEvent',rx.TxEvent,'TxUntilSeconds',rx.TxUntil, ...\n"
        "                'SameSpeed',rx.SameSpeed,'JsrDb',rx.JsrDb, ...\n"
        "                'TimeOffsetSeconds',rx.TimeOffsetSeconds,'SyncPresent',syncPresent, ...\n"
        "                'Signals',signals);\n"
        "            ac.Trace.record(obj.Scheduler.Now,'phy_boundary',rx.Id,details);\n"
        "        end\n\n",
    )
    return p


def instrument_model(model_root: Path | str) -> dict:
    root = Path(model_root)
    builders = {
        "+csr/+sim/EventScheduler.m": scheduler,
        "+csr/+mac/Layer.m": mac,
        "+csr/+phy/SignalEngine.m": phy,
    }
    generated = []
    # Validate all sources before any writes so source drift fails atomically.
    for rel, pin in PINS.items():
        original = (root / rel).read_bytes()
        if sha(original) != pin:
            raise ValueError(f"{rel}: expected pristine source SHA-256 {pin}, got {sha(original)}")
        patcher = builders[rel](original.decode("utf-8"))
        output = patcher.finish().encode("utf-8")
        generated.append((rel, output, {"path": rel, "source_sha256": pin,
            "instrumented_sha256": sha(output), "insertions": len(patcher.edits),
            "source_recovered_exactly_after_removing_insertions": True}))
    for rel, output, _ in generated:
        (root / rel).write_bytes(output)
    return {"schema": "csr-autonomous-passive-observer-seam-v1",
        "sink": "ac.Trace.record(time,kind,node,details)",
        "passivity_claim": "Static insertions only; runtime passive-equivalence gate remains required",
        "runtime_passivity_verified": False,
        "files": [row for _, _, row in generated]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_root", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    manifest = instrument_model(args.model_root)
    content = json.dumps(manifest, indent=2) + "\n"
    if args.manifest:
        args.manifest.write_text(content)
    print(content, end="")
