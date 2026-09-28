#!/usr/bin/env python3
"""Generate a validation-only SignalEngine copy with named native PHY draws.

The exact pinned production source hash is checked before transformation.
Only the two random call sites and constructor sampler slot are changed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = (HERE.parents[1] / "routing_work/grfix/candidate/+csr/+phy/SignalEngine.m")
TARGET = HERE / "DiscoverySignalEngine.m"
PIN = "289c764bac0de95fefa75812e1b5090dcdf1953e35960cf7f02c4e298f4e294e"


def replace_one(source: str, before: str, after: str) -> str:
    assert source.count(before) == 1, before[:110]
    return source.replace(before, after, 1)


def main() -> None:
    original = SOURCE.read_bytes()
    assert hashlib.sha256(original).hexdigest() == PIN, "Source changed; re-audit seam."
    text = original.decode()
    text = replace_one(text, "classdef SignalEngine < handle", "classdef DiscoverySignalEngine < handle")
    text = replace_one(text, "        Streams\n", "        Streams\n        NativeTape = [] % validation-only captured PHY draws\n")
    text = replace_one(text,
        "function obj = SignalEngine(config, scheduler, streams, onReceive, onTrace, onState, transportTiming)",
        "function obj = DiscoverySignalEngine(config, scheduler, streams, onReceive, onTrace, onState, transportTiming, nativeTape)")
    text = replace_one(text,
        "            if nargin < 5, onTrace = []; end",
        "            if nargin < 8, nativeTape = []; end\n"
        "            if nargin < 7, transportTiming = []; end\n"
        "            obj.NativeTape = nativeTape;\n"
        "            if nargin < 5, onTrace = []; end")
    text = replace_one(text,
        "                if profile.StochasticSyncThreshold && profile.SyncSnrThresholdVarianceDb2>0\n"
        "                    threshold=threshold+sqrt(profile.SyncSnrThresholdVarianceDb2)* ...\n"
        "                        randn(obj.Streams.get(obj.Receivers(index).Id,'sync'));\n"
        "                end",
        "                if ~isempty(obj.NativeTape) && obj.NativeTape.owns(obj.Receivers(index).Id)\n"
        "                    threshold=obj.NativeTape.syncThreshold(obj.Receivers(index).Id,incoming.Frame.Id);\n"
        "                elseif profile.StochasticSyncThreshold && profile.SyncSnrThresholdVarianceDb2>0\n"
        "                    threshold=threshold+sqrt(profile.SyncSnrThresholdVarianceDb2)* ...\n"
        "                        randn(obj.Streams.get(obj.Receivers(index).Id,'sync'));\n"
        "                end")
    text = replace_one(text,
        "                allocated=csr.phy.Model.allocateErrors(obj.Config.Nodes(index).RadioProfile, ...\n"
        "                    signal.FrontEnd,signal.StartSec,signal.PreambleBits,signal.PacketBits, ...\n"
        "                    signal.Frame.RateKeyKbps,interval,obj.Streams.get(obj.Receivers(index).Id,'phy'));",
        "                if ~isempty(obj.NativeTape) && obj.NativeTape.owns(obj.Receivers(index).Id)\n"
        "                    allocated=DiscoveryReplayAllocator.allocateErrors(obj.Config.Nodes(index).RadioProfile, ...\n"
        "                        signal.FrontEnd,signal.StartSec,signal.PreambleBits,signal.PacketBits, ...\n"
        "                        signal.Frame.RateKeyKbps,interval,obj.NativeTape, ...\n"
        "                        obj.Receivers(index).Id,signal.Frame.Id,signal.IntervalCount+1);\n"
        "                else\n"
        "                    allocated=csr.phy.Model.allocateErrors(obj.Config.Nodes(index).RadioProfile, ...\n"
        "                        signal.FrontEnd,signal.StartSec,signal.PreambleBits,signal.PacketBits, ...\n"
        "                        signal.Frame.RateKeyKbps,interval,obj.Streams.get(obj.Receivers(index).Id,'phy'));\n"
        "                end")
    TARGET.write_text(text)
    manifest={"schema":"csr-discovery-validation-seam-v1", "production_signal_engine_sha256":PIN,
              "generated_signal_engine_sha256": hashlib.sha256(text.encode()).hexdigest(),
              "scope":"Copied test engine, only captured PHY sampler call sites altered; production untouched"}
    (HERE / "seam_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest))


if __name__ == "__main__": main()
