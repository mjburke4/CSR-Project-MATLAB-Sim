#!/usr/bin/env python3
"""Mutation tests for new T15 auditing, never successful fabricated owner runs.

Small in-memory traces exercise arithmetic/identity failure paths. Genuine T13
native and owner records exercise preserved data and metrics independently.
"""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_tranche15_return as gate

SOURCE = Path(__file__).resolve().parents[2]


def sample(mode='c'):
    tx = 3.121001
    duration = (104 + 48) / 4 * .000510 + (48 * 8 + 32) / (4 / .000030)
    propagation = .000001
    components = [gate.rounded_ns(v) for v in (tx,duration,propagation)]
    continuous = (tx + duration) + propagation
    nanoseconds = sum(components) / 1_000_000_000
    arrival = continuous if mode == 'c' else nanoseconds
    timing = {key: '0' for key in gate.TIMING_FIELDS}
    timing.update(case='ok',tx_id='1',sender='4',wire_payload_bytes='48',segment_count='1',preamble='short',rate_kbps='128',power_dbm='33')
    for key, value in dict(tx=tx,duration=duration,propagation=propagation,continuous=continuous,
                           nanoseconds=nanoseconds,arrival=arrival,delta=arrival-continuous).items():
        timing[key + '_seconds'] = format(value, '.17g')
        timing[key + '_hex'] = gate.hex64(value)
    timing.update(zip(('tx_ns','duration_ns','propagation_ns'), map(str,components)))
    timing['sum_ns'] = str(sum(components))
    transport = {key: '0' for key in gate.loss.TRANSPORT_FIELDS}
    transport.update(case='ok',tx_id='1',group_id='1',segment_index='1',group_segments='1',
                     tx_time_ns=str(components[0]),arrival_ns=str(gate.rounded_ns(arrival)),sender='4',receiver='5',
                     kind='DATA',app_source='4',app_id='1',hop_seq='1',decision='pass',reason='none',boundary_distance_ns='-1')
    events = []
    for name, value, node, peer in (('tx_start',tx,4,5), ('ingress_before',arrival,5,4), ('ingress_after',arrival,5,4)):
        event = {key:'0' for key in gate.loss.EVENT_FIELDS}
        event.update(case='ok',order=str(len(events)+1),time_ns=str(gate.rounded_ns(value)),event=name,
                     node=str(node),peer=str(peer),app_source='4',app_id='1',hop_seq='1')
        events.append(event)
    precision = []
    for event, value in zip(events,(tx,arrival,arrival)):
        row = {key: event[key] for key in gate.PRECISION_FIELDS[:-2]}
        row.update(time_seconds=format(value,'.17g'),time_hex=gate.hex64(value))
        precision.append(row)
    return [timing],[transport],events,precision


