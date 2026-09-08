#!/usr/bin/env python3
"""Reproduce MATLAB BER data from the authoritative ns-3 source snapshot.

Usage: python scripts/import_ber_tables.py --source-dir ../ns3-source
       python scripts/import_ber_tables.py --source-dir ../ns3-source --check
       python scripts/import_ber_tables.py --source-dir ../ns3-source --check --verify-cpp

Only the Python standard library is required. --verify-cpp additionally needs
g++; it executes the actual source lookup implementation (no ns-3 libraries
needed). Its results validate data conversion, not MATLAB execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import tempfile


SOURCE_FILES = (
    "model/csr-opnet-ber-tables.h",
    "model/csr-opnet-ber-tables.cc",
    "model/csr-opnet-ber-tables-data.inc",
    "csr-phy-ber-ecc-smoke.cc",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def number(token: str) -> float | int:
    token = token.strip()
    if "0x" in token.lower():
        return float.fromhex(token)
    if re.fullmatch(r"[+-]?\d+", token):
        return int(token)
    return float(token)


def read_constant(source: str, name: str) -> float | int:
    match = re.search(r"\b" + re.escape(name) + r"\s*=\s*([^;]+);", source)
    if match is None:
        raise ValueError(f"Missing source constant {name}")
    return number(match.group(1))


def read_array(source: str, name: str) -> list[float | int]:
    match = re.search(r"\b" + re.escape(name) + r"\[\]\s*=\s*\{([^}]*)\};", source)
    if match is None:
        raise ValueError(f"Missing source array {name}")
    return [number(token) for token in match.group(1).split(",") if token.strip()]


def parse(source_dir: Path, commit: str) -> tuple[dict, dict]:
    raw = {name: (source_dir / name).read_bytes() for name in SOURCE_FILES}
    source = raw[SOURCE_FILES[2]].decode("utf-8")
    implementation = raw[SOURCE_FILES[1]].decode("utf-8")
    hashes = {name: sha256(data) for name, data in raw.items()}
    result = {"Schema": "csr-ber-tables-v1", "SourceCommit": commit}
    for key, prefix in (("Standard", "CSR_STANDARD"), ("Dqpsk", "CSR_DQPSK")):
        table = {
            "XStart": read_constant(source, prefix + "_X_START"),
            "XStep": read_constant(source, prefix + "_X_STEP"),
            "SampleCount": read_constant(source, prefix + "_SAMPLE_COUNT"),
            "StoredCount": read_constant(source, prefix + "_STORED_COUNT"),
            "Values": read_array(source, prefix + "_VALUES"),
        }
        if len(table["Values"]) != table["StoredCount"]:
            raise ValueError(f"Wrong {key} stored sample count")
        if not 0 < table["StoredCount"] <= table["SampleCount"]:
            raise ValueError(f"Wrong {key} sparse extent")
        result[key] = table
    collision = {
        "XStart": read_constant(source, "CSR_COLLISION_X_START"),
        "XStep": read_constant(source, "CSR_COLLISION_X_STEP"),
        "SampleCount": read_constant(source, "CSR_COLLISION_SAMPLE_COUNT"),
        "CurveCount": read_constant(source, "CSR_COLLISION_CURVE_COUNT"),
        "ValueOffsets": read_array(source, "CSR_COLLISION_VALUE_OFFSETS"),
        "Values": read_array(source, "CSR_COLLISION_VALUES"),
    }
    layout_match = re.search(r"CSR_RATE_LAYOUT\s*\{\{(.*?)\}\};", implementation, re.S)
    if layout_match is None:
        raise ValueError("Missing CSR_RATE_LAYOUT")
    layouts = []
    for row in re.findall(r"\{([^{}]+)\}", layout_match.group(1)):
        values = [number(token) for token in row.split(",")]
        if len(values) != 4:
            raise ValueError("Unexpected CSR_RATE_LAYOUT columns")
        layouts.append(dict(zip(("RateKbps", "SymbolDurationSeconds",
                                 "HalfChipOffsetCount", "FirstCurve"), values)))
    bucket_match = re.search(r"CSR_JSR_BUCKETS\s*\{\{(.*?)\}\};", implementation, re.S)
    if bucket_match is None:
        raise ValueError("Missing CSR_JSR_BUCKETS")
    result["JsrBuckets"] = [number(x) for x in bucket_match.group(1).split(",") if x.strip()]
    result["ChipSeconds"] = read_constant(implementation, "CSR_CHIP_SECONDS")
    result["RateLayout"] = layouts
    offsets = collision["ValueOffsets"]
    if len(offsets) != collision["CurveCount"] + 1 or offsets[0] != 0:
        raise ValueError("Invalid collision sparse offset extent")
    if offsets[-1] != len(collision["Values"]):
        raise ValueError("Collision sparse offsets do not cover stored values")
    if any(not 0 <= b - a <= collision["SampleCount"] for a, b in zip(offsets, offsets[1:])):
        raise ValueError("Collision sparse offsets are not valid monotonic ranges")
    cursor = 0
    for row in layouts:
        if row["FirstCurve"] != cursor:
            raise ValueError("Rate layouts have a gap/overlap")
        cursor += len(result["JsrBuckets"]) * row["HalfChipOffsetCount"]
    if cursor != collision["CurveCount"]:
        raise ValueError("Rate layouts do not cover all collision curves")
    result["Collision"] = collision
    for table in (result["Standard"], result["Dqpsk"], collision):
        if any(not math.isfinite(x) or not 0 <= x <= 1 for x in table["Values"]):
            raise ValueError("Stored BER is outside [0, 1]")
    original_hash = re.search(r"Parsed input SHA-256: ([0-9a-f]{64})", source)
    provenance = {
        "schema": "csr-ber-tables-provenance-v1",
        "source_repository": "mjburke4/CSR-Project-NS3-part2",
        "source_commit": commit,
        "source_file_sha256": hashes,
        "original_opnet_parsed_input_sha256": original_hash.group(1) if original_hash else None,
        "conversion": "C++ hexadecimal binary64 literals parsed exactly; JSON decimal round-trip",
        "sparse_convention": "Zero-based offsets; omitted tails are zero through SampleCount",
        "standard_samples": result["Standard"]["SampleCount"],
        "standard_stored_samples": result["Standard"]["StoredCount"],
        "dqpsk_samples": result["Dqpsk"]["SampleCount"],
        "dqpsk_stored_samples": result["Dqpsk"]["StoredCount"],
        "collision_curves": collision["CurveCount"],
        "collision_samples_per_curve": collision["SampleCount"],
        "collision_stored_values": len(collision["Values"]),
        "high_rate_mapping": {"500_kbps": "DPSK_PB analytical expression", "1000_kbps": "DQPSK table"},
        "dqpsk_low_snr_value": result["Dqpsk"]["Values"][0],
        "matlab_runtime_executed_by_converter": False,
        "converter_sha256": sha256(Path(__file__).read_bytes()),
    }
    return result, provenance


def cpp_verify(source_dir: Path, tables: dict) -> dict:
    """Exercise every table grid point and midpoint against actual C++ code."""
    queries = []
    expected = []

    def append_curve(family: str, table: dict, values: list, prefix: str = "") -> None:
        full = values + [0.0] * (table["SampleCount"] - len(values))
        # Exact samples also check the nearest-grid tolerance and zero tails.
        for i, value in enumerate(full):
            x = table["XStart"] + table["XStep"] * i
            queries.append(f"{family} {prefix}{x.hex()}")
            expected.append(value)
        for i in range(len(full) - 1):
            x = table["XStart"] + table["XStep"] * (i + 0.5)
            position = (x - table["XStart"]) / table["XStep"]
            fraction = position - math.floor(position)
            expected.append(full[i] + fraction * (full[i + 1] - full[i]))
            queries.append(f"{family} {prefix}{x.hex()}")

    for name, family in (("Standard", "s"), ("Dqpsk", "q")):
        append_curve(family, tables[name], tables[name]["Values"])
    collision = tables["Collision"]
    offsets = collision["ValueOffsets"]
    for row in tables["RateLayout"]:
        for jsr_index, jsr in enumerate(tables["JsrBuckets"]):
            for offset in range(row["HalfChipOffsetCount"]):
                curve = row["FirstCurve"] + jsr_index * row["HalfChipOffsetCount"] + offset
                values = collision["Values"][offsets[curve]:offsets[curve + 1]]
                prefix = f"{row['RateKbps']} {jsr} {(offset * 1e-6).hex()} "
                append_curve("c", collision, values, prefix)
    driver = r'''
#include "csr-opnet-ber-tables.h"
#include <cstdlib>
#include <iostream>
#include <string>
int main() {
  char family; std::string input, timing; int rate, jsr;
  while (std::cin >> family) {
    if (family == 'c') std::cin >> rate >> jsr >> timing;
    std::cin >> input;
    double x = std::strtod(input.c_str(), nullptr), value;
    if (family == 's') value = ns3::CsrOpnetBerTables::GetStandardBer(x);
    else if (family == 'q') value = ns3::CsrOpnetBerTables::GetDqpskBer(x);
    else value = ns3::CsrOpnetBerTables::GetCollisionBer(
      rate, jsr, std::strtod(timing.c_str(), nullptr), x);
    std::cout.write(reinterpret_cast<const char *>(&value), sizeof(value));
  }
}
'''
    with tempfile.TemporaryDirectory(prefix="csr-ber-") as tmp:
        directory = Path(tmp)
        cpp = directory / "verify.cc"
        exe = directory / "verify"
        cpp.write_text(driver, encoding="utf-8")
        subprocess.run(["g++", "-std=c++17", "-O0", "-ffp-contract=off", "-I",
                        str(source_dir / "model"), str(cpp),
                        str(source_dir / SOURCE_FILES[1]), "-o", str(exe)], check=True)
        actual = subprocess.run([str(exe)], input=("\n".join(queries) + "\n").encode(),
                                capture_output=True, check=True).stdout
    reference = struct.pack(f"={len(expected)}d", *expected)
    if actual != reference:
        if len(actual) != len(reference):
            raise AssertionError(f"C++ returned {len(actual)} bytes; expected {len(reference)}")
        for i, (observed,) in enumerate(struct.iter_unpack("=d", actual)):
            if struct.pack("=d", observed) != struct.pack("=d", expected[i]):
                raise AssertionError(f"C++ mismatch {queries[i]}: {observed} != {expected[i]}")
    return {"native_cpp_comparisons": len(expected), "comparison": "binary64 exact",
            "scope": "All standard/DQPSK/collision grid samples and midpoints; no MATLAB execution"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-commit", help="Snapshot SHA when source has no .git")
    parser.add_argument("--check", action="store_true", help="Verify byte-for-byte regeneration; write nothing")
    parser.add_argument("--verify-cpp", action="store_true", help="Execute source C++ lookup over every curve")
    args = parser.parse_args()
    source_dir = args.source_dir.resolve()
    commit = args.source_commit or subprocess.check_output(
        ["git", "-C", str(source_dir), "rev-parse", "HEAD"], text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Source commit must be a full 40-digit SHA")
    tables, provenance = parse(source_dir, commit)
    data = (json.dumps(tables, separators=(",", ":"), allow_nan=False) + "\n").encode()
    # Python's decimal JSON serialization must preserve all source binary64 values.
    if json.loads(data) != tables:
        raise AssertionError("JSON binary64 round-trip failed")
    provenance["data_sha256"] = sha256(data)
    files = {
        "data/ber_tables.json": data,
        "evidence/ber-tables-provenance.json": (json.dumps(provenance, indent=2) + "\n").encode(),
    }
    for name, content in files.items():
        path = args.output_dir / name
        if args.check:
            if not path.is_file() or path.read_bytes() != content:
                raise AssertionError(f"Generated artifact differs: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    report = {"artifacts": "verified" if args.check else "written",
              "collision_curves": tables["Collision"]["CurveCount"], "data_sha256": sha256(data)}
    if args.verify_cpp:
        report.update(cpp_verify(source_dir, tables))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
