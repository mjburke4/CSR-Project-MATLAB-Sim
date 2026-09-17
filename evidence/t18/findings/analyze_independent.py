from pathlib import Path
import csv,gzip,json,collections,statistics
BASE=Path('/workspace/scratch/ab77b42f47ca')
OUT=BASE/'t18-return-review/independent-findings'
RET=BASE/'t18-return-review/return/network'
REF=BASE/'csr18/evidence/tranche-18-ns3-reference'

def rows(path):
    with (gzip.open(path,'rt') if str(path).endswith('.gz') else open(path,encoding='utf-8-sig')) as h:
        yield from csv.DictReader(h)

def dist(xs):
    return {'n':len(xs),'mean':statistics.fmean(xs) if xs else None,'median':statistics.median(xs) if xs else None,'max':max(xs) if xs else None}

def main(case):
    duration=900 if case=='p128' else 600
    out={'case':case,'duration':duration}
    for engine in ['matlab','ns3']:
        app=collections.defaultdict(lambda:{'admitted':0,'delivered':0,'dropped':0,'pending':0,'delays':[]})
        admissions={}
        queue={}; qw=collections.defaultdict(list); counts=collections.defaultdict(collections.Counter); link=collections.Counter(); linksource=collections.defaultdict(collections.Counter)
        retries={};retrywaits=[];retrycancel=[];txcounts=collections.Counter()
        if engine=='matlab':
            for r in rows(RET/case/'analysis/applications.csv'):
                src=r['SourceId']; a=app[src];a['admitted']+=1;a[r['Outcome']]+=1
                if r['Outcome']=='delivered':a['delays'].append(float(r['LatencySeconds']))
            for r in rows(RET/case/'raw/application_admission_statistics.csv'):
                admissions[r['SourceId']]={k:int(r[k]) for k in ['Attempts','Admitted','BlockedNsdp']}
            for r in rows(RET/case/'raw/service_trace.csv'):
                if r['FrameKind'] not in ('APP','DATA') or r['PacketIdAvailable']!='1':continue
                node,peer,src,pid,event=r['NodeId'],r['PeerId'],r['ApplicationSourceId'],r['PacketId'],r['Event'];t=float(r['TimeSeconds'])
                if src=='NaN':continue
                if node=='5':
                    counts[src][event]+=1
                    if event=='network_enqueue':
                        assert pid not in queue
                        queue[pid]=(src,t)
                    elif event=='network_submit' and pid in queue:
                        ss,st=queue.pop(pid);assert ss==src;qw[src].append(t-st)
                    elif event=='network_custody_release':queue.pop(pid,None)
                if (node,peer)==('4','5'):
                    link[event]+=1;linksource[src][event]+=1
                    if event=='hop_retry':
                        assert pid not in retries
                        retries[pid]=(src,t)
                    elif event=='hop_sent':
                        txcounts[pid]+=1
                        if pid in retries:
                            ss,st=retries.pop(pid);retrywaits.append(t-st)
                    elif event in ('hop_ack','hop_dack','hop_failed') and pid in retries:
                        ss,st=retries.pop(pid);retrycancel.append(t-st)
        else:
            sends={};received=set()
            for r in rows(REF/case/'app-admission-diagnostics.csv'):
                admissions[r['source']]={k:int(r[v]) for k,v in [('Attempts','attempts'),('Admitted','admitted'),('BlockedNsdp','blocked_nsdp')]}
            for r in rows(REF/case/'ns3-service.csv.gz'):
                node,peer,src,pid,event=r['node'],r['peer'],r['src'],(r['src'],r['dst'],r['sequence']),r['event'];t=float(r['time_s'])
                if r['packet_type']!='data':continue
                if event=='app_send':
                    assert pid not in sends
                    sends[pid]=t;app[src]['admitted']+=1
                elif event=='nwk_delivery':
                    assert pid in sends
                    if pid not in received:
                        app[src]['delivered']+=1;app[src]['delays'].append(t-sends[pid]);received.add(pid)
                if node=='5':
                    counts[src][event]+=1
                    if event=='nwk_enqueue':
                        assert pid not in queue
                        queue[pid]=(src,t)
                    elif event=='nwk_forward' and pid in queue:
                        ss,st=queue.pop(pid);assert ss==src;qw[src].append(t-st)
                if (node,peer)==('4','5'):
                    if event=='hop_completion':event+=':'+r['reason']
                    link[event]+=1;linksource[src][event]+=1
            for src,a in app.items():
                a['unmatched_sends']=a['admitted']-a['delivered'];a.pop('dropped');a.pop('pending')
        for src,a in app.items():
            a['latency_s']=dist(a.pop('delays'));a['admission']=admissions[src]
        pendingq=collections.defaultdict(list)
        for src,t in queue.values():pendingq[src].append(duration-t)
        out[engine]={'applications':dict(app),'node5_events':dict(counts),'node5_enqueue_to_submit_s':{src:dist(v) for src,v in qw.items()},'node5_unsubmitted_at_stop_ages':{src:dist(v) for src,v in pendingq.items()},'link45_events':dict(link),'link45_by_source':dict(linksource)}
        if engine=='matlab':out[engine].update(link45_retry_wait_s=dist(retrywaits),link45_retry_cancel_wait_s=dist(retrycancel),link45_pending_retry_wait_s=dist([duration-t for src,t in retries.values()]),link45_actual_repeat_transmissions=sum(max(0,n-1) for n in txcounts.values()))
    return out

if __name__=='__main__':
    results=[]
    for case in ['r128','l128','m128','r129','l129','m129','r130','l130','m130','p128']:
        r=main(case);results.append(r)
        print(case,{e:{s:(a['admitted'],a['delivered']) for s,a in r[e]['applications'].items()} for e in ['matlab','ns3']},flush=True)
    (OUT/'independent_metrics.json').write_text(json.dumps(results,indent=2)+'\n')
    flat=[]
    for r in results:
        for e in ['matlab','ns3']:
            for src,a in r[e]['applications'].items():
                flat.append({'case':r['case'],'engine':e,'source':src,'admitted':a['admitted'],'delivered':a['delivered'],'conditional_delivery':a['delivered']/a['admitted'] if a['admitted'] else None,'unmatched':a['admitted']-a['delivered'],'mean_delay_s':a['latency_s']['mean'],'dropped':a.get('dropped'),'pending':a.get('pending')})
    with (OUT/'flow_comparison.csv').open('w') as h:
        w=csv.DictWriter(h,list(flat[0]));w.writeheader();w.writerows(flat)