class TimingEvidenceMutations(unittest.TestCase):
    def check(self, data, mode='c'):
        return gate.validate_timing(*data,mode,label='synthetic mutation unit only')

    def test_both_declared_arithmetic_modes_bind_actual_tx_and_ingress(self):
        for mode in ('c','n'):
            with self.subTest(mode=mode):
                result=self.check(sample(mode),mode)
                self.assertEqual(result['transmissions'],1)
                self.assertEqual(result['precision_events'],3)

    def test_missing_timing_tx_cannot_be_reported_as_complete(self):
        data=list(sample());data[0]=[]
        with self.assertRaisesRegex(ValueError,'no timing'):self.check(data)

    def test_duplicate_actual_tx_identity_is_rejected(self):
        data=list(sample());data[0] += copy.deepcopy(data[0])
        with self.assertRaisesRegex(ValueError,'identities'):self.check(data)

    def test_missing_semantic_precision_row_is_rejected(self):
        data=list(sample());data[3].pop()
        with self.assertRaisesRegex(ValueError,'precision observations'):self.check(data)

    def test_precision_event_identity_cannot_be_relabelled(self):
        data=sample();data[3][1]['app_id']='2'
        with self.assertRaisesRegex(ValueError,'precision identity'):self.check(data)

    def test_binary64_decimal_hex_roundtrip_is_mandatory(self):
        data=sample();data[3][0]['time_seconds']='3'
        with self.assertRaisesRegex(ValueError,'round-trip'):self.check(data)

    def test_full_width_id_does_not_pass_via_double_rounding(self):
        data=sample();data[2][0]['ack_bits']=str(2**63+1);data[3][0]['ack_bits']=str(2**63)
        with self.assertRaisesRegex(ValueError,'precision identity'):self.check(data)

    def test_fractional_component_nanoseconds_are_rejected(self):
        data=sample();data[0][0]['duration_ns']='25000.5'
        with self.assertRaisesRegex(ValueError,'unsigned decimal'):self.check(data)

    def test_rounding_whole_sum_is_not_component_policy(self):
        data=sample();data[0][0]['sum_ns']=str(int(data[0][0]['sum_ns'])+1)
        with self.assertRaisesRegex(ValueError,'integer sum'):self.check(data)

    def test_selected_arrival_must_follow_declared_mode(self):
        data=sample('n');self.assertNotEqual(data[0][0]['continuous_hex'],data[0][0]['nanoseconds_hex'])
        with self.assertRaisesRegex(ValueError,'arrival arithmetic'):self.check(data,'c')

    def test_one_ulp_arrival_change_is_not_hidden_by_rounded_ns(self):
        data=sample()
        value=gate.full_time(data[3][1]['time_seconds'],data[3][1]['time_hex'],'sample')
        changed=math.nextafter(value,math.inf)
        self.assertEqual(gate.rounded_ns(value),gate.rounded_ns(changed))
        for row in data[3][1:]:row.update(time_seconds=format(changed,'.17g'),time_hex=gate.hex64(changed))
        with self.assertRaisesRegex(ValueError,'full-precision ingress'):self.check(data)

    def test_missing_emitted_segment_is_rejected(self):
        data=list(sample());data[1]=[]
        with self.assertRaisesRegex(ValueError,'identities'):self.check(data)

    def test_transmit_identity_cannot_be_replaced_by_arrival_identity(self):
        data=sample();data[2][0]['peer']='1';data[3][0]['peer']='1'
        with self.assertRaisesRegex(ValueError,'full-precision tx_start'):self.check(data)

    def test_dropped_segment_cannot_fabricate_actual_ingress(self):
        data=sample();data[1][0]['decision']='drop'
        with self.assertRaisesRegex(ValueError,'full-precision ingress'):self.check(data)

    def test_nonfinite_callback_time_is_rejected(self):
        data=sample();data[0][0]['tx_seconds']='inf';data[0][0]['tx_hex']=gate.hex64(math.inf)
        with self.assertRaisesRegex(ValueError,'invalid binary64'):self.check(data)

    def test_changed_source_airtime_is_rejected_independent_of_roundtrip(self):
        data=sample();row=data[0][0];value=float(row['duration_seconds'])+.000001
        row['duration_seconds']=format(value,'.17g');row['duration_hex']=gate.hex64(value)
        with self.assertRaisesRegex(ValueError,'source airtime'):self.check(data)

    def test_128_rate_key_cannot_be_treated_as_128000_bps(self):
        data=sample();row=data[0][0]
        value=(104+48)/4*.000510+(48*8+32)/128000
        row['duration_seconds']=format(value,'.17g');row['duration_hex']=gate.hex64(value)
        with self.assertRaisesRegex(ValueError,'source airtime'):self.check(data)

    def test_emitted_envelope_segment_count_is_bound(self):
        data=sample();data[0][0]['segment_count']='2'
        with self.assertRaisesRegex(ValueError,'selection/count'):self.check(data)

    def test_wire_payload_cannot_be_forged_independently_of_actual_segments(self):
        data=sample();data[0][0]['wire_payload_bytes']='89'
        with self.assertRaisesRegex(ValueError,'segment accounting'):self.check(data)

    def test_preamble_and_radio_selection_are_bound(self):
        for field,value in (('preamble','none'),('rate_kbps','500'),('power_dbm','22')):
            data=sample();data[0][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'selection/count'):self.check(data)


class ExistingEvidenceMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gate.evidence_directory(SOURCE/'evidence/t13/owner.zip') as directory:
            cls.owner={name:gate.csv_rows(directory/'loss'/(name+'.csv'),fields) for name,fields in gate.FAMILIES}
        cls.native={name:gate.csv_rows(SOURCE/gate.loss.REFERENCE/(name+'.csv'),fields) for name,fields in gate.loss.FAMILIES}

    def test_continuous_original_requires_all_six_genuine_owner_tables(self):
        result=gate.verify_original_continuous(self.owner,SOURCE)
        self.assertTrue(result['matches_all_six_accepted_owner_tables_exactly'])

    def test_changed_continuous_table_cannot_pass_as_numerical_residual(self):
        for family,field in (('events','time_ns'),('draws','resolved'),('usage','unused'),
                             ('transport','arrival_ns'),('terminal','time_ns'),('check','actual')):
            actual=copy.deepcopy(self.owner);actual[family][0][field]=str(int(actual[family][0][field])+1)
            with self.subTest(family=family),self.assertRaisesRegex(ValueError,'Continuous baseline changed'):
                gate.verify_original_continuous(actual,SOURCE)

    def test_real_native_outcomes_reconcile_all_384_deliveries(self):
        result=gate.outcome_metrics(self.native)
        self.assertEqual(sum(row['totals']['delivered'] for row in result.values()),384)
        self.assertEqual(sum(row['totals']['generated'] for row in result.values()),384)
        self.assertEqual(sum(row['totals']['admitted'] for row in result.values()),384)
        self.assertGreater(result['data']['totals']['data_retries'],result['ok']['totals']['data_retries'])

    def test_real_owner_metrics_keep_delivery_retirement_overlap(self):
        result=gate.outcome_metrics(self.owner)
        for case in gate.loss.CASES:
            row=result[case]
            self.assertEqual(row['totals']['delivered'],len([app for app in row['applications'].values() if 'deliver_seconds' in app]))
            self.assertNotIn('release_seconds',next(iter(row['hop_retirements'].values())))
            self.assertTrue(row['capacity_release_series_by_node_source'])
            self.assertTrue(all(key.endswith(('/4','/5')) for key in row['capacity_release_series_by_node_source']))

    def test_identity_aligned_deltas_do_not_depend_on_row_position(self):
        original=gate.outcome_metrics(self.native)
        revised=copy.deepcopy(original)
        first=next(iter(revised['ok']['applications']))
        revised['ok']['applications'][first]['deliver_seconds']='999'
        delta=gate.metric_differences(original,revised)
        self.assertEqual([row['identity'] for row in delta['ok']['application_identity_changes']],[first])
        self.assertTrue(all(value==0 for value in delta['ok']['totals_right_minus_left'].values()))

    def test_exact_comparator_does_not_apply_legacy_one_ns_tolerance(self):
        a=copy.deepcopy(self.native['events'][:1]);b=copy.deepcopy(a)
        b[0]['time_ns']=str(int(a[0]['time_ns'])+1)
        self.assertTrue(gate.loss.compare_rows(a,b,gate.loss.EVENT_FIELDS,family='events')['matches_native'])
        self.assertFalse(gate.loss.compare_rows(a,b,gate.loss.EVENT_FIELDS,family='events',time_tolerance_ns=0)['matches_native'])

    def test_genuine_owner_recovery_adapter_recomputes_all_264_checks(self):
        with gate.evidence_directory(SOURCE/'evidence/t13/owner.zip') as directory:
            summary=gate.json_object(directory/'loss/summary.json')
            owner=gate.json_object(directory/'metadata.json')
            metadata={'Runtime': owner['Runtime'], 'RecoveryDirectory':'loss',
                      'RecoveryCompleted':summary['DiagnosticCompleted'], 'RecoveryPassed':summary['Passed'],
                      'RecoveryMatchesNative':summary['MatchesNative']}
            for field in ('CaseCount','EventCount','DrawCount','CheckpointCount','UnmatchedCount'):
                metadata['Recovery'+field]=summary[field]
            result=gate.loss.verify_recovery(directory,metadata,SOURCE,gate.json_object(SOURCE/gate.loss.CANDIDATE))
            self.assertEqual(result['checkpoint_count'],264)
            self.assertTrue(result['structural_complete'])
            self.assertFalse(result['matches_native'])

    def test_new_plan_pins_modes_schemas_inputs_and_existing_source(self):
        candidate={'TimingPlan':'scenarios/t15/plan.json','TimingPlanSHA256':gate.sha256(SOURCE/'scenarios/t15/plan.json')}
        plan,old=gate.verify_plan(SOURCE,candidate)
        self.assertEqual(plan['mode_directories'],['c','n'])
        self.assertEqual(old['SourceCommit'],gate.loss.PIN)


if __name__=='__main__':unittest.main()
