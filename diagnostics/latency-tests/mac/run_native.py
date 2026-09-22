#!/usr/bin/env python3
"""Build and execute controlled MAC fixtures against pinned source and verified installed headers."""
import argparse,csv,json,subprocess
from pathlib import Path
import native_build_support as B
from compare_mac import read,validate

def exact_events(out,cases):
    sampled=read(out/'sampled.csv'); rows=[]
    for c in cases:
        name=c['case_id'];rr=[r for r in sampled if r['case_id']==name]
        trace=[r for r in read(out/(name+'-trace.csv')) if r['event']=='tx_start' and r['node']=='2']
        if len(trace)!=len(rr):raise ValueError('Sampled/native TX count mismatch: '+name)
        data_bytes=int(c['payload_bytes'])+32
        for observed,tx in zip(rr,trace):
            # Derive membership independently from actual native TX wire bytes.
            size=int(tx['size_bytes']); membership={41:(1,0),data_bytes:(0,1),data_bytes+41:(1,1)}
            if size not in membership:raise ValueError('Unexpected transmitted wire size')
            ack,data=membership[size]
            if (ack,data)!=(int(observed['ack_segments']),int(observed['data_segments'])) or int(tx['rate_kbps'])!=int(observed['rate_kbps']):
                raise ValueError('Native trace contradicts inferred membership/rate')
            row=dict(observed);row['tx_time_s']=tx['time_s'];rows.append(row)
    checks=validate(rows,cases)
    with (out/'events.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    return checks

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ns3-source',required=True,type=Path);p.add_argument('--ns3-build',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--compiler',default='g++');a=p.parse_args()
    source=a.ns3_source.resolve();build=a.ns3_build.resolve();out=a.output.resolve();here=Path(__file__).resolve().parent
    B.check_source(source,build);out.mkdir(parents=True,exist_ok=False)
    before=B.input_snapshot(source,build);state={'status':'running','source_commit':B.PIN,'native_executed':False,'matlab_executed':False,'engine_rebuilt':False,'source_inputs':before}
    try:
        binary=out/'mac-tests';cmd=B.compile_runner(source,build,binary,a.compiler)
        cmd[cmd.index(str(source/'csr-opnet-scenario-runner.cc'))]=str(here/'mac_tests.cc');state['compile_command']=cmd
        with (out/'compile.log').open('w') as f:subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
        state['binary_sha256']=B.digest(binary)
        with (out/'run.log').open('w') as f:
            state['native_executed']=True
            subprocess.run([str(binary),str(here/'cases.csv'),str(out)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
        state['checks']=exact_events(out,read(here/'cases.csv'));state['structural_passed']=all(c['passed'] for c in state['checks'])
        B.check_source(source,build)
        if before!=B.input_snapshot(source,build):raise ValueError('Native source/build changed during run')
        state['status']='completed';state['source_stable']=True
    except Exception as e:state['status']='failed';state['error']=str(e);raise
    finally:
        state['fixture_inputs']={p.name:B.digest(p) for p in here.iterdir() if p.is_file() and p.suffix in ('.py','.cc','.csv')}
        (out/'metadata.json').write_text(json.dumps(state,indent=2)+'\n')
    if not state['structural_passed']:raise SystemExit(1)
if __name__=='__main__':main()
