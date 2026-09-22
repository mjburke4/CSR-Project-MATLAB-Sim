import csv,json,tempfile,unittest
from pathlib import Path
from analyze_load import metrics,percentile,native
from generate_scenarios import ROOT,sha
class LoadTests(unittest.TestCase):
 def test_quantiles_and_censoring(self):
  a=[dict(id=str(i),outcome='delivered',latency_s=v) for i,v in enumerate([1,3,5,7])]+[dict(id='x',outcome='pending',latency_s=None)]
  m=metrics(a,8); self.assertEqual(m['median_latency_s'],4); self.assertAlmostEqual(m['p95_latency_s'],6.7); self.assertEqual(m['pending'],1); self.assertEqual(m['admission_blocked'],3)
 def test_empty(self): self.assertIsNone(metrics([],0)['p95_latency_s'])
 def test_bad_latency(self):
  with self.assertRaises(AssertionError): metrics([dict(id='1',outcome='delivered',latency_s=-1)],1)
 def test_duplicate_identity(self):
  with self.assertRaises(AssertionError): metrics([dict(id='1',outcome='pending')]*2,2)
 def test_native_unique_and_unknown(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t)
   (d/'ns3-trace.csv').write_text('event,time_s,src,dst,sequence\napp_send,300,2,1,1\napp_send,301,2,1,2\nnwk_delivery,303,2,1,1\nnwk_delivery,304,2,1,1\n')
   (d/'app-admission-diagnostics.csv').write_text('source,attempts,admitted,blocked_no_route\n2,3,2,1\n')
   a,m=native(d); self.assertEqual(m['delivered_unique'],1); self.assertEqual(m['median_latency_s'],3); self.assertEqual(m['duplicate_delivery_events'],1); self.assertEqual(m['unresolved'],1); self.assertIsNone(m['pending'])
 def test_scenario_membership(self):
  plan=json.loads((ROOT/'plan.json').read_text()); self.assertEqual(len(plan['cases']),6)
  for c in plan['cases']:
   p=ROOT/c['scenario']; self.assertNotIn(b'\r',p.read_bytes()); self.assertEqual(c['sha256'],sha(p))
   with p.open(newline='') as f: rows=list(csv.DictReader(f))
   self.assertEqual(len([r for r in rows if r['record']=='node']),7)
   flows=[r for r in rows if r['record']=='flow']; self.assertEqual(len(flows),6)
   self.assertTrue(all(float(r['flow_start_s'])==300 and float(r['flow_interval_s'])==c['interval_s'] for r in flows))
if __name__=='__main__': unittest.main()
