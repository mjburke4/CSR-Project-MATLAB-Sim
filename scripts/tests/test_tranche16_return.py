#!/usr/bin/env python3
"""Negative evidence tests; synthetic rows never impersonate a MATLAB run."""
from __future__ import annotations
import copy
import csv
import json
import math
import warnings
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import analyze_tranche16_return as gate

SOURCE = Path(__file__).resolve().parents[2]


def fixture(mode='c'):
    config = {'DurationSeconds':1200,'Channel':{'PropagationSpeedMps':300000000},
              'Nodes':[{'Id':1,'PositionMeters':[0,0,0]},{'Id':2,'PositionMeters':[300,0,0]}]}
    tx,prop,duration,preamble = 3.121001,1e-6,.03,.01326
    components = [gate.rounded_ns(v) for v in (tx,prop,duration,preamble)]
    sums = [components[0]+components[1],sum((components[0],components[1],components[3])),sum(components[:3])]
    physical = [tx+prop,(tx+prop)+preamble,(tx+prop)+duration]
    selected = physical if mode == 'c' else [v/1e9 for v in sums]
    values = dict(zip(gate.TIME_FIELDS[:4],(tx,prop,duration,preamble)))
    for name,original,actual in zip(('Start','PreambleEnd','End'),physical,selected):
        values['Physical'+name+'Seconds']=original
        values[name+'Seconds']=actual
        values[name+'ShiftSeconds']=actual-original
    row={name:'0' for name in gate.TIMING_FIELDS}
    row.update(Ordinal='1',FrameId='1',SourceId='1',ReceiverId='2')
    for name,value in values.items():
        row[name]=format(value,'.15g');row[name+'Decimal']=format(value,'.17g');row[name+'Hex']=gate.hex64(value)
    for name,value in zip(('Tx','Propagation','Duration','Preamble'),components):row[name+'Nanoseconds']=str(value)
    for name,value in zip(('Start','PreambleEnd','End'),sums):row[name+'Nanoseconds']=str(value)
    audit={'Mode':gate.MODES[mode],'Count':1,'Omitted':0,'MaxRecords':100000,
           'MaxAbsShiftSeconds':max(abs(a-b) for a,b in zip(selected,physical))}
    protocol=[{'Event':'tx_start','PacketId':'1','NodeId':'1','TimeSeconds':format(tx,'.15g')}]
    return [row],audit,config,protocol


def applications():
    protocol=[]
    for event,packet,time,source,peer,reason in [('app_generate',1,1,1,2,''),('app_generate',2,2,1,2,''),
        ('app_receive',1,3,2,1,''),('app_generate',3,4,1,2,''),('app_drop',2,5,1,2,'retry_exhausted')]:
        protocol.append(dict(Event=event,PacketId=str(packet),TimeSeconds=str(time),NodeId=str(source),PeerId=str(peer),
                             Reason=reason,ApplicationBytes='16'))
    rows=[dict(PacketId='1',SourceId='1',DestinationId='2',ApplicationBytes='16',GeneratedSeconds='1',ReceivedSeconds='3',
              LatencySeconds='2',Outcome='delivered',DropReason=''),
          dict(PacketId='2',SourceId='1',DestinationId='2',ApplicationBytes='16',GeneratedSeconds='2',ReceivedSeconds='NaN',
              LatencySeconds='NaN',Outcome='dropped',DropReason='retry_exhausted'),
          dict(PacketId='3',SourceId='1',DestinationId='2',ApplicationBytes='16',GeneratedSeconds='4',ReceivedSeconds='NaN',
              LatencySeconds='NaN',Outcome='pending',DropReason='')]
    return rows,protocol,{'Generated':3,'Received':1,'Dropped':1,'Pending':1},{}


