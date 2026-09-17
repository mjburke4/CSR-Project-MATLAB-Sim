"""T18 source/derivation, observer and prefix-integrity mutation fixtures."""
from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import analyze_tranche18_return as review


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value)+'\n',encoding='utf-8')


def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


class TemporaryCase(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)


class DerivedWorkloads(TemporaryCase):
    @classmethod
    def setUpClass(cls):
        cls.repository = Path(__file__).resolve().parents[2]
        cls.plan = review.json_object(cls.repository/review.PLAN)
        cls.parent = list(review.t7.csv_records(cls.repository/cls.plan['parent_scenario']))

    def test_all_ten_real_canonical_derivations_pass(self):
        candidate = {'Plan':review.PLAN,'PlanSHA256':review.sha256(self.repository/review.PLAN)}
        plan = review.verify_plan(self.repository,candidate)
        self.assertEqual(len(plan['cases']),10)
        self.assertEqual(plan['planned_simulated_seconds'],6900)
        self.assertEqual(plan['cases'][-1]['expected_admission_attempts'],180000)

    def test_rehashed_retained_geometry_or_flow_modification_fails(self):
        case = self.plan['cases'][2]
        original = list(review.t7.csv_records(self.repository/case['scenario_file']))
        for column,value,kind in (('x_m','-1','node'),('flow_interval_s','0.03','flow'),('mac_profile','guessed','run')):
            actual = copy.deepcopy(original)
            next(row for row in actual if row['record'] == kind)[column] = value
            with self.subTest(column=column),self.assertRaisesRegex(ValueError,'retained geometry/traffic/profile'):
                review.verify_derived_rows(self.parent,actual,case)

    def test_duplicate_or_missing_derived_row_fails(self):
        case = self.plan['cases'][0]
        original = list(review.t7.csv_records(self.repository/case['scenario_file']))
        for actual in (original[:-1],original+[original[-1]]):
            with self.subTest(size=len(actual)),self.assertRaisesRegex(ValueError,'retained geometry/traffic/profile'):
                review.verify_derived_rows(self.parent,actual,case)

    def test_candidate_plan_horizon_mutation_fails_even_with_new_hash(self):
        for path in (self.repository/'scenarios/t18').rglob('*'):
            if path.is_file():
                target = self.root/path.relative_to(self.repository)
                target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(path,target)
        parent = self.root/self.plan['parent_scenario']; parent.parent.mkdir(parents=True)
        shutil.copyfile(self.repository/self.plan['parent_scenario'],parent)
        plan = copy.deepcopy(self.plan); plan['cases'][0]['duration_s'] = 599
        write_json(self.root/review.PLAN,plan)
        with self.assertRaisesRegex(ValueError,'workload/window/budget'):
            review.verify_plan(self.root,{'Plan':review.PLAN,'PlanSHA256':review.sha256(self.root/review.PLAN)})


class ExactConfiguration(TemporaryCase):
    def setUp(self):
        super().setUp()
        self.repository = Path(__file__).resolve().parents[2]
        self.plan = review.json_object(self.repository/review.PLAN)
        with zipfile.ZipFile(self.repository/'evidence/t17/owner.zip') as archive:
            self.parent = json.loads(archive.read('campus/c/raw/summary.json'))['Config']

    def fixture(self,case):
        config = copy.deepcopy(self.parent)
        config.update(Name=case['scenario'],DurationSeconds=case['duration_s'],Seed=case['seed'],MaxEvents=case['max_events'])
        config['Nodes'] = [row for row in config['Nodes'] if row['Id'] in case['node_ids']]
        config['Traffic'] = [row for row in config['Traffic'] if row['SourceId'] in case['flow_sources']]
        for flow in config['Traffic']:
            flow['PacketCount'] = int((case['duration_s']-300)/.02)
        config['Trace'].update(MaxRecords=case['trace_limits']['protocol'],MaxPhyRecords=case['trace_limits']['phy'],
                              MaxApplicationAdmissionRecords=case['trace_limits']['admission'])
        shared = config['SharedScenario']
        shared.update(SourcePath=str(self.repository/case['scenario_file']),SourceSHA256=case['scenario_sha256'],
            NodeNames=[f'CSR_node_{node}' for node in case['node_ids']],ConfiguredFlowPacketBytes=[200]*len(case['flow_sources']))
        shared['OriginalNodeApplicationSettings'] = [row for row in shared['OriginalNodeApplicationSettings'] if row['NodeId'] in case['node_ids']]
        config['Benchmark'] = {'Schema':'csr-matlab-benchmark-v1','CaseId':case['case_id'],'SourceKind':case['source_kind'],
            'ProfileId':case['profile_id'],'OpnetAvailable':False,'BucketWidthSeconds':60,'ReferenceDirectory':case['reference_directory'],
            'CatalogSHA256':review.sha256(self.repository/review.PLAN),'HistoricalOutcomeEquivalenceEstablished':False}
        if len(config['Traffic']) == 1:
            config['Traffic'] = config['Traffic'][0]
            shared['ConfiguredFlowPacketBytes'] = 200
        return config

    def check(self,config,case):
        return review.verify_configuration(config,self.parent,case,self.repository,review.sha256(self.repository/review.PLAN))

    def test_single_flow_matlab_scalar_and_full_prefix_configurations(self):
        for case in (self.plan['cases'][0],self.plan['cases'][2],self.plan['cases'][-1]):
            with self.subTest(case=case['case_id']):
                self.assertTrue(self.check(self.fixture(case),case)['original_campus_inheritance_verified'])

    def test_phy_retry_budget_and_hidden_extra_config_changes_fail(self):
        case = self.plan['cases'][2]
        original = self.fixture(case)
        for group,field,value in (('Phy','CaptureMarginDb',9),('Hop','MaxResends',8),('Trace','MaxRecords',10),
                                  ('Nwk','SendOnlyToGateway',True),('SharedScenario','HopSecurityProfile','guessed')):
            config = copy.deepcopy(original); config[group][field] = value
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.check(config,case)
        original['ExtraTimingPolicy'] = 'nanoseconds'
        with self.assertRaisesRegex(ValueError,'exact campus derivation'):
            self.check(original,case)


