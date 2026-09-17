"""Apply the owner's T21 ±10% descriptive target to accepted T20 results.

No simulator runs or accepted T20 file edits. Percentages have ns-3 denominators.
"""
from pathlib import Path
import argparse,csv,hashlib,json,statistics

EXPECTED={
 'acceptance.json':'69d9bafef93c64a674e8226a434c7c1a5d3b7ebb6f6f2fb76e64461fc497bc28',
 'analysis/review.json':'2d4dfbb66aa657cbfa230f3cf088c4be3815e0558e5573fbc9ba143aa4800b79',
 'independent-findings/comparisons.csv':'fa0145a1c175b4d26458edfcab2985c51ac2225159d6986eb1988d6677037883'}

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--review-package',type=Path,required=True)
 ap.add_argument('--output',type=Path,required=True)
 args=ap.parse_args();root=args.review_package
 for name,h in EXPECTED.items():
  assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h,name
 accepted=json.loads((root/'acceptance.json').read_text())
 assert accepted['accepted'] and accepted['tests_passed']==716
 review=json.loads((root/'analysis/review.json').read_text())
 assert review['full_structural_gate_completed']
 with (root/'independent-findings/comparisons.csv').open(newline='') as f: rows=list(csv.DictReader(f))
 assert {(int(r['seed']),r['source']) for r in rows}=={(s,x) for s in (128,129,130) for x in ('total','2','3','4','5','7','8')}
 comparisons=[]
 for r in rows:
  for metric,mcol,ncol in [('admitted','matlab_admitted','ns3_admitted'),('unique_delivered','matlab_delivered','ns3_unique_delivered'),('mean_delivered_delay_s','matlab_mean_delivered_latency_s','ns3_mean_first_delivery_latency_s')]:
   m=float(r[mcol]);n=float(r[ncol]);assert n>0 and m>=0
   residual=100*(m-n)/n
   comparisons.append({'seed':int(r['seed']),'source':r['source'],'metric':metric,'matlab':m,'ns3':n,
                       'difference_percent':residual,'within_5_percent':abs(residual)<=5,'within_10_percent':abs(residual)<=10})
 summaries=[]
 for metric in ['admitted','unique_delivered','mean_delivered_delay_s']:
  for group in ['whole_network','individual_flows']:
   selected=[r for r in comparisons if r['metric']==metric and (r['source']=='total')==(group=='whole_network')]
   summaries.append({'metric':metric,'group':group,'comparisons':len(selected),
                     'within_5_percent':sum(r['within_5_percent'] for r in selected),
                     'within_10_percent':sum(r['within_10_percent'] for r in selected)})
 pooled=[]
 for source in ['total','2','3','4','5','7','8']:
  for metric in ['admitted','unique_delivered']:
   selected=[r for r in comparisons if r['source']==source and r['metric']==metric]
   m=sum(r['matlab'] for r in selected);n=sum(r['ns3'] for r in selected)
   pooled.append({'source':source,'metric':metric,'matlab_sum':m,'ns3_sum':n,
                  'ratio_of_sums_percent':100*(m-n)/n,
                  'mean_per_seed_difference_percent':statistics.fmean(r['difference_percent'] for r in selected),
                  'matlab_range':[min(r['matlab'] for r in selected),max(r['matlab'] for r in selected)],
                  'ns3_range':[min(r['ns3'] for r in selected),max(r['ns3'] for r in selected)],
                  'all_seeds_within_10_percent':all(r['within_10_percent'] for r in selected)})
 out={'schema':'csr-tranche21-target-screen-v1','target_percent':10,'previous_descriptive_target_percent':5,
      'target_basis':'Owner requested ±10% as the T21 working parity goal; no retroactive change to T20 acceptance or results.',
      'band_is_structural_gate':False,'statistical_equivalence_established':False,
      'input_sha256':EXPECTED,'comparisons':comparisons,'summaries':summaries,'pooled_counts':pooled,
      'limitations':['Only three seeds.','Engine seeds do not establish common random draws.','Delay means are conditioned on different delivered populations.','Native duplicate delivery events are separate from unique delivered applications.','No new OPNET runs.']}
 args.output.mkdir(parents=True,exist_ok=True)
 (args.output/'target-screen.json').write_text(json.dumps(out,indent=2)+'\n')
 with (args.output/'comparisons.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(comparisons[0]));w.writeheader();w.writerows(comparisons)
 print(json.dumps(summaries,indent=2))

if __name__=='__main__':main()
