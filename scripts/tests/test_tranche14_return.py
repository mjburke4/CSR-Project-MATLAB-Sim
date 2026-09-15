#!/usr/bin/env python3
"""T14 evidence checks use real native files and bounded hostile inputs.

No test assembles a fabricated MATLAB success archive. Numerical residuals are
reported independently from malformed chronology, identities and ACK semantics.
"""
from __future__ import annotations

import copy
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analyze_tranche14_return as gate
SOURCE = Path(__file__).resolve().parents[2]


class ExactAndArchiveChecks(unittest.TestCase):
    def test_full_uint64_bitmap_low_bit_does_not_round_away(self):
        self.assertNotEqual(gate.exact_uint(str(2**63), 'bitmap'), gate.exact_uint(str(2**63 + 1), 'bitmap'))

    def test_float_rounded_uint64_max_fails(self):
        with self.assertRaises(ValueError):
            gate.exact_uint(str(int(float(2**64 - 1))), 'bitmap')

    def test_integer_text_cannot_hide_fraction_exponent_or_bool(self):
        for value in ('1.0', '1e0', '+1', '01', True, 1, '-1', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                gate.exact_uint(value, 'bitmap')

    def test_adjacent_binary64_times_remain_distinct_when_nanoseconds_round_equal(self):
        first = 3.144961
        second = gate.math.nextafter(first, gate.math.inf)
        self.assertEqual(gate.rounded_ns(first), gate.rounded_ns(second))
        self.assertNotEqual(gate.hex64(first), gate.hex64(second))
        self.assertLess(gate.decode_hex(gate.hex64(first), 'first'), gate.decode_hex(gate.hex64(second), 'second'))

    def test_binary64_nonfinite_negative_or_noncanonical_time_fails(self):
        for value in ('7ff0000000000000', '7ff8000000000000', '8000000000000000',
                      'bff0000000000000', '40092ABCDEF00000', '1.25', '00000000000000000'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                gate.decode_hex(value, 'time')

    def test_unsafe_zip_paths_duplicates_and_case_collisions_fail(self):
        groups = [('../escape.csv',), ('/absolute.csv',), ('bad\\name.csv',),
                  ('X.csv', 'x.csv'), ('same.csv', 'same.csv')]
        for names in groups:
            with self.subTest(names=names), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / 'hostile.zip'
                with zipfile.ZipFile(path, 'w') as archive:
                    archive.writestr('metadata.json', '{}')
                    for name in names:
                        archive.writestr(name, 'x')
                with self.assertRaises(ValueError), gate.evidence_directory(path):
                    self.fail('unsafe archive accepted')

    def test_zip_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'hostile.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('metadata.json', '{}')
                entry = zipfile.ZipInfo('link')
                entry.create_system = 3
                entry.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(entry, '../elsewhere')
            with self.assertRaises(ValueError), gate.evidence_directory(path):
                self.fail('symbolic link accepted')

    def test_closed_inventory_rejects_unlisted_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'x.csv').write_text('x')
            with self.assertRaises(ValueError):
                gate.inventory(root, [], excluded=())


class NativeBoundaryMutations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate=gate.json_object(SOURCE/gate.CANDIDATE)
        cls.plan=gate.verify_plan(SOURCE,cls.candidate)
        cls.actual={name:gate.csv_rows(SOURCE/gate.REFERENCE/(name+'.csv'),fields)
                    for name,fields in gate.OUTPUT_FIELDS.items() if name!='scheduler'}

    def validate(self,events=None,boundaries=None):
        return gate.validate_events(events if events is not None else self.actual['events'],
            boundaries if boundaries is not None else self.actual['boundary'],matlab=False,label='native mutation')

    def test_actual_native_and_fresh_build_provenance_pass(self):
        actual,result=gate.verify_native(SOURCE,self.candidate,self.plan)
        self.assertEqual((result['artifact_count'],result['event_count'],result['checkpoint_count']), (67,202,222))
        self.assertEqual((result['control_checks'],result['native_self_tests'],result['delivered']),(327,14,18))
        self.assertTrue(result['fresh_engine_build'])
        self.assertFalse(result['historical_library_identity_claimed'])

    def test_actual_data_ack_order_explains_first_bitmap_and_extra_feedback(self):
        results=self.validate()
        self.assertEqual([r['first_ack_bits'] for r in results],['7','3','7','3','7','7'])
        self.assertEqual([r['gateway_ack_transmissions'] for r in results],[5,6,5,6,5,5])

    def test_data_identity_cannot_be_replaced_while_preserving_delivery_count(self):
        rows=copy.deepcopy(self.actual['events'])
        next(row for row in rows if row['phase']=='deliver')['app_id']='2'
        with self.assertRaisesRegex(ValueError,'delivery identity'): self.validate(rows)

    def test_first_ack_cannot_anticipate_data_after_service(self):
        rows=copy.deepcopy(self.actual['events'])
        row=next(row for row in rows if row['case']=='tie_late' and row['phase']=='ack_tx')
        row['hop_seq'],row['ack_bits']='3','7'
        with self.assertRaisesRegex(ValueError,'receive-window order'):self.validate(rows)

    def test_first_ack_cannot_ignore_data_already_received(self):
        rows=copy.deepcopy(self.actual['events'])
        row=next(row for row in rows if row['case']=='tie_early' and row['phase']=='ack_tx')
        row['hop_seq'],row['ack_bits']='2','3'
        with self.assertRaisesRegex(ValueError,'receive-window order'):self.validate(rows)

    def test_extra_or_missing_cumulative_ack_repeat_is_rejected(self):
        rows=copy.deepcopy(self.actual['events'])
        row=next(row for row in rows if row['phase']=='ack_tx');rows.remove(row)
        for case in gate.CASES:
            for order,row in enumerate([r for r in rows if r['case']==case],1):row['order']=str(order)
        with self.assertRaises(ValueError):self.validate(rows)

    def test_companion_ack_ingress_cannot_be_omitted(self):
        rows=copy.deepcopy(self.actual['events'])
        row=next(row for row in rows if row['phase']=='feedback_ingress' and row['node']=='4');rows.remove(row)
        for case in gate.CASES:
            for order,row in enumerate([r for r in rows if r['case']==case],1):row['order']=str(order)
        with self.assertRaisesRegex(ValueError,'feedback transport'):self.validate(rows)

    def test_ack_feedback_cannot_arrive_before_its_actual_airtime(self):
        rows=copy.deepcopy(self.actual['events'])
        row=next(row for row in rows if row['phase']=='feedback_ingress' and row['node']=='5')
        value=float(row['time_seconds_dec'])-1e-9
        row['time_seconds_dec']=format(value,'.17g');row['time_seconds_hex']=gate.hex64(value)
        row['time_ns']=str(gate.rounded_ns(value))
        with self.assertRaisesRegex(ValueError,'airtime transport'):self.validate(rows)

    def test_final_queue_cannot_hide_behind_successful_delivery(self):
        rows=copy.deepcopy(self.actual['events']);next(row for row in rows if row['phase']=='settled')['ack_queue']='1'
        with self.assertRaisesRegex(ValueError,'queues fail to drain'):self.validate(rows)

    def test_binary64_observation_cannot_be_replaced_by_rounded_nanoseconds(self):
        rows=copy.deepcopy(self.actual['boundary']);row=rows[0]
        value=gate.math.nextafter(float(row['arrival_seconds_dec']),gate.math.inf)
        row['arrival_seconds_dec']=format(value,'.17g');row['arrival_seconds_hex']=gate.hex64(value)
        with self.assertRaisesRegex(ValueError,'transport arithmetic'):self.validate(boundaries=rows)

    def test_first_ack_one_ulp_shift_cannot_hide_behind_same_nanoseconds(self):
        rows=copy.deepcopy(self.actual['events'])
        row=next(row for row in rows if row['phase']=='ack_tx')
        value=gate.math.nextafter(float(row['time_seconds_dec']),gate.math.inf)
        row['time_seconds_dec']=format(value,'.17g');row['time_seconds_hex']=gate.hex64(value)
        with self.assertRaisesRegex(ValueError,'opportunity shifted'):self.validate(rows)

    def test_decimal_hex_roundtrip_is_mandatory(self):
        rows=copy.deepcopy(self.actual['events']);rows[0]['time_seconds_dec']='2.9'
        with self.assertRaisesRegex(ValueError,'round-trip'):self.validate(rows)

    def test_signed_before_delta_is_valid_and_cannot_flip_positive(self):
        row=next(row for row in self.actual['boundary'] if row['case']=='before')
        self.assertLess(gate.full_time(row['arrival_minus_tick_seconds_dec'],row['arrival_minus_tick_seconds_hex'],'delta',signed=True),0)
        rows=copy.deepcopy(self.actual['boundary']);row=next(row for row in rows if row['case']=='before')
        value=abs(float(row['arrival_minus_tick_seconds_dec']))
        row['arrival_minus_tick_seconds_dec']=format(value,'.17g');row['arrival_minus_tick_seconds_hex']=gate.hex64(value)
        with self.assertRaisesRegex(ValueError,'delta contradicts'):self.validate(boundaries=rows)

    def test_late_insertion_cannot_be_relabelled_as_early(self):
        rows=copy.deepcopy(self.actual['boundary']);rows[1]['late_insertion']='0'
        with self.assertRaisesRegex(ValueError,'insertion scope'):self.validate(boundaries=rows)

    def test_mixed_aggregate_wire_size_is_fixed_by_selected_frames(self):
        rows=copy.deepcopy(self.actual['boundary']);rows[0]['wire_payload_bytes']='48'
        with self.assertRaisesRegex(ValueError,'ACK41 plus DATA48'):self.validate(boundaries=rows)

    def test_uint64_bitmap_overflow_is_rejected(self):
        rows=copy.deepcopy(self.actual['events']);rows[0]['ack_bits']=str(2**64)
        with self.assertRaisesRegex(ValueError,'uint64'):self.validate(rows)

    def test_draw_tape_and_unused_suffix_reconcile(self):
        result=gate.validate_draws(self.actual['draws'],self.actual['usage'])
        self.assertEqual(result,{'consumed':74,'supplied':1152,'unused':1078})
        usage=copy.deepcopy(self.actual['usage']);usage[0]['unused']='0'
        with self.assertRaisesRegex(ValueError,'suffix accounting'):gate.validate_draws(self.actual['draws'],usage)

    def test_draw_cannot_leave_prescribed_support_or_ordinal(self):
        for field,value in (('draw','1'),('ordinal','2'),('resolved','32'),('purpose','unresolved')):
            rows=copy.deepcopy(self.actual['draws']);rows[0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):gate.validate_draws(rows,self.actual['usage'])

    def test_comparison_preserves_low_uint64_bits_and_one_ulp_hex(self):
        rows=copy.deepcopy(self.actual['events']);other=copy.deepcopy(rows)
        rows[0]['ack_bits']=str(2**63);other[0]['ack_bits']=str(2**63+1)
        result=gate.compare_cases(rows,other,['case','ack_bits'],'uint64 difference')
        self.assertEqual(result['unmatched_rows'],1)
        self.assertEqual(result['differences'][0]['fields'],['ack_bits'])
        result=gate.compare_cases(self.actual['events'],self.actual['events'],gate.EVENT_FIELDS,'same')
        self.assertTrue(result['matches_native'])

    def test_complete_next_case_is_not_shifted_by_previous_case_missing_row(self):
        rows=copy.deepcopy(self.actual['events']);rows.pop(0)
        result=gate.compare_cases(rows,self.actual['events'],['case','order','phase'],'case alignment')
        self.assertGreater(result['cases'][0]['unmatched_rows'],0)
        self.assertTrue(all(row['unmatched_rows']==0 for row in result['cases'][1:]))

    def test_frozen_plan_or_native_manifest_binding_cannot_be_substituted(self):
        candidate=copy.deepcopy(self.candidate);candidate['EdgePlanSHA256']='0'*64
        with self.assertRaisesRegex(ValueError,'plan hash'):gate.verify_plan(SOURCE,candidate)
        candidate=copy.deepcopy(self.candidate);candidate['EdgeReferenceManifestSHA256']='0'*64
        with self.assertRaises(ValueError):gate.verify_native(SOURCE,candidate,self.plan)


class SchedulerChronologyMutations(unittest.TestCase):
    def records(self):
        rows=[]
        def row(case,order,operation,identity,observed,scheduled,parent=0):
            return dict(zip(gate.SCHEDULER_FIELDS,(case,str(order),operation,str(identity),str(parent),
                format(observed,'.17g'),gate.hex64(observed),format(scheduled,'.17g'),gate.hex64(scheduled),'callback','1')))
        for case in gate.CASES:
            rows.extend([row(case,1,'schedule',1,0,1),row(case,2,'schedule',2,0,1),
                         row(case,3,'execute',1,1,1),row(case,4,'execute',2,1,1)])
        return rows

    def test_bounded_api_trace_replay_accepts_actual_fifo_rule(self):
        result=gate.validate_scheduler(self.records(),[],[],label='bounded scheduler input')
        self.assertEqual(result,{'operations':24,'scheduled':12,'executed':12})

    def test_equal_time_callbacks_cannot_swap_insertion_priority(self):
        rows=self.records();rows[2]['event_id'],rows[3]['event_id']='2','1'
        with self.assertRaisesRegex(ValueError,'FIFO priority'):gate.validate_scheduler(rows,[],[],label='swapped')

    def test_sub_nanosecond_priority_is_not_rounded_to_fifo_tie(self):
        rows=self.records();value=gate.math.nextafter(1.0,gate.math.inf)
        rows[0]['scheduled_seconds']=format(value,'.17g');rows[0]['scheduled_hex']=gate.hex64(value)
        rows[2]['scheduled_seconds']=format(value,'.17g');rows[2]['scheduled_hex']=gate.hex64(value)
        rows[2]['observed_seconds']=format(value,'.17g');rows[2]['observed_hex']=gate.hex64(value)
        with self.assertRaisesRegex(ValueError,'FIFO priority'):gate.validate_scheduler(rows,[],[],label='rounded tie')

    def test_unexecuted_due_callback_is_rejected(self):
        rows=self.records();rows.pop(3)
        with self.assertRaisesRegex(ValueError,'due callback omitted'):gate.validate_scheduler(rows,[],[],label='omitted')

    def test_protocol_event_must_bind_real_callback_and_full_precision(self):
        event={'case':'tie_early','scheduler_id':'99','time_seconds_hex':gate.hex64(1.0)}
        with self.assertRaisesRegex(ValueError,'actual executing callback'):gate.validate_scheduler(self.records(),[event],[],label='invented ID')

    def test_reused_insertion_id_is_rejected(self):
        rows=self.records();rows[1]['event_id']='1'
        with self.assertRaisesRegex(ValueError,'insertion identity'):gate.validate_scheduler(rows,[],[],label='duplicate ID')

    def test_callback_identity_cannot_change_after_scheduling(self):
        rows=self.records();rows[2]['callback']='different_callback'
        with self.assertRaisesRegex(ValueError,'callback identity'):gate.validate_scheduler(rows,[],[],label='different callback')

    def test_negative_or_false_cancel_cannot_erase_pending_event(self):
        rows=self.records();row=copy.deepcopy(rows[1]);row.update(operation='cancel',event_id='1',parent_id='0',
            scheduled_seconds='0',scheduled_hex=gate.hex64(0.0),callback='',was_pending='0');rows[1]=row
        with self.assertRaisesRegex(ValueError,'cancellation status'):gate.validate_scheduler(rows,[],[],label='false cancel')

if __name__ == '__main__':
    unittest.main()
