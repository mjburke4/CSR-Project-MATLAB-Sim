#!/usr/bin/env python3
"""Offline file-binding verification, not a substitute for MATLAB execution."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def check(entries,base):
 for r in entries:
  p=(base/r['path']).resolve()
  assert p.is_relative_to(ROOT),r['path']
  assert p.is_file(),r['path']
  assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],r['path']
 return len(entries)

def main():
 counts={}
 for key,name in [('package_files','PACKAGE_FILES.json'),('run_files','RUN_FILES.json')]:
  counts[key]=check(json.loads((ROOT/name).read_text())['files'],ROOT)
 baseline=json.loads((ROOT/'baseline_binding.json').read_text())
 counts['accepted_core_files']=check(baseline['matlab_baseline_files'],ROOT/'core')
 fidelity=json.loads((ROOT/'reference/fidelity.json').read_text())
 assert fidelity['all_passed'] and fidelity['time_tolerance_ns']==0
 assert fidelity['source_capture']['exact_prefix'] and len(fidelity['source_capture']['fields'])==30
 for node in fidelity['nodes']:
  assert node['canonical_tx_exact'] and node['draw_time_range_ordinal_value_exact'] and node['mac_trace_exact_except_global_event_index']
 for name,value in fidelity['input_sha256'].items():
  assert hashlib.sha256((ROOT/'inputs'/name).read_bytes()).hexdigest()==value,name
 for name,value in fidelity['reference_sha256'].items():
  assert hashlib.sha256((ROOT/'reference'/name).read_bytes()).hexdigest()==value,name
 rules=json.loads((ROOT/'diagnostics/rules/native_summary.json').read_text())
 assert rules['fixture_pass'] and not rules['unexpected_results']
 counts['native_tx_rows']=sum(n['full_warmup_tx'] for n in fidelity['nodes'])
 counts['native_mac_trace_rows']=sum(n['mac_trace_rows'] for n in fidelity['nodes'])
 counts['native_rule_cases']=rules['cases']
 print(json.dumps({'verified':True,**counts,'matlab_executed':False},indent=2))
if __name__=='__main__':main()
