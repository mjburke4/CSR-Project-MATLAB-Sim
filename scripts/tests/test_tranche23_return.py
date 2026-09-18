"""Adversarial T23 evidence checks. Synthetic fixtures are not MATLAB runs."""
import copy
import csv
import shutil
from decimal import Decimal
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import analyze_tranche23_return as r


def fixture():
    def action(step,kind,packet='',sequence='0',source='0',destination='1',ack='',dack=''):
        time = Decimal('0.1')*step
        return dict(zip(r.ACTION_FIELDS,('synthetic',str(step),str(time),str(time+Decimal('0.000001')),
             kind,packet,sequence,source,destination,ack,dack,'')))
    actions = [action(1,'RX','p','1','7'),action(2,'RX','p','1','7'),action(3,'TX',sequence='1'),
               action(4,'FEEDBACK',ack='1')]
    rows = []
    for index,act in enumerate(actions):
        row = {field:'0' for field in r.STATE_FIELDS}
        row.update(case_id='synthetic',step=act['step'],time_s=act['observe_s'],action=act['action'],
                   packet=act['packet'],accepted='-1',rx_highest='1',rx_ack_hex='0000000000000001',
                   rx_dack_hex='0000000000000000',ack_generated=str(min(index+1,2)),rx_received=str(min(index+1,2)),
                   rx_delivered='1',rx_duplicates=str(min(index,1)),data_tx=str(int(index>=2)))
        for field in ('nsdp_relay','nwk_owned','hop_pending','hop_outstanding','hop_resend'):
            row[field] = str(int(index<3))
        row['nsdp_releases']=row['ack_completed']=str(int(index==3))
        rows.append(row)
    feedback = []
    for action in actions[:2]:
        feedback.append(dict(zip(r.FEEDBACK_FIELDS,('synthetic',action['step'],action['time_s'],'ACK','1',
                         '0000000000000001','0000000000000000','1','0','1'))))
    return actions,rows,feedback


def receipt(comparison):
    return {'ReferencePresent':True,'SchemaMatches':True,'ActualRows':comparison['actual_rows'],
            'ReferenceRows':comparison['reference_rows'],'MatchedRows':comparison['matched_rows'],
            'UnmatchedRows':comparison['unmatched_rows'],'FailedRows':[x['row'] for x in comparison['differences']]}


class ActionMutationTests(unittest.TestCase):
    def setUp(self): self.actions,_,_ = fixture()
    def runcheck(self): return r.verify_actions(self.actions,['synthetic'])
    def test_duplicate_reception_is_valid_workload(self):
        self.assertEqual(self.runcheck(),{'synthetic':4})
    def test_unknown_case_rejected(self):
        self.actions[1]['case_id']='unknown'
        with self.assertRaisesRegex(ValueError,'Unknown action case'):self.runcheck()
    def test_duplicate_step_rejected(self):
        self.actions[1]['step']='1'
        with self.assertRaisesRegex(ValueError,'step'):self.runcheck()
    def test_missing_case_rejected(self):
        with self.assertRaisesRegex(ValueError,'Missing planned case'):r.verify_actions(self.actions,['synthetic','absent'])
    def test_alias_cannot_change_application_identity(self):
        self.actions[1]['destination']='8'
        with self.assertRaisesRegex(ValueError,'alias identity'):self.runcheck()
    def test_nonapplication_identity_rejected(self):
        self.actions[2]['packet']='p'
        with self.assertRaisesRegex(ValueError,'Nonapplication'):self.runcheck()
    def test_feedback_has_numeric_sequence_not_alias(self):
        self.actions[3]['ack_packets']='p'
        with self.assertRaises(ValueError):self.runcheck()
    def test_duplicate_feedback_sequence_rejected(self):
        self.actions[3]['ack_packets']='1;1'
        with self.assertRaisesRegex(ValueError,'Duplicate feedback'):self.runcheck()
    def test_overlapping_feedback_sequence_rejected(self):
        self.actions[3]['dack_packets']='1'
        with self.assertRaisesRegex(ValueError,'Overlapping'):self.runcheck()
    def test_changed_settling_interval_rejected(self):
        self.actions[1]['observe_s']='0.200002'
        with self.assertRaisesRegex(ValueError,'settling'):self.runcheck()
    def test_overlapping_actions_rejected(self):
        self.actions[1]['time_s']='0.1000005';self.actions[1]['observe_s']='0.1000015'
        with self.assertRaisesRegex(ValueError,'overlaps'):self.runcheck()
    def test_sequence_above_uint16_rejected(self):
        self.actions[0]['sequence']='65536'
        with self.assertRaisesRegex(ValueError,'uint16'):self.runcheck()
    def test_unknown_action_rejected(self):
        self.actions[0]['action']='FORCE_OWNER_COUNT'
        with self.assertRaisesRegex(ValueError,'Unknown action'):self.runcheck()


