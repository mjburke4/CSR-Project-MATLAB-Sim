#!/usr/bin/env python3
"""Offline population reconciliation; does not execute or modify a simulator."""
import argparse,csv,hashlib,json,math,statistics
from collections import defaultdict,Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--input',type=Path,default=HERE/'inputs'/'latency-review',help='Path containing matlab/ and native/output/ packet evidence.')
ap.add_argument('--output',type=Path,default=HERE/'output')
ap.add_argument('--admission-evidence',type=Path,default=HERE/'admission_evidence.json')
args=ap.parse_args()
BASE=args.input;OUT=args.output;OUT.mkdir(parents=True,exist_ok=True)
ADME=json.loads(args.admission_evidence.read_text()) if args.admission_evidence.exists() else None
SEEDS=range(128,133); SOURCES=[2,3,4,5,7,8]; STOP=6000.
P={}; hashes=[]; griderrs={}; alias={'m':'MATLAB','n':'ns-3'}
def mean(xs):return statistics.mean(xs) if xs else None
def pct(m,n):return 100*(m/n-1) if m is not None and n not in (0,None) else None
def wr(name,rows):
 if rows:
  with (OUT/name).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def quantile(xs,p):
 xs=sorted(xs)
 if not xs:return None
 i=(len(xs)-1)*p;j=int(i);return xs[j]+(xs[min(j+1,len(xs)-1)]-xs[j])*(i-j)
for seed in SEEDS:
 for e in 'mn':
  path=BASE/(f'matlab/packets-{seed}.csv' if e=='m' else f'native/output/s{seed}-packets.csv')
  raw=path.read_bytes();hashes.append({'file':str(path.relative_to(BASE)),'sha256':hashlib.sha256(raw).hexdigest()})
  rows=list(csv.DictReader(raw.decode().splitlines()));pop={};maxerr=0
  for x in rows:
   t=float(x['generated_s' if e=='m' else 'send_time_s']);slot=round((t-300)*50);err=abs(t-(300+slot/50));maxerr=max(maxerr,err)
   assert err<1e-7,(e,seed,t,err)
   delivered=x['outcome']=='delivered' if e=='m' else x['delivered']=='True'
   source=int(x['source']);key=(source,slot)
   assert key not in pop,(seed,e,key)
   pop[key]={'seed':seed,'source':source,'slot':slot,'generated':t,'delivered':delivered,'outcome':x['outcome'] if e=='m' else ('delivered' if delivered else 'undelivered_unsplit'),'delay':float(x['delivered_delay_s' if e=='m' else 'latency_s']) if delivered else None,'nwk':float(x['nwk_admission_wait_s' if e=='m' else 'nwk_wait_s']) if delivered else None,'post':float(x['post_admission_to_causal_receipt_s' if e=='m' else 'post_admission_s']) if delivered else None}
  P[seed,e]=pop;griderrs[f'{seed}/{e}']=maxerr
