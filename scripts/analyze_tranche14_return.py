#!/usr/bin/env python3
"""Independently audit returned MATLAB DATA-ingress/ACK-edge diagnostics.

Closed owner archives and genuine native output are distinct evidence sources.
The checker reconstructs binary64 event order and ACK bitmap semantics without
running MATLAB or inventing a successful owner archive.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime
from decimal import Decimal
import json
import math
from pathlib import Path
import re
import struct
import zipfile

from analyze_tranche11_return import (
    all_files, candidate_snapshot, csv_rows, evidence_directory, integer,
    inventory, json_object, json_value, logical, number, record_map, records,
    require, safe_name, safe_path, selected_test_names, sha256, verify_bindings,
    verify_references, verify_sources, verify_tests,
)
from analyze_tranche12_return import verify_manifest

SCHEMA = "csr-matlab-tranche-14-validation-v1"
REVIEW_SCHEMA = "csr-matlab-tranche-14-return-review-v1"
PIN = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"
ENGINE_PIN = "6b5cd24ea80713ce16d88575869aedd6f432bdae"
CANDIDATE = "evidence/tranche-14-candidate.json"
BASELINE = "evidence/t13/source.json"
BASELINE_SHA = "205a86d0ae163b7a9fbeb13c2d003900af23df26c1e3be6cb0016505d4d55fc3"
OWNER_SHA = "82fb77cc5724f79f554e7c0d91169e79d89da5b47713064f003d380a2fd7d9b1"
PARENT_CANDIDATE_SHA = "3c9ba4a9d9029180b82611d71dcbb01ac6cd2ddc273ee6ecf6dec36ba81881e0"
CORE_BASELINE = "evidence/tranche-10-r2025a-accepted/owner/source_snapshot.json"
CORE_BASELINE_SHA = "9be444b0fb1ffbfe818cab86502a287b19e3da83467d210ef426ec3b19e183da"
REFERENCE = "evidence/tranche-14-edge-reference"


def verify_baseline(metadata, source_root, candidate):
    result = {}
    for label, name, digest, source_count, matlab_count, prefix in (
        ("tranche13", BASELINE, BASELINE_SHA, 271, 138, "Baseline"),
        ("accepted_core", CORE_BASELINE, CORE_BASELINE_SHA, 225, 124, "CoreBaseline"),
    ):
        require(candidate.get(prefix + "SourceSnapshot") == name, f"Unexpected {label} baseline path")
        key = "BaseSourceSnapshotSHA256" if prefix == "Baseline" else prefix + "SourceSnapshotSHA256"
        require(sha256(source_root / name) == candidate.get(key) == digest, f"{label} baseline snapshot binding mismatch")
        expected = record_map(json_value(source_root / name), label + " source")
        require(len(expected) == source_count and sum(name.endswith(".m") for name in expected) == matlab_count,
                f"{label} source membership/count changed")
        for relative, row in expected.items():
            require(sha256(safe_path(source_root, relative)) == row["sha256"], f"{label} baseline source changed: {relative}")
        for field, count in (("SourceFiles", source_count), ("MatlabFiles", matlab_count)):
            require(integer(metadata.get(prefix + field + "Verified"), field) == count and
                    integer(candidate.get(prefix + field + "Unchanged"), field) == count,
                    f"{label} baseline verification counts disagree")
        result[label] = {"source_files": source_count, "matlab_files": matlab_count,
                         "unchanged": True, "snapshot_sha256": digest}
    for field, name, digest in (("BaselineOwnerEvidence", "evidence/t13/owner.zip", OWNER_SHA),
                                 ("BaselineCandidate", "evidence/t13/candidate.json", PARENT_CANDIDATE_SHA)):
        require(candidate.get(field) == name and candidate.get(field + "SHA256") == digest
                and sha256(source_root / name) == digest, "Reviewed T13 owner/candidate provenance mismatch")
    # The parent owner archive must itself bind exactly this source snapshot and
    # candidate; a renamed unrelated archive is not an accepted source anchor.
    with evidence_directory(source_root / "evidence/t13/owner.zip") as owner:
        parent = json_object(owner / "metadata.json")
        require(parent.get("CandidateSHA256") == PARENT_CANDIDATE_SHA and
                parent.get("SourceSnapshotSHA256") == BASELINE_SHA and sha256(owner / "source.json") == BASELINE_SHA,
                "T13 source snapshot is not bound by the reviewed owner run")
    return result


def verify_run_identity(root, metadata, source_root, candidate):
    require(candidate.get("Schema") == "csr-tranche-14-candidate-v1" and candidate.get("Tranche") == 14
            and candidate.get("SourceCommit") == PIN, "Candidate schema or native source pin mismatch")
    require(metadata.get("Schema") == SCHEMA and metadata.get("Tranche") == 14 and metadata.get("Status") == "completed",
            "Return is not a completed T14 diagnostic")
    require(metadata.get("MATLABExecuted") is True and metadata.get("NativeExecuted") is False
            and metadata.get("SourceCommit") == PIN, "Owner MATLAB execution/source identity missing")
    runtime = metadata.get("Runtime")
    require(isinstance(runtime, dict) and runtime.get("Runtime") == "MATLAB" and runtime.get("DefaultBackend") == "portable"
            and isinstance(runtime.get("Version"), str) and runtime["Version"], "Missing or unsupported MATLAB runtime provenance")
    require(metadata.get("CandidateFile") == CANDIDATE and metadata.get("CandidateSHA256") == sha256(source_root / CANDIDATE),
            "Candidate identity mismatch")
    started, completed = (datetime.fromisoformat(metadata.get(field, "").replace("Z", "+00:00"))
                          for field in ("StartedUTC", "CompletedUTC"))
    require(started.tzinfo is not None and completed.tzinfo is not None and completed >= started,
            "Invalid owner execution timestamps")
    require(metadata.get("InventoryExcludedPaths") == ["metadata.json"] and metadata.get("EvidenceArchive") == "t14.zip",
            "Evidence inventory exclusion or archive identity changed")
    local = record_map(metadata.get("LocalArtifacts", []), "local artifacts", sizes=True, empty=True)
    require(all(name.endswith(".mat") and name not in all_files(root) for name in local), "Invalid local-only artifacts")
    require(metadata.get("FocusedGateExecuted") is True and metadata.get("DiagnosticOnly") is True
            and all(metadata.get(field) is False for field in ("FullAcceptanceGateExecuted", "AcceptanceEstablished", "NumericalParityEstablished")),
            "Focused diagnostic scope or acceptance claim contradicts authorized gate")
    return runtime



def hex64(value):
    """Canonical network-order IEEE-754 binary64, shared with MATLAB num2hex."""
    return struct.pack('>d', value).hex()


def decode_hex(value, label):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{16}', value),
            f'{label}: expected canonical 16-digit lowercase binary64 hex')
    result = struct.unpack('>d', bytes.fromhex(value))[0]
    require(math.isfinite(result) and result >= 0 and not (result == 0 and value[0] == '8'),
            f'{label}: nonfinite, negative or negative-zero event time')
    return result


def rounded_ns(value):
    """All experiment times are nonnegative; MATLAB round uses positive half-up."""
    return math.floor(value * 1_000_000_000 + .5)


def exact_uint(value, label, bits=64):
    require(isinstance(value, str) and re.fullmatch('0|[1-9][0-9]*', value),
            f'{label}: expected exact unsigned decimal text')
    result = int(value)
    require(result < 2**bits, f'{label}: exceeds uint{bits}')
    return result


CASES = ('tie_early', 'tie_late', 'before', 'after', 'continuous', 'quantized')
EVENT_FIELDS = ('case','order','phase','time_ns','time_seconds_dec','time_seconds_hex','scheduler_id',
                'node','peer','kind','app_source','app_id','hop_seq','ack_bits','dack_bits','ack_queue','data_queue','transmissions')
BOUNDARY_FIELDS = ('case','transport_mode','late_insertion','wire_payload_bytes','segment_count','tx_time_ns',
    'tx_seconds_dec','tx_seconds_hex','duration_ns','duration_seconds_dec','duration_seconds_hex','tick_time_ns',
    'tick_seconds_dec','tick_seconds_hex','arm_time_ns','arm_seconds_dec','arm_seconds_hex','arrival_time_ns',
    'arrival_seconds_dec','arrival_seconds_hex','arrival_minus_tick_seconds_dec','arrival_minus_tick_seconds_hex','ingress_event_id')
DRAW_FIELDS = ('case','node','ordinal','time_ns','min','max','draw','resolved','purpose')
USAGE_FIELDS = ('case','node','supplied','consumed','unused')
SCHEDULER_FIELDS = ('case','order','operation','event_id','parent_id','observed_seconds','observed_hex',
                    'scheduled_seconds','scheduled_hex','callback','was_pending')
CHECK_FIELDS = ('case','checkpoint','node','actual','expected','pass')
OUTPUT_FIELDS = {'events': EVENT_FIELDS, 'boundary': BOUNDARY_FIELDS, 'draws': DRAW_FIELDS,
                 'usage': USAGE_FIELDS, 'scheduler': SCHEDULER_FIELDS}
INPUT_HASHES = {
    'plan.json': '7e7ec33e946cb1fb315b0990813a2102d18c64b6f966b46cee021f8f273b61b9',
    'cases.csv': 'df29719730e7022f7bb8e912e0863c2109bae300fb75021d4eb8d8bb2a13262f',
    'draws.csv': '5aff5bb3467c36370cc0c2617724022f69fc87d1601fee65f34fb06bef0efeb8'}


def verify_plan(source_root, candidate):
    require(candidate.get('EdgePlan') == 'scenarios/edge/plan.json', 'Unexpected edge plan path')
    for name, digest in INPUT_HASHES.items():
        require(sha256(source_root / 'scenarios/edge' / name) == digest, f'Frozen edge input changed: {name}')
    require(candidate.get('EdgePlanSHA256') == INPUT_HASHES['plan.json'], 'Candidate edge plan hash mismatch')
    plan = json_object(source_root / candidate['EdgePlan'])
    require(plan.get('schema') == 'csr-tranche14-edge-input-v1' and plan.get('source_pin') == PIN and
            plan.get('engine_pin') == ENGINE_PIN and plan.get('cases') == list(CASES), 'Edge plan identity mismatch')
    require(plan.get('events_schema') == list(EVENT_FIELDS) and plan.get('boundary_schema') == list(BOUNDARY_FIELDS),
            'Edge trace schema mismatch')
    return plan


def full_time(decimal_text, hex_text, label, *, signed=False):
    require(isinstance(hex_text, str) and re.fullmatch('[0-9a-f]{16}', hex_text),
            f'{label}: malformed binary64 hex')
    value = struct.unpack('>d', bytes.fromhex(hex_text))[0]
    require(math.isfinite(value) and (signed or value >= 0) and not (value == 0 and hex_text[0] == '8'),
            f'{label}: invalid binary64 value')
    observed = number(decimal_text, label)
    require(hex64(float(observed)) == hex_text, f'{label}: decimal text does not round-trip to hex')
    return value


def validate_scheduler(rows, events, boundaries, *, label):
    """Replay observed insertion/cancel/execute API operations against FIFO heap order."""
    require(rows and [row['case'] for row in rows if row['order'] == '1'] == list(CASES),
            f'{label}: missing or reordered scheduler case')
    require([CASES.index(row['case']) for row in rows] == sorted(CASES.index(row['case']) for row in rows),
            f'{label}: scheduler case rows interleaved')
    executed = {}
    scheduled = {}
    for case in CASES:
        own = [row for row in rows if row['case'] == case]
        active = {}; next_id = 1; previous_time = 0.0; current_id = 0
        for order, row in enumerate(own, 1):
            require(tuple(row) == SCHEDULER_FIELDS and integer(row['order'], 'scheduler order', 1) == order,
                    f'{label}: missing or duplicate scheduler order')
            event_id = exact_uint(row['event_id'], 'scheduler ID')
            parent = exact_uint(row['parent_id'], 'scheduler parent')
            observed = full_time(row['observed_seconds'], row['observed_hex'], 'scheduler observed')
            due = full_time(row['scheduled_seconds'], row['scheduled_hex'], 'scheduler due')
            pending = logical(row['was_pending'], 'was_pending')
            require(previous_time <= observed <= 4, f'{label}: reversed or outside-run scheduler observation')
            previous_time = observed
            operation = row['operation']
            require(operation in ('schedule', 'execute', 'cancel'), f'{label}: unknown scheduler operation')
            if operation == 'execute':
                require(event_id in active and pending and parent == 0, f'{label}: unowned or repeated execution')
                require(min((time, identity) for identity, time in active.items()) == (observed, event_id)
                        and due == observed, f'{label}: execution violates actual binary64/FIFO priority')
                require(scheduled[case, event_id]['callback'] == row['callback'], f'{label}: callback identity changed')
                del active[event_id]; current_id = event_id
                executed[case, event_id] = row
            else:
                if parent:
                    require((case, parent) in executed and parent == current_id and
                            executed[case, parent]['observed_hex'] == row['observed_hex'],
                            f'{label}: scheduler parent is not current callback')
                if operation == 'schedule':
                    require(event_id == next_id and due >= observed and pending and row['callback'],
                            f'{label}: insertion identity/time invalid')
                    next_id += 1; active[event_id] = due; scheduled[case, event_id] = row
                else:
                    require(pending == (event_id in active) and row['callback'] == '' and due == observed,
                            f'{label}: cancellation status/time contradicts pending event')
                    active.pop(event_id, None)
        require(all(time > 4 for time in active.values()), f'{label}: due callback omitted at stop')
    require(all(row['case'] in CASES for row in rows), f'{label}: unknown scheduler case')
    for row in events:
        key = row['case'], exact_uint(row['scheduler_id'], 'event scheduler ID')
        require(key in executed and row['time_seconds_hex'] == executed[key]['observed_hex'],
                f'{label}: protocol event lacks its actual executing callback/time')
    for row in boundaries:
        key = row['case'], exact_uint(row['ingress_event_id'], 'boundary ingress ID')
        require(key in scheduled and key in executed and
                row['arrival_seconds_hex'] == scheduled[key]['scheduled_hex'] == executed[key]['observed_hex'] and
                row['arm_seconds_hex'] == scheduled[key]['observed_hex'],
                f'{label}: boundary arm/arrival not bound to real scheduler operations')
        ingress = [event for event in events if event['case'] == row['case'] and event['phase'] == 'ingress_before']
        require(ingress and all(exact_uint(event['scheduler_id'], 'ingress callback') == key[1] for event in ingress),
                f'{label}: boundary ingress callback does not own actual protocol ingress')
    return {'operations': len(rows), 'scheduled': len(scheduled), 'executed': len(executed)}


def validate_boundaries(rows, *, matlab):
    require([row['case'] for row in rows] == list(CASES), 'Boundary cases missing, duplicate or reordered')
    output = {}
    for row in rows:
        require(tuple(row) == BOUNDARY_FIELDS, 'Unexpected boundary schema')
        case = row['case']
        mode = 'continuous' if case == 'continuous' else 'local_ns' if case == 'quantized' else 'target'
        require(row['transport_mode'] == mode and logical(row['late_insertion'], 'late insertion') == (case == 'tie_late'),
                'Boundary transport mode/insertion scope changed')
        require(integer(row['wire_payload_bytes'], 'wire bytes') == 89 and integer(row['segment_count'], 'segments') == 2,
                'Boundary actual aggregate is not ACK41 plus DATA48')
        values = {}
        for field in ('tx','duration','tick','arm','arrival'):
            value = full_time(row[field + '_seconds_dec'], row[field + '_seconds_hex'], field)
            ns_field = field + ('_ns' if field == 'duration' else '_time_ns')
            require(integer(row[ns_field], ns_field) == rounded_ns(value), 'Boundary rounded nanoseconds contradict full precision')
            values[field] = value
        require(values['tx'] == 3.12 and values['tick'] == 3.144961, 'Actual TX/ACK opportunity shifted from explicit fixture epochs')
        # Native PHY resolves each modeled frame duration to integer Time;
        # MATLAB keeps its original binary64 arithmetic. Neither is rewritten.
        duration = (104 + 48) / 4 * .000510 + (89 * 8 + 32) / (4 / .000030)
        target_duration = duration if matlab else rounded_ns(duration) / 1e9
        require(hex64(values['duration']) == hex64(target_duration), 'Modeled aggregate airtime changed')
        expected_arm = 3_144_960_998 / 1e9 if case == 'tie_late' else values['tx']
        require(values['arm'] == expected_arm, 'Ingress armed at wrong callback time')
        if case == 'continuous' and matlab:
            arrival = (values['tx'] + duration) + .000001
        elif mode in ('continuous', 'local_ns'):
            arrival = (rounded_ns(values['tx']) + rounded_ns(duration) + 1000) / 1e9
        else:
            arrival = (3_144_961_000 + {'before': -1, 'after': 1}.get(case, 0)) / 1e9
        require(hex64(values['arrival']) == hex64(arrival), 'Boundary arrival contradicts prescribed local transport arithmetic')
        delta = full_time(row['arrival_minus_tick_seconds_dec'], row['arrival_minus_tick_seconds_hex'], 'arrival minus tick', signed=True)
        require(hex64(delta) == hex64(values['arrival'] - values['tick']), 'Boundary delta contradicts full-precision timestamps')
        require(exact_uint(row['ingress_event_id'], 'ingress ID') > 0, 'Missing actual scheduled ingress ID')
        output[case] = values | {'delta': delta}
    return output


def validate_draws(draws, usage):
    keys = [(row['case'], integer(row['node'], 'usage node')) for row in usage]
    require(keys == [(case, node) for case in CASES for node in (1,4,5)], 'Draw usage inventory missing/reordered')
    consumed = Counter()
    for row in draws:
        require(tuple(row) == DRAW_FIELDS and row['case'] in CASES and integer(row['node'], 'draw node') in (1,4,5),
                'Unknown draw schema/case/node')
        key = row['case'], integer(row['node'], 'draw node')
        consumed[key] += 1
        require(integer(row['ordinal'], 'draw ordinal', 1) == consumed[key] <= 64 and
                (integer(row['min'], 'minimum'), integer(row['max'], 'maximum'), integer(row['draw'], 'draw')) == (0,31,0),
                'Draw identity/support differs from prescribed tape')
        require(integer(row['time_ns'], 'draw time') <= 4_000_000_000 and
                0 <= integer(row['resolved'], 'resolved') <= 31 and row['purpose'] in ('prepare','advertise'),
                'Unresolved or invalid draw observation')
    for row in usage:
        key = row['case'], integer(row['node'], 'usage node')
        require(integer(row['consumed'], 'consumed') == consumed[key] and integer(row['supplied'], 'supplied') == 64 and
                integer(row['unused'], 'unused') == 64 - consumed[key], 'Draw suffix accounting disagrees')
    return {'consumed': len(draws), 'supplied': 1152, 'unused': 1152 - len(draws)}



def validate_events(rows, boundaries, *, matlab, label):
    require(rows, f'{label}: empty event trace')
    times = validate_boundaries(boundaries, matlab=matlab)
    require([row['case'] for row in rows if row['order'] == '1'] == list(CASES), f'{label}: incomplete event case order')
    require(all(row['case'] in CASES for row in rows) and [CASES.index(row['case']) for row in rows] ==
            sorted(CASES.index(row['case']) for row in rows), f'{label}: event case rows interleaved or unknown')
    reports = []
    for case in CASES:
        own = [row for row in rows if row['case'] == case]
        previous_time = 0.0
        for order, row in enumerate(own, 1):
            require(tuple(row) == EVENT_FIELDS and integer(row['order'], 'event order', 1) == order,
                    f'{label}: duplicate/missing event order')
            time = full_time(row['time_seconds_dec'], row['time_seconds_hex'], 'event time')
            require(previous_time <= time <= 4 and integer(row['time_ns'], 'event time ns') == rounded_ns(time),
                    f'{label}: event time unordered or rounded display contradicts binary64')
            previous_time = time
            require(row['phase'] in ('prime_before','prime_after','aggregate_tx','ingress_before','ingress_after',
                    'deliver','ack_tx','feedback_ingress','settled'), f'{label}: unknown protocol event phase')
            require(integer(row['node'], 'event node') in (1,4,5) and integer(row['peer'], 'event peer') in (0,1,4,5),
                    f'{label}: invalid protocol endpoint')
            require(row['kind'] in ('ACK','DATA','NONE'), f'{label}: invalid frame kind')
            for field in ('scheduler_id','app_id','ack_bits','dack_bits'):
                exact_uint(row[field], field)
            for field in ('app_source','hop_seq','ack_queue','data_queue','transmissions'):
                integer(row[field], field)
            require(integer(row['hop_seq'], 'HOP seq') <= 65535, f'{label}: HOP sequence outside uint16')
            require(row['dack_bits'] == '0', f'{label}: unsolicited DACK in gateway boundary experiment')
            if matlab:
                require(exact_uint(row['scheduler_id'], 'scheduler ID') > 0, f'{label}: event lacks executing scheduler ID')
            else:
                require(row['scheduler_id'] == '0', f'{label}: fabricated native callback UID')
        def selected(phase, node=None):
            return [row for row in own if row['phase'] == phase and (node is None or row['node'] == str(node))]
        prime_before, prime_after = selected('prime_before'), selected('prime_after')
        require([row['app_id'] for row in prime_before] == ['1','2'] == [row['app_id'] for row in prime_after],
                f'{label}: initial receive window not established by exactly DATA1/2')
        for row in prime_before + prime_after:
            require((row['node'],row['peer'],row['kind'],row['app_source'],row['time_ns']) == ('1','5','DATA','5','2832961000')
                    and row['hop_seq'] == row['app_id'] and row['ack_bits'] == '0', f'{label}: invalid priming DATA')
        for before, after in zip(prime_before, prime_after):
            require(int(before['order']) < int(after['order']) and after['ack_queue'] == '1', f'{label}: priming did not queue actual feedback')
        aggregate = selected('aggregate_tx')
        require(len(aggregate) == 6 and [(row['peer'],row['kind'],row['app_source'],row['app_id'],row['hop_seq'],row['ack_bits'])
                for row in aggregate[:2]] == [('4','ACK','0','0','4','15'), ('1','DATA','5','3','3','0')],
                f'{label}: actual mixed aggregate changed, reordered or duplicated')
        require(all(row['node'] == '5' and row['time_ns'] == '3120000000' and row['time_seconds_hex'] == hex64(times[case]['tx'])
                    for row in aggregate[:2]), f'{label}: mixed aggregate TX not at actual prescribed opportunity')
        before, after = selected('ingress_before'), selected('ingress_after')
        require(len(before) == len(after) == 1 and before[0]['node'] == after[0]['node'] == '1',
                f'{label}: primary DATA ingress missing, duplicate or wrong receiver')
        for incoming, outgoing, source in zip(before, after, aggregate[1:2]):
            for row in (incoming, outgoing):
                require(row['peer'] == '5' and row['time_seconds_hex'] == hex64(times[case]['arrival']) and
                        all(row[field] == source[field] for field in ('kind','app_source','app_id','hop_seq','ack_bits','dack_bits')),
                        f'{label}: actual ingress content/time differs from cached transmitted segment')
            require(int(incoming['order']) < int(outgoing['order']), f'{label}: ingress after precedes before')
        delivery = selected('deliver')
        require([(row['node'],row['peer'],row['app_source'],row['app_id']) for row in delivery] ==
                [('1','5','5',str(identity)) for identity in (1,2,3)], f'{label}: application delivery identity not conserved')
        for row, incoming, outgoing in zip(delivery, prime_before + before[-1:], prime_after + after[-1:]):
            require(int(incoming['order']) < int(row['order']) < int(outgoing['order']) and
                    row['time_seconds_hex'] == incoming['time_seconds_hex'], f'{label}: delivery is not within real DATA receive callback')
        acks = selected('ack_tx', 1)
        require(acks and acks[0]['time_ns'] == '3144961000' and acks[0]['time_seconds_hex'] == hex64(times[case]['tick']), f'{label}: first gateway ACK opportunity shifted')
        data_order = int(before[-1]['order'])
        first_includes = int(acks[0]['order']) > data_order
        if case in ('before','tie_early','quantized'):
            require(first_includes, f'{label}: early control failed DATA-before-ACK order')
        if case in ('after','tie_late'):
            require(not first_includes, f'{label}: late control failed ACK-before-DATA order')
        for row in acks:
            includes = int(row['order']) > data_order
            require((row['peer'],row['kind'],row['app_source'],row['app_id'],row['hop_seq'],row['ack_bits']) ==
                    ('5','ACK','0','0','3' if includes else '2','7' if includes else '3'),
                    f'{label}: transmitted cumulative ACK contradicts actual receive-window order')
        require(len(acks) == (5 if first_includes else 6), f'{label}: cumulative ACK replacement resend-count policy changed')
        companion = [row for row in aggregate if row['kind'] == 'ACK']
        require(len(companion) == 5 and all((row['node'],row['peer'],row['kind'],row['hop_seq'],row['ack_bits']) == ('5','4','ACK','4','15')
                for row in companion), f'{label}: companion ACK repeat inventory changed')
        require(all(row['node'] == '1' for row in selected('ack_tx')), f'{label}: non-gateway ACK logged as gateway emission')
        feedback = selected('feedback_ingress')
        require(len(feedback) == len(acks) + len(companion), f'{label}: feedback transport inventory incomplete')
        expected_feedback = Counter((row['peer'],row['node'],row['hop_seq'],row['ack_bits']) for row in acks + companion)
        actual_feedback = Counter((row['node'],row['peer'],row['hop_seq'],row['ack_bits']) for row in feedback)
        require(actual_feedback == expected_feedback and all(row['kind'] == 'ACK' and row['app_source'] == row['app_id'] == '0'
                    for row in feedback), f'{label}: transmitted feedback lacks exactly one matching ingress')
        primary_feedback = next(row for row in feedback if row['node'] == '4')
        require(primary_feedback['time_seconds_hex'] == hex64(times[case]['arrival']) and
                int(primary_feedback['order']) < int(before[0]['order']), f'{label}: mixed companion ACK reordered after DATA')
        ack_duration = (104 + 48) / 4 * .000510 + (41 * 8 + 32) / (4 / .000030)
        for sender, receiver, tx_rows in ((1,5,acks),(5,4,companion)):
            receive_rows = [row for row in feedback if row['node'] == str(receiver)]
            for index, (sent, received) in enumerate(zip(tx_rows, receive_rows)):
                tx = full_time(sent['time_seconds_dec'], sent['time_seconds_hex'], 'feedback TX')
                if sender == 5 and index == 0:
                    arrival = times[case]['arrival']
                elif matlab and case != 'quantized':
                    arrival = (tx + ack_duration) + .000001
                else:
                    arrival = (integer(sent['time_ns'], 'ACK TX ns') + rounded_ns(ack_duration) + 1000) / 1e9
                require(received['time_seconds_hex'] == hex64(arrival) and int(received['order']) > int(sent['order']),
                        f'{label}: feedback arrival contradicts actual TX plus unchanged airtime transport')
                require(integer(sent['transmissions'], 'TX count') == index,
                        f'{label}: ACK transmit callback count contradicts actual emission order')
        final = selected('settled')
        require([row['node'] for row in final] == ['1','4','5'] and all(row['time_ns'] == '4000000000'
                and row['ack_queue'] == row['data_queue'] == '0' for row in final), f'{label}: final queues fail to drain')
        require([integer(row['transmissions'], 'final TX count') for row in final] == [len(acks),0,5],
                f'{label}: final transmission counters disagree with real emission inventory')
        reports.append({'case': case, 'delivered': 3, 'first_ack_sequence': int(acks[0]['hop_seq']),
                        'first_ack_bits': acks[0]['ack_bits'], 'gateway_ack_transmissions': len(acks),
                        'source_ack_transmissions': 5, 'source_data_transmissions': 1,
                        'data_precedes_first_ack': first_includes, 'final_queues_clear': True})
    require(all(row['case'] in CASES for row in rows), f'{label}: unknown event case')
    return reports



def compare_cases(actual, native, fields, family):
    """Exact per-case row comparisons; numerical decimals never pass through float."""
    output = {'family':family, 'fields':list(fields), 'actual_rows':len(actual), 'reference_rows':len(native),
              'compared_rows':0, 'unmatched_rows':0, 'cases':[], 'differences':[]}
    text = {'case','phase','kind','purpose','transport_mode'}
    for case in CASES:
        left = [row for row in actual if row['case'] == case]
        right = [row for row in native if row['case'] == case]
        differences = []
        for index in range(max(len(left),len(right))):
            a = left[index] if index < len(left) else None
            b = right[index] if index < len(right) else None
            unequal = ['missing_row'] if a is None or b is None else []
            if a is not None and b is not None:
                for field in fields:
                    if field in text or field.endswith('_hex'):
                        equal = a[field] == b[field]
                    elif field == 'late_insertion':
                        equal = logical(a[field],field) == logical(b[field],field)
                    else:
                        equal = number(a[field],field) == number(b[field],field)
                    if not equal:
                        unequal.append(field)
            if unequal:
                differences.append({'case':case,'row':index+1,'fields':unequal,'matlab':a,'ns3':b})
        output['cases'].append({'case':case,'actual_rows':len(left),'reference_rows':len(right),'unmatched_rows':len(differences)})
        output['compared_rows'] += max(len(left),len(right)); output['unmatched_rows'] += len(differences)
        output['differences'].extend(differences)
    output['matches_native'] = output['unmatched_rows'] == 0
    return output


def verify_comparison(claim, actual):
    require(isinstance(claim,dict) and claim.get('ReferencePresent') is True and claim.get('SchemaMatches') is True,
            'Comparison reference/schema claim differs')
    for key,target in (('ActualRows','actual_rows'),('ReferenceRows','reference_rows'),
                       ('ComparedRows','compared_rows'),('UnmatchedCount','unmatched_rows')):
        require(integer(claim.get(key),key) == actual[target], 'Comparison row counts disagree')
    require(claim.get('ComparedFields') == actual['fields'], 'Comparison field scope changed')
    cases = records(claim.get('Cases'),'comparison cases')
    require(len(cases) == 6, 'Comparison case inventory incomplete')
    for row, expected in zip(cases,actual['cases']):
        require(row.get('Case') == expected['case'] and all(integer(row.get(key),key) == expected[target]
                for key,target in (('ActualRows','actual_rows'),('ReferenceRows','reference_rows'),('UnmatchedCount','unmatched_rows'))),
                'Comparison per-case observations disagree')


def verify_owner_checks(rows, events, boundaries, results):
    """Validate all check identities; reconcile observable values with raw tables.