class StateMutationTests(unittest.TestCase):
    def setUp(self): self.actions,self.rows,self.feedback = fixture()
    def runcheck(self): return r.validate_checkpoints(self.rows,self.actions,'synthetic')
    def test_exact_ack_duplicate_and_release(self):
        rows=self.runcheck();self.assertEqual(rows[1]['rx_duplicates'],1);self.assertEqual(rows[-1]['nsdp_releases'],1)
    def test_missing_checkpoint_rejected(self):
        self.rows.pop()
        with self.assertRaisesRegex(ValueError,'checkpoint rows'):self.runcheck()
    def test_extra_checkpoint_rejected(self):
        self.rows.append(copy.deepcopy(self.rows[-1]))
        with self.assertRaisesRegex(ValueError,'checkpoint rows'):self.runcheck()
    def test_wrong_action_rejected(self):
        self.rows[1]['action']='LOCAL'
        with self.assertRaisesRegex(ValueError,'action/case/packet'):self.runcheck()
    def test_raw_action_time_is_not_settled_observation_time(self):
        self.rows[1]['time_s']=self.actions[1]['time_s']
        with self.assertRaisesRegex(ValueError,'observation time'):self.runcheck()
    def test_one_nanosecond_tolerance(self):
        self.rows[1]['time_s']=str(Decimal(self.rows[1]['time_s'])+Decimal('1e-9'));self.runcheck()
        self.rows[1]['time_s']=str(Decimal(self.rows[1]['time_s'])+Decimal('1e-12'))
        with self.assertRaisesRegex(ValueError,'observation time'):self.runcheck()
    def test_noninteger_state_rejected(self):
        self.rows[0]['nwk_owned']='1.1'
        with self.assertRaisesRegex(ValueError,'integer'):self.runcheck()
    def test_boolean_state_rejected(self):
        self.rows[0]['nwk_owned']=True
        with self.assertRaisesRegex(ValueError,'Boolean'):self.runcheck()
    def test_nan_state_rejected(self):
        self.rows[0]['nwk_owned']='NaN'
        with self.assertRaisesRegex(ValueError,'finite'):self.runcheck()
    def test_bitmap_must_preserve_full_64_bits(self):
        self.rows[0]['rx_ack_hex']='1'
        with self.assertRaisesRegex(ValueError,'16-digit'):self.runcheck()
    def test_lowercase_bitmap_rejected(self):
        self.rows[0]['rx_ack_hex']='000000000000000a'
        with self.assertRaisesRegex(ValueError,'uppercase'):self.runcheck()
    def test_ack_and_dack_bits_may_overlap_on_reassessment(self):
        self.rows[1]['rx_dack_hex']='0000000000000001';self.runcheck()
    def test_nonlocal_accepted_sentinel_rejected(self):
        self.rows[0]['accepted']='1'
        with self.assertRaisesRegex(ValueError,'sentinel'):self.runcheck()
    def test_per_flow_ownership_must_reconcile(self):
        self.rows[0]['nsdp_local']='1'
        with self.assertRaisesRegex(ValueError,'per-flow'):self.runcheck()
    def test_waiting_and_submitted_cannot_double_count(self):
        self.rows[0]['nwk_waiting']='1'
        with self.assertRaisesRegex(ValueError,'waiting/submitted'):self.runcheck()
    def test_hop_hold_cannot_disappear_from_pending(self):
        self.rows[0]['hop_holds']='1'
        with self.assertRaisesRegex(ValueError,'resend/hold'):self.runcheck()
    def test_release_cannot_happen_twice(self):
        self.rows[-1]['nsdp_releases']='2'
        with self.assertRaisesRegex(ValueError,'exactly once'):self.runcheck()
    def test_duplicate_receive_cannot_create_delivered_count(self):
        self.rows[1]['rx_delivered']='2'
        with self.assertRaisesRegex(ValueError,'identity counts'):self.runcheck()
    def test_cumulative_transmit_counter_cannot_decrease(self):
        self.rows[-1]['data_tx']='0'
        with self.assertRaisesRegex(ValueError,'decreased'):self.runcheck()
    def test_uint16_highest_bound(self):
        self.rows[0]['rx_highest']='65536'
        with self.assertRaisesRegex(ValueError,'uint16'):self.runcheck()


