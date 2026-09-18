"""Adversarial T22 evidence checks. Synthetic fixtures are not MATLAB runs."""
import copy
import csv
from decimal import Decimal
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import analyze_tranche22_return as r


def fixture():
    def action(step,time,kind,packet='',ack='',dack=''):
        return dict(zip(r.ACTION_FIELDS,('hold',str(step),str(time),kind,packet,'8',ack,dack,'')))
    actions = [action(1,0,'PROBE'), action(2,.1,'SEND','p'), action(3,.1,'TX','p'),
               action(4,.2,'FEEDBACK',dack='p'), action(5,20.3,'PROBE')]
    state_values = [
        (-1,0,0,0,0,0,0,1,0,0,0,0,0,0,0),
        (1,0,0,1,1,0,1,0,0,0,0,0,0,0,0),
        (-1,0,0,1,1,0,1,0,0,0,0,0,0,1,0),
        (-1,0,0,1,1,1,0,0,0,1,0,1,0,1,0),
        (-1,0,0,0,0,0,0,1,0,1,0,1,0,1,1),
    ]
    rows = []
    for action,values in zip(actions,state_values):
        row = {field:action[field] for field in r.STATE_FIELDS[:6]}
        row.update({field:str(value) for field,value in zip(r.STATE_FIELDS[6:],values)})
        rows.append(row)
    return actions,rows


class ActionMembershipTests(unittest.TestCase):
    def setUp(self): self.actions,_ = fixture()
    def test_complete_ordered_actions(self):
        self.assertEqual(r.verify_actions(self.actions,['hold']),{'hold':5})
    def test_unknown_case_rejected(self):
        self.actions[2]['case_id']='unexpected'
        with self.assertRaisesRegex(ValueError,'Unknown action case'):r.verify_actions(self.actions,['hold'])
    def test_duplicate_step_rejected(self):
        self.actions[2]['step']='2'
        with self.assertRaisesRegex(ValueError,'step'):r.verify_actions(self.actions,['hold'])
    def test_reordered_case_rejected(self):
        self.actions[0]['case_id']='other'
        with self.assertRaisesRegex(ValueError,'reordered'):r.verify_actions(self.actions,['hold','other'])
    def test_missing_case_rejected(self):
        with self.assertRaisesRegex(ValueError,'Missing planned case'):r.verify_actions(self.actions,['hold','missing'])
    def test_unknown_feedback_identity_rejected(self):
        self.actions[3]['dack_packets']='absent'
        with self.assertRaisesRegex(ValueError,'feedback alias'):r.verify_actions(self.actions,['hold'])
    def test_repeated_feedback_alias_rejected(self):
        self.actions[3]['dack_packets']='p;p'
        with self.assertRaisesRegex(ValueError,'feedback alias'):r.verify_actions(self.actions,['hold'])
    def test_unoffered_tx_rejected(self):
        self.actions[2]['packet']='absent'
        with self.assertRaisesRegex(ValueError,'TX alias'):r.verify_actions(self.actions,['hold'])
    def test_time_reversal_rejected(self):
        self.actions[3]['time_s']='0.09'
        with self.assertRaisesRegex(ValueError,'backwards'):r.verify_actions(self.actions,['hold'])


