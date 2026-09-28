#!/usr/bin/env python3
"""Offline independent finite-stop accounting of the returned 6000-second pair.

Reads owner-return final application ledgers and raw admission counters, the
issued kit's pinned ns-3 references, and the preserved historical MATLAB ledger.
Does not simulate or modify inputs. Native unresolved fate remains unknown.
"""
import csv, hashlib, io, json, math, statistics, zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
REC = ROOT / 'recovered' / 'NS3 to MATLAB Network Simulation'
SEEDS = (131, 132)
SOURCES = (2, 3, 4, 5, 7, 8)
NS = 10**9
STOP = 6000 * NS
ATTEMPTS = 285000
TARGET = 15
checks = []
inputs = []

def read_csv(path):
    inputs.append({'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    with path.open(newline='') as f: return list(csv.DictReader(f))

def zip_csv(z, name):
    b = z.read(name)
    inputs.append({'archive': str(Path(z.filename).relative_to(ROOT)), 'member': name, 'sha256': hashlib.sha256(b).hexdigest()})
    return list(csv.DictReader(io.StringIO(b.decode())))

def num(s): return float(s) if s not in ('', None) else math.nan
def avg(v): return statistics.fmean(v) if v else math.nan
def quant(v, p):
    if not v: return math.nan
    v = sorted(v); pos = (len(v)-1)*p; lo = math.floor(pos); hi = math.ceil(pos)
    return v[lo] + (pos-lo)*(v[hi]-v[lo])

def check(label, value, expected, tol=2e-8):
    good = (math.isnan(value) and math.isnan(expected)) or math.isclose(value, expected, rel_tol=1e-11, abs_tol=tol)
    checks.append({'check': label, 'passed': good, 'recomputed': value, 'returned': expected})
    if not good: raise AssertionError(checks[-1])

def transform(rows, model, seed):
    result = []
    for r in rows:
        if model == 'matlab':
            g = round(float(r['GeneratedSeconds'])*NS)
            state = r['Outcome']
            d = round(float(r['ReceivedSeconds'])*NS) if state == 'delivered' else None
            x = {'source': int(r['SourceId']), 'id': int(r['PacketId']), 'state': state, 'generated_ns': g, 'delivered_ns': d,
                 'events': int(state == 'delivered'), 'drop_lower': int(state == 'dropped')}
            if d is not None: check(f'epoch_latency_{seed}_{x["id"]}', (d-g)/NS, float(r['LatencySeconds']), 2e-9)
        else:
            g = int(r['generated_time_ns']); state = r['status']
            state = {'proven_terminal_drop':'dropped', 'unresolved_at_cutoff':'pending' if model == 'old_matlab' else 'unresolved'}.get(state,state)
            x = {'source': int(r['source']), 'id': int(r['app_id'] if model == 'old_matlab' else r['native_app_id']), 'state': state,
                 'generated_ns': g, 'delivered_ns': int(r['first_delivery_time_ns']) if state == 'delivered' else None,
                 'events': int(r['delivery_event_count']), 'drop_lower': int(state == 'dropped') if model == 'old_matlab' else int(r['proven_terminal_drop_count_lower_bound'])}
        assert x['source'] in SOURCES and 300*NS <= g < STOP
        assert (g-300*NS) % 20000000 == 0
        x['latency_s'] = (x['delivered_ns']-g)/NS if x['delivered_ns'] is not None else math.nan
        x['age_s'] = (STOP-g)/NS
        if x['delivered_ns'] is not None: assert g <= x['delivered_ns'] <= STOP
        result.append(x)
    assert len({x['id'] for x in result}) == len(result)
    assert len({(x['source'],x['generated_ns']) for x in result}) == len(result)
    return result

def summarize(rows, model, seed, source):
    p = [r for r in rows if source == 0 or r['source'] == source]
    cnt = Counter(r['state'] for r in p)
    lat = [r['latency_s'] for r in p if r['state']=='delivered']
    ages = [r['age_s'] for r in p if r['state'] in ('pending','unresolved')]
    scheduled = ATTEMPTS*(6 if source==0 else 1)
    a = dict(model=model, seed=seed, source=source, destination=1, attempted=scheduled, admitted=len(p), not_admitted=scheduled-len(p),
         delivered=cnt['delivered'], delivery_events=sum(r['events'] for r in p), duplicate_delivery_events=sum(r['events'] for r in p)-cnt['delivered'],
         known_terminal_dropped=cnt['dropped'] if model!='native' else math.nan,
         known_model_pending=cnt['pending'] if model!='native' else math.nan,
         unresolved_at_cutoff=cnt['pending']+cnt['unresolved'], undelivered_total=len(p)-cnt['delivered'],
         proven_terminal_drop_lower_bound=sum(r['drop_lower'] for r in p), terminal_drop_total_known=int(model!='native'),
         delivery_fraction_of_attempts=cnt['delivered']/scheduled,
         delivery_fraction_of_admitted=cnt['delivered']/len(p) if p else math.nan,
         mean_delivered_latency_s=avg(lat), p50_delivered_latency_s=quant(lat,.5), p95_delivered_latency_s=quant(lat,.95),
         max_delivered_latency_s=max(lat,default=math.nan), mean_unresolved_age_s=avg(ages), p95_unresolved_age_s=quant(ages,.95), max_unresolved_age_s=max(ages,default=math.nan))
    return a

def horizon(rows, model, seed, source, h):
    selected = [x for x in rows if source==0 or x['source']==source]
    p = [x for x in selected if 300*NS <= x['generated_ns'] < STOP-h*NS]
    scheduled = int((6000-h-300)*50)*(6 if source==0 else 1)
    timely = sum(x['delivered_ns'] is not None and x['delivered_ns']-x['generated_ns']<=h*NS for x in p)
    count = Counter(x['state'] for x in p)
    return dict(model=model, seed=seed, source=source, horizon_s=h, generation_start_s=300,generation_end_exclusive_s=6000-h,
                scheduled_attempts=scheduled,admitted=len(p),not_admitted=scheduled-len(p),delivered_by_age=timely,
                delivered_later_by_stop=count['delivered']-timely,
                known_terminal_dropped_by_stop=count['dropped'] if model!='native' else math.nan,
                known_model_pending_at_stop=count['pending'] if model!='native' else math.nan,
                unresolved_at_stop=count['pending']+count['unresolved'],proven_terminal_drop_lower_bound=sum(x['drop_lower'] for x in p),
                fraction_of_scheduled=timely/scheduled,fraction_of_admitted=timely/len(p) if p else math.nan,
                admissions_outside_window=len(selected)-len(p))

def delta(m,n): return 100*(m/n-1) if math.isfinite(m) and math.isfinite(n) and n>0 else math.nan

def compare(a,n):
    out = dict(seed=a['seed'],source=a['source'],matlab_delivered=a['delivered'],native_delivered=n['delivered'],
               matlab_mean_delivered_latency_s=a['mean_delivered_latency_s'], native_mean_delivered_latency_s=n['mean_delivered_latency_s'])
    for k,field in [('delivered','delivered'),('latency','mean_delivered_latency_s')]:
        diff=delta(a[field],n[field]); defined=math.isfinite(diff)
        out[k+'_signed_relative_percent']=diff; out[k+'_absolute_relative_percent']=abs(diff)
        out[k+'_relative_defined']=int(defined);out[k+'_target_pass']=int(abs(diff)<=TARGET) if defined else math.nan
    return out

def clean(v):
    if isinstance(v,float) and not math.isfinite(v): return None
    if isinstance(v,dict): return {k:clean(x) for k,x in v.items()}
    if isinstance(v,list): return [clean(x) for x in v]
    return v

def write_csv(name,rows):
    with (OUT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    populations={};accounting=[];fixed=[];comparisons=[];oldcomparisons=[];summaries={}
    with zipfile.ZipFile(REC/'csr-6000-batch.zip') as kit, zipfile.ZipFile(REC/'csr-6000s-accounting-evidence.zip') as old:
        oldrows=zip_csv(old,'longrun_review/matlab/applications.csv')
        for seed in SEEDS:
            case=ROOT/'data'/f's{seed}'/'attempt_001'
            populations['matlab',seed]=transform(read_csv(case/'analysis/applications.csv'),'matlab',seed)
            populations['native',seed]=transform(zip_csv(kit,f'csr6000/reference/s{seed}/applications.csv'),'native',seed)
            populations['old_matlab',seed]=transform([r for r in oldrows if int(r['seed'])==seed],'old_matlab',seed)
            counters={
                'matlab':{int(r['SourceId']):r for r in read_csv(case/'raw/application_admission_statistics.csv')},
                'native':{int(r['source']):r for r in zip_csv(kit,f'csr6000/reference/s{seed}/app-admission-diagnostics.csv')}}
            returned={ (r['model'],int(r['source'])):r for r in read_csv(case/'analysis/source_accounting.csv') }
            rh={ (r['model'],int(r['source']),int(r['horizon_s'])):r for r in read_csv(case/'analysis/fixed_age_delivery.csv') }
            rc={int(r['source']):r for r in read_csv(case/'analysis/source_target_comparison.csv')}
            sums={}
            for model in ['matlab','native','old_matlab']:
                for source in (0,)+SOURCES:
                    a=summarize(populations[model,seed],model,seed,source);sums[model,source]=a;accounting.append(a)
                    if model!='old_matlab' and source:
                        c=counters[model][source]
                        if model=='matlab':
                            attempted=int(c['Attempts']); admitted=int(c['Admitted'])
                            blocked=sum(int(c['Blocked'+s]) for s in ['Discovery','Topology','GatewayRoute','Destination','Nsdp'])
                        else:
                            attempted=int(c['attempts']); admitted=int(c['admitted'])
                            blocked=sum(int(c['blocked_'+s]) for s in ['discovery','topology','gateway_route','destination','nsdp'])
                        check(f'{seed}_{model}_{source}_raw_attempts',a['attempted'],attempted,0)
                        check(f'{seed}_{model}_{source}_raw_admitted',a['admitted'],admitted,0)
                        check(f'{seed}_{model}_{source}_raw_blocked',a['not_admitted'],blocked,0)
                        for k,v in a.items():
                            if k!='model':check(f'{seed}_{model}_{source}_account_{k}',v,num(returned[model,source][k]))
                    for h in [60,300,600,1200]:
                        x=horizon(populations[model,seed],model,seed,source,h);fixed.append(x)
                        if model!='old_matlab':
                            for k,v in x.items():
                                if k!='model':check(f'{seed}_{model}_{source}_{h}_deadline_{k}',v,num(rh[model,source,h][k]))
            for source in SOURCES:
                c=compare(sums['matlab',source],sums['native',source]);comparisons.append(c)
                oldcomparisons.append(compare(sums['old_matlab',source],sums['native',source]))
                for k,v in c.items():check(f'{seed}_{source}_comparison_{k}',v,num(rc[source][k]))
            summaries[seed]=sums

    def aggregate(model):
        rows=sum((populations[model,s] for s in SEEDS),[])
        a=summarize(rows,model,0,0)
        a['attempted']*=2;a['not_admitted']=a['attempted']-a['admitted'];a['delivery_fraction_of_attempts']=a['delivered']/a['attempted']
        return a
    totals={m:aggregate(m) for m in ['matlab','native','old_matlab']}
    def commonweight(model,seeds):
        pairs=[(summaries[s][model,k],summaries[s]['native',k]) for s in seeds for k in SOURCES]
        common=[(m,n) for m,n in pairs if m['delivered'] and n['delivered']]
        denom=sum(n['delivered'] for m,n in common)
        mmean=sum(n['delivered']*m['mean_delivered_latency_s'] for m,n in common)/denom
        nmean=sum(n['delivered']*n['mean_delivered_latency_s'] for m,n in common)/denom
        return {'model':model,'seeds':list(seeds),'common_cells':len(common),'native_delivery_weight_total':denom,
                'matlab_weighted_mean_latency_s':mmean,'native_weighted_mean_latency_s':nmean,'signed_relative_percent':delta(mmean,nmean),
                'matlab_excluded_deliveries':sum(m['delivered'] for m,n in pairs if not n['delivered']),
                'native_excluded_deliveries':sum(n['delivered'] for m,n in pairs if not m['delivered'])}
    standard=[commonweight(m,ss) for m in ['matlab','old_matlab'] for ss in [SEEDS,(131,),(132,)]]
    for seed in SEEDS:
        f=ROOT/'data'/f's{seed}'/'attempt_001'/'analysis/comparison_summary.json'
        inputs.append({'path':str(f.relative_to(ROOT)),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
        j=json.loads(f.read_text())
        for model in ['matlab','native']:
            for k,v in summaries[seed][model,0].items():
                if k!='model':check(f'{seed}_{model}_json_total_{k}',v,num(j['totals'][model][k]))
        w=next(x for x in standard if x['model']=='matlab' and x['seeds']==[seed])
        for k in ['matlab_weighted_mean_latency_s','native_weighted_mean_latency_s','signed_relative_percent','matlab_excluded_deliveries','native_excluded_deliveries']:
            check(f'{seed}_json_commonweight_{k}',w[k],num(j['native_delivery_weighted_latency'][k]))
        check(f'{seed}_json_raw_latency',delta(summaries[seed]['matlab',0]['mean_delivered_latency_s'],summaries[seed]['native',0]['mean_delivered_latency_s']),num(j['raw_pooled_latency_comparison']['signed_relative_percent']))
    def gates(cs):
        r={}
        for metric in ['delivered','latency']:
            r[metric]={'evaluated':sum(c[metric+'_relative_defined'] for c in cs),
                       'passed':sum(c[metric+'_target_pass']==1 for c in cs),'failed':sum(c[metric+'_target_pass']==0 for c in cs),
                       'undefined':sum(not c[metric+'_relative_defined'] for c in cs)}
        r['both_metrics_pass']=sum(c['delivered_target_pass']==1 and c['latency_target_pass']==1 for c in cs)
        return r
    change=[]
    for seed in SEEDS:
        for source in (0,)+SOURCES:
            a=summaries[seed]['matlab',source];b=summaries[seed]['old_matlab',source]
            c={'seed':seed,'source':source}
            for k in ['admitted','delivered','known_terminal_dropped','known_model_pending','mean_delivered_latency_s']:
                c['old_'+k]=b[k];c['new_'+k]=a[k];c['change_'+k]=a[k]-b[k]
            change.append(c)
    result={'schema':'independent-return6000-accounting-v1','seeds':list(SEEDS),'target_percent':TARGET,'no_simulation':True,
            'inputs':inputs,'checks':{'passed':len(checks),'failed':0,'scope':'Ledger integrity, raw admission closure, all numeric source accounting/comparison/fixed-age fields'},
            'totals':totals,'raw_latency_signed_relative_percent':delta(totals['matlab']['mean_delivered_latency_s'],totals['native']['mean_delivered_latency_s']),
            'old_raw_latency_signed_relative_percent':delta(totals['old_matlab']['mean_delivered_latency_s'],totals['native']['mean_delivered_latency_s']),
            'delivered_count_signed_relative_percent':delta(totals['matlab']['delivered'],totals['native']['delivered']),
            'gates_current':gates(comparisons),'gates_old':gates(oldcomparisons),'native_common_cell_weighting':standard,
            'limitations':['This is only seeds 131 and 132, not a new five-seed evaluation.',
                           'Native undelivered identities have unresolved fate; terminal losses and live queued counts remain unknown.',
                           'Pending MATLAB outcome is not proof of a live queued copy.',
                           'Admitted latency is conditioned on delivery; excluded outcomes are not assigned latency.',
                           'Common-source weights exclude zero-native sources; weighting does not establish network parity.',
                           'These checks validate returned final ledgers against counters and pinned references; protocol-trace reconstruction is separate.']}
    write_csv('source_accounting.csv',accounting)
    write_csv('fixed_age_delivery.csv',fixed)
    write_csv('source_targets.csv',comparisons)
    write_csv('historical_source_targets.csv',oldcomparisons)
    write_csv('old_new_matlab_changes.csv',change)
    write_csv('checks.csv',checks)
    (OUT/'summary.json').write_text(json.dumps(clean(result),indent=2)+'\n')
    print(json.dumps(clean({k:v for k,v in result.items() if k not in ['inputs','limitations']}),indent=2))

if __name__=='__main__':main()
