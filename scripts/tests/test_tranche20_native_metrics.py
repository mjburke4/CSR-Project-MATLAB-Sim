import copy
import csv
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tranche20_native_metrics as metrics

FIXTURE=Path(__file__).resolve().parents[2]/'data/t20/native-duplicate.csv'

class NativeDuplicateAccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        with FIXTURE.open(newline='') as stream:self.rows=list(csv.DictReader(stream))
    def tearDown(self):self.temp.cleanup()
    def prepare(self,rows):
        trace=self.root/'ns3-trace.csv'
        with trace.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
        series,provenance=metrics.upstream.derive_series(trace,'blue_radio_campus-multihop',60,6000,0)
        metrics.upstream.write_outputs(series,provenance,self.root/'ns3-aggregates.csv',self.root/'ns3-aggregates.provenance.json')
        (self.root/'ns3-trace.csv.gz').write_bytes(gzip.compress(trace.read_bytes(),mtime=0))
        (self.root/'app-admission-diagnostics.csv').write_text('source,attempts,admitted\n7,1,1\n')
    def test_proven_duplicate_has_one_unique_two_events(self):
        self.prepare(self.rows);result=metrics.native_applications(self.root)
        self.assertEqual(result['totals']['delivered'],1)
        self.assertEqual(result['totals']['delivery_events'],2)
        self.assertEqual(result['totals']['duplicate_delivery_events'],1)
        self.assertEqual(result['totals']['unmatched_sends'],0)
        self.assertEqual(result['flows'][0]['first_delivery_delay_s']['count'],1)
    def test_missing_prior_dack_is_rejected(self):
        rows=copy.deepcopy(self.rows)
        for row in rows:
            if row['event']=='hop_feedback':row['detail']=row['detail'].replace('first_reception=1','first_reception=0')
        self.prepare(rows)
        with self.assertRaisesRegex(ValueError,'without exact source lineage'):metrics.native_applications(self.root)
    def test_wrong_duplicate_payload_is_rejected(self):
        rows=copy.deepcopy(self.rows);rows[-1]['size_bytes']='191';self.prepare(rows)
        with self.assertRaisesRegex(ValueError,'size mismatch'):metrics.native_applications(self.root)
    def test_forged_proof_metadata_is_rejected(self):
        self.prepare(self.rows);p=self.root/'ns3-aggregates.provenance.json';j=json.loads(p.read_text());j['source_exact_dack_retry_duplicates']['matched_duplicate_delivery_count']=0;p.write_text(json.dumps(j))
        with self.assertRaisesRegex(ValueError,'proof mismatch'):metrics.native_applications(self.root)
    def test_changed_aggregate_value_is_rejected(self):
        self.prepare(self.rows);p=self.root/'ns3-aggregates.csv'
        with p.open(newline='') as stream:rows=list(csv.DictReader(stream))
        rows[0]['value']='99'
        with p.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
        with self.assertRaisesRegex(ValueError,'series differs'):metrics.native_applications(self.root)

if __name__=='__main__':unittest.main()