class CheckpointMutationTests(unittest.TestCase):
    def setUp(self): self.actions,self.rows = fixture()
    def validate(self): return r.validate_checkpoints(self.rows,self.actions,'synthetic')
    def test_dack_releases_custody_before_capacity(self):
        rows = self.validate()
        self.assertEqual(rows[3]['nsdp_release_total'],1)
        self.assertEqual(rows[3]['global_pending'],1)
        self.assertEqual(rows[-1]['nsdp_release_total'],1)
        self.assertEqual(rows[-1]['global_pending'],0)
    def test_missing_checkpoint_rejected(self):
        self.rows.pop()
        with self.assertRaisesRegex(ValueError,'checkpoint rows'):self.validate()
    def test_extra_checkpoint_rejected(self):
        self.rows.append(copy.deepcopy(self.rows[-1]))
        with self.assertRaisesRegex(ValueError,'checkpoint rows'):self.validate()
    def test_duplicate_case_step_rejected(self):
        self.rows[3]=copy.deepcopy(self.rows[2])
        with self.assertRaises(ValueError):self.validate()
    def test_renamed_action_rejected(self):
        self.rows[2]['action']='PROBE'
        with self.assertRaisesRegex(ValueError,'action/case/packet'):self.validate()
    def test_peer_change_rejected(self):
        self.rows[2]['peer']='9'
        with self.assertRaisesRegex(ValueError,'peer'):self.validate()
    def test_fractional_state_rejected(self):
        self.rows[3]['threshold']='0.5'
        with self.assertRaisesRegex(ValueError,'integer'):self.validate()
    def test_boolean_state_rejected(self):
        self.rows[3]['outstanding']=True
        with self.assertRaisesRegex(ValueError,'Boolean'):self.validate()
    def test_nan_state_rejected(self):
        self.rows[3]['threshold']='NaN'
        with self.assertRaisesRegex(ValueError,'finite'):self.validate()
    def test_unexpected_column_rejected(self):
        self.rows[3]['pass']='true'
        with self.assertRaisesRegex(ValueError,'CSV schema'):self.validate()
    def test_hold_does_not_consume_resend_entry(self):
        self.rows[3]['resend']='1'
        with self.assertRaisesRegex(ValueError,'ownership'):self.validate()
    def test_duplicate_nsdp_release_at_expiry_rejected(self):
        self.rows[-1]['nsdp_release_total']='2'
        with self.assertRaisesRegex(ValueError,'custody release'):self.validate()
    def test_fabricated_completion_rejected(self):
        self.rows[-1]['ack_total']='1';self.rows[-1]['nsdp_release_total']='2'
        with self.assertRaisesRegex(ValueError,'identity conservation'):self.validate()
    def test_can_send_must_include_global_capacity(self):
        self.rows[3]['can_send']='1'
        with self.assertRaisesRegex(ValueError,'admission'):self.validate()
    def test_time_tolerance_boundary(self):
        self.rows[3]['time_s']='0.200000001'
        self.validate()
        self.rows[3]['time_s']='0.2000000011'
        with self.assertRaisesRegex(ValueError,'time mismatch'):self.validate()
    def test_acceptance_sentinel_rejected(self):
        self.rows[3]['accepted']='0'
        with self.assertRaisesRegex(ValueError,'sentinel'):self.validate()
    def test_dack_expiry_counter_cannot_exceed_completions(self):
        self.rows[-1]['dack_expired_total']='2'
        with self.assertRaisesRegex(ValueError,'expirations'):self.validate()
    def test_monotonic_counters_required(self):
        self.rows[-1]['tx_total']='0'
        with self.assertRaisesRegex(ValueError,'decreased'):self.validate()
    def test_ack_accumulator_bound(self):
        self.rows[-1]['ack_count']='3'
        with self.assertRaisesRegex(ValueError,'threshold'):self.validate()


class ComparisonAndReceiptTests(unittest.TestCase):
    def setUp(self):
        actions,rows = fixture()
        self.actual = r.validate_checkpoints(rows,actions,'synthetic')
        self.comparison = r.compare_checkpoints(self.actual,copy.deepcopy(self.actual))
        self.summary = {'DiagnosticCompleted':True,'Passed':True,'CaseCount':1,'CheckpointCount':5,'FailedCount':0,
            'NativeComparison':{'ReferencePresent':True,'SchemaMatches':True,'ActualRows':5,'ReferenceRows':5,
                                'MatchedRows':5,'UnmatchedRows':0,'FailedRows':[]}}
        self.metadata = {'ContractCompleted':True,'ContractPassed':True,'ContractCaseCount':1,
                         'ContractCheckpointCount':5,'ContractFailedCount':0}
    def test_complete_receipt(self):
        self.assertEqual(r.verify_summary(self.summary,self.metadata,self.comparison,1)['FailedCount'],0)
    def test_integer_difference_is_not_ten_percent_tolerance(self):
        other=copy.deepcopy(self.actual);other[-1]['threshold']=1
        result=r.compare_checkpoints(self.actual,other)
        self.assertFalse(result['matches_native']);self.assertEqual(result['unmatched_rows'],1)
        self.assertEqual(result['differences'][0]['fields'],['threshold'])
    def test_time_roundoff_can_match(self):
        other=copy.deepcopy(self.actual);other[-1]['time_s']+=Decimal('1e-9')
        self.assertTrue(r.compare_checkpoints(self.actual,other)['matches_native'])
    def test_false_pass_flag_rejected(self):
        other=copy.deepcopy(self.actual);other[-1]['threshold']=1
        with self.assertRaisesRegex(ValueError,'flags disagree'):
            r.verify_summary(self.summary,self.metadata,r.compare_checkpoints(self.actual,other),1)
    def test_wrong_comparison_count_rejected(self):
        self.summary['NativeComparison']['MatchedRows']=4
        with self.assertRaisesRegex(ValueError,'receipt count'):r.verify_summary(self.summary,self.metadata,self.comparison,1)
    def test_wrong_case_count_rejected(self):
        self.metadata['ContractCaseCount']=2
        with self.assertRaisesRegex(ValueError,'count'):r.verify_summary(self.summary,self.metadata,self.comparison,1)
    def test_missing_native_receipt_rejected(self):
        self.summary['NativeComparison']['ReferencePresent']=False
        with self.assertRaisesRegex(ValueError,'native comparison'):r.verify_summary(self.summary,self.metadata,self.comparison,1)
    def test_truthfully_failed_contract_is_not_accepted(self):
        self.comparison.update(matches_native=False,matched_rows=4,unmatched_rows=1)
        self.comparison['differences']=[{'row':5}]
        self.summary.update(Passed=False,FailedCount=1)
        self.summary['NativeComparison'].update(MatchedRows=4,UnmatchedRows=1,FailedRows=5)
        self.metadata.update(ContractPassed=False,ContractFailedCount=1)
        with self.assertRaisesRegex(ValueError,'differs from pinned native'):
            r.verify_summary(self.summary,self.metadata,self.comparison,1)
    def test_unknown_failed_row_identity_rejected(self):
        self.summary['NativeComparison']['FailedRows']=[2]
        with self.assertRaisesRegex(ValueError,'failed-row identity'):
            r.verify_summary(self.summary,self.metadata,self.comparison,1)


class EvidenceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)
        self.file=self.root/'rows.csv';self.file.write_text('row\n1\n')
        self.inventory=[{'path':'rows.csv','sha256':r.sha256(self.file),'bytes':self.file.stat().st_size}]
    def tearDown(self):self.temporary.cleanup()
    def test_closed_inventory_passes(self):self.assertEqual(len(r.inventory(self.root,self.inventory)),1)
    def test_unlisted_artifact_rejected(self):
        (self.root/'extra.txt').write_text('unexpected')
        with self.assertRaisesRegex(ValueError,'not closed'):r.inventory(self.root,self.inventory)
    def test_modified_evidence_rejected(self):
        self.file.write_text('row\n2\n')
        with self.assertRaisesRegex(ValueError,'hash or size'):r.inventory(self.root,self.inventory)
    def test_case_colliding_inventory_rejected(self):
        self.inventory.append(dict(self.inventory[0],path='ROWS.csv'))
        with self.assertRaisesRegex(ValueError,'Duplicate'):r.inventory(self.root,self.inventory)
    def test_path_traversal_rejected(self):
        self.inventory[0]['path']='../rows.csv'
        with self.assertRaisesRegex(ValueError,'Unsafe'):r.inventory(self.root,self.inventory)
    def test_duplicate_json_keys_rejected(self):
        file=self.root/'metadata.json';file.write_text('{"Passed":true,"Passed":false}')
        with self.assertRaisesRegex(ValueError,'Duplicate JSON'):r.json_object(file)
    def test_failed_owner_return_rejected(self):
        with self.assertRaisesRegex(ValueError,'not a completed'):
            r.verify_identity(self.root,{'Schema':r.SCHEMA,'Tranche':22,'Status':'failed'},self.root,{})
    def test_review_cannot_overwrite_evidence(self):
        with self.assertRaisesRegex(ValueError,'modify input'):
            r.t17.output_location(self.root,self.root/'source',self.root/'review')


class IndependentMilestoneTests(unittest.TestCase):
    def setUp(self):
        actions,rows=fixture();self.rows=r.validate_checkpoints(rows,actions,'synthetic')
        self.contract={'milestones':[{'case_id':'hold','step':4,
            'equals':{'dack_holds':1,'global_pending':1,'resend':0,'nsdp_release_total':1}}]}
    def test_dack_identity_milestone_passes(self):
        self.assertEqual(r.verify_milestones(self.rows,self.contract,'synthetic')['integer_assertions'],4)
    def test_milestone_mutation_rejected_independent_of_native(self):
        self.contract['milestones'][0]['equals']['dack_holds']=0
        with self.assertRaisesRegex(ValueError,'milestone mismatch'):r.verify_milestones(self.rows,self.contract,'synthetic')
    def test_unknown_milestone_case_rejected(self):
        self.contract['milestones'][0]['case_id']='unknown'
        with self.assertRaisesRegex(ValueError,'Unknown'):r.verify_milestones(self.rows,self.contract,'synthetic')
    def test_duplicate_milestone_rejected(self):
        self.contract['milestones']*=2
        with self.assertRaisesRegex(ValueError,'duplicate'):r.verify_milestones(self.rows,self.contract,'synthetic')
    def test_unsupported_milestone_field_rejected(self):
        self.contract['milestones'][0]['equals']['pass']=True
        with self.assertRaisesRegex(ValueError,'Unsupported'):r.verify_milestones(self.rows,self.contract,'synthetic')


@unittest.skipUnless(os.environ.get('CSR_T22_INTEGRATION') == '1',
                     'Set CSR_T22_INTEGRATION=1 after freezing the candidate/native reference.')
