#!/usr/bin/env python3
"""Verify T24's accepted input archives and unchanged T23 source bindings."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline-root',type=Path,required=True)
    p.add_argument('--inputs',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    archive_dir=a.inputs/'NS3 to MATLAB Network Simulation'
    expected={'t20.zip':'41ee42fd72d3246b005cffa6eb0731aef1f465ac19747be82feb481571a72861',
              't21review.zip':'4778405d7948a43a2b40ffadbacc2c88e5965b5afce504d60d3b1d2c4cd7c739'}
    archives={}
    for n,h in expected.items():
        f=archive_dir/n
        assert sha(f)==h,n
        archives[n]={'sha256':h,'bytes':f.stat().st_size}
    manifest_path=a.inputs/'t21review/SHA256SUMS.json'
    with zipfile.ZipFile(archive_dir/'t21review.zip') as archive:
        assert manifest_path.read_bytes()==archive.read('SHA256SUMS.json')
    manifest=json.loads(manifest_path.read_text())['files']
    actual={x.relative_to(a.inputs/'t21review').as_posix() for x in (a.inputs/'t21review').rglob('*') if x.is_file()}
    assert actual==set(manifest)|{'SHA256SUMS.json'}
    for rel,binding in manifest.items():
        f=a.inputs/'t21review'/rel
        assert sha(f)==binding['sha256'] and f.stat().st_size==binding['bytes'],rel
    candidate=a.baseline_root/'evidence/tranche-23-candidate.json'
    assert sha(candidate)=='b40afd3755ceb47576ea2c9854b4af15a14cebcf87024331e67bf53e069f0818'
    source=json.loads(candidate.read_text())['SourceFiles']
    for binding in source:
        assert sha(a.baseline_root/binding['path'])==binding['sha256'],binding['path']
    receipts={}
    prior=json.loads((a.inputs/'t21review/matlab/matlab_node8.json').read_text())
    for seed in (129,130):
        receipt=a.inputs/'t20'/f's{seed}'/'receipt.json'
        expected=next(x for x in prior['results'] if x['seed']==seed)['receipt_sha256']
        assert sha(receipt)==expected
        receipts[str(seed)]=expected
        issued={r['path']:r['sha256'] for r in json.loads(receipt.read_text())['identity']['SourceFiles']}
        for name in ('+csr/+nwk/Layer.m','+csr/+hop/Layer.m'):
            assert sha(a.baseline_root/name)==issued[name]
    result={'schema':'csr-tranche24-input-verification-v1','status':'pass',
            'archives':archives,'t21_closed_manifest_members':len(manifest)+1,
            't23_source_bindings_verified_including_candidate':len(source)+1,
            't23_matlab_sources_verified':sum(x['path'].endswith('.m') for x in source),
            'matlab_receipts_match_accepted_T21':receipts,
            'matlab_NWK_HOP_unchanged_since_T20':True,
            'script_sha256':sha(Path(__file__))}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__':main()
