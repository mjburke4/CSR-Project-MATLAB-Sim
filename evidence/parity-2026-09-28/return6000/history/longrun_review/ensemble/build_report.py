#!/usr/bin/env python3
"""Render concise report from analyze_ensemble.py's already checked outputs."""
import csv,json
from pathlib import Path
P=Path(__file__).resolve().parent
J=json.loads((P/'summary.json').read_text())
def rows(name):
 with (P/name).open(newline='') as f:return list(csv.DictReader(f))
def fmt(v,d=2):return 'undefined' if v is None or v=='' else f'{float(v):,.{d}f}'
def lookup(rs,**kw):return next(r for r in rs if all(r[k]==str(v) for k,v in kw.items()))
A=rows('pooled_source_accounting.csv');F=rows('fixed_age_delivery.csv');S=rows('standardized_latency.csv');U=rows('unfinished_ages.csv')
m,n=J['totals']['matlab'],J['totals']['native']
lines=['# Original 6,000-second accounting: five-seed extension','',
'This review reuses seeds 128–132 and runs no new simulation. It independently reproduces 210 accepted count/mean checks and extends the earlier latency review with scheduled-attempt accounting, equal-weight comparisons, deadline delivery with complete follow-up, and explicit unfinished populations. The archived mix and queue-location findings are confirmed; they are not new discoveries.','',
'## Application accounting','',
'Attempts are the generator’s periodic admission checks, not persistent application objects. Only an admitted check creates the application whose latency is measured. Each source has 285,000 scheduled checks per run (300–6,000 s, every 20 ms). Direct attempt counters were rechecked for seeds 131–132; attempts for 128–130 are schedule-derived and explicitly labeled in the CSV.','',
'| Engine | Scheduled attempts | Admitted | Delivered | Terminal drops | Pending | Unresolved fate |',
'|---|---:|---:|---:|---:|---:|---:|',
f"| MATLAB | {m['scheduled_attempts']:,} | {m['admitted']:,} | {m['delivered']:,} | {m['known_terminal_dropped']:,} | {m['known_pending']:,} | 0 |",
f"| ns-3 | {n['scheduled_attempts']:,} | {n['admitted']:,} | {n['delivered']:,} | Unknown | Unknown | {n['unresolved_fate']:,} |",'',
'Native owner completion, `no_ack`, DACK expiration, and receiver drops do not establish global terminal application fate. Its 3,255 undelivered identities remain unresolved, potentially including unobserved terminal drops. They must not all be labeled pending, assigned completed latency, or treated as ordinary survival-analysis censoring. MATLAB’s pending count is its application-status classification, not a claim that every packet remains in one particular queue.','',
'| Source | MATLAB admitted / delivered / dropped / pending | ns-3 admitted / delivered / unresolved | MATLAB / ns-3 delivered mean (s) |',
'|---|---:|---:|---:|']
for so in [2,3,4,5,7,8]:
 a=lookup(A,engine='matlab',source=so);b=lookup(A,engine='native',source=so)
 lines.append(f"| {so} | {a['admitted']} / {a['delivered']} / {a['known_terminal_dropped']} / {a['known_pending']} | {b['admitted']} / {b['delivered']} / {b['unresolved_fate']} | {fmt(a['mean_latency_s'])} / {fmt(b['mean_latency_s'])} |")
lines+=['','Detailed source/seed balances are in `per_seed_source_accounting.csv`. Aggregate delivery count is close (59,273 versus 59,376), but source-level differences remain substantial. Native seed 131 admits nothing from sources 2, 7, or 8, despite 285,000 checks each. MATLAB admits 1,835 and delivers 1,304 across those three cells.','',
'## Delivered latency and source mix','',
f"The unchanged raw pooled delivered means are **{m['pooled_delivered_mean_s']:.3f} versus {n['pooled_delivered_mean_s']:.3f} s (+{J['pooled_residual_percent']:.2f}%)**. Equal weighting of the five run means gives {m['equal_seed_mean_s']:.3f} versus {n['equal_seed_mean_s']:.3f} s (+{J['equal_seed_mean_residual_percent']:.2f}%).",'',
'The prior exact arithmetic partition reproduces: 19.009 s of the 21.098 s pooled gap is the contribution of MATLAB’s three unmatched seed-131 cells relative to the native overall mean; 2.089 s is the common-support remainder. This is a descriptive identity, not proof that discovery causally explains 90% of the discrepancy. The source-only symmetric alternative gives 11.787 s from delivery mix and 9.311 s from pooled within-source means; these alternative partitions must not be added.','',
'The following common-weight diagnostics retain only the 27 seed/source cells delivered in both models. The absent native means remain undefined. Reweighting uses observed deliveries, not a new physical traffic model.','',
'| Common weighting | MATLAB mean (s) | ns-3 mean (s) | Difference |',
'|---|---:|---:|---:|']
for method in ['native_delivery_weights','pooled_delivery_weights','equal_cell_weights']:
 r=lookup(S,scope='seed_source',weighting=method)
 lines.append(f"| {method.replace('_',' ')} | {fmt(r['matlab_standardized_mean_s'],3)} | {fmt(r['native_standardized_mean_s'],3)} | +{fmt(r['residual_percent'])}% |")