class TimingMutations(unittest.TestCase):
    def check(self,data,mode='c'):
        rows,audit,config,protocol=data
        return gate.validate_timing(rows,audit,mode,config,protocol,label='synthetic checker unit only')
    def test_both_modes_reconstruct_components_and_actual_transmission_identity(self):
        for mode in ('c','n'):
            with self.subTest(mode=mode):self.assertEqual(self.check(fixture(mode),mode)['receiver_records'],1)
    def test_no_observations_rejected(self):
        data=list(fixture());data[0]=[]
        with self.assertRaisesRegex(ValueError,'no receiver'):self.check(data)
    def test_zero_case_cannot_hide_as_audit_count_zero(self):
        data=list(fixture());data[0]=[];data[1]['Count']=0
        with self.assertRaises(ValueError):self.check(data)
    def test_omission_is_failure_even_when_remaining_rows_valid(self):
        data=fixture();data[1]['Omitted']=1
        with self.assertRaisesRegex(ValueError,'capacity/completion'):self.check(data)
    def test_over_capacity_audit_rejected(self):
        data=fixture();data[1]['MaxRecords']=0
        with self.assertRaisesRegex(ValueError,'capacity/completion'):self.check(data)
    def test_unknown_policy_rejected(self):
        with self.assertRaisesRegex(ValueError,'unknown policy'):self.check(fixture(),'x')
    def test_wrong_selected_policy_rejected(self):
        data=fixture('n');data[1]['Mode']='continuous'
        with self.assertRaisesRegex(ValueError,'policy/arithmetic'):self.check(data)
    def test_component_rounding_not_round_whole_sum(self):
        data=fixture();data[0][0]['EndNanoseconds']=str(int(data[0][0]['EndNanoseconds'])+1)
        with self.assertRaisesRegex(ValueError,'receiver sum'):self.check(data)
    def test_integer_component_not_fraction_or_float_string(self):
        data=fixture();data[0][0]['PropagationNanoseconds']='1000.0'
        with self.assertRaisesRegex(ValueError,'unsigned decimal'):self.check(data)
    def test_timing_ids_preserve_full_uint64(self):
        data=fixture();data[0][0]['FrameId']=str(2**63+1);data[3][0]['PacketId']=str(2**63+1)
        self.assertEqual(self.check(data)['transmissions'],1)
    def test_unknown_actual_tx_rejected(self):
        data=fixture();data[0][0]['FrameId']='2'
        with self.assertRaisesRegex(ValueError,'actual network TX'):self.check(data)
    def test_missing_peer_coverage_rejected(self):
        data=fixture();data[2]['Nodes'].append({'Id':3,'PositionMeters':[600,0,0]})
        with self.assertRaisesRegex(ValueError,'receiver timing coverage'):self.check(data)
    def test_duplicate_receiver_rejected(self):
        data=fixture();data[0].append(copy.deepcopy(data[0][0]));data[0][1]['Ordinal']='2';data[1]['Count']=2
        with self.assertRaisesRegex(ValueError,'duplicate/invalid receiver'):self.check(data)
    def test_changed_topology_prop_delay_rejected(self):
        data=fixture();data[2]['Nodes'][1]['PositionMeters'][0]=301
        with self.assertRaisesRegex(ValueError,'propagation differs'):self.check(data)
    def test_decimal_hex_roundtrip_required(self):
        data=fixture();data[0][0]['EndSecondsDecimal']='4'
        with self.assertRaisesRegex(ValueError,'round-trip'):self.check(data)
    def test_one_ulp_selected_target_not_hidden_by_nanoseconds(self):
        data=fixture();row=data[0][0];old=float(row['EndSecondsDecimal']);value=math.nextafter(old,math.inf)
        self.assertEqual(gate.rounded_ns(old),gate.rounded_ns(value))
        row.update(EndSecondsDecimal=format(value,'.17g'),EndSecondsHex=gate.hex64(value))
        with self.assertRaisesRegex(ValueError,'policy/arithmetic'):self.check(data)
    def test_wrong_physical_arithmetic_rejected(self):
        data=fixture();row=data[0][0];value=float(row['PhysicalEndSecondsDecimal'])+1e-9
        row.update(PhysicalEndSeconds=format(value,'.15g'),PhysicalEndSecondsDecimal=format(value,'.17g'),PhysicalEndSecondsHex=gate.hex64(value))
        with self.assertRaisesRegex(ValueError,'policy/arithmetic'):self.check(data)
    def test_max_shift_cannot_be_reported_as_zero(self):
        data=fixture('n');self.assertGreater(data[1]['MaxAbsShiftSeconds'],0);data[1]['MaxAbsShiftSeconds']=0
        with self.assertRaisesRegex(ValueError,'maximum shift'):self.check(data,'n')
    def test_nonfinite_time_is_rejected(self):
        data=fixture();data[0][0]['TxSecondsDecimal']='NaN';data[0][0]['TxSecondsHex']=gate.hex64(math.nan)
        with self.assertRaises(ValueError):self.check(data)
    def test_changed_schema_rejected(self):
        data=fixture();data[0][0]['invented']='1'
        with self.assertRaisesRegex(ValueError,'schema'):self.check(data)