class FeedbackMutationTests(unittest.TestCase):
    def setUp(self):
        self.actions,self.rows,self.feedback=fixture()
    def runcheck(self):
        state=r.validate_checkpoints(self.rows,self.actions,'synthetic')
        return r.validate_feedback(self.feedback,self.actions,state,'synthetic')
    def test_exact_emitted_feedback(self): self.assertEqual(len(self.runcheck()),2)
    def test_feedback_must_belong_to_receive_action(self):
        self.feedback[1]['step']='3'
        with self.assertRaisesRegex(ValueError,'membership'):self.runcheck()
    def test_frame_generated_at_receive_time_not_observe_time(self):
        self.feedback[0]['time_s']=self.actions[0]['observe_s']
        with self.assertRaisesRegex(ValueError,'time differs'):self.runcheck()
    def test_inconsistent_missing_feedback_rejected(self):
        self.feedback.pop()
        with self.assertRaisesRegex(ValueError,'cumulative count'):self.runcheck()
    def test_truthful_missing_feedback_preserved_as_difference(self):
        original=r.validate_feedback(self.feedback,self.actions,r.validate_checkpoints(self.rows,self.actions,'synthetic'),'synthetic')
        self.feedback.pop()
        for row in self.rows[1:]:row['ack_generated']='1'
        actual=self.runcheck();comparison=r.compare_rows(actual,original,r.FEEDBACK_FIELDS)
        self.assertFalse(comparison['matches_native']);self.assertEqual(comparison['unmatched_rows'],1)
    def test_truthful_duplicate_feedback_preserved_as_difference(self):
        original=r.validate_feedback(self.feedback,self.actions,r.validate_checkpoints(self.rows,self.actions,'synthetic'),'synthetic')
        self.feedback.append(copy.deepcopy(self.feedback[-1]))
        for row in self.rows[1:]:row['ack_generated']='3'
        actual=self.runcheck();comparison=r.compare_rows(actual,original,r.FEEDBACK_FIELDS)
        self.assertFalse(comparison['matches_native']);self.assertEqual(comparison['unmatched_rows'],1)
    def test_feedback_per_flow_count_must_sum(self):
        self.feedback[1]['relay_nsdp']='2'
        with self.assertRaisesRegex(ValueError,'per-flow'):self.runcheck()
    def test_feedback_kind_count_must_reconcile(self):
        self.feedback[1]['kind']='DACK'
        with self.assertRaisesRegex(ValueError,'cumulative count'):self.runcheck()
    def test_unknown_feedback_kind_rejected(self):
        self.feedback[1]['kind']='IMPLICIT_ACK'
        with self.assertRaisesRegex(ValueError,'unsupported'):self.runcheck()
    def test_reordered_feedback_rejected(self):
        self.feedback.reverse()
        with self.assertRaisesRegex(ValueError,'order'):self.runcheck()