Radio selections and internal window/custody readings occur only in check.csv;
these are explicitly reported internal observations, bound to reviewed source.
"""
    targets = []
    for case, report in zip(CASES,results):
        own = [row for row in events if row['case']==case]
        boundary = next(row for row in boundaries if row['case']==case)
        first = next(row for row in own if row['phase']=='ack_tx')
        final = {int(row['node']):row for row in own if row['phase']=='settled'}
        primary = [row for row in own if row['phase']=='aggregate_tx'][:2]
        count = report['gateway_ack_transmissions']; bits=int(report['first_ack_bits']); seq=report['first_ack_sequence']
        pairs = [('case_completed',0,1),('primary_aggregate_count',5,1),('primary_wire_bytes',5,89),
            ('primary_segment_count',5,2),('primary_tx_time_ns',5,3120000000),('primary_rate_kbps',5,128),
            ('primary_power_dbm',5,33),('primary_short_preamble',5,1),('primary_selected_members',5,1),
            ('source_data_transmissions',5,1),('gateway_deliveries',1,3),('gateway_identity_set',1,1),
            ('first_ack_bits',1,bits),('first_ack_sequence',1,seq),('first_ack_time_ns',1,3144961000),
            ('primed_window_sequence',1,2),('primed_window_bits',1,3),('gateway_ack_transmissions',1,count),
            ('boundary_row_count',0,1),('ingress_precedes_first_ack',1,int(report['data_precedes_first_ack'])),
            ('controlled_case_order',1,int(report['data_precedes_first_ack'])),('trace_decimal_hex_roundtrip',0,1),('scheduler_execution_identity',0,1),
            ('draw_usage_conservation',0,1),('raw_support_and_resolution',0,1),
            ('final_window_sequence',1,3),('final_window_bits',1,7),('final_window_dack_bits',1,0)]
        for node in (1,4,5):
            pairs.extend([('final_ack_queue',node,int(final[node]['ack_queue'])),
                          ('final_data_queue',node,int(final[node]['data_queue'])),('final_sender_custody',node,0)])
        targets.extend({'case':case,'checkpoint':key,'node':node,'actual':value,'expected':value,'pass':True}
                       for key,node,value in pairs)
    require(len(rows)==len(targets), 'Owner checkpoint inventory incomplete')
    for row,target in zip(rows,targets):
        require(tuple(row)==CHECK_FIELDS and (row['case'],row['checkpoint'],integer(row['node'],'check node')) ==
                (target['case'],target['checkpoint'],target['node']), 'Owner checkpoint identity missing/reordered')
        require(integer(row['actual'],'check actual',-1)==target['actual'] and integer(row['expected'],'check expected',-1)==target['expected']
                and logical(row['pass'],'check pass'), 'Owner checkpoint contradicts independent observations or fixed contract')
    return len(targets)


def verify_boundary(root, metadata, source_root, candidate):
    plan = verify_plan(source_root,candidate)
    require(metadata.get('BoundaryDirectory')=='edge','Unexpected boundary output directory')
    native, provenance = verify_native(source_root,candidate,plan)
    directory=root/'edge'
    actual={name:csv_rows(directory/(name+'.csv'),fields) for name,fields in OUTPUT_FIELDS.items()}
    reports=validate_events(actual['events'],actual['boundary'],matlab=True,label='MATLAB')
    scheduling=validate_scheduler(actual['scheduler'],actual['events'],actual['boundary'],label='MATLAB')
    draws=validate_draws(actual['draws'],actual['usage'])
    check_count=verify_owner_checks(csv_rows(directory/'check.csv',CHECK_FIELDS),actual['events'],actual['boundary'],reports)
    comparison_fields={
        'EventComparison':('events',[name for name in EVENT_FIELDS if name not in ('time_seconds_dec','time_seconds_hex','scheduler_id')]),
        'BoundaryComparison':('boundary',[name for name in BOUNDARY_FIELDS if not name.endswith('_seconds_dec') and name!='ingress_event_id']),
        'FullPrecisionComparison':('events',['case','order','phase','time_seconds_hex']),
        'DrawComparison':('draws',list(DRAW_FIELDS)), 'UsageComparison':('usage',list(USAGE_FIELDS))}
    comparisons={name:compare_cases(actual[family],native[family],fields,name) for name,(family,fields) in comparison_fields.items()}
    unmatched=sum(row['unmatched_rows'] for row in comparisons.values())
    shared=all(row['unmatched_rows']==0 for row in comparisons['EventComparison']['cases'] if row['case']!='continuous')
    continuous=next(row for row in actual['boundary'] if row['case']=='continuous')
    continuous_report=next(row for row in reports if row['case']=='continuous')
    delta=full_time(continuous['arrival_minus_tick_seconds_dec'],continuous['arrival_minus_tick_seconds_hex'],'continuous delta',signed=True)
    expected_residual=delta==math.ulp(3.144961) and continuous_report['first_ack_bits']=='3'
    summary=json_object(directory/'summary.json')
    expected={'Schema':'csr-tranche14-ack-edge-contract-v1','DiagnosticCompleted':True,'Passed':True,'MatchesNative':unmatched==0,
        'SharedIntegerMatchesNative':shared,'ExpectedContinuousResidual':expected_residual,'FullPrecisionCompared':True,
        'DecimalRoundTripRequired':True,'GlobalClockChanged':False,'TransportQuantizationScope':'quantized case fixture transport only',
        'SchedulerIdScope':'Actual underlying EventScheduler IDs; local causality only, no cross-runtime ID equality',
        'TimeToleranceNanoseconds':0,'Scope':plan['scope'],'Runtime':metadata['Runtime']['Version']}
    for key,value in expected.items():
        require(summary.get(key)==value and (type(value) is not bool or type(summary.get(key)) is bool),f'Boundary summary {key} disagrees')
    for key,value in (('CaseCount',6),('EventCount',len(actual['events'])),('BoundaryCount',6),('DrawCount',len(actual['draws'])),
                      ('SchedulerRowCount',len(actual['scheduler'])),('CheckpointCount',check_count),('FailedCount',0),('UnmatchedCount',unmatched)):
        require(integer(summary.get(key),key)==value,f'Boundary summary {key} count disagrees')
    verify_bindings(summary.get('InputBindings'),source_root,['scenarios/edge/'+name for name in INPUT_HASHES],'Edge inputs')
    verify_bindings(summary.get('ReferenceBindings'),source_root,[REFERENCE+'/'+name+'.csv' for name in ('events','boundary','draws','usage')],'Edge reference')
    claims=records(summary.get('CaseResults'),'boundary case results')
    require([row.get('Case') for row in claims]==list(CASES),'Boundary case results missing or reordered')
    for row,result in zip(claims,reports):
        require(row.get('Completed') is True and row.get('Passed') is True and row.get('ErrorIdentifier')==row.get('ErrorMessage')=='',
                'Boundary case incomplete or failed')
        for key,name in (('FirstAckBits','first_ack_bits'),('FirstAckSequence','first_ack_sequence'),
                          ('GatewayAckTransmissions','gateway_ack_transmissions'),('Delivered','delivered'),('SourceDataTransmissions','source_data_transmissions')):
            require(integer(row.get(key),key)==int(result[name]),'Boundary per-case outcome contradicts actual events')
        boundary=next(value for value in actual['boundary'] if value['case']==result['case'])
        first=next(value for value in actual['events'] if value['case']==result['case'] and value['phase']=='ack_tx')
        require(integer(row.get('IngressEventId'),'ingress ID')==exact_uint(boundary['ingress_event_id'],'ingress ID') and
                integer(row.get('FirstAckEventId'),'ACK ID')==exact_uint(first['scheduler_id'],'ACK ID') and
                integer(row.get('CheckpointCount'),'case checks')==37,'Case scheduler/check identities disagree')
    for name,result in comparisons.items(): verify_comparison(summary.get(name),result)
    for key,value in (('BoundaryCaseCount',6),('BoundaryEventCount',len(actual['events'])),
                      ('BoundaryCheckpointCount',check_count),('BoundaryUnmatchedCount',unmatched)):
        require(integer(metadata.get(key),key)==value,f'{key} metadata disagrees')
    require(metadata.get('BoundaryCompleted') is True and metadata.get('BoundaryPassed') is True and
            metadata.get('BoundaryMatchesNative') is (unmatched==0),'Boundary completion/match metadata disagrees')
    return {'structural_complete':True,'matches_native':unmatched==0,'shared_integer_matches_native':shared,
            'expected_continuous_residual':expected_residual,'unmatched_rows':unmatched,'case_count':6,
            'event_count':len(actual['events']),'checkpoint_count':check_count,'cases':reports,'comparisons':comparisons,
            'scheduler':scheduling,'draws':draws,'native_provenance':provenance,'scope':plan['scope'],
            'reported_internal_observations':'Radio/preamble selections and final internal receive-window/custody readings are reported in check.csv; '
                'ACK sequence/bitmap, deliveries, queue drain, timing, scheduling and transport are independently reconciled with raw event tables. '
                'No source HOP custody or admission improvement is inferred from this fixture.'}



def native_checks(events):
    targets=[]
    for case in CASES:
        own=[row for row in events if row['case']==case]
        acks=[row for row in own if row['phase']=='ack_tx']
        seq=int(acks[0]['hop_seq']); bits=int(acks[0]['ack_bits'])
        values=[('primed_deliveries',1,2),('primed_ack_queue',1,1),('mixed_tx_ns',5,3120000000),
                ('mixed_bytes',5,89),('mixed_segments',5,2),('mixed_duration_ns',5,24960000),
                ('mixed_rate',5,128),('mixed_power_tenths',5,330),('mixed_preamble_short',5,0),
                ('mixed_aggregate_count',5,1),('mixed_ingress_count',5,1),('delivered_count',1,3),
                ('delivered_id_1',1,1),('delivered_id_2',1,1),('delivered_id_3',1,1),
                ('gateway_first_ack_ns',1,3144961000),('gateway_first_ack_seq',1,seq),
                ('gateway_first_ack_bits',1,bits),('gateway_ack_count',1,len(acks)),
                ('gateway_last_ack_seq',1,3),('gateway_last_ack_bits',1,7)]
        for node in (1,4,5):
            values.extend((name,node,0) for name in ('final_ack_queue','final_data_queue','final_hop_pending','final_resend_queue','final_dack_holds'))
        values.append(('final_nwk_queue',1,0))
        targets.extend((case,name,node,value) for name,node,value in values)
    return targets


def verify_native(source_root,candidate,plan):
    require(candidate.get('EdgeReferenceManifest')==REFERENCE+'/manifest.json','Unexpected native edge reference path')
    directory,manifest=verify_manifest(source_root,candidate['EdgeReferenceManifest'],candidate.get('EdgeReferenceManifestSHA256'),
                                      'csr-tranche14-edge-reference-files-v1')
    summary=json_object(directory/'summary.json')
    for key,value in {'schema':'csr-tranche14-edge-native-v1','status':'passed','source_pin':PIN,'engine_pin':ENGINE_PIN,
        'native_executed':True,'matlab_executed':False,'production_source_unchanged':True,'engine_source_unchanged':True,
        'global_scheduler_changed':False,'native_time_resolution':'integer nanoseconds','scope':plan['scope'],
        'numerical_parity_established':False,'full_network_acceptance_established':False}.items():
        require(summary.get(key)==value and (type(value) is not bool or type(summary.get(key)) is bool),f'Native {key} provenance differs')
    build_path='evidence/tranche-14-native-build.json'
    require(candidate.get('NativeBuildManifest')==summary.get('native_build_manifest')==build_path and
            candidate.get('NativeBuildManifestSHA256')==summary.get('native_build_manifest_sha256')==sha256(source_root/build_path),
            'Fresh native build binding mismatch')
    build=json_object(source_root/build_path)
    for key,value in {'schema':'csr-tranche14-native-control-build-v1','status':'passed','source_commit':PIN,'engine_commit':ENGINE_PIN,
        'engine_rebuilt':True,'reused_historical_libraries':False,'historical_libraries_byte_identity_claimed':False,
        'csr_tracked_sources_unchanged':True,'engine_tracked_sources_unchanged':True,'matlab_executed':False,
        'build_profile':'Debug','assertions':True,'logging':True,'native_control_checks':327}.items():
        require(build.get(key)==value and (type(value) is not bool or type(build.get(key)) is bool),f'Fresh native build {key} differs')
    modules={'csr','spectrum','buildings','propagation','mobility','antenna','network','stats','core'}
    libraries=records(build.get('libraries'),'fresh libraries')
    names=[Path(row['path']).name.removeprefix('libns3-dev-').removesuffix('-debug.so') for row in libraries]
    require(len(libraries)==9 and set(names)==modules and all(integer(row.get('bytes'),'library bytes',1)>1000 and
                re.fullmatch('[0-9a-f]{64}',row.get('sha256','')) for row in libraries), 'Fresh library inventory malformed or empty')
    require(summary.get('shared_libraries')=={name:row['sha256'] for name,row in zip(names,libraries)},'Native run did not use recorded fresh libraries')
    models=record_map(build.get('module_files'),'native model sources')
    require(summary.get('model_sources')=={Path(name).name:row['sha256'] for name,row in models.items()},'Native model source closure changed')
    logs=build.get('artifact_files')
    require(isinstance(logs,dict) and logs and set(all_files(source_root/'evidence/tranche-14-native-build'))==set(logs),
            'Native build log inventory incomplete')
    for name,digest in logs.items():
        require(sha256(safe_path(source_root/'evidence/tranche-14-native-build',name))==digest,'Native build log hash mismatch')
    require(isinstance(build.get('records'),dict) and all(integer(row.get('exit_code'),'build command exit')==0
            for row in build['records'].values()),'Native configure/build command failed')
    commands=records(summary.get('commands'),'native commands')
    require(len(commands)==15 and all(integer(row.get('exit_code'),'native command exit')==0 for row in commands),
            'Native compile/control/fixture execution incomplete')
    fixtures=('scripts/run_tranche14_ns3_reference.py','scripts/run_tranche4_ns3_reference.py','scripts/build_tranche12_overlay.py',
              'scripts/ns3/tranche14_edge.cc','scripts/ns3/tranche12-relay-hooks.h','scripts/ns3/tranche9_ack_contract.cc',
              'scripts/ns3/tranche10_receiver_contract.cc','scripts/ns3/tranche12_clock.cc')
    require(summary.get('fixture_sources')=={name:sha256(source_root/name) for name in fixtures},'Native fixture source binding differs')
    require(summary.get('input_bindings')=={'scenarios/edge/'+name:digest for name,digest in INPUT_HASHES.items()},'Native input binding differs')
    controls={}
    for name,count in (('ack',101),('receiver',154),('clock',72)):
        clean=directory/'controls'/('clock-clean/checks.csv' if name=='clock' else name+'-clean.csv')
        off=directory/'controls'/('clock-off/checks.csv' if name=='clock' else name+'-off.csv')
        rows=csv_rows(clean)
        require(len(rows)==count and all(logical(row['pass'],'native control pass') for row in rows) and sha256(clean)==sha256(off),
                'Native clean/disabled control evidence disagrees')
        baseline=(source_root/'evidence/tranche-12-clock-reference/checks.csv' if name=='clock' else
                  source_root/'evidence/tranche-13-loss-reference/controls'/(name+'-clean.csv'))
        require(sha256(clean)==sha256(baseline),'Fresh native control changed retained contract')
        if name=='clock':
            require(sha256(directory/'controls/clock-clean/events.csv')==sha256(directory/'controls/clock-off/events.csv')==
                    sha256(source_root/'evidence/tranche-12-clock-reference/events.csv'),'Fresh clock event control changed')
        controls[name]={'checks':count,'passed':True,'clean_and_disabled_byte_equal':True,'sha256':sha256(clean)}
    require(summary.get('controls')==build.get('controls')==controls,'Native control summary disagrees')
    require(summary.get('self_tests')=={'checks':14,'failed':0} and
            (directory/'controls/self-test.log').read_text().strip()=='EDGE_SELF_TEST checks=14 failed=0','Native negative self-tests missing')
    loaded={name:csv_rows(directory/(name+'.csv'),fields) for name,fields in OUTPUT_FIELDS.items() if name!='scheduler'}
    results=validate_events(loaded['events'],loaded['boundary'],matlab=False,label='native')
    usage=validate_draws(loaded['draws'],loaded['usage'])
    expected=native_checks(loaded['events']);check_rows=csv_rows(directory/'checks.csv',CHECK_FIELDS)
    require(len(check_rows)==len(expected)==222,'Native checkpoint inventory incomplete')
    for row,(case,name,node,value) in zip(check_rows,expected):
        require((row['case'],row['checkpoint'],integer(row['node'],'check node'))==(case,name,node) and
                integer(row['actual'],'check actual')==integer(row['expected'],'check expected')==value and
                logical(row['pass'],'check pass'),'Native checkpoint contradicts expected observation')
    raw={name:[] for name in loaded}
    raw_checks=[]
    for case in CASES:
        folder=directory/'raw'/case
        for name,fields in OUTPUT_FIELDS.items():
            if name in ('draws','scheduler'):continue
            raw[name].extend(csv_rows(folder/(name+'.csv'),fields))
        raw_checks.extend(csv_rows(folder/'checks.csv',CHECK_FIELDS))
        observations=csv_rows(folder/'native.csv');purposes={}
        for row in observations:
            if row['event']=='reservation_advertise':purpose='advertise'
            elif row['event']=='reservation_prepare' and row['reason']=='new':purpose='prepare'
            else:continue
            ns=number(row['time_s'],'native seconds')*1_000_000_000
            require(abs(ns-ns.to_integral_value())<Decimal('.0001'),'Native raw draw timestamp lost precision')
            key=row['node'],str(int(ns.to_integral_value()))
            purposes.setdefault(key,[]).append((purpose,row['reservation_slot']))
        for row in csv_rows(folder/'raw.csv'):
            key=row['node'],row['time_ns']; require(purposes.get(key),'Raw draw lacks actual reservation purpose')
            purpose,resolved=purposes[key].pop(0)
            require(row['resolved']==resolved,'Raw draw resolution differs from native MAC trace')
            raw['draws'].append({key:row[key] for key in DRAW_FIELDS if key!='purpose'}|{'purpose':purpose})
        require(not any(purposes.values()),'Native reservation lacks recorded raw draw')
    require(raw==loaded and raw_checks==check_rows,'Canonical native output differs from original execution records')
    for key,value in (('case_count',6),('event_count',len(loaded['events'])),('checkpoint_count',222),
                      ('draw_count',len(loaded['draws'])),('boundary_count',6),('failed_count',0)):
        require(integer(summary.get(key),key)==value,'Native summary counts disagree')
    require([row.get('case') for row in summary.get('cases',[])]==list(CASES),'Native per-case summary missing')
    for claim,result in zip(summary['cases'],results):
        require(claim.get('structural_passed') is True and all(str(claim.get(key))==str(result[key]) for key in
                ('delivered','gateway_ack_transmissions','first_ack_sequence','first_ack_bits')),'Native per-case result disagrees')
    return loaded,{'source_pin':PIN,'engine_pin':ENGINE_PIN,'fresh_engine_build':True,'historical_library_identity_claimed':False,
                  'artifact_count':len(manifest['files']),'control_checks':327,'native_self_tests':14,'case_count':6,
                  'event_count':len(loaded['events']),'checkpoint_count':222,'delivered':18,'draws':usage,'cases':results}


def review(evidence, source_root, output):
    evidence, source_root, output = Path(evidence).resolve(), Path(source_root).resolve(), Path(output).resolve()
    candidate = json_object(source_root / CANDIDATE)
    with evidence_directory(evidence) as root:
        metadata = json_object(root / 'metadata.json')
        runtime = verify_run_identity(root, metadata, source_root, candidate)
        artifacts = inventory(root, metadata.get('Artifacts'), excluded=('metadata.json',))
        require({'run.log', 'source.json', 'references.json', 'tests.csv', 'edge/check.csv', 'edge/summary.json'} |
                {'edge/' + name + '.csv' for name in OUTPUT_FIELDS} <= set(artifacts),
                'Required boundary evidence missing')
        source = verify_sources(root, metadata, source_root)
        baseline = verify_baseline(metadata, source_root, candidate)
        references = verify_references(root, metadata, source_root, candidate)
        tests = verify_tests(root, metadata, source_root, candidate)
        boundary = verify_boundary(root, metadata, source_root, candidate)
        result = {'schema': REVIEW_SCHEMA, 'status': 'focused_diagnostic_review_completed',
                  'evidence_integrity_verified': True, 'focused_structural_gate_completed': True,
                  'boundary_matches_native': boundary['matches_native'],
                  'acceptance_established': False, 'numerical_parity_established': False,
                  'matlab_executed_by_reviewer': False, 'runtime': runtime,
                  'evidence': {'path': evidence.name, 'sha256': sha256(evidence), 'bytes': evidence.stat().st_size},
                  'source': source, 'baseline': baseline, 'references': references,
                  'tests': tests, 'boundary': boundary}
    output.mkdir(parents=True, exist_ok=True)
    (output / 'review.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = review(args.evidence, args.source_root, args.output)
    except (ValueError, OSError, csv.Error, zipfile.BadZipFile, KeyError, TypeError, OverflowError) as error:
        args.output.mkdir(parents=True, exist_ok=True)
        failure = {'schema': REVIEW_SCHEMA, 'status': 'review_failed', 'evidence_integrity_verified': False,
                   'focused_structural_gate_completed': False, 'acceptance_established': False,
                   'numerical_parity_established': False, 'matlab_executed_by_reviewer': False, 'error': str(error)}
        (args.output / 'review.json').write_text(json.dumps(failure, indent=2) + '\n', encoding='utf-8')
        print(f'T14 evidence rejected: {error}')
        return 1
    print(f"T14 focused review complete; native match={result['boundary_matches_native']}. "
          'MATLAB execution is owner-returned; exact differences remain recorded.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
