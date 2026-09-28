"""Export scientific figures from verified historical packet summaries."""
from pathlib import Path
import csv
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT.parent / 'longrun_recovery/extracted/latency-review/latency-review'
OUT = ROOT / 'figures'
OUT.mkdir(exist_ok=True)
data = json.loads((ROOT / 'pooled_phase_check.json').read_text())
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.spines.left': False, 'axes.spines.bottom': False})
sources = ['2', '3', '4', '5', '7', '8']
fig, axes = plt.subplots(1, 2, figsize=(11.2, 5.5), sharey=True)
for ax, metric, title in zip(axes, ['delivered', 'delay_s'],
                            ['Delivered applications', 'Mean delivered latency']):
    values = [100 * (data['matlab'][s][metric] / data['native'][s][metric] - 1)
              for s in sources]
    ax.axvspan(-10, 10, color='#e8eef2', zorder=0)
    ax.axvline(0, color='#68747e', lw=1)
    ax.barh(np.arange(6), values, height=.56,
            color=['#b8612f' if abs(v) > 10 else '#327596' for v in values])
    for y, v in enumerate(values):
        ax.text(v + (1.3 if v >= 0 else -1.3), y, f'{v:+.2f}%',
                va='center', ha='left' if v >= 0 else 'right', fontsize=10)
    ax.set_xlim(-55, 61)
    ax.set_yticks(np.arange(6), [f'Source {s}' for s in sources])
    ax.set_title(title, loc='left', fontweight='bold', pad=13)
    ax.set_xlabel('MATLAB relative to native (%)')
    ax.grid(axis='x', color='#eeeeee', zorder=0)
    ax.set_axisbelow(True)
axes[0].invert_yaxis()
fig.suptitle('Close network totals hide differences between sources',
             x=.09, y=.97, ha='left', fontsize=16, fontweight='bold')
fig.subplots_adjust(top=.82, bottom=.29, left=.09, right=.98, wspace=.13)
fig.text(.09, .055, 'Original 6,000-second histories, seeds 128–132, pooled by source.\n'
         'Shading is the descriptive ±10% target. Latency conditions on delivery; unfinished traffic is separate.\n'
         'Historical baseline: these are not new results for the corrected candidate.', fontsize=9, color='#4d5963')
fig.savefig(OUT / 'source_comparison.png', dpi=190)
fig.savefig(OUT / 'source_comparison.svg')
plt.close(fig)

def read(path):
    with path.open() as stream:
        return {(int(r['seed']), int(r['source'])): r for r in csv.DictReader(stream)}

tables = {'matlab': read(ARCHIVE / 'matlab/flow-summary.csv'),
          'native': read(ARCHIVE / 'native/output/flow-latency-summary.csv')}
groups = [(130, 7), (130, 8), (132, 7), (132, 8)]
fig, ax = plt.subplots(figsize=(11.2, 6.6))
yticks, labels = [], []
for group_index, (seed, source) in enumerate(groups):
    for offset, model in enumerate(['native', 'matlab']):
        y = group_index * 2.65 + offset
        row = tables[model][seed, source]
        nwk = float(row['nwk_admission_wait_s'] if model == 'matlab'
                    else row['mean_nwk_admission_wait_s'])
        service = float(row['post_admission_to_causal_receipt_s'] if model == 'matlab'
                        else row['mean_post_admission_to_receipt_s'])
        ax.barh(y, nwk, height=.7, color='#327596',
                label='NWK waiting' if group_index == 0 and offset == 0 else None)
        ax.barh(y, service, left=nwk, height=.7, color='#c48631',
                label='After HOP admission to next receipt' if group_index == 0 and offset == 0 else None)
        ax.text(nwk + service + 18, y, f'{nwk + service:,.1f} s', va='center', fontsize=10)
        yticks.append(y)
        labels.append(f'{seed} / source {source}   {"Native" if model == "native" else "MATLAB"}')
ax.set_yticks(yticks, labels)
ax.invert_yaxis()
ax.set_xlim(0, 1850)
ax.set_xlabel('Mean delivered latency across the complete path (seconds)')
ax.grid(axis='x', color='#eeeeee')
ax.set_axisbelow(True)
ax.legend(loc='lower right', bbox_to_anchor=(1.01, 1.02), frameon=False, fontsize=9)
fig.suptitle('The large within-source differences occur before HOP admission',
             x=.05, y=.97, ha='left', fontsize=15, fontweight='bold')
fig.subplots_adjust(left=.245, right=.975, top=.80, bottom=.16)
fig.text(.05, .045, 'Each bar uses its own delivered population. Queue and service intervals do not overlap.\n'
         'Opposite seed-130 and seed-132 effects can cancel when pooled. Subsequent ACK custody is excluded.',
         fontsize=9, color='#4d5963')
fig.savefig(OUT / 'latency_phases.png', dpi=190)
fig.savefig(OUT / 'latency_phases.svg')
plt.close(fig)
print('Exported source_comparison and latency_phases as PNG/SVG.')