class ApplicationAndBucketMutations(unittest.TestCase):
    def test_finite_stop_drop_and_pending_are_valid_outcomes(self):
        sent,received=gate.validate_applications(*applications())
        self.assertEqual(len(sent),3);self.assertEqual(len(received),1)
    def test_duplicate_application_export_is_rejected(self):
        data=applications();data[0][1]=copy.deepcopy(data[0][0])
        with self.assertRaisesRegex(ValueError,'duplicate'):gate.validate_applications(*data)
    def test_analysis_latency_cannot_be_forged_separate_from_raw_identity(self):
        data=applications();data[0][0]['ReceivedSeconds']='3.1'
        with self.assertRaisesRegex(ValueError,'delivery/latency'):gate.validate_applications(*data)
    def test_pending_cannot_be_counted_as_drop(self):
        data=applications();data[0][2]['Outcome']='dropped'
        with self.assertRaisesRegex(ValueError,'outcome differs'):gate.validate_applications(*data)
    def test_drop_reason_bound(self):
        data=applications();data[0][1]['DropReason']='unknown'
        with self.assertRaisesRegex(ValueError,'drop reason'):gate.validate_applications(*data)
    def test_generation_bound_to_original_packet(self):
        data=applications();data[0][2]['GeneratedSeconds']='4.1'
        with self.assertRaisesRegex(ValueError,'generation differs'):gate.validate_applications(*data)
    def test_bucket_comparison_joins_statistic_and_time_not_position(self):
        names=list(gate.aggregate.CORE_SERIES)
        a=[{'statistic':name,'time_s':'12','value':'1'} for name in names]
        b=list(reversed(copy.deepcopy(a)));b[0]['value']='2'
        result=gate.bucket_differences(a,b)
        self.assertEqual(sum(item['max_abs_bucket_difference'] for item in result),1)
    def test_missing_bucket_sample_is_not_converted_to_zero(self):
        a=[{'statistic':name,'time_s':'12','value':'NaN'} for name in gate.aggregate.CORE_SERIES]
        b=copy.deepcopy(a);b[0]['value']='0'
        result=gate.bucket_differences(a,b)
        self.assertEqual(result[0]['missing_sample_difference_count'],1)
        self.assertIsNone(result[0]['mean_signed_bucket_difference'])
    def test_duplicate_bucket_identity_rejected(self):
        a=[{'statistic':next(iter(gate.aggregate.CORE_SERIES)),'time_s':'12','value':'1'}]
        with self.assertRaisesRegex(ValueError,'Duplicate aggregate'):gate.bucket_differences(a+a,a)


class ArchiveAndRetainedEvidence(unittest.TestCase):
    def bad_archive(self,entries):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'bad.zip'
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                with zipfile.ZipFile(path,'w') as out:
                    for name,data in entries:out.writestr(name,data)
            with self.assertRaises((ValueError,zipfile.BadZipFile)):
                with gate.evidence_directory(path):pass
    def test_archive_parent_traversal_rejected(self):self.bad_archive([('../source.json','{}'),('metadata.json','{}')])
    def test_archive_case_colliding_paths_rejected(self):self.bad_archive([('Source.json','{}'),('source.json','{}'),('metadata.json','{}')])
    def test_archive_duplicate_members_rejected(self):self.bad_archive([('source.json','{}'),('source.json','{}'),('metadata.json','{}')])
    def test_inventory_hash_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'file').write_text('actual')
            with self.assertRaisesRegex(ValueError,'hash or size'):
                gate.inventory(root,[{'path':'file','sha256':'0'*64,'bytes':6}])
    def test_retained_native_workload_and_original_owner_configuration_are_bound(self):
        plan=gate.t8.verify_plan(SOURCE)
        case=next(row for row in plan['cases'] if row['case_id']=='two_node_admission_1200_s128')
        with zipfile.ZipFile(SOURCE/gate.CONFIG_ARCHIVE) as archive:
            old=json.loads(archive.read('b/a128/raw/summary.json'))['Config']
        self.assertTrue(gate.retained.same_configuration(old,copy.deepcopy(old),SOURCE,case)['configuration_equal'])
        mutated=copy.deepcopy(old);mutated['DurationSeconds']=1201
        with self.assertRaises(ValueError):gate.retained.same_configuration(old,mutated,SOURCE,case)
    def test_genuine_native_application_buckets_reconstruct_without_exact_rng_claim(self):
        plan=gate.t8.verify_plan(SOURCE);case=plan['cases'][0]
        result=gate.metrics.ns3_applications(SOURCE/case['reference_directory'],case)
        self.assertGreater(result['admitted'],0)
        self.assertIsNone(result['explicit_drops']);self.assertIsNone(result['pending'])