class IssuedCandidateIntegrationTests(unittest.TestCase):
    """End-to-end parser fixture only; native rows are NOT MATLAB measurements."""
    def test_synthetic_return_exercises_all_verification_layers(self):
        source_root=Path(__file__).resolve().parents[2]
        candidate=r.json_object(source_root/r.CANDIDATE)
        with tempfile.TemporaryDirectory(prefix='t22-synthetic-parser-test-') as temporary:
            base=Path(temporary);evidence=base/'synthetic-evidence';evidence.mkdir()
            contract=evidence/'contract';contract.mkdir()
            def write(name,value):
                (evidence/name).write_text(json.dumps(value,indent=2)+'\n')
            for origin,name in ((r.CANDIDATE,'candidate.json'),(r.PLAN,'plan.json'),
                                (r.ACTIONS,'contract/actions.csv'),(r.CASES,'contract/cases.csv'),
                                (r.REFERENCE+'/checkpoints.csv','contract/checkpoints.csv')):
                shutil.copyfile(source_root/origin,evidence/name)
            source=[{'path':path,'sha256':digest} for path,digest in r.candidate_snapshot(source_root).items()]
            references=candidate['ReferenceFileInventory']
            write('source.json',source);write('references.json',references)
            names=candidate['ExpectedTestNames']
            with (evidence/'tests.csv').open('w',newline='') as stream:
                writer=csv.writer(stream);writer.writerow(['Name','Passed','Failed','Incomplete','DurationSeconds'])
                writer.writerows((name,'true','false','false','0') for name in names)
            count=candidate['ExpectedCheckpointCount'];cases=candidate['ExpectedCaseCount']
            summary={'Schema':'csr-tranche22-adaptive-window-contract-v1','DiagnosticCompleted':True,'Passed':True,
                'CaseCount':cases,'CheckpointCount':count,'FailedCount':0,'ActionsSHA256':r.sha256(source_root/r.ACTIONS),
                'CasesSHA256':r.sha256(source_root/r.CASES),'NativeReferenceSHA256':r.sha256(source_root/r.REFERENCE/'checkpoints.csv'),
                'DataQueuedRetryPolicy':'actual-tx','NativeComparison':{'ReferencePresent':True,'SchemaMatches':True,
                    'ActualRows':count,'ReferenceRows':count,'MatchedRows':count,'UnmatchedRows':0,'FailedRows':[]},
                'Scope':'SYNTHETIC PARSER TEST ONLY. No MATLAB has executed.'}
            write('contract/summary.json',summary)
            metadata={'Schema':r.SCHEMA,'Tranche':22,'Status':'completed-review-required','CandidateFile':r.CANDIDATE,
                'CandidateSHA256':r.sha256(source_root/r.CANDIDATE),'Runtime':{'Runtime':'MATLAB','DefaultBackend':'portable',
                    'Version':'synthetic parser fixture only','Release':'synthetic fixture, not an executed release'},
                'MATLABExecuted':True,'NativeExecuted':False,'SourceCommit':r.PIN,'FocusedGateExecuted':True,
                'FullAcceptanceGateExecuted':False,'AcceptanceEstablished':False,'NumericalParityEstablished':False,
                'WorkingCampusBandPercent':10,'StartedUTC':'2026-09-17T00:00:00+00:00','CompletedUTC':'2026-09-17T00:00:01+00:00',
                'SourceFilesFinal':source,'SourceFilesStableDuringRun':True,'SourceSnapshotSHA256':r.sha256(evidence/'source.json'),
                'ReferenceFilesFinal':references,'ReferenceFilesStableDuringRun':True,'ReferenceSnapshotSHA256':r.sha256(evidence/'references.json'),
                'AllBaselineSourcesUnchanged':True,'BaselineSourceFilesVerified':376,'BaselineMatlabFilesVerified':175,
                'TestFiles':candidate['TestFiles'],'ExpectedTestNames':names,'TestResultsFile':'tests.csv','TestsExecuted':True,
                'TestsPassed':True,'TestCount':len(names),'PassedTests':len(names),'FailedTests':0,'IncompleteTests':0,
                'ContractCompleted':True,'ContractPassed':True,'ContractCaseCount':cases,'ContractCheckpointCount':count,
                'ContractFailedCount':0,'SyntheticParserFixtureOnly':True,'Artifacts':[
                    {'path':path.relative_to(evidence).as_posix(),'sha256':r.sha256(path),'bytes':path.stat().st_size}
                    for path in sorted(evidence.rglob('*')) if path.is_file()]}
            write('metadata.json',metadata)
            reviewed=r.review(evidence,source_root,base/'review')
            self.assertEqual(reviewed['contract']['checkpoint_count'],364)
            self.assertEqual(reviewed['tests']['count'],89)
            self.assertTrue(reviewed['contract']['native_comparison']['matches_native'])
            self.assertFalse(reviewed['matlab_executed_by_reviewer'])
            self.assertFalse(reviewed['numerical_parity_established'])


if __name__=='__main__':unittest.main()
