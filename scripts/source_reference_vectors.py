#!/usr/bin/env python3
"""Compile the unchanged CSR C++ BER implementation and record its answers.

This is actual execution of the original table source, without an ns-3 engine.
It does not execute the ns-3 receive pipeline or MATLAB, and contains no BER
reimplementation. The output is consumed by MATLAB differential unit tests.
"""

import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


PINNED_COMMIT = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"
INPUTS = [
    "model/csr-opnet-ber-tables.cc",
    "model/csr-opnet-ber-tables.h",
    "model/csr-opnet-ber-tables-data.inc",
]

PROBE = r'''#include "csr-opnet-ber-tables.h"
#include <iomanip>
#include <iostream>
using B = ns3::CsrOpnetBerTables;
int main() {
  std::cout << std::setprecision(17) << "{";
  const double snrs[] = {-100,-20,-19.95,-10,0,5,10,11.7,11.8,16.25,20,100};
  const char* curves[] = {"standard", "dpsk", "dqpsk"};
  for (int c=0;c<3;c++) {
    if(c) std::cout << ",";
    std::cout << "\"" << curves[c] << "\":[";
    int n=0;
    for(double s:snrs) {
      if(n++) std::cout << ",";
      double p=c==0?B::GetStandardBer(s):(c==1?B::GetDpskBer(s):B::GetDqpskBer(s));
      std::cout << "{\"snr_db\":" << s << ",\"ber\":" << p << "}";
    }
    std::cout << "]";
  }
  std::cout << ",\"collision\":[";
  int n=0;
  for(int rate:{8,16,32,64,128})
    for(double jsr:{-12.,-9.,-6.,-3.,0.})
      for(double fraction:{0.,0.125,0.5,0.999})
        for(double snr:{-100.,3.9794,100.}) {
          if(n++) std::cout << ",";
          double offset=fraction*B::SymbolDurationSeconds(rate);
          std::cout << "{\"rate_kbps\":" << rate << ",\"jsr_db\":" << jsr
            << ",\"offset_seconds\":" << offset << ",\"snr_db\":" << snr
            << ",\"ber\":" << B::GetCollisionBer(rate,jsr,offset,snr) << "}";
        }
  std::cout << "],\"jsr_quantization\":["; n=0;
  for(double jsr:{-100.,-10.500001,-10.5,-10.499999,-7.5,-7.499999,
                  -4.5,-4.499999,-1.5,-1.499999,0.,100.}) {
    if(n++) std::cout << ",";
    std::cout << "{\"jsr_db\":" << jsr << ",\"bucket_db\":" << B::QuantizeJsrDb(jsr) << "}";
  }
  std::cout << "],\"offset_quantization\":["; n=0;
  for(int rate:{8,16,32,64,128})
    for(double offset:{-0.5001e-6,-0.5e-6,0.,0.5e-6,0.5001e-6,1e-6,15e-6,30e-6,509.5001e-6}) {
      if(n++) std::cout << ",";
      std::cout << "{\"rate_kbps\":" << rate << ",\"offset_seconds\":" << offset
        << ",\"chip_offset\":" << B::QuantizeChipOffset(rate,offset) << "}";
    }
  std::cout << "],\"symbol_duration\":["; n=0;
  for(int rate:{8,16,32,64,128,500,1000}) {
    if(n++) std::cout << ",";
    std::cout << "{\"rate_kbps\":" << rate << ",\"seconds\":" << B::SymbolDurationSeconds(rate) << "}";
  }
  std::cout << "]}\n";
}
'''


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Clean CSR ns-3 module checkout")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1]
                        / "evidence/tranche-1-ns3-reference.json")
    parser.add_argument("--compiler", default="g++")
    args = parser.parse_args()
    source = args.source.resolve()
    commit = run(["git", "-C", str(source), "rev-parse", "HEAD"]).stdout.strip()
    if commit != PINNED_COMMIT:
        raise SystemExit(f"Expected source {PINNED_COMMIT}; found {commit}")
    run(["git", "-C", str(source), "diff", "--quiet", "HEAD", "--", *INPUTS])
    compiler = shutil.which(args.compiler)
    if not compiler:
        raise SystemExit(f"Compiler not found: {args.compiler}")
    hashes = {name: digest(source / name) for name in INPUTS}
    with tempfile.TemporaryDirectory(prefix="csr-original-ber-") as directory:
        temporary = Path(directory)
        harness = temporary / "probe.cc"
        binary = temporary / "probe"
        harness.write_text(PROBE)
        build = run([compiler, "-std=c++17", "-O2", "-I", str(source / "model"),
                     str(harness), str(source / INPUTS[0]), "-o", str(binary)], timeout=180)
        execution = run([str(binary)], timeout=30)
        vectors = json.loads(execution.stdout)
        for name, expected in hashes.items():
            if digest(source / name) != expected:
                raise SystemExit(f"Source changed during reference execution: {name}")
        output = {
            "schema": "csr-matlab-original-cpp-ber-reference-v1",
            "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source_repository": "https://github.com/mjburke4/CSR-Project-NS3-part2",
            "source_commit": commit,
            "source_sha256": hashes,
            "execution": {
                "scope": "Original unchanged CSR C++ BER table source, compiled standalone",
                "original_cpp_executed": True,
                "ns3_network_simulation_executed": False,
                "matlab_executed": False,
                "compiler": compiler,
                "compiler_version": run([compiler, "--version"]).stdout.splitlines()[0],
                "compiler_sha256": digest(compiler),
                "probe_source_sha256": digest(harness),
                "probe_binary_sha256": digest(binary),
                "generator_sha256": digest(__file__),
                "compile_exit_code": build.returncode,
                "compile_stderr": build.stderr,
                "run_exit_code": execution.returncode,
                "run_stderr": execution.stderr,
                "vector_count": sum(len(values) for values in vectors.values()),
            },
            "vectors": vectors,
            "limitations": [
                "No ns-3 engine, CsrPhyModel, CsrNetDevice, or complete smoke workflow executes in this probe.",
                "This evidence validates table and quantization outputs only; MATLAB comparison remains pending execution.",
                "Shared table provenance does not independently validate historical OPNET numerical accuracy.",
            ],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(f"Recorded {output['execution']['vector_count']} original C++ reference vectors: {args.output}")


if __name__ == "__main__":
    main()
