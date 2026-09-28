#!/usr/bin/env python3
"""Offline seed131 causal analysis using previously audited parser unchanged."""
import ast, csv, hashlib, json, statistics
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
HISTORY = ROOT/'history/longrun_recovery/extracted/latency-review/latency-review'
PARSER = HISTORY/'matlab/analyze_matlab_latency.py'
ARCHIVE = ROOT.parent/'upload/out_6000_20260924_152302.zip'

def table(p):
    with p.open(newline='') as f: return list(csv.DictReader(f))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def ns(s): return int((Decimal(str(s))*10**9).to_integral_value(rounding=ROUND_HALF_EVEN))
def writecsv(p, rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def main():
    tree=ast.parse(PARSER.read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='analyze')
    idx=next(i for i,n in enumerate(fn.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='source_files' for t in n.targets))
    fn.body=fn.body[:idx]+[ast.Return(value=ast.Name(id='cases',ctx=ast.Load()))]
    tree.body=[n for n in tree.body if not isinstance(n,ast.If)]
    ast.fix_missing_locations(tree)
    namespace={'__file__':str(PARSER),'__name__':'audited_parser'}
    exec(compile(tree,str(PARSER),'exec'),namespace)
    namespace['CASES']=[(131,'s131/attempt_001',str(ARCHIVE))]
    cases=namespace['analyze'](ROOT,OUT)
    c=cases[0]
    assert not c['decomposition_failures']
    apps=table(ROOT/'data/s131/attempt_001/analysis/applications.csv')
    hops=table(OUT/'causal-hops-131.csv')
    hp=defaultdict(list)
    for h in hops: hp[h['packet_id']].append(h)
    closure=[]
    for a in apps:
        if a['Outcome']!='delivered': continue
        path=hp[a['PacketId']]
        bounds=[(ns(h['arrival_s']),ns(h['hop_admit_s']),ns(h['causal_receipt_s'])) for h in path]
        previous=ns(a['GeneratedSeconds'])
        for arrive,admit,receipt in bounds:
            assert arrive==previous and arrive<=admit<=receipt
            previous=receipt
        assert previous==ns(a['ReceivedSeconds'])
        closure.append(sum(b-a+c-b for a,b,c in bounds)-(ns(a['ReceivedSeconds'])-ns(a['GeneratedSeconds'])))
    assert not any(closure)
    old=json.loads((HISTORY/'matlab/seed-131.json').read_text())
    native=table(ROOT/'history/longrun_review/native_s131/applications.csv')
    native_hops=table(ROOT/'history/longrun_review/native_s131/causal_hops.csv')
    sources=[]; nodes=[]
    for current in c['flows']:
        src=current['source']; prior=next(f for f in old['flows'] if f['source']==src)
        np=[r for r in native if int(r['source'])==src]; nd=[r for r in np if r['status']=='delivered']
        row={'source':src}
        for label,f in [('current_matlab',current),('old_matlab',prior)]:
            for k in ['admitted','delivered','dropped','pending']: row[label+'_'+k]=f[k]
            row[label+'_mean_latency_s']=f['delay']['mean']
            row[label+'_mean_nwk_wait_s']=f['components']['nwk_admission_wait_s']['mean']
            row[label+'_mean_post_hop_s']=f['components']['post_admission_to_causal_receipt_s']['mean']
            for node in f['node_residence']:
                nodes.append(dict(model=label,source=src,node=node['node'],delivered_hops=node['hop_rows'],mean_nwk_wait_s=node['components']['nwk_admission_wait_s']['mean'],mean_post_hop_s=node['components']['post_admission_to_causal_receipt_s']['mean'],mean_arrival_queue_depth=node['mean_network_queue_depth_at_arrival']))
        row.update(native_admitted=len(np),native_delivered=len(nd),native_undelivered_unresolved=len(np)-len(nd),native_mean_latency_s=statistics.mean(int(r['latency_ns'])/1e9 for r in nd) if nd else None,native_mean_nwk_wait_s=statistics.mean((int(r['source_nwk_wait_ns'])+int(r['relay_nwk_wait_ns']))/1e9 for r in nd) if nd else None,native_mean_post_hop_s=statistics.mean(int(r['post_admission_ns'])/1e9 for r in nd) if nd else None)
        sources.append(row)
        bynode=defaultdict(list)
        for h in native_hops:
            if int(h['source'])==src: bynode[h['node']].append(h)
        for node,rows in bynode.items():
            nodes.append(dict(model='native',source=src,node=int(node),delivered_hops=len(rows),mean_nwk_wait_s=statistics.mean(int(h['nwk_wait_ns'])/1e9 for h in rows),mean_post_hop_s=statistics.mean(int(h['post_admission_ns'])/1e9 for h in rows),mean_arrival_queue_depth=None))
    writecsv(OUT/'source_phase_comparison.csv',sources)
    writecsv(OUT/'node_phase_comparison.csv',nodes)
    discovery=[]; control_counts=Counter(); first_gen={}
    with (ROOT/'data/s131/attempt_001/raw/protocol_trace.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            if r['Event']=='discovery_finished' or (float(r['TimeSeconds'])<200 and r['Event'] in ['neighbor_active','neighbor_control_send']): discovery.append(r)
            if r['Event']=='neighbor_control_send': control_counts[r['ControlType']]+=1
            if r['Event']=='app_generate': first_gen.setdefault(r['NodeId'],r['TimeSeconds'])
    writecsv(OUT/'discovery_events.csv',discovery)
    result=dict(parser_sha256=sha(PARSER),input_archive_sha256=sha(ARCHIVE),delivered=len(closure),causal_hops=len(hops),exact_nanosecond_closure=True,max_closure_error_ns=max(closure),raw_protocol_sha256=c['protocol_sha256'],raw_protocol_rows=c['protocol_rows'],outcomes=c['outcomes'],discovery_finished=[r for r in discovery if r['Event']=='discovery_finished'],first_generation_by_source=first_gen,neighbor_control_send_counts=dict(control_counts),sources=sources,node_phases=nodes,parser_adaptation='Only CASES points to returned archive and final all-case source-binding report omitted; causal matching unchanged.',semantics='Winning delivered path only. Custody arrival to HOP admission is NWK waiting; HOP admission through downstream accepted custody is post-admission service. Upstream ACK custody after receipt excluded. Unfinished ages never counted as latency.')
    denominator=sum(r['native_delivered'] for r in sources)
    result['native_delivery_weighted_common_sources']={label:{k:sum(r['native_delivered']*r[label+'_mean_'+k+'_s'] for r in sources if r['native_delivered'])/denominator for k in ['latency','nwk_wait','post_hop']} for label in ['current_matlab','old_matlab','native']}
    result['winning_delivered_node_load']=[dict(model=model,node=node,source_counts={str(r['source']):r['delivered_hops'] for r in nodes if r['model']==model and r['node']==node},total_delivered_hops=sum(r['delivered_hops'] for r in nodes if r['model']==model and r['node']==node)) for model in ['current_matlab','old_matlab','native'] for node in [4,5]]
    stats=json.loads((ROOT/'data/s131/attempt_001/raw/summary.json').read_text())['Statistics']
    assert stats['OmittedTraceRecords']==0 and stats['OmittedPhyTraceRecords']==0
    assert len(apps)==stats['Generated']==c['event_counts']['app_generate']
    assert c['outcomes']['delivered']==stats['Received']==c['event_counts']['app_receive']
    assert c['outcomes']['dropped']==stats['Dropped']==c['event_counts']['app_drop']
    assert c['outcomes']['pending']==stats['Pending']
    result['raw_counter_closure']=True
    result['omitted_protocol_rows']=stats['OmittedTraceRecords']
    result['omitted_phy_rows']=stats['OmittedPhyTraceRecords']
    result['omitted_admission_attempt_rows']=stats['OmittedApplicationAdmissionRecords']
    (OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(sources,indent=2))

if __name__=='__main__': main()