allp={e:[x for seed in SEEDS for x in P[seed,e].values()] for e in 'mn'}
flows=[]
for seed in SEEDS:
 for s in SOURCES:
  row={'seed':seed,'source':s}
  for e in 'mn':
   ps=[x for x in P[seed,e].values() if x['source']==s];ds=[x for x in ps if x['delivered']];c=Counter(x['outcome'] for x in ps)
   row.update({f'{e}_admitted':len(ps),f'{e}_delivered':len(ds),f'{e}_not_delivered':len(ps)-len(ds),f'{e}_dropped':c['dropped'] if e=='m' else None,f'{e}_pending':c['pending'] if e=='m' else None,f'{e}_delivered_mean_s':mean([x['delay'] for x in ds]),f'{e}_delivered_p95_s':quantile([x['delay'] for x in ds],.95)})
  row['relative_mean_gap_percent']=pct(row['m_delivered_mean_s'],row['n_delivered_mean_s'])
  native_summary=BASE/f'native/output/s{seed}.json'
  native_raw=native_summary.read_bytes()
  if s==SOURCES[0]:hashes.append({'file':str(native_summary.relative_to(BASE)),'sha256':hashlib.sha256(native_raw).hexdigest()})
  summary=json.loads(native_raw)
  rejects=[x for x in summary.get('app_rejection_counts',[]) if int(x['source'])==s]
  if rejects:
   row['n_attempted']=row['n_admitted']+sum(x['count'] for x in rejects)
   row['n_attempts_provenance']='observed: app_send identities plus app_rejection_counts in native/output/s%d.json'%seed
   row['n_blocked_reasons']=json.dumps({x['reason']:x['count'] for x in rejects},sort_keys=True)
  else:
   row['n_attempted']=ADME['schedule']['attempts_per_source_per_seed'] if ADME else None
   row['n_attempts_provenance']='schedule-derived; original extract lacks rejected-attempt events'
   row['n_blocked_reasons']='not observed'
  mo=[x for x in ADME['observed_matlab'] if x['seed']==seed and x['source']==s] if ADME else []
  if mo:
   assert mo[0]['admitted']==row['m_admitted']
   row['m_attempted']=mo[0]['attempts'];row['m_attempts_provenance']='observed: '+mo[0]['member'];row['m_blocked_reasons']=json.dumps(mo[0]['blocked'],sort_keys=True)
  else:
   row['m_attempted']=ADME['schedule']['attempts_per_source_per_seed'] if ADME else None
   row['m_attempts_provenance']='schedule-derived; not recounted from raw attempt statistics'
   row['m_blocked_reasons']='not observed'
  for e in 'mn':
   row[f'{e}_blocked_before_creation']=row[f'{e}_attempted']-row[f'{e}_admitted'] if row[f'{e}_attempted'] is not None else None
  flows.append(row)
wr('source_outcomes.csv',flows)
pooled_ledger=[]
for source in SOURCES:
 rows=[x for x in flows if x['source']==source];row={'source':source}
 for e in 'mn':
  for key in ['attempted','blocked_before_creation','admitted','delivered','not_delivered','dropped','pending']:
   vals=[x[f'{e}_{key}'] for x in rows];row[f'{e}_{key}']=sum(vals) if all(v is not None for v in vals) else None
 pooled_ledger.append(row)
wr('pooled_source_outcomes.csv',pooled_ledger)
common=[];common_rows=[];common_pairs=[];outcome_matrix=Counter()
for seed in SEEDS:
 m,n=P[seed,'m'],P[seed,'n'];both=m.keys()&n.keys()
 for source in SOURCES:
  pairs=[(m[k],n[k]) for k in sorted(both) if k[0]==source];dd=[(a,b) for a,b in pairs if a['delivered'] and b['delivered']]
  c=Counter((a['outcome'],b['outcome']) for a,b in pairs);outcome_matrix.update(c)
  row={'seed':seed,'source':source,'m_admitted':sum(k[0]==source for k in m),'n_admitted':sum(k[0]==source for k in n),'common_admitted':len(pairs),'both_delivered':len(dd),'m_only_delivered':sum(a['delivered'] and not b['delivered'] for a,b in pairs),'n_only_delivered':sum(b['delivered'] and not a['delivered'] for a,b in pairs),'neither_delivered':sum(not a['delivered'] and not b['delivered'] for a,b in pairs),'m_double_delivered_mean_s':mean([a['delay'] for a,b in dd]),'n_double_delivered_mean_s':mean([b['delay'] for a,b in dd]),'common_admitted_first_10s':sum(a['generated']<310 for a,b in pairs),'double_delivered_first_10s':sum(a['generated']<310 for a,b in dd)}
  row['relative_mean_gap_percent']=pct(row['m_double_delivered_mean_s'],row['n_double_delivered_mean_s']);common_rows.append(row);common_pairs.extend(pairs)
  for a,b in pairs:
   common.append({'seed':seed,'source':source,'slot':a['slot'],'generated_s':a['generated'],'m_outcome':a['outcome'],'n_outcome':b['outcome'],'m_delay_s':a['delay'],'n_delay_s':b['delay']})
