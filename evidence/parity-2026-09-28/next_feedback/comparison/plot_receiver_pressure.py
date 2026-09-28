"""Plot complete, unsampled observed node-2 custody trajectories."""
from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'next_feedback/deliverables'
with (ROOT/'next_feedback/comparison/node2_custody_trajectories.csv').open() as f:
    rows=list(csv.DictReader(f))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,
    'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,axes=plt.subplots(2,1,figsize=(11,7.4),sharex=True)
fig.subplots_adjust(left=.095,right=.965,top=.82,bottom=.23,hspace=.31)
for ax,src in zip(axes,[7,8]):
    for model,label,color in [('matlab','Corrected MATLAB','#24658A'),('ns3','ns-3','#D57626')]:
        part=[r for r in rows if r['model']==model and int(r['source'])==src]
        x=[300.]+[float(r['time_s']) for r in part]+[6000.]
        y=[0]+[int(r['custody_after']) for r in part]+[int(part[-1]['custody_after'])]
        ax.step(x,y,where='post',label=label,color=color,lw=1.5)
    ax.axhline(16,color='#596775',ls='--',lw=1,label='DACK threshold: 16')
    ax.set_title(f'Original source {src} → gateway 1',loc='left',fontsize=12,fontweight='bold')
    ax.set_ylabel('Applications in custody')
    ax.set_ylim(0,180 if src==7 else 45)
    ax.set_xlim(300,6000)
    ax.grid(axis='y',color='#E0E6EB',lw=.65)
    ax.set_axisbelow(True)
axes[1].set_xlabel('Simulation time (s)')
fig.suptitle('Node 2 holds substantially more source-7 traffic in MATLAB',
             x=.07,y=.968,ha='left',fontsize=17,fontweight='bold')
fig.text(.07,.920,'Seed 132 · complete custody histories from the existing 6,000-second traces',fontsize=12,color='#405363')
handles,labels=axes[0].get_legend_handles_labels()
fig.legend(handles,labels,loc='upper left',bbox_to_anchor=(.066,.89),ncol=3,frameon=False)
fig.text(.07,.055,'Custody includes applications waiting in NWK and already admitted to HOP. Panel scales differ.\nFor the observed first receptions, DACK is selected when the same flow has ≥16 owners before arrival.\nThe curves show autonomous histories; equal application identities or causal effects of a code change are not assumed.',
         fontsize=10,color='#405363',linespacing=1.5)
for ext in ('png','svg'):fig.savefig(OUT/f'Seed132_Receiver_Backlog_2026-09-25.{ext}',dpi=180,facecolor='white')
print('Wrote PNG and SVG from all recorded custody changes.')
