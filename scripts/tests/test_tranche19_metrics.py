"""Synthetic micro-ledgers exercise review logic; these are NOT owner runs."""
import copy
import csv
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tranche19_metrics as m


def write_csv(path,rows,fields=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='') as stream:
        writer = csv.DictWriter(stream,fieldnames=fields or list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def fixture(root):
    """Two synthetic applications, overlapping retry requests and DACK hold."""
    raw = root/'raw'; raw.mkdir()
    config = {'Nodes':[{'Id':4},{'Id':5}], 'Traffic':{'SourceId':4,'StartSeconds':0,
              'IntervalSeconds':3000,'PacketCount':2}}
    (raw/'summary.json').write_text(json.dumps({'Config':config}))
    apps = [{'PacketId':'1','SourceId':'4','DestinationId':'5','ApplicationBytes':'185','GeneratedSeconds':'0',
        'LastEventSeconds':'10','ReceivedSeconds':'10','LatencySeconds':'10','Outcome':'delivered','DropReason':''},
        {'PacketId':'2','SourceId':'4','DestinationId':'5','ApplicationBytes':'185','GeneratedSeconds':'3000',
        'LastEventSeconds':'3000','ReceivedSeconds':'NaN','LatencySeconds':'NaN','Outcome':'pending','DropReason':''}]
    write_csv(root/'analysis/applications.csv',apps)
    write_csv(raw/'application_admission_statistics.csv',[{'SourceId':4,'Attempts':2,'Admitted':2,'BlockedNsdp':0}])
    def e(time,event,packet=1,node=4):
        hop = event.startswith('hop_')
        return {'TimeSeconds':str(time),'Event':event,'NodeId':str(node),'PeerId':'5' if node==4 else '4',
            'PacketId':str(packet),'FrameKind':'DATA' if hop else 'APP','Sequence':str(packet if hop else 0),
            'ApplicationBytes':'185','Reason':''}
    trace = [e(0,'network_enqueue'),e(0,'app_generate'),e(1,'hop_admit'),e(1,'network_submit'),
        e(2,'hop_sent'),e(2,'tx_start',100),e(3,'hop_retry'),e(4,'hop_retry'),e(5,'hop_sent'),e(5,'tx_start',101),
        e(6,'hop_retry'),e(10,'app_receive',node=5),e(12,'network_custody_release'),e(13,'hop_dack'),
        e(100,'hop_dack_expired'),e(3000,'network_enqueue',2),e(3000,'app_generate',2),e(3001,'hop_admit',2),
        e(3001,'network_submit',2),e(3002,'hop_sent',2),e(3002,'tx_start',102),e(4000,'hop_retry',2)]
    write_csv(raw/'protocol_trace.csv',trace)
    base = {'NodeId':4,'PendingData':1,'DackHoldCount':0,'Admitted':2,'Transmitted':3,
        'Retransmissions':4,'Acknowledged':0,'Dacked':1,'Failed':0,'DackExpired':1}
    empty = {k:0 for k in base}; empty['NodeId']=5
    write_csv(raw/'hop_nodes.csv',[base,empty])
    write_csv(raw/'nwk_nodes.csv',[{'NodeId':4,'PendingCustody':1},{'NodeId':5,'PendingCustody':0}])
    return trace


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.trace = fixture(self.root)
        self.case = {'case_id':'synthetic-micro-ledger','policy':'native-provisional','duration_s':6000}

    def tearDown(self): self.temp.cleanup()

    def analyze(self): return m.analyze_case(self.root,self.case)

    def trace_write(self): write_csv(self.root/'raw/protocol_trace.csv',self.trace)

    def test_ordered_complete_ledger_and_finite_stop(self):
        result = self.analyze()
        self.assertEqual(result['totals'],{'attempts':2,'admitted':2,'blocked':0,'delivered':1,'dropped':0,'pending':1})
        self.assertEqual(result['ownership'][0]['hop_pending_at_stop'],1)
        self.assertEqual(result['ownership'][0]['nwk_custody_at_stop'],1)
        self.assertEqual(result['flow_timeline'][-1]['pending_at_end'],1)
        self.assertEqual(result['flow_timeline'][10]['admitted'],1)
        self.assertEqual(result['flow_timeline'][9]['pending_at_end'],0)

    def test_overlapping_requests_are_separate_and_not_bijective(self):
        episode = self.analyze()['hop_episodes'][0]
        waits = episode['retry_request_waits']
        self.assertEqual([w['seconds'] for w in waits],[2,1,7])
        self.assertEqual(waits[0]['end_row'],waits[1]['end_row'])
        self.assertEqual(waits[2]['completion'],'terminal_before_next_hop_sent')

    def test_dack_ends_retry_service_but_retains_capacity(self):
        result = self.analyze(); entry = result['hop_episodes'][0]
        self.assertEqual(entry['dack_capacity_hold_s'],87)
        self.assertEqual(entry['capacity_retention_s'],99)
        self.assertEqual(result['nwk_custody_episodes'][0]['release']['time_s'],12)
        self.assertAlmostEqual(result['ownership'][0]['hop_data_capacity_300s'][0]['mean_count'],99/300)
        self.assertAlmostEqual(result['ownership'][0]['nwk_custody_300s'][0]['mean_count'],12/300)

    def test_pending_wait_censored_at_horizon(self):
        wait = self.analyze()['hop_episodes'][1]['retry_request_waits'][0]
        self.assertEqual(wait['completion'],'censored_at_stop'); self.assertEqual(wait['seconds'],2000)

    def test_unowned_transmitted_remainder_is_valid_and_not_assigned(self):
        rows = list(m.rows(self.root/'raw/hop_nodes.csv')); rows[0]['Transmitted']='4'
        write_csv(self.root/'raw/hop_nodes.csv',rows)
        coverage = self.analyze()['data_transmission_callback_coverage']
        self.assertEqual(next(r for r in coverage if r['node']==4)['sent_indications_without_owned_confirmation'],1)

    def test_confirmations_exceeding_sent_counter_rejected(self):
        rows = list(m.rows(self.root/'raw/hop_nodes.csv')); rows[0]['Transmitted']='2'
        write_csv(self.root/'raw/hop_nodes.csv',rows)
        with self.assertRaisesRegex(ValueError,'confirmations'): self.analyze()

    def test_capacity_endpoint_mutation_rejected(self):
        rows = list(m.rows(self.root/'raw/hop_nodes.csv')); rows[0]['PendingData']='0'
        write_csv(self.root/'raw/hop_nodes.csv',rows)
        with self.assertRaisesRegex(ValueError,'endpoint'): self.analyze()

    def test_release_without_custody_rejected(self):
        self.trace = [r for r in self.trace if not (r['Event']=='network_enqueue' and r['PacketId']=='1')]
        self.trace_write()
        with self.assertRaisesRegex(ValueError,'custody'): self.analyze()

    def test_release_before_dack_expiration_rejected(self):
        self.trace = [r for r in self.trace if r['Event']!='hop_dack_expired']; self.trace_write()
        with self.assertRaisesRegex(ValueError,'endpoint'): self.analyze()

    def test_unknown_data_identity_rejected(self):
        next(r for r in self.trace if r['Event']=='hop_retry')['PacketId']='999'
        self.trace_write()
        with self.assertRaisesRegex(ValueError,'Unknown DATA'): self.analyze()

    def test_control_namespace_does_not_borrow_application_identity(self):
        control = dict(self.trace[6],FrameKind='CONTROL',PacketId='999')
        self.trace.insert(7,control); self.trace_write()
        self.assertEqual(self.analyze()['hop_4_to_5']['retry_requests'],4)

    def test_application_endpoint_mutation_rejected(self):
        next(r for r in self.trace if r['Event']=='app_receive')['NodeId']='4'
        self.trace_write()
        with self.assertRaisesRegex(ValueError,'endpoint'): self.analyze()

    def test_duplicate_delivery_rejected(self):
        index = next(i for i,r in enumerate(self.trace) if r['Event']=='app_receive')
        self.trace.insert(index,dict(self.trace[index])); self.trace_write()
        with self.assertRaisesRegex(ValueError,'Duplicate'): self.analyze()

    def test_payload_mutation_rejected(self):
        next(r for r in self.trace if r['Event']=='app_receive')['ApplicationBytes']='186'; self.trace_write()
        with self.assertRaisesRegex(ValueError,'payload'): self.analyze()

    def test_admission_counter_mutation_rejected(self):
        write_csv(self.root/'raw/application_admission_statistics.csv',[{'SourceId':4,'Attempts':3,'Admitted':2,'BlockedNsdp':1}])
        with self.assertRaisesRegex(ValueError,'counts disagree'): self.analyze()

    def test_exact_scientific_unsigned_integer(self):
        self.assertEqual(m.integer('4.294967295e+09','broadcast'),4294967295)
        self.assertEqual(m.integer('18446744073709551615','uint64'),2**64-1)
        for value in (True,'1.5','NaN',float(2**53),'18446744073709551616'):
            with self.assertRaises(ValueError): m.integer(value,'invalid')

    def test_endpoint_time_in_final_bin(self):
        self.assertEqual(m.bucket(6000,6000,300),19)
        self.assertEqual(m.bucket(300,6000,300),1)
        with self.assertRaises(ValueError): m.bucket(6001,6000,300)

    def test_numeric_band_is_descriptive(self):
        one = {'flows':[{'source':4,'admitted':100,'delivered':90}],'totals':{'admitted':100,'delivered':90}}
        two = {'flows':[{'source':4,'admitted':50,'delivered':10}],'totals':{'admitted':50,'delivered':10}}
        report = m.compare_cases(one,two,one)
        self.assertFalse(report['band_is_acceptance_gate'])
        self.assertTrue(report['rows'][0]['actual_tx_within_descriptive_band'])
        self.assertFalse(report['rows'][0]['native_provisional_within_descriptive_band'])

    def test_native_identity_join_and_unmatched_scope(self):
        native = self.root/'native'; native.mkdir()
        write_csv(native/'app-admission-diagnostics.csv',[{'source':4,'attempts':2,'admitted':2}])
        content = 'time_s,event,src,sequence\n0,app_send,4,1\n10,nwk_delivery,4,1\n3000,app_send,4,2\n'
        with gzip.open(native/'ns3-trace.csv.gz','wt') as stream: stream.write(content)
        result = m.native_applications(native)
        self.assertEqual(result['totals']['unmatched_sends'],1)
        self.assertNotIn('pending',result['totals'])
        with gzip.open(native/'ns3-trace.csv.gz','wt') as stream:
            stream.write(content.replace('3000,app_send,4,2','11,nwk_delivery,4,1\n3000,app_send,4,2'))
        with self.assertRaisesRegex(ValueError,'duplicate native'): m.native_applications(native)


if __name__ == '__main__': unittest.main()
