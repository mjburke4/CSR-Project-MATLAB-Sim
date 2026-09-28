"""Compare autonomous receiver histories without pairing application IDs."""
from pathlib import Path
from collections import defaultdict
import csv,json
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
def rows(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def write(name,data):
    with (OUT/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
def main():
    comparisons=[]
    for model,folder in [('matlab','matlab_receiver'),('ns3','native_receiver')]:
        for r in rows(ROOT/f'next_feedback/{folder}/flow_summary.csv'):
            comparisons.append(dict(model=model,source=int(r['source']),
                data_admissions=int(r['admissions']),receipts=int(r['receptions']),
                ack=int(r['receiver_acks']),dack=int(r['receiver_dacks']),
                ack_fraction=float(r['ack_fraction_of_receptions']),
                mean_nsdp_at_arrival=float(r['mean_nsdp_at_arrival']),
                max_nsdp_at_arrival=int(r['max_nsdp_at_arrival']),
                first_receipt_s=float(r['first_reception_s']),first_dack_s=float(r['first_dack_s']),
                no_receipt_failures=int(r['no_reception_failures']),unfinished=int(r['unfinished'])))
    write('flow_comparison.csv',comparisons)
    # State counts change only at enqueue and custody release. Step trajectories
    # include all exact changes, without temporal sampling or aggregation.
    states=[]
    for r in rows(ROOT/'next_feedback/matlab_receiver/node2_custody_events.csv'):
        if r['event']=='network_submit':continue
        states.append(dict(model='matlab',time_s=float(r['time_s']),source=int(r['source']),
                           custody_after=int(r['nsdp_after'])))
    for r in rows(ROOT/'next_feedback/native_receiver/nsdp_state_changes.csv'):
        if r['node']!='2':continue
        states.append(dict(model='ns3',time_s=float(r['time_s']),source=int(r['source']),
                           custody_after=int(r['count_after'])))
    write('node2_custody_trajectories.csv',states)
    occupancy=[]
    for model in ['matlab','ns3']:
        for source in [2,7,8]:
            part=[r for r in states if r['model']==model and r['source']==source]
            t=300.; count=0; area=high=0.
            for r in part+[dict(time_s=6000,custody_after=part[-1]['custody_after'])]:
                dt=r['time_s']-t;assert dt>=0
                area+=dt*count;high+=dt*(count>=16);count=r['custody_after'];t=r['time_s']
            occupancy.append(dict(model=model,source=source,mean_custody=area/5700,
                fraction_time_at_or_above16=high/5700,final_custody=count))
    write('node2_custody_occupancy.csv',occupancy)
    bins=[]
    for model,folder in [('matlab','matlab_receiver'),('ns3','native_receiver')]:
        for r in rows(ROOT/f'next_feedback/{folder}/receiver_service_100s_bins.csv'):
            bins.append(dict(model=model,**r))
    write('receiver_service_comparison.csv',bins)
    summary={'scope':'Different autonomous histories, same per-flow receiver threshold; no matched-application claim.',
      'matlab_received':sum(r['receipts'] for r in comparisons if r['model']=='matlab'),
      'ns3_received':sum(r['receipts'] for r in comparisons if r['model']=='ns3'),
      'flows':comparisons,'node2_occupancy':occupancy,
      'first_source8_receipt_difference_s':comparisons[1]['first_receipt_s']-comparisons[3]['first_receipt_s']}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