class PassiveObserver(TemporaryCase):
    def setUp(self):
        super().setUp()
        self.on,self.off = self.root/'m128',self.root/'m128_off'
        for path in (self.on,self.off):
            write_json(path/'raw/summary.json',{'Config':{'Seed':128},'Statistics':{'Pending':3},
                'Metadata':{'RuntimeSeconds':1 if path == self.on else 2,'PendingEvents':4}})
            for filename in review.CORE_CSV:
                write_csv(path/'raw'/filename,[{'identity':1,'value':'same'}])
            for filename in ('applications.csv','aggregates.csv'):
                write_csv(path/'analysis'/filename,[{'identity':1,'value':'same'}])

    def test_nonzero_pending_and_different_wall_time_are_allowed(self):
        self.assertTrue(review.verify_nonperturbation(self.on,self.off)['passed'])

    def test_any_changed_core_csv_fails_without_numeric_tolerance(self):
        write_csv(self.off/'raw/protocol_trace.csv',[{'identity':1,'value':'changed'}])
        with self.assertRaisesRegex(ValueError,'core CSV bytes'):
            review.verify_nonperturbation(self.on,self.off)

    def test_changed_statistics_or_pending_event_state_fails(self):
        path = self.off/'raw/summary.json'; original = review.json_object(path)
        for group,key in (('Statistics','Pending'),('Metadata','PendingEvents')):
            changed = copy.deepcopy(original); changed[group][key] += 1; write_json(path,changed)
            with self.subTest(group=group),self.assertRaisesRegex(ValueError,'Observer changes'):
                review.verify_nonperturbation(self.on,self.off)

    def test_missing_or_duplicate_claim_file_cannot_pass(self):
        claim = {'Schema':'csr-tranche18-observer-nonperturbation-v1','ObserverOnCase':'m128','ObserverOffCase':'m128_off',
            'MetadataExcludedFields':['RuntimeSeconds'],'Passed':True,'StatisticsEqual':True,'ConfigurationEqual':True,
            'MetadataEqualExcludingRuntimeSeconds':True,'ObservedSummarySHA256':review.sha256(self.on/'raw/summary.json'),
            'ControlSummarySHA256':review.sha256(self.off/'raw/summary.json'),
            'Files':[{'Path':filename,'ObservedSHA256':review.sha256(self.on/'raw'/filename),
                'ControlSHA256':review.sha256(self.off/'raw'/filename),'Equal':True} for filename in review.CORE_CSV]}
        review.verify_nonperturbation_claim(claim,self.on,self.off)
        original = copy.deepcopy(claim['Files'])
        for files in (original[:-1],original[:-1]+[original[0]]):
            claim['Files'] = files
            with self.subTest(size=len(files)),self.assertRaisesRegex(ValueError,'membership mismatch'):
                review.verify_nonperturbation_claim(claim,self.on,self.off)


