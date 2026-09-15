#!/usr/bin/env python3
"""Make two explicit test seams plus one read-only DACK getter in a copied, pinned CSR header tree.

The raw-draw seam retains UniformRandomVariable creation and all occupancy
probing. The controlled-delivery seam runs after unchanged airtime calculation
and NotifyPhyTxStart. Empty callbacks preserve the original branches.
"""
from __future__ import annotations
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import shutil


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected exactly one pinned patch anchor: {old[:90]}")
    return text.replace(old, new)


def build(source: Path, output: Path):
    model = source / "model"
    if output.exists() and any(output.iterdir()):
        raise ValueError("Overlay destination must be empty")
    destination = output / "ns3"
    destination.mkdir(parents=True, exist_ok=True)
    original = {}
    for path in sorted(model.glob("csr-*")):
        if path.is_file():
            shutil.copy2(path, destination / path.name)
            original[path.name] = digest(path)
    hooks = Path(__file__).parent / "ns3" / "tranche12-relay-hooks.h"
    shutil.copy2(hooks, destination / hooks.name)
    name = "csr-mac-core.h"
    text = (destination / name).read_text()
    text = once(text, "#pragma once", '#pragma once\n#include "tranche12-relay-hooks.h"')
    anchor = """        // collision slot R cannot be revisited.
        int chosenSlot = rng->GetInteger (0, slotRange);"""
    replacement = """        // collision slot R cannot be revisited.
        // TRANCHE12 TEST SEAM: only the raw integer, before native probing.
        int chosenSlot = csr_t12::rawDraw
          ? csr_t12::rawDraw (m_nodeId, 0, slotRange)
          : rng->GetInteger (0, slotRange);"""
    text = once(text, anchor, replacement)
    anchor = """                          << " using historical next_tslot modulo probe"
                          << std::endl;
                return chosenSlot;"""
    replacement = """                          << " using historical next_tslot modulo probe"
                          << std::endl;
                if (csr_t12::resolvedDraw)
                  csr_t12::resolvedDraw (m_nodeId, chosenSlot, probes);
                return chosenSlot;"""
    text = once(text, anchor, replacement)
    (destination / name).write_text(text)
    name = "csr-net-device.h"
    text = (destination / name).read_text()
    anchor = """  m_mac.NotifyPhyTxStart (Seconds (duration));

  for (const auto &peer : m_peers)"""
    replacement = """  m_mac.NotifyPhyTxStart (Seconds (duration));

  // TRANCHE12 TEST SEAM: actual airtime and TX state, prescribed delivery.
  if (csr_t12::transport)
    {
      csr_t12::transport (m_id, frameCopies, Seconds (duration), rateKbps,
                          txPowerDbm, static_cast<int> (preamble), slot);
      return Seconds (duration);
    }

  for (const auto &peer : m_peers)"""
    text = once(text, anchor, replacement)
    (destination / name).write_text(text)
    name = "csr-hop-layer.h"
    text = (destination / name).read_text()
    text = once(text, "  uint32_t GetPendingDataCount () const\n", "  // TRANCHE12 read-only observation of actual DACK ownership.\n  uint32_t GetDackHoldCountForTranche12 () const\n  { return static_cast<uint32_t> (m_dackList.size ()); }\n\n  uint32_t GetPendingDataCount () const\n")
    (destination / name).write_text(text)
    modified = [name for name in original if digest(destination / name) != original[name]]
    if sorted(modified) != ["csr-hop-layer.h", "csr-mac-core.h", "csr-net-device.h"]:
        raise ValueError("Unexpected overlay modifications")
    patch = []
    for name in modified:
        patch.extend(difflib.unified_diff(
            (model / name).read_text().splitlines(True),
            (destination / name).read_text().splitlines(True),
            fromfile="pinned/" + name, tofile="overlay/" + name))
    (output / "seams.patch").write_text("".join(patch))
    manifest = {
        "schema": "csr-tranche12-overlay-v1",
        "scope": "Pinned NWK/MAC/HOP with test-only raw draw and controlled transport seams; no RF claim",
        "unchanged_native_rng_construction": True,
        "unchanged_native_occupancy_probe": True,
        "disabled_hooks_execute_original_paths": True,
        "dack_getter_reads_actual_hold_list_without_mutation": True,
        "original_files": original,
        "modified_files": {name: {"original_sha256": original[name],
                                  "overlay_sha256": digest(destination / name)} for name in modified},
        "hooks_sha256": digest(destination / hooks.name),
        "patch_sha256": digest(output / "seams.patch"),
        "recipe_sha256": digest(Path(__file__)),
    }
    (output / "overlay.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.source.resolve(), args.output.resolve())
