import csv,tempfile,unittest
from pathlib import Path
from compare_hop_replay import inspect,STATE
class ReplayChecks(unittest.TestCase):
 def make(self,d,alter=None):
  c={'case_id':'x','upstream_first_s':'-1','upstream_second_s':'-1','feedback_s':'12','stop_s':'12.1'}
  rows=[]
  for event,time,pending,released in [('admit',0,1,0),('feedback_before',12,1,0),('feedback_after',12,0,1),('final',12.1,0,1)]:
   r=dict.fromkeys(STATE,0);r.update(case_id='x',observed_time_s=time,event=event,hop_pending=pending,neighbor_outstanding=pending,released=released);rows.append(r)
  if alter:alter(rows)
  p=Path(d)/'data.csv'
  with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
  return p,[c]
 def test_release_contract(self):
  with tempfile.TemporaryDirectory() as d:
   p,c=self.make(d);self.assertTrue(all(inspect(p,c)['x']['checks'].values()))
 def test_duplicate_release_fails(self):
  with tempfile.TemporaryDirectory() as d:
   p,c=self.make(d,lambda r:r[-1].update(released=2));self.assertFalse(inspect(p,c)['x']['checks']['final_capacity_released'])
 def test_nan_time_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p,c=self.make(d,lambda r:r[-1].update(observed_time_s='nan'))
   with self.assertRaises(ValueError):inspect(p,c)
 def test_recorded_original_return(self):
  with Path(__file__).with_name('inputs.csv').open(newline='') as f:
   cases=[r for r in csv.DictReader(f) if r['case_id']!='hop_baseline_timely']
  recorded=Path(__file__).resolve().parents[1]/'validation/returned-hop.csv'
  result=inspect(recorded,cases)
  self.assertTrue(all(all(x['checks'].values()) for x in result.values()))
  cases[0]['feedback_effect']='ack'
  self.assertFalse(inspect(recorded,cases)['hop_baseline']['checks']['expected_pre_feedback_custody'])
 def test_late_ack_does_not_release_twice(self):
  with tempfile.TemporaryDirectory() as d:
   def change(rows):
    rows[1].update(hop_pending=0,neighbor_outstanding=0,released=1)
    rows[2].update(released=2)
   p,c=self.make(d,change);c[0]['feedback_effect']='expired'
   self.assertFalse(inspect(p,c)['x']['checks']['expected_feedback_effect'])
if __name__=='__main__':unittest.main()
