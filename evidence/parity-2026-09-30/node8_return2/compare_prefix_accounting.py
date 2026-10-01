"""Application identity accounting for the strict prefix before the stopped TX.
No simulator invocation. Native duplicate deliveries count once per application.
"""
from pathlib import Path
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_EVEN
import csv, hashlib, json

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / 'accounting'
OUT.mkdir(exist_ok=True)
STOP = 895115000000
def ns(s): return int((Decimal(s) * 1000000000).to_integral_value(rounding=ROUND_HALF_EVEN))
def detail(s): return dict(v.split('=', 1) for v in s.split(';') if '=' in v)
def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

mat_adm = ROOT/'node8_return2/data/S132_1200/application_admission_trace.csv'
mat_pro = ROOT/'node8_return2/data/S132_1200/protocol_trace.csv'
native = ROOT/'node8_1200/native/s132_1200/run/ns3-trace.csv'
ids = {'matlab': {}, 'native': {}}
attempts = {'matlab': {}, 'native': {}}
admitted = {'matlab': {}, 'native': {}}
deliveries = {'matlab': {}, 'native': {}}
raw_delivery_counts = Counter()
raw_drops = defaultdict(set)
for r in csv.DictReader(mat_adm.open()):
    t = ns(r['TimeSeconds'])
    if t >= STOP: continue
    k = (int(r['SourceId']), int(r['AttemptIndex']))
    assert k not in attempts['matlab']
    attempts['matlab'][k] = (t, r['Accepted']=='1', r['Reason'])
    if r['Accepted']=='1':
        ids['matlab'][int(r['PacketId'])] = k
        admitted['matlab'][k] = t
for r in csv.DictReader(mat_pro.open()):
    t = ns(r['TimeSeconds'])
    if t >= STOP: continue
    if r['Event'] in ('app_receive', 'app_drop'):
        k = ids['matlab'][int(r['PacketId'])]
        if r['Event']=='app_receive':
            raw_delivery_counts['matlab'] += 1
            deliveries['matlab'].setdefault(k, t)
        else: raw_drops[k].add(r['Reason'])
for r in csv.DictReader(native.open()):
    t = ns(r['time_s'])
    if t >= STOP: continue
    if r['event']=='app_admission':
        d = detail(r['detail']); k = (int(r['src']), int(d['attempt_index']))
        assert k not in attempts['native']
        attempts['native'][k] = (t, r['success']=='1', r['reason'])
        if r['success']=='1':
            ids['native'][int(r['sequence'])] = k
            admitted['native'][k] = t
    elif r['event']=='nwk_delivery':
        k = ids['native'][int(r['sequence'])]
        raw_delivery_counts['native'] += 1
        deliveries['native'].setdefault(k, t)

rows = []
for source in [2,3,4,5,7,8]:
    row = {'source': source}
    for name in ['native', 'matlab']:
        a = {k:v for k,v in admitted[name].items() if k[0]==source}
        d = {k:v for k,v in deliveries[name].items() if k[0]==source}
        row.update({name+'_attempted': sum(k[0]==source for k in attempts[name]),
                    name+'_admitted': len(a), name+'_delivered': len(d),
                    name+'_unresolved': len(set(a)-set(d)),
                    name+'_mean_delivered_latency_s': sum((t-a[k])/1e9 for k,t in d.items())/len(d) if d else None})
    row['delivered_identity_population_equal'] = {k for k in deliveries['matlab'] if k[0]==source} == {k for k in deliveries['native'] if k[0]==source}
    row['matlab_unresolved_with_prior_drop_event'] = sum(k[0]==source and k not in deliveries['matlab'] for k in raw_drops)
    rows.append(row)

common = set(deliveries['native']) & set(deliveries['matlab'])
time_delta = Counter(deliveries['matlab'][k]-deliveries['native'][k] for k in common)
all_attempt_keys = set(attempts['native']) | set(attempts['matlab'])
mismatches = [{'source':k[0], 'attempt':k[1], 'native':attempts['native'].get(k), 'matlab':attempts['matlab'].get(k)} for k in sorted(all_attempt_keys) if attempts['native'].get(k)!=attempts['matlab'].get(k)]
summary = {'schema':'csr-node8-stopped-prefix-accounting-v1', 'cutoff_ns_exclusive':STOP,
           'input_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [mat_adm,mat_pro,native]},
           'attempt_populations_equal':set(attempts['matlab'])==set(attempts['native']),
           'attempt_time_admission_reason_mismatches':len(mismatches),
           'first_attempt_mismatches':mismatches[:10],
           'admitted_identities_and_times_equal':admitted['matlab']==admitted['native'],
           'unique_delivered_identities_equal':set(deliveries['matlab'])==set(deliveries['native']),
           'common_unique_delivered':len(common),
           'matlab_minus_native_delivery_time_ns_counts':dict(time_delta),
           'raw_delivery_counts':dict(raw_delivery_counts), 'rows':rows,
           'accounting_scope':'Unique source/attempt applications; unresolved means admitted without first delivery before cutoff. Raw drop events are provisional and may include multiple relay events.',
           'time_import':'Decimal seconds rounded to nearest integer nanosecond to recover native integer time from its decimal CSV rendering; no added comparison tolerance.',
           'interpretation':'Partial common-input diagnostic only. No 1200-second completion or autonomous 6000-second parity claim.'}
(OUT/'prefix_accounting.json').write_text(json.dumps(summary,indent=2)+'\n')
with (OUT/'source_prefix_accounting.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps({k:v for k,v in summary.items() if k!='input_sha256'},indent=2))
