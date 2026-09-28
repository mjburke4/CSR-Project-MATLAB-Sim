"""Build the static scientific figure from the audited phase tables."""
from pathlib import Path
import csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'deliverables'
OUT.mkdir(exist_ok=True)
def rows(p):
    with p.open(newline='') as f:
        return list(csv.DictReader(f))

data = {}
for r in rows(ROOT / 'return6000/review/phase131/source_phase_comparison.csv'):
    for model in ['native', 'old_matlab', 'current_matlab']:
        if r[model + '_mean_latency_s']:
            data[131, int(r['source']), model] = (
                float(r[model + '_mean_nwk_wait_s']),
                float(r[model + '_mean_post_hop_s']),
                int(r[model + '_delivered']))
names = {'ns3_reference':'native', 'matlab_original':'old_matlab', 'matlab_current':'current_matlab'}
for r in rows(ROOT / 'return6000/review/phase132/source_phase_comparison.csv'):
    data[132, int(r['source']), names[r['model']]] = (
        float(r['mean_nwk_wait_s']), float(r['mean_post_hop_admission_s']), int(r['delivered']))

plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':11, 'axes.spines.top':False,
                     'axes.spines.right':False, 'axes.titleweight':'bold', 'svg.fonttype':'none'})
fig, axes = plt.subplots(2, 2, figsize=(12, 9))
fig.subplots_adjust(top=.82, bottom=.13, hspace=.51, wspace=.24)
models = ['native', 'old_matlab', 'current_matlab']
labels = ['ns-3', 'Original\nMATLAB', 'Corrected\nMATLAB']
colors = ['#24658A', '#EDA84D']
plot_rows = []
for ax, (seed, src, ylim) in zip(axes.flat, [(131,4,310),(131,5,80),(132,7,1900),(132,8,1725)]):
    vals = [data[seed,src,m] for m in models]
    for x, (model, (nwk, post, n)) in enumerate(zip(models, vals)):
        ax.bar(x, nwk, .58, color=colors[0])
        ax.bar(x, post, .58, bottom=nwk, color=colors[1])
        ax.text(x, nwk+post+ylim*.025, f'{nwk+post:,.1f} s', ha='center', fontsize=11, fontweight='bold')
        plot_rows.append(dict(seed=seed,source=src,model=model,delivered=n,nwk_wait_s=nwk,post_hop_admission_s=post,total_latency_s=nwk+post))
    ax.set_xticks(range(3), [f'{label}\n(n={v[2]:,})' for label,v in zip(labels,vals)], fontsize=10)
    ax.set_ylim(0, ylim)
    ax.set_ylabel('Mean delivered latency (s)')
    ax.set_title(f'Seed {seed} · source {src}', loc='left', pad=16)
    ax.set_axisbelow(True)
    ax.grid(axis='y', color='#DDE4E9', linewidth=.7)
    ax.spines['left'].set_color('#AEBCC5')
    ax.spines['bottom'].set_color('#AEBCC5')
fig.suptitle('Remaining delay is dominated by NWK waiting', x=.065, y=.97, ha='left', fontsize=20, fontweight='bold')
fig.text(.065, .925, 'Selected flows from the 6,000-second runs · each bar uses that model’s delivered population', fontsize=12, color='#405363')
fig.legend(handles=[Patch(color=colors[0], label='NWK wait before HOP admission'),
                    Patch(color=colors[1], label='Subsequent MAC/HOP service, including retries')],
           loc='upper left', bbox_to_anchor=(.057,.902), ncol=2, frameon=False, fontsize=11)
fig.text(.065,.035,'Panel scales differ. n = unique deliveries; dropped and unfinished applications are excluded from latency.\nSeed 131 has different reachable-source populations. Lower delivered means alone do not establish better service.',
         fontsize=10, color='#405363', linespacing=1.5)
for ext in ['png','svg']:
    fig.savefig(OUT/f'CSR_6000s_Latency_Phases_2026-09-25.{ext}', dpi=180, facecolor='white')
with (ROOT/'return6000/review/presentation/plotted_phase_data.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(plot_rows[0])); w.writeheader(); w.writerows(plot_rows)
print('Wrote latency phase PNG, SVG, and underlying data.')