class ActualPhyCallbackMutations(unittest.TestCase):
    def sample(self):
        timing=fixture()[0]
        rows=[]
        for event,field in (('phy_signal_start','StartSecondsDecimal'),('phy_signal_end','EndSecondsDecimal')):
            rows.append({'Event':event,'PacketId':'1','NodeId':'2','SourceId':'1','TimeSeconds':timing[0][field],
                         'Reason':'' if event=='phy_signal_start' else 'received','Success':'1'})
        stats={'PhysicalReceived':1,'PhysicalDropped':0,'PhysicalPending':0}
        return timing,rows,stats,1200
    def test_actual_completed_receiver_joins_schedule(self):
        self.assertEqual(gate.validate_phy_callbacks(*self.sample())['actual_ends_joined'],1)
    def test_physical_callback_timestamp_tamper_rejected(self):
        data=self.sample();data[1][1]['TimeSeconds']=str(float(data[1][1]['TimeSeconds'])+1e-6)
        with self.assertRaisesRegex(ValueError,'outside scheduled'):gate.validate_phy_callbacks(*data)
    def test_missing_actual_completion_rejected(self):
        data=list(self.sample());data[1].pop()
        with self.assertRaisesRegex(ValueError,'coverage'):gate.validate_phy_callbacks(*data)
    def test_closure_completion_has_no_start_event(self):
        data=list(self.sample());data[1]=data[1][1:];data[1][0].update(Reason='closure',Success='0')
        data[2].update(PhysicalReceived=0,PhysicalDropped=1)
        self.assertEqual(gate.validate_phy_callbacks(*data)['actual_starts_joined'],0)
    def test_unknown_callback_receiver_rejected(self):
        data=self.sample();data[1][0]['NodeId']='3'
        with self.assertRaisesRegex(ValueError,'unknown receiver'):gate.validate_phy_callbacks(*data)
    def test_future_end_target_remains_pending(self):
        data=list(self.sample());data[3]=float(data[1][0]['TimeSeconds'])+.001;data[1].pop()
        data[2].update(PhysicalReceived=0,PhysicalPending=1)
        self.assertEqual(gate.validate_phy_callbacks(*data)['future_end_targets'],1)


class GenuineRetainedExports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory();cls.directory=Path(cls.temporary.name)
        with zipfile.ZipFile(SOURCE/gate.CONFIG_ARCHIVE) as archive:
            for name in archive.namelist():
                if name.startswith('b/a128/') and not name.endswith('/'):
                    target=cls.directory/name[len('b/a128/'):];target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(archive.read(name))
        cls.case=next(item for item in gate.t8.verify_plan(SOURCE)['cases'] if item['case_id']=='two_node_admission_1200_s128')
        cls.summary=gate.json_object(cls.directory/'raw/summary.json')
        cls.protocol=list(gate.metrics.csv_rows(cls.directory/'raw/protocol_trace.csv'))
    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()
    def test_real_owner_application_and_feedback_reconstruction(self):
        rows=list(gate.metrics.csv_rows(self.directory/'analysis/applications.csv'))
        counts=gate.t7.count_balance(self.summary['Statistics'],'real T8')
        sent,received=gate.validate_applications(rows,self.protocol,counts,self.case)
        self.assertGreater(len(sent),0)
        result=gate.verify_feedback(self.directory,self.summary,self.case,self.protocol)
        self.assertGreater(result['actual_feedback_member_count'],0)
    def test_real_owner_aggregate_schema_grid_and_raw_trace_binding(self):
        rows=list(gate.metrics.csv_rows(self.directory/'analysis/applications.csv'))
        counts=gate.t7.count_balance(self.summary['Statistics'],'real T8')
        sent,received=gate.validate_applications(rows,self.protocol,counts,self.case)
        manifest=gate.json_object(self.directory/'benchmark_manifest.json')
        result=gate.verify_buckets(self.directory,self.case,manifest['source_snapshot_sha256'],sent,received)
        self.assertEqual(len(result),800)
    def test_forged_feedback_configuration_power_rejected(self):
        summary=copy.deepcopy(self.summary)
        summary['Config']['Nodes'][0]['RadioProfile']['TxPowerDbm']+=1
        with self.assertRaisesRegex(ValueError,'configured power differs'):
            gate.verify_feedback(self.directory,summary,self.case,self.protocol)


if __name__=='__main__':unittest.main()
