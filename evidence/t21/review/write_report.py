"""Build the T21 synthesis from independently checked offline diagnostics."""
from pathlib import Path
import csv,datetime,hashlib,json,re

HERE=Path(__file__).resolve().parent
def read(name):return json.loads((HERE/name).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
target=read('target/target-screen.json');matlab=read('matlab/matlab_node8.json')
native={s:read(f'native/s{s}.json') for s in (129,130)}
cohorts={r['seed']:{(c['node'],c['source']):c for c in r['cohorts']} for r in matlab['results']}
node8=[]
for seed in (129,130):
 for source in (7,8):
  m=cohorts[seed][8,source]
  n=next(x for x in native[seed]['nsdp_state'] if x['node']==8 and x['source']==source)
  w=next(x for x in native[seed]['residence'] if x['node']==8 and x['source']==source)
  node8.append({'seed':seed,'source':source,'matlab_mean_custody_apps':m['mean_nwk_custody_traffic_window'],
    'ns3_mean_nsdp_apps':n['time_weighted_mean_300_6000'],
    'matlab_completed_first_submit_mean_s':m['completed_nwk_first_submit_wait']['mean_s'],
    'ns3_completed_first_admission_mean_s':w['nwk_queue_wait_s']['mean'],
    'matlab_pending_custody_apps_at_stop':m['nwk_pending_at_stop'],'ns3_nsdp_apps_at_stop':n['last']})
summary={'schema':'csr-tranche21-offline-diagnostic-v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'status':'diagnostic_completed','independent_review_file':'review/final-review.json','working_numerical_band_percent':10,
 'target_change_is_simulator_change':False,'matlab_simulations_executed':0,'native_simulations_executed':0,
 'accepted_source_bindings_unchanged':376,'accepted_matlab_sources_unchanged':175,
 'accepted_matlab_tests_reused':716,'new_matlab_tests_executed':0,'matlab_rerun_required':False,
 'default_policy':'actual-tx','production_change_justified':False,
 'numerical_equivalence_established':False,'target_summary':target['summaries'],'node8_comparison':node8,
 'engineering_decision':'Retain the accepted default, PHY/ECC and continuous timing. The larger native seed130 relay backlog and upstream adaptive admission window are observed; differing seed histories do not alone establish a code defect.',
 'next_bounded_question':'Audit the early 7-to-8 ACK/retry sequence that establishes the adaptive outstanding window, preserving actual event order and the known queued-retry policy distinction; use a controlled source-contract comparison before any production change.',
 'input_provenance':{'t20_acceptance_sha256':'69d9bafef93c64a674e8226a434c7c1a5d3b7ebb6f6f2fb76e64461fc497bc28',
  't20_original_return_sha256':'41ee42fd72d3246b005cffa6eb0731aef1f465ac19747be82feb481571a72861',
  't20_candidate_sha256':'ba4cedf3551a0bc1fe31385108e1f33011d1c97211bba993b6061a2de31389c1',
  't20_update_archive_sha256':'f808b63f7901c5278cf586ccb7df25674293003a4d12a79e62536277194f5fc0'},
 'result_files':{name:sha(HERE/name) for name in ['target/target-screen.json','matlab/matlab_node8.json','matlab/matlab_threshold_replay.json','native/s129.json','native/s130.json','native/s129-outcome-joins.json','native/s130-outcome-joins.json','source4/source4.json']}}
(HERE/'diagnostic.json').write_text(json.dumps(summary,indent=2)+'\n')
lines=['# Tranche 21: explain the remaining flow differences','',
 '**Existing-trace investigation completed. The working numerical target is now ±10%. No new MATLAB or ns-3 simulations were needed, and no production source was changed.**','',
 '## Revised target','',
 'This is a new engineering screening band for T21. T20’s accepted results and its original ±5% report remain unchanged. Structural correctness and evidence integrity remain separate requirements. Three seeds do not establish statistical equivalence.','',
 '| Measure | Within ±5% | Within ±10% |','| --- | ---: | ---: |']
for row in target['summaries']:
 label={'admitted':'Admissions','unique_delivered':'Unique deliveries','mean_delivered_delay_s':'Mean delivered delay'}[row['metric']]
 group='network totals' if row['group']=='whole_network' else 'individual flows'
 lines.append(f"| {label}, {group} | {row['within_5_percent']}/{row['comparisons']} | {row['within_10_percent']}/{row['comparisons']} |")
lines += ['', 'The delivery differences, with ns-3 as denominator, are:', '',
 '| Source | Seed128 | Seed129 | Seed130 |','| --- | ---: | ---: | ---: |']
for source in ('2','3','4','5','7','8'):
 vals=[next(r for r in target['comparisons'] if r['metric']=='unique_delivered' and r['source']==source and r['seed']==s)['difference_percent'] for s in (128,129,130)]
 lines.append('| '+source+' | '+' | '.join(f'{v:+.2f}%' for v in vals)+' |')
lines += ['',
 'All six flows in seed129 now meet the delivery band. The remaining delivery exceptions are sources4/5 in seed128 and sources5/7/8 in seed130. Whole-network delivery is within0.55% in each seed; pooling all three produces +0.320%. Only sources2 and3 meet ±10% in every seed. Four of six pooled flow-delivery ratios meet ±10%, but pooling must not hide a single-seed exception.','',
 '## Node8: sustained relay backlog in native seed130','',
 'The measurements distinguish original source7 traffic relayed by node8 from node8’s own source8 traffic. Occupancy means cover300–6000s. Completed first-submit/admission waits use the same lifecycle endpoints in each engine, but are different packet populations; right-censored waits remain separately recorded.','',
 '| Seed | Original source at node8 | MATLAB mean retained apps | ns-3 mean NSDP apps | MATLAB mean pre-HOP wait (s) | ns-3 mean pre-HOP wait (s) | MATLAB / ns-3 owners at stop |',
 '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
for r in node8:
 lines.append(f"| {r['seed']} | {'7, relayed' if r['source']==7 else '8, local'} | {r['matlab_mean_custody_apps']:.2f} | {r['ns3_mean_nsdp_apps']:.2f} | {r['matlab_completed_first_submit_mean_s']:.2f} | {r['ns3_completed_first_admission_mean_s']:.2f} | {r['matlab_pending_custody_apps_at_stop']} / {r['ns3_nsdp_apps_at_stop']} |")
lines += ['',
 'Native seed130 enqueues1,361 source7 applications at node8 and forwards1,043 to HOP, leaving318 waiting. MATLAB enqueues778 and submits747, leaving31. Native node8 ends with334 waiting applications across these two sources:318 relayed and16 local. Native relay occupancy peaks at361. This is a sustained arrival-versus-service imbalance, not a count of dropped packets.','',
 'Both engines keep node8’s own NSDP population almost continuously at its16-application limit. The limit is per original source/destination, not one shared16-packet pool: relay source7 owners do not directly consume source8’s NSDP quota. They compete for downstream queue service and HOP capacity, delaying releases that admit the next local application. No explicit local-versus-relay priority branch was found in the retained source contracts.','',
 'Native seed130 gateway routes have no changes after103.09s, before traffic starts at300s. The native backlog is not coincident with a later route switch. MATLAB observed DATA next hops consistently follow7→8→2→4, but its final route snapshots and aggregate route-change counters cannot exclude every transient route change.','',
 'MATLAB also exhibits a local-suppression regime: in seed129 during2100–2400s, node8 admits only6 local applications while41 relayed source7 applications enter HOP; relayed applications waiting for first submission average84.55. The much stronger native seed130 regime therefore cannot by itself be labeled a unique native or MATLAB scheduling bug.','',
 '## Upstream adaptive admission window','',
 'Native7→8 HOP admissions increase from854 in seed129 to1,365 in seed130. Their completion counts are50 ACK /799 DACK /5 no-ACK versus28 ACK /1,333 DACK /4 no-ACK. Mean completed HOP capacity retention, including the delayed DACK hold, is20.45s versus21.41s. The extra upstream traffic is not explained by shorter per-packet capacity retention.','',
 'At native admissions, the permitted outstanding threshold is mostly2 in seed129 (609/854 admissions, observed range0–4). Seed130 has581 admissions at threshold3,430 at5 and202 at7, with observed range0–7. The effective permitted outstanding window is threshold+1. More admitted traffic at these larger window values is consistent with node8 being fed faster than it can drain. This is an observed mechanism, not a controlled counterfactual proving the origin of the cross-engine gap.','',
 'A source-derived replay of MATLAB’s ordered callbacks reconstructs its threshold and ACK accumulator. In seed130,654 of787 HOP admissions occur at threshold1 or2, and the reconstructed state spends5,090 of5,700 active-traffic seconds at those levels. All observed admissions satisfy reconstructed neighbor/global limits, and final DATA, DACK-hold and resend populations reconcile. These values are derived from the unchanged source rules and exported events; they are not additional hidden-state measurements. The contrast supports different adaptive-window histories, without demonstrating a mismatch in the update rules.','',
 'The exact pinned native HOP header was re-fetched and matches its previously audited SHA-256. Its adaptive rules agree with MATLAB: every third qualifying ACK grows the threshold up to16; a retried ACK resets the ACK accumulator after the increment/test; DACK resets that accumulator without shrinking the threshold; final DATA failure decreases the threshold toward0. Different event histories can therefore retain different permitted windows under the same rules. The known queued-retry timing distinction remains separate and was not changed.','',
 '## Source4 disposition','',
 'Source4 meets ±10% in seeds129/130 (−6.57%,−6.37%); seed128 remains−16.95%. The ratio of three-seed sums is−9.85%, which does not erase the seed128 exception.','',
 'The delivery difference equals the admission difference minus the difference in applications still undelivered at stop. For128,129,130 respectively: −71=−59−12; −28=+2−30; −29=−37−(−8). The gap therefore does not have one uniformly worse admission or completion component.','',
 'All199 final source4 MATLAB drops were linked to the same application’s final HOP failure:62/75/62 across the seeds, mainly at4→5. Node4 transmitter failures from relayed sources are kept separate. Native source4 no-ACK completions at4→5 still lead to11 deliveries in seed129 and2 in seed130, demonstrating why hop-level no-ACK events cannot be counted as end-to-end application drops.','',
 'For seed129, source4’s mean NWK-enqueue→HOP-admission wait at node4 is177.95s in MATLAB and177.66s in ns-3; for130 it is173.97s and164.79s. These observations do not justify a blanket source4 queue-policy change.','',
 '## Engineering decision','',
 'Retain actual-tx, continuous timing and the existing PHY/ECC. T21 provides a reproducible diagnosis rather than a simulator patch. The practical network-delivery target is met in all three seeds; per-flow and delay parity remain qualified by the listed exceptions.','',
 'If another behavior tranche is pursued, make it a controlled7→8 adaptive-window contract comparison: preserve initial state and ACK/retry/DACK/failure event order, then test whether the implementations update threshold, ACK accumulator and outstanding capacity identically. Use the observed seed130 startup history to select the contract. Change production behavior only for a demonstrated contract mismatch; do not cap the window or retune PHY solely to force these three results to agree.','',
 '## Verification and limits','',
 '- All376 issued source bindings and98 reference bindings are unchanged; accepted716/716 MATLAB tests are reused, not re-executed.','- Independent review recomputed all63 revised-target comparisons and checked packet conservation, interval clipping, complete/censored ownership areas, receipt hashes, and native before/after state snapshots.','- Native traces contain11,786,557 events across the three seeds and retain exact accepted raw hashes. Historical128 lacks the detailed custody events needed for equivalent native occupancy reconstruction; unavailable measurements are not zero.','- MATLAB’s detailed admission prefix ends at633.32s. Full protocol generation records and complete counters support later admissions; omitted per-attempt blocking states are not invented.','- DACK releases NSDP before later HOP capacity release. Those endpoints and their population counts remain distinct.','- Native duplicate delivery events remain separate from unique application deliveries. Native unmatched sends alone do not identify terminal drops.','- Cross-engine packet identities and random draws are not paired. Conditional delay populations and pooled ratios remain explicitly labeled.','- No fresh OPNET runs, MATLAB runs or native runs were performed.','',
 'Detailed scripts, CSV tables, event joins, source bindings and independent review records accompany this report.']
report='\n'.join(lines)+'\n'
report=re.sub(r'\b(source|sources|seed|seeds|node|threshold|from|to|within|at|only|by|is|for|than|has|with|all|in|of|and|versus|not|after|before|time|are|mean|range|on|while|follow)(?=\d)',r'\1 ',report,flags=re.I)
report=re.sub(r'(?<=[A-Za-z])(?=\d)',' ',report)
report=re.sub(r'\bT (\d+)',r'T\1',report)
report=re.sub(r'(?<=\d)s\b',' s',report)
report=re.sub(r'(?<=[A-Za-z])(?=[−+]\d)',' ',report)
report=report.replace('sources:318','sources: 318').replace('threshold 3,430','threshold 3, 430').replace('seed 130,654','seed 130, 654').replace('average 84.55.','average 84.55 applications.')
report=re.sub(r' /(?=\d)',' / ',report)
(HERE/'T21_Review.md').write_text(report)
print(json.dumps({'status':'synthesis_written','node8_comparisons':len(node8),'new_simulations':0}))
