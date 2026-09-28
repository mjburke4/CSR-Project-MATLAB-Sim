#!/usr/bin/env python3
"""Offline audit of the unchanged T25 6,000 s five-seed ensemble.

Consumes accepted admitted-application ledgers and independently checks accepted
counts and means. No simulator invocation, model changes, completion imputation,
or equality assumption for same numeric random seeds. Standard library only.
"""
import argparse,csv,hashlib,json,math,statistics
from collections import Counter,defaultdict
from pathlib import Path

SEEDS=range(128,133); SOURCES=[2,3,4,5,7,8]; START=300.; STOP=6000.; DT=.02
ATTEMPTS=285000; HORIZONS=[60,300,600,1200]
def load_csv(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def write_csv(p,rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def fmean(xs):return math.fsum(xs)/len(xs) if xs else None
def pct(m,n):return 100*(m/n-1) if m is not None and n else None
def quantile(xs,p):
    if not xs:return None
    xs=sorted(xs); x=(len(xs)-1)*p;lo=math.floor(x);hi=math.ceil(x)
    return xs[lo]*(hi-x)+xs[hi]*(x-lo) if lo!=hi else xs[lo]
def stat(xs):return {'n':len(xs),'mean':fmean(xs),'p50':quantile(xs,.5),'p95':quantile(xs,.95),'max':max(xs) if xs else None}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--workspace',type=Path,default=Path.cwd());ap.add_argument('--out',type=Path);args=ap.parse_args();w=args.workspace.resolve();out=args.out or w/'longrun_review/ensemble';out.mkdir(parents=True,exist_ok=True)
    src=w/'longrun_recovery/extracted/latency-review/latency-review'; ref=w/'longrun_recovery/extracted/t25review/analysis/per-seed-comparisons.csv'
    inputs=[ref];records={};groups={};mapping=[];accounting=[];checks=[]
    for engine in ['matlab','native']:
        for seed in SEEDS:
            fp=src/(f'matlab/packets-{seed}.csv' if engine=='matlab' else f'native/output/s{seed}-packets.csv');inputs.append(fp);rr=[];seen=set();maxerr=0.
            for old in load_csv(fp):
                t=float(old['generated_s' if engine=='matlab' else 'send_time_s']); k=round((t-START)/DT);err=abs(t-(START+k*DT));maxerr=max(maxerr,err)
                source=int(old['source']);key=(source,k);assert key not in seen;seen.add(key);assert 0<=k<ATTEMPTS and err<1e-8
                delivered=old['outcome']=='delivered' if engine=='matlab' else old['delivered']=='True'
                outcome=old['outcome'] if engine=='matlab' else ('delivered' if delivered else 'unresolved')
                lat=float(old['delivered_delay_s' if engine=='matlab' else 'latency_s']) if delivered else None
                r={'engine':engine,'seed':seed,'source':source,'id':int(old['packet_id' if engine=='matlab' else 'sequence']),'attempt_index':k,'generated_s':t,'outcome':outcome,'latency_s':lat,'age_at_stop_s':STOP-t,'nwk_wait_s':float(old['nwk_admission_wait_s' if engine=='matlab' else 'nwk_wait_s']) if delivered else None,'post_admission_s':float(old['post_admission_to_causal_receipt_s' if engine=='matlab' else 'post_admission_s']) if delivered else None,'last_custody_node':int(old['last_custody_node']) if engine=='matlab' else None,'drop_reason':old.get('drop_reason','')}
                if delivered:
                    assert lat>=0 and t+lat<=STOP+1e-8
                    assert math.isclose(r['nwk_wait_s']+r['post_admission_s'],lat,abs_tol=1e-8)
                rr.append(r)
            records[engine,seed]=rr;mapping.append({'engine':engine,'seed':seed,'admitted_count':len(rr),'unique_source_attempt_keys':len(seen),'max_grid_residual_s':maxerr})
            for source in SOURCES:
                group=[r for r in rr if r['source']==source];groups[engine,seed,source]=group;dd=[r for r in group if r['outcome']=='delivered'];cc=Counter(r['outcome'] for r in group)
                accounting.append({'engine':engine,'seed':seed,'source':source,'scheduled_attempts':ATTEMPTS,'attempt_count_basis':'archived_direct_counters' if seed>=131 else 'fixed_scenario_schedule_300_to_6000_half_open_20_ms','admitted':len(group),'not_admitted':ATTEMPTS-len(group),'delivered':len(dd),'known_terminal_dropped':cc['dropped'] if engine=='matlab' else None,'known_pending':cc['pending'] if engine=='matlab' else None,'unresolved_fate':cc['unresolved'] if engine=='native' else 0,'undelivered_total':len(group)-len(dd),'delivery_fraction_of_admitted':len(dd)/len(group) if group else None,'delivery_fraction_of_attempts':len(dd)/ATTEMPTS,'mean_delivered_latency_s':fmean([r['latency_s'] for r in dd]),'p95_delivered_latency_s':quantile([r['latency_s'] for r in dd],.95),'mean_nwk_wait_s':fmean([r['nwk_wait_s'] for r in dd]),'mean_post_admission_s':fmean([r['post_admission_s'] for r in dd])})
    # Compare all saved total and source count/latency checks to accepted T25.
    for rr in load_csv(ref):
        seed=int(rr['seed']);source=int(rr['source']) if rr['source'] else None
        for engine,col in [('matlab','matlab'),('native','ns3')]:
            g=groups[engine,seed,source] if source else records[engine,seed];d=[r for r in g if r['outcome']=='delivered'];metric=rr['metric'];actual=len(g) if metric=='admitted' else (len(d) if metric=='unique_delivered' else fmean([r['latency_s'] for r in d]));expected=float(rr[col]) if rr[col] else None
            ok=(actual is None and expected is None) or (actual is not None and expected is not None and math.isclose(actual,expected,abs_tol=1e-8,rel_tol=1e-12));assert ok,(engine,seed,source,metric,actual,expected);checks.append({'engine':engine,'seed':seed,'source':source,'metric':metric,'actual':actual,'expected':expected,'passed':ok})
    # Direct observed attempt counters for fresh 131/132 runs.
    for engine in ['matlab','native']:
        for seed in [131,132]:
            fp=w/(f'longrun_recovery/extracted/t25/s{seed}/raw/application_admission_statistics.csv' if engine=='matlab' else f'routing_recovery/t25/evidence/tranche-25-ns3-reference/s{seed}/app-admission-diagnostics.csv');inputs.append(fp)
            for rr in load_csv(fp):
                so=int(rr['SourceId' if engine=='matlab' else 'source']);assert int(rr['Attempts' if engine=='matlab' else 'attempts'])==ATTEMPTS;assert int(rr['Admitted' if engine=='matlab' else 'admitted'])==len(groups[engine,seed,so])
    # Headline estimates and alternate standardizations (descriptive only).
    totals={};seedmeans=[]
    for engine in ['matlab','native']:
        allr=sum([records[engine,s] for s in SEEDS],[]);all_d=[r for r in allr if r['outcome']=='delivered'];cc=Counter(r['outcome'] for r in allr)
        totals[engine]={'scheduled_attempts':ATTEMPTS*30,'admitted':len(allr),'not_admitted':ATTEMPTS*30-len(allr),'delivered':len(all_d),'known_terminal_dropped':cc['dropped'] if engine=='matlab' else None,'known_pending':cc['pending'] if engine=='matlab' else None,'unresolved_fate':cc['unresolved'],'undelivered_total':len(allr)-len(all_d),'pooled_delivered_mean_s':fmean([r['latency_s'] for r in all_d]),'equal_seed_mean_s':fmean([fmean([r['latency_s'] for r in records[engine,s] if r['outcome']=='delivered']) for s in SEEDS]),'mean_nwk_wait_s':fmean([r['nwk_wait_s'] for r in all_d]),'mean_post_admission_s':fmean([r['post_admission_s'] for r in all_d])}
    for seed in SEEDS:
        mm=fmean([r['latency_s'] for r in records['matlab',seed] if r['outcome']=='delivered']);nn=fmean([r['latency_s'] for r in records['native',seed] if r['outcome']=='delivered']);seedmeans.append({'seed':seed,'matlab_mean_s':mm,'native_mean_s':nn,'residual_percent':pct(mm,nn)})
    standards=[];decomps=[]
    for scope in ['seed_source','pooled_source']:
        keys=[(s,so) for s in SEEDS for so in SOURCES] if scope=='seed_source' else [(None,so) for so in SOURCES]
        cells={}
        for seed,so in keys:
            for engine in ['matlab','native']:
                g=groups[engine,seed,so] if seed else sum([groups[engine,s,so] for s in SEEDS],[]);d=[r for r in g if r['outcome']=='delivered'];cells[engine,seed,so]={'n':len(d),'mean':fmean([r['latency_s'] for r in d]),'nwk':fmean([r['nwk_wait_s'] for r in d]),'post':fmean([r['post_admission_s'] for r in d])}
        common=[k for k in keys if all(cells[e,*k]['n'] for e in ['matlab','native'])];excluded=[k for k in keys if k not in common];nt={e:sum(cells[e,*k]['n'] for k in common) for e in ['matlab','native']}
        for method in ['native_delivery_weights','pooled_delivery_weights','equal_cell_weights']:
            ww={k:cells['native',*k]['n']/nt['native'] if method=='native_delivery_weights' else ((cells['native',*k]['n']+cells['matlab',*k]['n'])/(nt['native']+nt['matlab']) if method=='pooled_delivery_weights' else 1/len(common)) for k in common}
            mean={e:math.fsum(ww[k]*cells[e,*k]['mean'] for k in common) for e in ['matlab','native']};standards.append({'scope':scope,'weighting':method,'common_cells':len(common),'excluded_cells':json.dumps(excluded),'matlab_standardized_mean_s':mean['matlab'],'native_standardized_mean_s':mean['native'],'difference_s':mean['matlab']-mean['native'],'residual_percent':pct(mean['matlab'],mean['native']),**{e+'_'+part+'_standardized_mean_s':math.fsum(ww[k]*cells[e,*k][part] for k in common) for e in ['matlab','native'] for part in ['nwk','post']}})
        if not excluded:
            for seed,so in common:
                m=cells['matlab',seed,so];n=cells['native',seed,so];wm=m['n']/nt['matlab'];wn=n['n']/nt['native'];decomps.append({'scope':scope,'seed':seed,'source':so,'matlab_n':m['n'],'native_n':n['n'],'matlab_mean_s':m['mean'],'native_mean_s':n['mean'],'mix_contribution_s':(wm-wn)*(m['mean']+n['mean'])/2,'within_contribution_s':(wm+wn)*(m['mean']-n['mean'])/2})
    mmean=totals['matlab']['pooled_delivered_mean_s'];nmean=totals['native']['pooled_delivered_mean_s'];commonkeys=[(s,so) for s in SEEDS for so in SOURCES if groups['native',s,so] and groups['matlab',s,so]]
    assert commonkeys==[(s,so) for s in SEEDS for so in SOURCES if all(any(r['outcome']=='delivered' for r in groups[e,s,so]) for e in ['matlab','native'])]
    unmatched_m=[r for s in SEEDS for r in records['matlab',s] if r['outcome']=='delivered' and (s,r['source']) not in commonkeys];common_m=[r for s in SEEDS for r in records['matlab',s] if r['outcome']=='delivered' and (s,r['source']) in commonkeys];weight=len(unmatched_m)/totals['matlab']['delivered'];unmatched_term=weight*(fmean([r['latency_s'] for r in unmatched_m])-nmean);common_term=(1-weight)*(fmean([r['latency_s'] for r in common_m])-nmean)
    assert math.isclose(unmatched_term+common_term,mmean-nmean,abs_tol=1e-9)
    # Scheduled-time intersection: pair source+zero-based scheduled attempt, NEVER local packet IDs.
    matched=[];match_detail=[]
    for seed in SEEDS:
        md={(r['source'],r['attempt_index']):r for r in records['matlab',seed]};nd={(r['source'],r['attempt_index']):r for r in records['native',seed]}
        for so in [None]+SOURCES:
            kk=[k for k in set(md)&set(nd) if so is None or k[0]==so];dd=[k for k in kk if md[k]['outcome']=='delivered' and nd[k]['outcome']=='delivered'];ml=[md[k]['latency_s'] for k in dd];nl=[nd[k]['latency_s'] for k in dd];gaps=[a-b for a,b in zip(ml,nl)]
            matched.append({'seed':seed,'source':so,'jointly_admitted':len(kk),'jointly_delivered':len(dd),'matlab_delivered_given_joint_admission':sum(md[k]['outcome']=='delivered' for k in kk),'native_delivered_given_joint_admission':sum(nd[k]['outcome']=='delivered' for k in kk),'matlab_mean_jointly_delivered_s':fmean(ml),'native_mean_jointly_delivered_s':fmean(nl),'residual_percent':pct(fmean(ml),fmean(nl)),'mean_paired_absolute_difference_s':fmean([abs(x) for x in gaps]),'matlab_total_admitted':sum(so is None or r['source']==so for r in records['matlab',seed]),'native_total_admitted':sum(so is None or r['source']==so for r in records['native',seed])})
        for k in sorted(set(md)&set(nd)):
            a,b=md[k],nd[k];match_detail.append({'seed':seed,'source':k[0],'attempt_index':k[1],'scheduled_s':START+k[1]*DT,'matlab_id':a['id'],'native_id':b['id'],'matlab_outcome':a['outcome'],'native_outcome':b['outcome'],'matlab_latency_s':a['latency_s'],'native_latency_s':b['latency_s']})
    # Fixed-age delivery with full follow-up: common half-open generation window.
    deadline=[]
    for horizon in HORIZONS:
        maxk=int(round((STOP-horizon-START)/DT))
        for engine in ['matlab','native']:
            for seed in [None]+list(SEEDS):
                for so in [None]+SOURCES:
                    use_seeds=list(SEEDS) if seed is None else [seed];use_sources=SOURCES if so is None else [so]
                    allg=[r for s in use_seeds for r in records[engine,s] if r['source'] in use_sources];g=[r for r in allg if r['attempt_index']<maxk];hits=[r for r in g if r['outcome']=='delivered' and r['latency_s']<=horizon];late=[r for r in g if r['outcome']=='delivered' and r['latency_s']>horizon];c=Counter(r['outcome'] for r in g);attempts=maxk*len(use_seeds)*len(use_sources)
                    assert len(hits)+len(late)+c['dropped']+c['pending']+c['unresolved']==len(g)
                    deadline.append({'horizon_s':horizon,'generation_window_start_s':START,'generation_window_end_exclusive_s':STOP-horizon,'engine':engine,'seed':seed,'source':so,'scheduled_attempts':attempts,'admitted':len(g),'not_admitted':attempts-len(g),'delivered_by_age':len(hits),'delivered_later_by_stop':len(late),'known_terminal_dropped_by_stop':c['dropped'] if engine=='matlab' else None,'known_pending_at_stop':c['pending'] if engine=='matlab' else None,'unresolved_at_stop':c['unresolved'],'deadline_fraction_of_scheduled_attempts':len(hits)/attempts,'deadline_fraction_of_admitted':len(hits)/len(g) if g else None,'late_generation_admissions_excluded':len(allg)-len(g)})
    # Unfinished populations: ages are elapsed exposure, never completed latency.
    unfinished=[];custody=[];pooled=[]
    for engine in ['matlab','native']:
        for seed in [None]+list(SEEDS):
            for so in [None]+SOURCES:
                rr=[r for s in (SEEDS if seed is None else [seed]) for r in records[engine,s] if so is None or r['source']==so]
                for outcome in (['dropped','pending'] if engine=='matlab' else ['unresolved']):
                    g=[r for r in rr if r['outcome']==outcome];ages=[r['age_at_stop_s'] for r in g];ss=stat(ages)
                    unfinished.append({'engine':engine,'seed':seed,'source':so,'outcome':outcome,'n':ss['n'],'age_at_stop_mean_s':ss['mean'],'age_at_stop_p50_s':ss['p50'],'age_at_stop_p95_s':ss['p95'],'age_at_stop_max_s':ss['max'],'count_age_gt_300_s':sum(v>300 for v in ages),'count_age_gt_600_s':sum(v>600 for v in ages),'count_age_gt_1200_s':sum(v>1200 for v in ages),'age_is_completed_latency':False,'age_measures_model_pending_application':engine=='matlab' and outcome=='pending'})
                if engine=='matlab':
                    for node,n in sorted(Counter(r['last_custody_node'] for r in rr if r['outcome']=='pending').items()):custody.append({'seed':seed,'source':so,'last_custody_node':node,'pending_applications':n})
        for so in SOURCES:
            ar=[x for x in accounting if x['engine']==engine and x['source']==so];g=sum([groups[engine,s,so] for s in SEEDS],[]);d=[r for r in g if r['outcome']=='delivered'];pooled.append({'engine':engine,'source':so,'attempted':ATTEMPTS*5,'admitted':sum(x['admitted'] for x in ar),'not_admitted':sum(x['not_admitted'] for x in ar),'delivered':len(d),'known_terminal_dropped':sum(x['known_terminal_dropped'] for x in ar) if engine=='matlab' else None,'known_pending':sum(x['known_pending'] for x in ar) if engine=='matlab' else None,'unresolved_fate':sum(x['unresolved_fate'] for x in ar),'mean_latency_s':fmean([r['latency_s'] for r in d]),'mean_nwk_wait_s':fmean([r['nwk_wait_s'] for r in d]),'mean_post_admission_s':fmean([r['post_admission_s'] for r in d])})
    for fn,rows in [('per_seed_source_accounting.csv',accounting),('pooled_source_accounting.csv',pooled),('accepted_metric_checks.csv',checks),('attempt_grid_validation.csv',mapping),('per_seed_latency.csv',seedmeans),('standardized_latency.csv',standards),('source_mix_decomposition.csv',decomps),('scheduled_attempt_intersection.csv',matched),('jointly_admitted_attempts.csv',match_detail),('fixed_age_delivery.csv',deadline),('unfinished_ages.csv',unfinished),('pending_custodian_counts.csv',custody)]:write_csv(out/fn,rows)
    jointd=[r for r in match_detail if r['matlab_outcome']=='delivered' and r['native_outcome']=='delivered'];jmm=fmean([r['matlab_latency_s'] for r in jointd]);jnn=fmean([r['native_latency_s'] for r in jointd])
    summary={'schema':'csr-original-6000s-ensemble-accounting-v1','new_simulations':0,'production_changes':0,'seeds':list(SEEDS),'duration_s':STOP,'application_start_s':START,'attempt_interval_s':DT,'attempt_schedule_end_exclusive':True,'accepted_metric_checks_passed':len(checks),'ledger_provenance':'Original latency-review admitted ledgers; fresh131/132 separately revalidated against original traces by companion audits. Older128–130 reuse archived audit provenance.','totals':totals,'pooled_residual_percent':pct(mmean,nmean),'equal_seed_mean_residual_percent':pct(totals['matlab']['equal_seed_mean_s'],totals['native']['equal_seed_mean_s']),'unmatched_seed_source_partition':{'unmatched_matlab_delivery_count':len(unmatched_m),'unmatched_native_delivery_count':0,'unmatched_matlab_mean_s':fmean([r['latency_s'] for r in unmatched_m]),'unmatched_term_s':unmatched_term,'common_support_term_s':common_term,'common_support_own_weights_matlab_mean_s':fmean([r['latency_s'] for r in common_m]),'native_mean_s':nmean,'sum_s':unmatched_term+common_term,'causal_attribution':False},'pooled_source_symmetric_partition':{'mix_s':math.fsum(x['mix_contribution_s'] for x in decomps),'within_s':math.fsum(x['within_contribution_s'] for x in decomps)},'scheduled_attempt_sensitivity':{'jointly_admitted':len(match_detail),'jointly_delivered':len(jointd),'jointly_delivered_matlab_mean_s':jmm,'jointly_delivered_native_mean_s':jnn,'residual_percent':pct(jmm,jnn),'jointly_delivered_source_counts':dict(Counter(r['source'] for r in jointd)),'fraction_of_matlab_deliveries':len(jointd)/totals['matlab']['delivered'],'fraction_of_native_deliveries':len(jointd)/totals['native']['delivered'],'max_grid_residual_s':max(x['max_grid_residual_s'] for x in mapping),'is_rng_coupled_pair':False,'interpretation':'Shared source and scheduled interrupt; admission outcomes and stochastic paths remain different. Small, highly selected intersection cannot establish parity.'},'fixed_age_method':'For horizon T use scheduled times in [300,6000-T), count final delivery by generation+T. Every included attempt has full follow-up. Report same numerator over all scheduled attempts and over admitted applications. Nonadmitted attempts did not create retained application objects. No pending age is substituted for completion latency.','native_terminal_fate_limit':'No trace event globally proves terminal application discard. Known terminal drop totals and live pending totals remain unknown; all nondelivered native identities labelled unresolved, including possibly unobserved terminal drops.','interpretation':'All standardized/matched estimates are descriptive sensitivity checks, not parity gates or causal effects. Missing seed131 source means remain undefined.','inputs':[{'path':str(p.relative_to(w)),'sha256':sha(p)} for p in inputs]}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'totals':totals,'checks':len(checks),'standardized':standards,'joint':summary['scheduled_attempt_sensitivity']},indent=2))
if __name__=='__main__':main()