wr('common_admitted_by_source.csv',common_rows);wr('common_admitted_attempts.csv',common)
dd=[(a,b) for a,b in common_pairs if a['delivered'] and b['delivered']]
match_summary={'common_admitted':len(common_pairs),'both_delivered':len(dd),'m_mean_s':mean([a['delay'] for a,b in dd]),'n_mean_s':mean([b['delay'] for a,b in dd]),'mean_paired_difference_s':mean([a['delay']-b['delay'] for a,b in dd]),'m_common_delivered':sum(a['delivered'] for a,b in common_pairs),'n_common_delivered':sum(b['delivered'] for a,b in common_pairs),'m_common_admitted_fraction':len(common_pairs)/len(allp['m']),'n_common_admitted_fraction':len(common_pairs)/len(allp['n']),'first_10s_pairs':sum(a['generated']<310 for a,b in common_pairs),'first_10s_double_delivered':sum(a['generated']<310 for a,b in dd),'outcome_matrix':[{'m_outcome':a,'n_outcome':b,'n':v} for (a,b),v in sorted(outcome_matrix.items())]}
match_summary['relative_gap_percent']=pct(match_summary['m_mean_s'],match_summary['n_mean_s'])
# Fixed follow-up: all eligible admissions, all terminal losses retained as failures.
fixed=[]
for h in [300,600,1200]:
 for seed in SEEDS:
  for source in SOURCES:
   row={'horizon_s':h,'seed':seed,'source':source,'latest_admission_s':STOP-h}
   for e in 'mn':
    ps=[p for p in P[seed,e].values() if p['source']==source and p['generated']<=STOP-h+1e-8];ds=[p for p in ps if p['delivered'] and p['delay']<=h+1e-8]
    row.update({f'{e}_eligible_admitted':len(ps),f'{e}_delivered_within_h':len(ds),f'{e}_prob_delivery_within_h_given_admitted':len(ds)/len(ps) if ps else None,f'{e}_successful_mean_s':mean([x['delay'] for x in ds])})
   pp=[(a,b) for a,b in common_pairs if a['seed']==seed and a['source']==source and a['generated']<=STOP-h+1e-8]
   row['common_eligible_admitted']=len(pp)
   for e,idx in [('m',0),('n',1)]:
    ds=[x[idx] for x in pp if x[idx]['delivered'] and x[idx]['delay']<=h+1e-8]
    row[f'{e}_common_delivered_within_h']=len(ds)
    row[f'{e}_common_prob_delivery_within_h']=len(ds)/len(pp) if pp else None
   fixed.append(row)
wr('fixed_followup_by_source.csv',fixed)
fixed_summary=[]
for h in [300,600,1200]:
 rows=[x for x in fixed if x['horizon_s']==h]; common_support=[x for x in rows if x['m_eligible_admitted'] and x['n_eligible_admitted']]
 ss={'horizon_s':h,'common_seed_source_cells':len(common_support)}
 for e in 'mn':
  n=sum(x[f'{e}_eligible_admitted'] for x in rows);d=sum(x[f'{e}_delivered_within_h'] for x in rows)
  cn=sum(x['common_eligible_admitted'] for x in rows);cd=sum(x[f'{e}_common_delivered_within_h'] for x in rows)
  ss.update({f'{e}_eligible_admitted':n,f'{e}_delivered_within_h':d,f'{e}_prob_delivery_within_h':d/n,f'{e}_common_admitted':cn,f'{e}_common_delivered_within_h':cd,f'{e}_common_prob_delivery_within_h':cd/cn,f'{e}_equal_common_cell_probability':mean([x[f'{e}_prob_delivery_within_h_given_admitted'] for x in common_support])})
 fixed_summary.append(ss)