class ComparisonReceiptTests(unittest.TestCase):
    def setUp(self):
        actions,rows,feedback=fixture();self.state=r.validate_checkpoints(rows,actions,'synthetic')
        self.feedback=r.validate_feedback(feedback,actions,self.state,'synthetic')
        self.sc=r.compare_rows(self.state,copy.deepcopy(self.state),r.STATE_FIELDS)
        self.fc=r.compare_rows(self.feedback,copy.deepcopy(self.feedback),r.FEEDBACK_FIELDS)
    def summaries(self):
        passed=self.sc['matches_native'] and self.fc['matches_native']
        summary={'DiagnosticCompleted':True,'Passed':passed,'CaseCount':1,'CheckpointCount':self.sc['actual_rows'],
                 'FailedCount':self.sc['unmatched_rows'],'FeedbackCount':self.fc['actual_rows'],
                 'FeedbackFailedCount':self.fc['unmatched_rows'],'NativeComparison':receipt(self.sc),
                 'NativeFeedbackComparison':receipt(self.fc)}
        metadata={'ContractCompleted':True,'ContractPassed':passed}
        metadata.update({'Contract'+k:summary[k] for k in ('CaseCount','CheckpointCount','FailedCount','FeedbackCount','FeedbackFailedCount')})
        return summary,metadata
    def test_complete_matching_receipts(self):
        summary,metadata=self.summaries()
        self.assertTrue(r.verify_summary(summary,metadata,self.sc,self.fc,1)['matches_native'])
    def test_truthful_integer_difference_is_diagnostic_not_accepted(self):
        other=copy.deepcopy(self.state);other[-1]['nwk_owned']=1
        self.sc=r.compare_rows(self.state,other,r.STATE_FIELDS)
        summary,metadata=self.summaries()
        result=r.verify_summary(summary,metadata,self.sc,self.fc,1)
        self.assertFalse(result['matches_native']);self.assertEqual(result['FailedCount'],1)
    def test_fabricated_pass_hiding_mismatch_rejected(self):
        other=copy.deepcopy(self.state);other[-1]['nwk_owned']=1
        self.sc=r.compare_rows(self.state,other,r.STATE_FIELDS);summary,metadata=self.summaries();summary['Passed']=True
        with self.assertRaisesRegex(ValueError,'flags disagree'):r.verify_summary(summary,metadata,self.sc,self.fc,1)
    def test_failure_row_index_cannot_be_hidden(self):
        summary,metadata=self.summaries();summary['NativeComparison']['FailedRows']=[1]
        with self.assertRaisesRegex(ValueError,'failed-row identity'):r.verify_summary(summary,metadata,self.sc,self.fc,1)
    def test_feedback_count_cannot_be_borrowed_from_native(self):
        self.fc=r.compare_rows(self.feedback[:-1],self.feedback,r.FEEDBACK_FIELDS)
        summary,metadata=self.summaries();summary['FeedbackCount']=2
        with self.assertRaisesRegex(ValueError,'count disagrees'):r.verify_summary(summary,metadata,self.sc,self.fc,1)
    def test_false_reference_presence_rejected(self):
        summary,metadata=self.summaries();summary['NativeFeedbackComparison']['ReferencePresent']=False
        with self.assertRaisesRegex(ValueError,'Missing feedback'):r.verify_summary(summary,metadata,self.sc,self.fc,1)
    def test_feedback_bitmap_difference_is_exact(self):
        other=copy.deepcopy(self.feedback);other[0]['ack_hex']='8000000000000001'
        self.fc=r.compare_rows(self.feedback,other,r.FEEDBACK_FIELDS)
        self.assertEqual(self.fc['differences'][0]['fields'],['ack_hex'])
    def test_small_time_roundoff_permitted(self):
        other=copy.deepcopy(self.feedback);other[0]['time_s']+=Decimal('1e-9')
        self.assertTrue(r.compare_rows(self.feedback,other,r.FEEDBACK_FIELDS)['matches_native'])
    def test_clock_difference_beyond_tolerance_reported(self):
        other=copy.deepcopy(self.feedback);other[0]['time_s']+=Decimal('1.001e-9')
        self.assertFalse(r.compare_rows(self.feedback,other,r.FEEDBACK_FIELDS)['matches_native'])


