"""Adverse evidence tests for T27; these synthetic records are not MATLAB runs."""
import copy
import json
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
import warnings
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import analyze_tranche27_return as t27

ROOT = Path(__file__).resolve().parents[2]


def control(case, order, target, time):
    return dict(zip(t27.CONTROL_FIELDS,(case,str(order),str(time),'START','1',str(target),
        str(target),'0','1','[]')))


def state_document(case):
    snapshots = []
    for index,time in enumerate(case['checkpoints_s'],1):
        peers = list(case['initial_peers'])
        if case['late_peer_time_s'] is not None and time > case['late_peer_time_s']:
            peers.append(case['late_peer'])
        active = time < .1
        snapshots.append({'event_order':index,'time_s':time,'event':'checkpoint',
            'local_discovery_active':active,'topology_known':True,'gateway_available':False,'local_is_gateway':True,
            'active_peers':peers,'route_storage_order':peers,
            'logical_destination_birth_order_fixture':list(reversed(peers)),
            'application_state':{'DiscoveryActive':active,'TopologyKnown':True,'GatewayId':[]},
            'stats':{'DiscoveryStarts':1,'DiscoveryCompletions':int(not active)},
            'routes':[{'DestinationId':p,'NextHop':p,'Capability':1,'Selected':True} for p in peers],
            'neighbors':[{'Id':p,'Active':True,'Stale':False} for p in peers]})
    return {'Schema':'csr-tranche27-matlab-controller-states-v1','CaseId':case['id'],
        'PrivateControllerStateAvailable':False,
        'UnavailableControllerFields':['ScanKnown','ScanRequested','ScanWaiting','ScanGeneration',
                                       'NeighborDiscoveryState','WatchdogDeadline'],
        'ObservationMethod':'Synthetic public-state schema for checker tests only.','Snapshots':snapshots}