wr('fixed_followup_summary.csv',fixed_summary)
# Delivered-population standardization. Identical average delivery-share weights, restricted to strata with delivered observations in both engines.
def standardize(label,keyfn):
 cells={}
 for e in 'mn':
  ce=defaultdict(list)
  for x in allp[e]:
   if x['delivered']:ce[keyfn(x)].append(x)
  cells[e]=ce
 keys=cells['m'].keys()&cells['n'].keys();nn={e:sum(len(cells[e][k]) for k in keys) for e in 'mn'}
 weighted={e:0. for e in 'mn'};within_nwk=within_post=0;details=[]
 for k in sorted(keys):
  ns={e:len(cells[e][k]) for e in 'mn'};w=.5*(ns['m']/nn['m']+ns['n']/nn['n']);mus={e:mean([x['delay'] for x in cells[e][k]]) for e in 'mn'}
  for e in 'mn':weighted[e]+=w*mus[e]
  dq=mean([x['nwk'] for x in cells['m'][k]])-mean([x['nwk'] for x in cells['n'][k]]);dp=mean([x['post'] for x in cells['m'][k]])-mean([x['post'] for x in cells['n'][k]])
  within_nwk+=w*dq;within_post+=w*dp
  details.append({'stratum':str(k),'m_n':ns['m'],'n_n':ns['n'],'common_weight':w,'m_mean':mus['m'],'n_mean':mus['n'],'mean_gap':mus['m']-mus['n'],'weighted_gap':w*(mus['m']-mus['n'])})
 wr(f'standardized_{label}_cells.csv',details)
 return {'stratification':label,'common_cells':len(keys),'m_delivered_included':nn['m'],'n_delivered_included':nn['n'],'m_mean_s':weighted['m'],'n_mean_s':weighted['n'],'gap_s':weighted['m']-weighted['n'],'relative_gap_percent':pct(weighted['m'],weighted['n']),'weighted_nwk_gap_s':within_nwk,'weighted_post_gap_s':within_post,'excluded_m_delivered':sum(x['delivered'] for x in allp['m'])-nn['m'],'excluded_n_delivered':sum(x['delivered'] for x in allp['n'])-nn['n']}
standard=[standardize('source',lambda x:(x['source'],)),standardize('seed_source',lambda x:(x['seed'],x['source'])),standardize('seed_source_admission1200s',lambda x:(x['seed'],x['source'],min(int((x['generated']-300)//1200),4))),standardize('seed_source_admission600s',lambda x:(x['seed'],x['source'],int((x['generated']-300)//600)))]
wr('standardized_summary.csv',standard)
summary={'inputs':hashes,'admission_evidence_sha256':hashlib.sha256(args.admission_evidence.read_bytes()).hexdigest() if ADME else None,'admission_provenance_note':'Attempts from observed counts where available, otherwise accepted schedule. Native terminal outcomes remain unsplit in original packet extracts.','grid_max_abs_error_s':griderrs,'totals':{e:{'admitted':len(allp[e]),'delivered':sum(x['delivered'] for x in allp[e]),'outcomes':dict(Counter(x['outcome'] for x in allp[e])),'delivered_mean_s':mean([x['delay'] for x in allp[e] if x['delivered']])} for e in 'mn'},'common_scheduled_attempts':match_summary,'fixed_followup':fixed_summary,'standardization':standard,'limitations':['Matched key is equal scheduled attempt time at the same source and nominal seed, NOT equal random stream or trajectory. Both-admitted intersection and double-delivered subset are selected by outcomes and not representative of all offered traffic.','Native packet extracts collapse terminal dropped and unresolved; no pending-only claim follows from non-delivery.','Fixed-horizon rates include every eligible admitted packet, avoiding stop-related follow-up censoring at that horizon, but admission selection and topology histories remain different.','Standardization is descriptive; common support excludes undefined cells and finer bins may select more strongly.','A rejected generation interrupt creates no persistent queued application, so attempted-to-admitted time is not measurable packet latency.']}
(OUT/'reconciliation.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:summary[k] for k in ['totals','common_scheduled_attempts','fixed_followup','standardization']},indent=2))