class CampusPrefix(unittest.TestCase):
    @staticmethod
    def row(time,event='app_generate',packet=1):
        return {'TimeSeconds':str(time),'Event':event,'PacketId':str(packet)}

    def test_strict_pre_stop_prefix_separates_boundary(self):
        baseline = [self.row(300),self.row(899.99,packet=2),self.row(900,packet=3),self.row(901,packet=4)]
        current = baseline[:2]+[self.row(900,'hop_timer',9)]
        result = review.compare_prefix_rows(baseline,current,horizon=900)
        self.assertEqual(result['matched_pre_stop_rows'],2)
        self.assertEqual((result['baseline_boundary_rows'],result['current_boundary_rows']),(1,1))

    def test_missing_extra_or_modified_pre_stop_row_fails(self):
        baseline = [self.row(300),self.row(899.99,packet=2),self.row(900,packet=3)]
        for current in (baseline[:1],baseline[:1]+[self.row(899.98,packet=2)],baseline[:2]+[self.row(899.999,packet=9)]):
            with self.subTest(current=current),self.assertRaises(ValueError):
                review.compare_prefix_rows(baseline,current,horizon=900)

    def test_censored_admission_tail_is_reported_without_fabricated_baseline(self):
        baseline = [self.row(300),self.row(600,packet=2)]
        current = baseline+[self.row(700,packet=3),self.row(899,packet=4)]
        result = review.compare_prefix_rows(baseline,current,horizon=900,partial_baseline=True)
        self.assertEqual(result['matched_pre_stop_rows'],2)
        self.assertEqual(result['new_rows_beyond_retained_baseline'],2)
        self.assertTrue(result['baseline_capture_censored'])

    def test_horizon_overrun_or_early_current_prefix_termination_fails(self):
        baseline = [self.row(300),self.row(600,packet=2)]
        for current in (baseline+[self.row(901,packet=3)],baseline[:1]):
            with self.subTest(current=current),self.assertRaises(ValueError):
                review.compare_prefix_rows(baseline,current,horizon=900,partial_baseline=True)


class ClosedCallbackHorizon(TemporaryCase):
    def test_exact_stop_transmission_is_censored_as_pending_receiver(self):
        config = {'DurationSeconds':600,'Nodes':[{'Id':1},{'Id':4}]}
        stats = {'PhysicalTransmissions':1,'PhysicalAttempts':1,'PhysicalReceived':0,'PhysicalDropped':0,'PhysicalPending':1}
        performance = {'ProtocolTraceRecords':1,'PhyTraceRecords':0}
        write_csv(self.root/'raw/protocol_trace.csv',[{'TimeSeconds':600,'Event':'tx_start','NodeId':4,'PacketId':1}])
        path = self.root/'raw/phy_trace.csv'; path.write_text('TimeSeconds,Event,PacketId,NodeId,SourceId,Success,Reason\n')
        result = review.verify_physical_trace(self.root,config,stats,performance)
        self.assertEqual(result['transmissions_exactly_at_stop'],1)
        self.assertEqual(result['pending_receivers'],1)
        write_csv(self.root/'raw/protocol_trace.csv',[{'TimeSeconds':600.00001,'Event':'tx_start','NodeId':4,'PacketId':1}])
        with self.assertRaisesRegex(ValueError,'closed simulation horizon'):
            review.verify_physical_trace(self.root,config,stats,performance)


class ReferenceAndFailure(TemporaryCase):
    def test_reference_membership_and_frozen_content_are_both_required(self):
        names = sorted([review.BASELINE,'evidence/t17/owner.zip','evidence/t17/candidate.json',
                        'evidence/t17/acceptance.json',review.REFERENCE+'/manifest.json'])
        for name in names:
            path = self.root/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text('{}\n')
        inventory = [{'path':name,'sha256':review.sha256(self.root/name),'bytes':(self.root/name).stat().st_size} for name in names]
        candidate = {'ReferenceRoots':[],'ReferenceFiles':names,'ReferenceFileInventory':inventory}
        self.assertEqual(len(review.verify_references(self.root,candidate)),5)
        candidate['ReferenceFiles'] = names[:-1]
        with self.assertRaisesRegex(ValueError,'membership mismatch'):
            review.verify_references(self.root,candidate)
        candidate['ReferenceFiles'] = names
        (self.root/names[0]).write_text('changed')
        with self.assertRaisesRegex(ValueError,'hash or size mismatch'):
            review.verify_references(self.root,candidate)

    def test_partial_return_always_writes_failed_review(self):
        evidence = self.root/'return'; write_json(evidence/'metadata.json',{'Status':'failed'})
        output = self.root/'review'
        with patch.object(review,'verify_preparation',side_effect=ValueError('incomplete required case')):
            code = review.main(['--evidence',str(evidence),'--source-root',str(self.root/'source'),'--output',str(output)])
        self.assertEqual(code,1)
        result = review.json_object(output/'review.json')
        self.assertEqual(result['status'],'review_failed')
        self.assertFalse(result['evidence_integrity_verified'])
        self.assertFalse(result['focused_structural_gate_completed'])
        self.assertFalse(result['numerical_parity_established'])

    def test_unsafe_failure_output_does_not_modify_input(self):
        evidence = self.root/'return'; write_json(evidence/'metadata.json',{'Status':'failed'})
        before = (evidence/'metadata.json').read_bytes()
        code = review.main(['--evidence',str(evidence),'--source-root',str(self.root/'source'),'--output',str(evidence/'review')])
        self.assertEqual(code,1)
        self.assertFalse((evidence/'review').exists())
        self.assertEqual((evidence/'metadata.json').read_bytes(),before)


if __name__ == '__main__':
    unittest.main()
