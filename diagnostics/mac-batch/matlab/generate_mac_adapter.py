#!/usr/bin/env python3
"""Make the validation-only receiver-boundary adapter from the accepted MAC.

The recorded receiver-availability tape owns duty-cycle wake/sleep transitions.
The production MAC queue, selection, slot, holdoff, and TX paths stay unchanged.
This script deliberately refuses an unexpected source rather than fuzzy patching.
"""
from pathlib import Path
import difflib
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "core/+csr/+mac/Layer.m"
if not SOURCE.exists():
    SOURCE = ROOT.parent / "receiver_replay/core/+csr/+mac/Layer.m"
OUT = ROOT / "matlab/+mac_replay/MacLayer.m"
original = SOURCE.read_text()
edits = [
    ("classdef Layer < handle", "classdef MacLayer < handle"),
    ("function obj = Layer(nodeId, scheduler, streams, config, callbacks)",
     "function obj = MacLayer(nodeId, scheduler, streams, config, callbacks)"),
    ("obj.WakeEvent = obj.Scheduler.scheduleAt(nextWake, @() obj.periodicWake());",
     "% Replay receiver tape owns periodic wake; preserve DutyCycleEnabled\n"
     "                % for the unmodified IdleRts near-wake guard.\n"
     "                obj.WakeEvent = uint64(0); %#ok<NASGU>"),
    ("                obj.setState('Idle');\n            end\n        end\n\n        function seconds = postTxSeconds(obj)",
     "                % Replay receiver tape owns the post-TX Search-to-Idle edge.\n"
     "            end\n        end\n\n        function seconds = postTxSeconds(obj)"),
    ("                            obj.SleepEvent = obj.after(obj.Config.SearchSeconds, @() obj.sleep());",
     "                            % Replay receiver tape owns the Track-to-Search sleep edge.\n"
     "                            obj.SleepEvent = uint64(0);"),
    ("                    obj.ReservationCounter = obj.ReservationCounter - 1;",
     "                    obj.ReservationCounter = obj.ReservationCounter - 1;\n"
     "                    obj.emit('mac_reservation_tick', struct(), ...\n"
     "                        struct('ReservationCounter', obj.ReservationCounter));"),
    ("        function removed = cancelControl(obj,peerId,controlType)",
     "        function removed = replayCancelWindow(obj,peerId,baseSequence,bitmap)\n"
     "            % Boundary translation: native CancelAcknowledgedFrames accepts\n"
     "            % a bitmap and excludes structured-destination frames. The\n"
     "            % MATLAB HOP caller filters custody before invoking cancel.\n"
     "            % Translate queue-cancellation intent, then use production cancel.\n"
     "            sequences = []; protected = [];\n"
     "            for index = 1:obj.DataQueueCount\n"
     "                frame = obj.DataQueue{index}.Frame;\n"
     "                if ~frame.AckRequired || frame.DestinationId ~= peerId, continue; end\n"
     "                if isfield(frame,'DestinationIds') && ~isempty(frame.DestinationIds)\n"
     "                    protected(end+1) = double(frame.Sequence); %#ok<AGROW>\n"
     "                    continue;\n"
     "                end\n"
     "                age = mod(double(baseSequence)-double(frame.Sequence),65536);\n"
     "                if age < 64 && bitget(bitmap,age+1)\n"
     "                    sequences(end+1) = double(frame.Sequence); %#ok<AGROW>\n"
     "                end\n"
     "            end\n"
     "            assert(isempty(intersect(sequences,protected)), ...\n"
     "                'mac_replay:AmbiguousCancellation', ...\n"
     "                'Structured and unstructured queued frames share a cancellation key.');\n"
     "            removed = 0;\n"
     "            for sequence = unique(sequences,'stable')\n"
     "                removed = removed + obj.cancel(peerId,sequence);\n"
     "            end\n"
     "        end\n\n"
     "        function removed = cancelControl(obj,peerId,controlType)"),
]
modified = original
for before, after in edits:
    if modified.count(before) != 1:
        raise SystemExit(f"Expected exactly one adapter seam: {before!r}")
    modified = modified.replace(before, after)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(modified)
diff = ''.join(difflib.unified_diff(original.splitlines(True), modified.splitlines(True),
                                 fromfile='core/+csr/+mac/Layer.m', tofile='matlab/+mac_replay/MacLayer.m'))
OUT.with_suffix('.patch').write_text(diff)
digest = lambda b: hashlib.sha256(b).hexdigest()
record = {
    "source_relative_path": "core/+csr/+mac/Layer.m",
    "source_sha256": digest(original.encode()),
    "adapter_relative_path": "matlab/+mac_replay/MacLayer.m",
    "adapter_sha256": digest(modified.encode()),
    "patch_sha256": digest(diff.encode()),
    "edit_count": len(edits),
    "behavioral_seams": [
        "Receiver tape owns periodic wake (IdleRts guard remains enabled).",
        "Receiver tape owns post-TX idle edge; post-TX wait flag expiry is retained.",
        "Receiver tape owns sleep after tracked reception."
    ],
    "unchanged": "Queue ordering, cancellation, ACK repetition, packing, preamble, slot/holdoff clocks, historical slot avoidance, IdleRts and actual transmission paths.",
    "scope": "Conditional MAC scheduling parity under common receiver availability; not a duty-cycle lifecycle test."
}
record['passive_observer'] = 'Emit the actual local reservation counter after each production decrement; no extra clock event, draw, or state change.'
record['cancellation_boundary'] = {
    'native': 'CancelAcknowledgedFrames scans the queued window and excludes structured destination sequences.',
    'matlab': 'HOP Layer.receiveFeedback/complete filters control custody before calling MAC.cancel; calling MAC.cancel for every bitmap bit is not an equivalent boundary.',
    'adapter': 'replayCancelWindow selects only native-eligible actual queued keys, then calls unchanged production cancel. Ambiguous protected/unprotected keys abort.',
    'scope': 'Queue-cancellation intent is exogenous. This test does not validate HOP custody or group completion.'
}
(ROOT / 'matlab/adapter_provenance.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps(record, indent=2))
