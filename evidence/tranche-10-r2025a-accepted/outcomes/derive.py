"""Independent application reconstruction; inputs remain read only."""
import csv
import gzip
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
import statistics
import zipfile

WORK = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SRC = WORK / 'csr10'
INPUT = WORK / 'upload/tranche10_evidence.zip'
Z10 = zipfile.ZipFile(INPUT)
Z9 = zipfile.ZipFile(SRC / 'evidence/tranche-9-r2025a-accepted/tranche9_evidence.zip')
Z7 = zipfile.ZipFile(SRC / 'evidence/tranche-7-r2025a-accepted/tranche7_evidence.zip')


def records(bundle, name):
    return csv.DictReader(io.TextIOWrapper(bundle.open(name), encoding='utf-8-sig'))


def matlab(bundle, prefix):
    applications = {}
    failed_hops = Counter()
    for row in records(bundle, prefix + '/raw/protocol_trace.csv'):
        event = row['Event']
        if event not in {'app_generate', 'app_receive', 'app_drop', 'relay_accept', 'hop_failed'}:
            continue
        packet = row['PacketId']
        when = float(row['TimeSeconds'])
        if event == 'app_generate':
            assert packet not in applications
            applications[packet] = dict(source=row['NodeId'], generated=when,
                                        outcome='pending', received=None)
        elif event == 'hop_failed':
            if row['FrameKind'] == 'DATA':
                failed_hops[(row['NodeId'], row['PeerId'])] += 1
        else:
            item = applications[packet]
            if event == 'app_receive':
                assert item['received'] is None
                item.update(outcome='delivered', received=when)
            elif event == 'app_drop':
                assert item['outcome'] != 'delivered'
                item['outcome'] = 'dropped'
            elif item['outcome'] != 'delivered':
                item['outcome'] = 'pending'

    # Independently reconstructed identities/outcomes must also match the
    # owner-exported application table, without using that table for counts.
    exported = list(records(bundle, prefix + '/analysis/applications.csv'))
    assert len(exported) == len(applications)
    for row in exported:
        item = applications[row['PacketId']]
        assert row['SourceId'] == item['source']
        assert row['Outcome'] == item['outcome']
        assert float(row['GeneratedSeconds']) == item['generated']
        if item['outcome'] == 'delivered':
            assert float(row['ReceivedSeconds']) == item['received']
            assert abs(float(row['LatencySeconds']) - (item['received'] - item['generated'])) < 1e-8
    return summarize(applications.values(), native=False) | {
        'hop_failures_by_link': {f'{a}->{b}': n for (a, b), n in sorted(failed_hops.items())},
        'raw_identities_checked_against_export': len(exported),
    }


def native(path):
    applications = {}
    with gzip.open(path, 'rt') as stream:
        for row in csv.DictReader(stream):
            if row['event'] not in {'app_send', 'nwk_delivery'}:
                continue
            key = row['src'], row['dst'], row['sequence']
            when = float(row['time_s'])
            if row['event'] == 'app_send':
                assert key not in applications
                applications[key] = dict(source=row['src'], generated=when,
                                         outcome='unresolved', received=None)
            else:
                item = applications[key]
                assert item['received'] is None
                item.update(outcome='delivered', received=when)
    return summarize(applications.values(), native=True)


def summarize(items, native):
    items = list(items)

    def stats(rows):
        latencies = [r['received'] - r['generated'] for r in rows if r['received'] is not None]
        result = dict(generated=len(rows), delivered=len(latencies),
                      mean_packet_latency_seconds=statistics.mean(latencies),
                      first_delivery_seconds=min(r['received'] for r in rows if r['received'] is not None),
                      delivered_300_to_320=sum(r['received'] is not None and 300 <= r['received'] < 320 for r in rows),
                      delivered_320_to_stop=sum(r['received'] is not None and r['received'] >= 320 for r in rows))
        if native:
            result['unresolved'] = sum(r['outcome'] == 'unresolved' for r in rows)
        else:
            result['dropped'] = sum(r['outcome'] == 'dropped' for r in rows)
            result['pending'] = sum(r['outcome'] == 'pending' for r in rows)
        return result

    return dict(total=stats(items), flows={source: stats([r for r in items if r['source'] == source])
                for source in sorted({r['source'] for r in items}, key=int)})


result = {}
for key in ['campus', 'c128', 'c129', 'c130', 'c131', 'c132', 'a129']:
    item = {'T10': matlab(Z10, f'b/{key}')}
    if key == 'campus':
        item['T7'] = matlab(Z7, 'benchmarks/campus_multihop_6000')
        ref = SRC / 'evidence/tranche-7-ns3-reference/campus_multihop_6000/ns3-trace.csv.gz'
    else:
        item['T9'] = matlab(Z9, f'b/{key}')
        scenario = ('three_node_contention_360_s' if key.startswith('c') else 'two_node_admission_1200_s') + key[1:]
        ref = SRC / 'evidence/tranche-8-ns3-reference' / scenario / 'ns3-trace.csv.gz'
    item['NS3'] = native(ref)
    result[key] = item

payload = dict(input_archive_sha256=hashlib.sha256(INPUT.read_bytes()).hexdigest(),
               method='Unique applications reconstructed from MATLAB protocol_trace.csv and native app_send/nwk_delivery events. MATLAB application exports are then checked independently. Latency is pooled over delivered packets.',
               limitations=['Native unresolved applications are not classified as drops or finite-stop pending.',
                            'Only one campus seed is represented; equal seed numbers do not establish identical random draws.',
                            'Campus admission attempt trace is truncated; complete counters and complete application events support counts.'],
               results=result)
(OUT / 'independent-outcomes.json').write_text(json.dumps(payload, indent=2) + '\n')

rows = []
for source in result['campus']['T10']['flows']:
    row = {'Source': source}
    for model in ['T7', 'T10', 'NS3']:
        for field, value in result['campus'][model]['flows'][source].items():
            row[f'{model}_{field}'] = value
    row['T10_delivery_delta_vs_NS3_percent'] = 100 * (row['T10_delivered'] - row['NS3_delivered']) / row['NS3_delivered']
    rows.append(row)
with (OUT / 'campus-flows.csv').open('w', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(json.dumps({key: {model: data['total'] for model, data in item.items()} for key, item in result.items()}, indent=2))