class Tranche27EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = t27.json_object(ROOT/t27.PLAN)
        cls.cases = {case['id']:case for case in cls.plan['cases']}

    def test_native_reference_actual_execution_is_verified(self):
        result = t27.verify_native(ROOT,self.plan)
        self.assertEqual((result['case_count'],result['checkpoint_count'],result['control_count']),(5,44,10))
        self.assertTrue(result['observer_on_off_identical'])
        self.assertFalse(result['matlab_executed'])

    def test_native_reference_byte_mutation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT/t27.REFERENCE,root/t27.REFERENCE)
            with (root/t27.REFERENCE/'C1.json').open('a') as stream:
                stream.write(' ')
            with self.assertRaisesRegex(ValueError,'Native reference hash mismatch'):
                t27.verify_native(root,self.plan)

    def test_known_late_peer_difference_remains_a_finding(self):
        case = self.cases['C1']
        native = t27.validate_controls([control('C1',1,3,.1)],case,'native')
        matlab = t27.validate_controls([control('C1',1,3,.1),control('C1',2,4,20)],case,'MATLAB')
        result = t27.compare_controls(matlab,native)
        self.assertFalse(result['matches_native'])
        self.assertEqual(result['differing_rows'],1)
        self.assertEqual(result['differences'][0]['fields'],['row_membership'])

    def test_unmatched_done_time_difference_is_not_hidden(self):
        case = self.cases['C2']
        native = t27.validate_controls([control('C2',1,4,.1),control('C2',2,5,1)],case,'native')
        matlab = t27.validate_controls([control('C2',1,4,.1),control('C2',2,5,60.1)],case,'MATLAB')
        result = t27.compare_controls(matlab,native)
        self.assertEqual(result['differences'][0]['fields'],['time_s'])
        self.assertFalse(result['matches_native'])

    def test_false_zero_difference_counter_rejected(self):
        case = self.cases['C1']
        native = t27.validate_controls([control('C1',1,3,.1)],case,'native')
        matlab = t27.validate_controls([control('C1',1,3,.1),control('C1',2,4,20)],case,'MATLAB')
        results = {'C1':{'controls':t27.compare_controls(matlab,native)}}
        summary = {'DifferingCaseCount':1,'DifferingControlRows':1}
        metadata = {'ContractDifferingCaseCount':1,'ContractDifferingControlRows':1}
        t27.verify_difference_counters(summary,metadata,results)
        metadata['ContractDifferingControlRows'] = 0
        with self.assertRaisesRegex(ValueError,'hide or invent'):
            t27.verify_difference_counters(summary,metadata,results)

    def test_control_clock_tolerance_is_absolute_one_nanosecond(self):
        case = self.cases['C0']
        left = t27.validate_controls([control('C0',1,5,.1),control('C0',2,3,60.1)],case,'left')
        right = copy.deepcopy(left)
        right[1]['time_s'] = '60.100000001'
        self.assertTrue(t27.compare_controls(left,right)['matches_native'])
        right[1]['time_s'] = '60.100000002'
        self.assertFalse(t27.compare_controls(left,right)['matches_native'])

    def test_control_loss_does_not_become_parity(self):
        left = t27.validate_controls([control('C0',1,5,.1)],self.cases['C0'],'left')
        right = t27.validate_controls([control('C0',1,5,.1),control('C0',2,3,60.1)],self.cases['C0'],'right')
        self.assertFalse(t27.compare_controls(left,right)['matches_native'])

    def test_duplicate_controls_rejected(self):
        with self.assertRaisesRegex(ValueError,'duplicated controller destination'):
            t27.validate_controls([control('C0',1,5,.1),control('C0',2,5,60.1)],self.cases['C0'],'case')

    def test_control_order_gap_rejected(self):
        with self.assertRaisesRegex(ValueError,'schema/case/order'):
            t27.validate_controls([control('C0',2,5,.1)],self.cases['C0'],'case')

    def test_nonfinite_control_time_rejected(self):
        for value in ('NaN','Infinity','-Infinity'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                t27.validate_controls([control('C0',1,5,value)],self.cases['C0'],'case')

    def test_boundary_control_outside_stop_rejected(self):
        with self.assertRaisesRegex(ValueError,'out-of-window'):
            t27.validate_controls([control('C0',1,5,.1),control('C0',2,3,60.3)],self.cases['C0'],'case')

    def test_ack_owned_control_rejected(self):
        row = control('C0',1,5,.1); row['ackable'] = '1'
        with self.assertRaisesRegex(ValueError,'best effort'):
            t27.validate_controls([row],self.cases['C0'],'case')

    def test_failed_enqueue_is_not_valid_complete_fixture(self):
        row = control('C0',1,5,.1); row['send_result'] = '0'
        with self.assertRaisesRegex(ValueError,'successfully enqueued'):
            t27.validate_controls([row],self.cases['C0'],'case')

    def test_state_complete_public_schema_accepted(self):
        document = state_document(self.cases['C1'])
        result = t27.validate_states(document,self.cases['C1'],'case')
        self.assertEqual(result['checkpoint_count'],8)
        self.assertFalse(result['private_controller_state_available'])

    def test_missing_checkpoint_rejected(self):
        document = state_document(self.cases['C1']); document['Snapshots'].pop()
        with self.assertRaisesRegex(ValueError,'missing/extra state checkpoints'):
            t27.validate_states(document,self.cases['C1'],'case')

    def test_late_peer_must_actually_become_usable(self):
        document = state_document(self.cases['C1'])
        document['Snapshots'][-1]['active_peers'] = [3]
        with self.assertRaisesRegex(ValueError,'usable peer membership'):
            t27.validate_states(document,self.cases['C1'],'case')

    def test_wrong_route_capability_cannot_masquerade_as_late_peer(self):
        document = state_document(self.cases['C1'])
        document['Snapshots'][-1]['routes'][-1]['Capability'] = 0
        with self.assertRaisesRegex(ValueError,'capable direct routes'):
            t27.validate_states(document,self.cases['C1'],'case')

    def test_private_state_claim_rejected(self):
        document = state_document(self.cases['C0']); document['PrivateControllerStateAvailable'] = True
        with self.assertRaisesRegex(ValueError,'private-access claim'):
            t27.validate_states(document,self.cases['C0'],'case')

    def test_mutated_public_flag_rejected(self):
        document = state_document(self.cases['C0']); document['Snapshots'][-1]['topology_known'] = False
        with self.assertRaisesRegex(ValueError,'topology/gateway setup'):
            t27.validate_states(document,self.cases['C0'],'case')

    def test_public_flag_raw_state_disagreement_rejected(self):
        document = state_document(self.cases['C0']); document['Snapshots'][-1]['application_state']['GatewayId'] = 3
        with self.assertRaisesRegex(ValueError,'flags disagree'):
            t27.validate_states(document,self.cases['C0'],'case')

    def test_json_duplicate_and_overflow_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'json'
            for contents in ('{"passed":true,"passed":false}','{"duration":1e999}','{"value":NaN}'):
                path.write_text(contents)
                with self.subTest(contents=contents), self.assertRaises(ValueError):
                    t27.json_object(path)

    def test_csv_duplicate_header_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'bad.csv'; path.write_text('time_s,time_s\n0,1\n')
            with self.assertRaises(ValueError):
                t27.csv_rows(path)

    def test_zip_duplicate_case_collision_and_traversal_rejected(self):
        for member in ('metadata.json','METADATA.JSON','../outside.json','/absolute.json','x\\outside.json'):
            with self.subTest(member=member), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary)/'t27.zip'
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore',UserWarning)
                    with zipfile.ZipFile(path,'w') as archive:
                        archive.writestr('metadata.json','{}'); archive.writestr(member,'{}')
                with self.assertRaises(ValueError), t27.evidence_directory(path):
                    pass

    def test_zip_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'t27.zip'
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('metadata.json','{}')
                info = zipfile.ZipInfo('alias'); info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info,'metadata.json')
            with self.assertRaisesRegex(ValueError,'Symlink'), t27.evidence_directory(path):
                pass

    def test_inventory_cannot_hide_unlisted_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root/'listed').write_text('1'); (root/'extra').write_text('2')
            items = [{'path':'listed','bytes':1,'sha256':t27.sha256(root/'listed')}]
            with self.assertRaisesRegex(ValueError,'not closed'):
                t27.inventory(root,items)


if __name__ == '__main__':
    unittest.main()