class MilestoneTests(unittest.TestCase):
    def setUp(self):
        actions,rows,_=fixture();self.rows=r.validate_checkpoints(rows,actions,'synthetic')
        self.contract={'milestones':[{'case_id':'synthetic','step':4,'equals':{'nsdp_releases':1}}],
                       'native_milestones':[{'case_id':'synthetic','step':2,'equals':{'nwk_owned':2}}]}
    def test_native_specific_milestone_does_not_hide_matlab_difference(self):
        self.assertEqual(r.verify_milestones(self.rows,self.contract,'MATLAB')['field_assertions'],1)
        with self.assertRaisesRegex(ValueError,'milestone mismatch'):r.verify_milestones(self.rows,self.contract,'native',native=True)
    def test_common_milestone_failure_blocks(self):
        self.contract['milestones'][0]['equals']['nsdp_releases']=2
        with self.assertRaisesRegex(ValueError,'milestone mismatch'):r.verify_milestones(self.rows,self.contract,'synthetic')
    def test_unknown_milestone_step_rejected(self):
        self.contract['milestones'][0]['step']=99
        with self.assertRaisesRegex(ValueError,'Unknown milestone'):r.verify_milestones(self.rows,self.contract,'synthetic')
    def test_duplicate_milestone_constraint_rejected(self):
        self.contract['milestones']*=2
        with self.assertRaisesRegex(ValueError,'Duplicate milestone'):r.verify_milestones(self.rows,self.contract,'synthetic')


class OutputAndInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        self.source=self.root/'source';self.source.mkdir();self.evidence=self.root/'owner';self.evidence.mkdir()
        (self.source/'keep.txt').write_text('source unchanged');(self.evidence/'metadata.json').write_text('{}')
    def tearDown(self): self.temporary.cleanup()
    def test_output_cannot_overwrite_owner_input(self):
        result=r.main(['--source-root',str(self.source),'--evidence',str(self.evidence),'--output',str(self.evidence)])
        self.assertEqual(result,1);self.assertEqual((self.evidence/'metadata.json').read_text(),'{}')
        self.assertFalse((self.evidence/'review.json').exists())
    def test_output_cannot_be_inside_source(self):
        result=r.main(['--source-root',str(self.source),'--verify-candidate','--output',str(self.source/'analysis')])
        self.assertEqual(result,1);self.assertFalse((self.source/'analysis').exists())
        self.assertEqual((self.source/'keep.txt').read_text(),'source unchanged')
    def test_output_cannot_contain_input_root(self):
        with self.assertRaises(ValueError):r.t17.output_location(self.evidence,self.source,self.root)
    def test_inventory_cannot_omit_unexpected_artifact(self):
        (self.evidence/'unlisted.csv').write_text('unlisted')
        records=[{'path':'metadata.json','sha256':r.sha256(self.evidence/'metadata.json'),'bytes':2}]
        with self.assertRaisesRegex(ValueError,'not closed'):r.inventory(self.evidence,records)
    def test_inventory_hash_mismatch_rejected(self):
        records=[{'path':'metadata.json','sha256':'0'*64,'bytes':2}]
        with self.assertRaisesRegex(ValueError,'hash or size'):r.inventory(self.evidence,records)
    def test_zip_path_escape_rejected(self):
        archive=self.root/'bad.zip'
        with zipfile.ZipFile(archive,'w') as bundle:
            bundle.writestr('metadata.json','{}');bundle.writestr('../escape','bad')
        with self.assertRaises(ValueError):
            with r.t17.evidence_directory(archive):pass
        self.assertFalse((self.root/'escape').exists())
    def test_duplicate_json_keys_rejected(self):
        (self.evidence/'metadata.json').write_text('{"passed":true,"passed":false}')
        with self.assertRaisesRegex(ValueError,'Duplicate JSON'):r.json_object(self.evidence/'metadata.json')


class InheritedReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        self.archive='evidence/t23/baseline/parity-ledger.csv';path=self.root/self.archive
        path.parent.mkdir(parents=True);path.write_text('accepted ledger\n')
        self.inherited={'docs/parity-ledger.csv':{'path':'docs/parity-ledger.csv','sha256':r.sha256(path),'bytes':path.stat().st_size}}
        self.inherited.update({f'evidence/inherited-{index}.json':{'path':f'evidence/inherited-{index}.json','sha256':'1'*64,'bytes':1} for index in range(156)})
        self.entries=copy.deepcopy(self.inherited)
        self.entries[self.archive]=dict(self.inherited['docs/parity-ledger.csv'],path=self.archive)
        self.entries['docs/parity-ledger.csv']['sha256']='2'*64
        self.candidate={'AllowedModifiedReferenceFiles':['docs/parity-ledger.csv']}
    def tearDown(self):self.temporary.cleanup()
    def runcheck(self):return r.verify_inherited_references(self.root,self.candidate,self.entries,self.inherited)
    def test_current_documentation_can_change_when_accepted_copy_is_exact(self):self.runcheck()
    def test_other_reference_change_rejected(self):
        self.entries['evidence/inherited-0.json']['sha256']='3'*64
        with self.assertRaisesRegex(ValueError,'non-ledger'):self.runcheck()
    def test_reference_omission_rejected(self):
        self.entries.pop('evidence/inherited-0.json')
        with self.assertRaisesRegex(ValueError,'non-ledger'):self.runcheck()
    def test_preserved_ledger_byte_tamper_rejected(self):
        (self.root/self.archive).write_text('rewritten ledger')
        with self.assertRaisesRegex(ValueError,'not preserved exactly'):self.runcheck()
    def test_preserved_ledger_inventory_tamper_rejected(self):
        self.entries[self.archive]['sha256']='3'*64
        with self.assertRaisesRegex(ValueError,'not preserved exactly'):self.runcheck()
    def test_missing_preserved_ledger_rejected(self):
        self.entries.pop(self.archive)
        with self.assertRaisesRegex(ValueError,'reference missing'):self.runcheck()
    def test_exception_cannot_expand_to_production_reference(self):
        self.candidate['AllowedModifiedReferenceFiles'].append('evidence/inherited-0.json')
        with self.assertRaisesRegex(ValueError,'Only the current'):self.runcheck()


class NativeTraceMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=Path(__file__).resolve().parents[2]
        cls.native=cls.source/r.REFERENCE
        actions=r.csv_rows(cls.source/r.ACTIONS,r.ACTION_FIELDS)
        cls.states=r.validate_checkpoints(r.csv_rows(cls.native/'checkpoints.csv',r.STATE_FIELDS),actions,'native')
        cls.frames=r.validate_feedback(r.csv_rows(cls.native/'feedback.csv',r.FEEDBACK_FIELDS),actions,cls.states,'native')
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.directory=Path(self.temporary.name)/'native';self.directory.mkdir()
        for name in ('trace_on','trace_off'):shutil.copytree(self.native/name,self.directory/name)
        for name in ('checkpoints.csv','feedback.csv'):shutil.copy2(self.native/name,self.directory/name)
    def tearDown(self):self.temporary.cleanup()
    def runcheck(self):return r.verify_native_raw(self.directory,self.states,self.frames,list(r.CASE_IDS))
    def alter_trace(self,mutator):
        path=self.directory/'trace_on/release_idempotence/trace.csv';rows=r.csv_rows(path);mutator(rows)
        with path.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
    def test_raw_traces_reconcile_observed_states(self):
        result=self.runcheck();self.assertTrue(result['observer_on_off_identical']);self.assertEqual(result['trace_events'],1678)
    def test_duplicate_capacity_release_trace_rejected(self):
        def mutate(rows):
            item=next(row for row in rows if row['event']=='hop_capacity_release');item['detail']=item['detail'].replace('nsdp_released=0','nsdp_released=1')
        self.alter_trace(mutate)
        with self.assertRaisesRegex(ValueError,'delayed capacity'):self.runcheck()
    def test_missing_nwk_release_detected_without_summary_receipts(self):
        def mutate(rows):
            item=next(row for row in rows if row['event']=='nwk_nsdp_release');item['event']='removed_release'
        self.alter_trace(mutate)
        with self.assertRaisesRegex(ValueError,'ordered feedback/completion'):self.runcheck()
    def test_expiry_must_release_the_dacked_identity(self):
        def mutate(rows):
            item=next(row for row in rows if row['event']=='hop_capacity_release');item['detail']=item['detail'].replace('hop_sequence=2','hop_sequence=1')
        self.alter_trace(mutate)
        with self.assertRaisesRegex(ValueError,'delayed capacity'):self.runcheck()
    def test_unordered_event_index_rejected(self):
        def mutate(rows):rows[1]['event_index']=rows[0]['event_index']
        self.alter_trace(mutate)
        with self.assertRaisesRegex(ValueError,'not ordered'):self.runcheck()
    def test_changed_export_cannot_override_raw_checkpoint(self):
        path=self.directory/'checkpoints.csv';path.write_text(path.read_text().replace('relay_boundary,1,','altered,1,',1))
        with self.assertRaisesRegex(ValueError,'exported checkpoints'):self.runcheck()
    def test_observer_off_divergence_rejected(self):
        path=self.directory/'trace_off/relay_boundary/states.csv';path.write_text(path.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'Observer on/off'):self.runcheck()
    def test_actual_radio_execution_invalidates_scope(self):
        def mutate(rows):rows[0]['event']='tx_start'
        self.alter_trace(mutate)
        with self.assertRaisesRegex(ValueError,'actual PHY/MAC'):self.runcheck()