r=lookup(S,scope='seed_source',weighting='native_delivery_weights')
lines+=['',f"At native delivery weights, NWK waiting averages {fmt(r['matlab_nwk_standardized_mean_s'],3)} versus {fmt(r['native_nwk_standardized_mean_s'],3)} s; post-admission service averages {fmt(r['matlab_post_standardized_mean_s'],3)} versus {fmt(r['native_post_standardized_mean_s'],3)} s. Thus the standardized +{fmt(r['difference_s'],3)} s difference still sits mainly before HOP admission.",'',
'**These values are not ±10% parity passes.** They exclude meaningful missing traffic, condition on successful completion, and allow large positive and negative source errors to cancel. Pooling by source before reweighting changes the question again: equal weight to six pooled source means gives +11.53%. The result is sensitive to the declared estimand.','',
'## Include unfinished traffic through fixed-age delivery','',
'For each horizon T, use the same half-open generation window [300, 6000−T) in both models. Every included scheduled check or admitted application has at least T seconds of observation. Count final delivery by generation+T; report that numerator both over scheduled checks and admitted applications. Rejected checks and unfinished or dropped applications are not assigned invented completion times. Different horizons deliberately have different eligible windows, so the rows are not one cumulative-distribution curve.','',
'| Deadline age (s) | Scheduled checks per engine | MATLAB delivered / admitted | ns-3 delivered / admitted | MATLAB / ns-3 delivery per scheduled check |',
'|---|---:|---:|---:|---:|']
for t in [60,300,600,1200]:
 a=lookup(F,horizon_s=t,engine='matlab',seed='',source='');b=lookup(F,horizon_s=t,engine='native',seed='',source='')
 lines.append(f"| {t} | {int(a['scheduled_attempts']):,} | {int(a['delivered_by_age']):,} / {int(a['admitted']):,} ({100*float(a['deadline_fraction_of_admitted']):.2f}%) | {int(b['delivered_by_age']):,} / {int(b['admitted']):,} ({100*float(b['deadline_fraction_of_admitted']):.2f}%) | {100*float(a['deadline_fraction_of_scheduled_attempts']):.4f}% / {100*float(b['deadline_fraction_of_scheduled_attempts']):.4f}% |")
lines+=['','Whole-network deadline counts again mask source-level differences. At a 1,200-second deadline, both models have the same 225,000 scheduled checks per source in [300, 4,800):','',
'| Seed / source | MATLAB delivered within 1,200 s / admitted | ns-3 delivered within 1,200 s / admitted |',
'|---|---:|---:|']
for s,so in [(130,7),(130,8),(132,2),(132,7),(132,8)]:
 a=lookup(F,horizon_s=1200,engine='matlab',seed=s,source=so);b=lookup(F,horizon_s=1200,engine='native',seed=s,source=so)
 lines.append(f"| {s} / {so} | {a['delivered_by_age']} / {a['admitted']} ({100*float(a['deadline_fraction_of_admitted']):.2f}%) | {b['delivered_by_age']} / {b['admitted']} ({100*float(b['deadline_fraction_of_admitted']):.2f}%) |")
lines+=['','The opposite long-delay behavior in seeds 130 and 132 therefore survives an explicit deadline comparison with complete follow-up. The main problem is not solely an end-of-run censoring artifact. These outcome differences still do not identify an implementation defect because each model develops its own admission, route, and feedback history.','',
'MATLAB has 1,493 pending applications at the stop: median elapsed age 367.82 s, 95th percentile 1,737.408 s, maximum 2,151.44 s; 239 exceed 1,200 s. Seed-132 source 7 alone retains 298 pending, with 131 over 1,200 s old. Native unresolved ages are retained separately in the CSV and are not comparable live-queue age statistics.','',
'## Exact scheduled-attempt overlap is only a sensitivity check','',
'All admitted times map uniquely to source and a zero-based 20 ms scheduled index; maximum reconstruction residual is 9.1×10⁻¹³ s. The two models jointly admit only 1,827 checks and jointly deliver 1,726, about 2.9% of each delivered population. This selected intersection has means 39.144 versus 41.549 s (−5.79%), but 1,385 of the 1,726 come from source 3. Equal scheduled checks do not imply shared random draws or trajectories. This small, selected subset cannot establish network parity.','',
'## Scope and reproducibility','',
'Run `python3 longrun_review/ensemble/analyze_ensemble.py --workspace <restored-workspace>` and then `python3 longrun_review/ensemble/build_report.py`. All calculations use the Python standard library. `summary.json` binds input hashes and defines estimands. `accepted_metric_checks.csv` preserves all 210 reproduction checks; `jointly_admitted_attempts.csv` retains the sparse intersection identities. No production code was edited. Native and MATLAB 131/132 companion audits validate the original trace-to-ledger mappings; 128–130 use the prior archived audit and its accepted provenance.','',
'The evidence supports retaining the original network discrepancy as open, with explicit per-source accounting and NWK admission waiting as the dominant location. It supports no timer/window adjustment or new production fix without a specific behavioral mismatch.']
(P/'ENSEMBLE_REVIEW.md').write_text('\n'.join(lines)+'\n')