class FullSyntheticReturnTests(unittest.TestCase):
    """Exercise the complete review path with explicitly synthetic, temporary data."""
    @classmethod
    def setUpClass(cls):
        cls.source=Path(__file__).resolve().parents[2]
        if not (cls.source/r.CANDIDATE).is_file():raise unittest.SkipTest('Candidate not frozen yet')
        cls.candidate=r.json_object(cls.source/r.CANDIDATE)
        cls.prepared=r.verify_preparation(cls.source)
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
    def tearDown(self):self.temporary.cleanup()
    def write_return(self,mismatch=False):
        owner=self.root/'synthetic_owner';owner.mkdir();contract=owner/'contract';contract.mkdir()
        def write_json(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
        def write_csv(path,rows,fields):
            with path.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
        for name,path in (('candidate.json',r.CANDIDATE),('plan.json',r.PLAN)):
            shutil.copy2(self.source/path,owner/name)
        for name,path in (('actions.csv',r.ACTIONS),('cases.csv',r.CASES)):
            shutil.copy2(self.source/path,contract/name)
        sources=[{'path':name,'sha256':digest} for name,digest in sorted(self.prepared['source'].items())]
        references=list(self.prepared['references'].values())
        write_json(owner/'source.json',sources);write_json(owner/'references.json',references)
        states=r.csv_rows(self.source/r.REFERENCE/'checkpoints.csv',r.STATE_FIELDS)
        frames=r.csv_rows(self.source/r.REFERENCE/'feedback.csv',r.FEEDBACK_FIELDS)
        if mismatch:
            state=next(row for row in states if row['case_id']=='dack_duplicate_pressure' and row['step']=='18')
            for field in ('nsdp_relay','nwk_owned','nwk_waiting'):state[field]=str(int(state[field])-1)
            frame=next(row for row in frames if row['case_id']=='dack_duplicate_pressure' and row['step']=='18')
            for field in ('relay_nsdp','nwk_owned'):frame[field]=str(int(frame[field])-1)
        write_csv(contract/'checkpoints.csv',states,r.STATE_FIELDS);write_csv(contract/'feedback.csv',frames,r.FEEDBACK_FIELDS)
        parsed=r.validate_checkpoints(states,self.prepared['actions'],'synthetic-not-MATLAB')
        parsed_frames=r.validate_feedback(frames,self.prepared['actions'],parsed,'synthetic-not-MATLAB')
        comparison=r.compare_rows(parsed,self.prepared['native']['checkpoints'],r.STATE_FIELDS)
        frame_comparison=r.compare_rows(parsed_frames,self.prepared['native']['feedback'],r.FEEDBACK_FIELDS)
        passed=comparison['matches_native'] and frame_comparison['matches_native']
        summary={'Schema':'csr-tranche23-receiver-feedback-contract-v1','DiagnosticCompleted':True,'Passed':passed,
                 'CaseCount':len(r.CASE_IDS),'CheckpointCount':len(states),'FailedCount':comparison['unmatched_rows'],
                 'FeedbackCount':len(frames),'FeedbackFailedCount':frame_comparison['unmatched_rows'],
                 'NativeComparison':receipt(comparison),'NativeFeedbackComparison':receipt(frame_comparison),
                 'ActionsSHA256':r.sha256(self.source/r.ACTIONS),'CasesSHA256':r.sha256(self.source/r.CASES),
                 'NativeReferenceSHA256':r.sha256(self.source/r.REFERENCE/'checkpoints.csv'),
                 'NativeFeedbackReferenceSHA256':r.sha256(self.source/r.REFERENCE/'feedback.csv'),
                 'DataQueuedRetryPolicy':'actual-tx','SyntheticTestFixture':True}
        write_json(contract/'summary.json',summary)
        names=self.candidate['ExpectedTestNames']
        tests=[{'Name':name,'Passed':'1','Failed':'0','Incomplete':'0','DurationSeconds':'0'} for name in names]
        write_csv(owner/'tests.csv',tests,('Name','Passed','Failed','Incomplete','DurationSeconds'))
        (owner/'run.log').write_text('SYNTHETIC PYTHON UNIT TEST ONLY. No MATLAB executed.\n')
        metadata={'Schema':r.SCHEMA,'Tranche':23,'SyntheticTestFixture':True,
                  'Status':'completed-review-required' if passed else 'completed-differences-review-required',
                  'CandidateFile':r.CANDIDATE,'CandidateSHA256':r.sha256(self.source/r.CANDIDATE),
                  'Runtime':{'Runtime':'MATLAB','DefaultBackend':'portable','Version':'SYNTHETIC-NOT-EXECUTION','Release':'synthetic'},
                  'MATLABExecuted':True,'NativeExecuted':False,'SourceCommit':r.PIN,'FocusedGateExecuted':True,
                  'FullAcceptanceGateExecuted':False,'AcceptanceEstablished':False,'NumericalParityEstablished':False,
                  'WorkingCampusBandPercent':10,'StartedUTC':'2026-01-01T00:00:00Z','CompletedUTC':'2026-01-01T00:00:01Z',
                  'AllBaselineSourcesUnchanged':True,'BaselineSourceFilesVerified':390,'BaselineMatlabFilesVerified':178,
                  'SourceFilesFinal':sources,'SourceFilesStableDuringRun':True,'SourceSnapshotSHA256':r.sha256(owner/'source.json'),
                  'ReferenceFilesFinal':references,'ReferenceFilesStableDuringRun':True,'ReferenceSnapshotSHA256':r.sha256(owner/'references.json'),
                  'TestFiles':self.candidate['TestFiles'],'ExpectedTestNames':names,'TestResultsFile':'tests.csv',
                  'TestsExecuted':True,'TestsPassed':True,'TestCount':len(names),'PassedTests':len(names),'FailedTests':0,'IncompleteTests':0,
                  'ContractCompleted':True,'ContractPassed':passed,'EvidenceArchive':'t23.zip','InventoryExcludedPaths':['metadata.json','t23.zip']}
        metadata.update({'Contract'+field:summary[field] for field in ('CaseCount','CheckpointCount','FailedCount','FeedbackCount','FeedbackFailedCount')})
        metadata['Artifacts']=[{'path':name,'sha256':r.sha256(owner/name),'bytes':(owner/name).stat().st_size} for name in sorted(r.all_files(owner))]
        write_json(owner/'metadata.json',metadata)
        archive=self.root/'synthetic.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as bundle:
            for name in sorted(r.all_files(owner)):bundle.write(owner/name,name)
        return archive
    def test_complete_synthetic_matching_return(self):
        result=r.review(self.write_return(),self.source,self.root/'review')
        self.assertEqual(result['status'],'controlled_receiver_review_completed')
        self.assertTrue(result['cross_engine_contract_passed']);self.assertFalse(result['acceptance_established'])
        self.assertFalse(result['matlab_executed_by_reviewer']);self.assertEqual(result['tests']['count'],len(self.candidate['ExpectedTestNames']))
    def test_complete_synthetic_custody_difference_preserved(self):
        result=r.review(self.write_return(mismatch=True),self.source,self.root/'review')
        self.assertTrue(result['evidence_integrity_verified']);self.assertFalse(result['cross_engine_contract_passed'])
        self.assertFalse(result['acceptance_established']);self.assertEqual(result['contract']['native_comparison']['unmatched_rows'],1)
        self.assertEqual(result['contract']['native_feedback_comparison']['unmatched_rows'],1)


if __name__=='__main__':unittest.main()
