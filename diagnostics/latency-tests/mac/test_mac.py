import copy,csv,unittest
from pathlib import Path
from compare_mac import read,validate,compare
CASES=read(Path(__file__).with_name('cases.csv'))
def synthetic():
 out=[]
 for c in CASES:
  da=int(c['expected_data_ordinal']);acks=int(c['expected_ack_count']);n=max(da,acks)
  for i in range(1,n+1):
   ack=int(i<=acks);data=int(i==da)
   out.append(dict(case_id=c['case_id'],ordinal=i,tx_time_s=i,sample_time_s=i,
    ack_segments=ack,data_segments=data,data_queue_after=int(i<da),ack_queue_after=int(i<acks),
    wire_bytes=41*ack+(int(c['payload_bytes'])+32)*data,rate_kbps=int(c['rate_kbps']),reservation_after=1))
 return out
class ComparatorTests(unittest.TestCase):
 def test_expected_sequences(self):
  a=synthetic();r=compare(a,a,CASES);self.assertTrue(r['structural_passed'] and r['discrete_rows_match'])
 def test_missing_case_rejected(self):
  with self.assertRaises(ValueError):validate(synthetic()[1:],CASES)
 def test_fractional_membership_rejected(self):
  a=synthetic();a[0]['data_segments']=.5
  with self.assertRaises(ValueError):validate(a,CASES)
 def test_stale_sample_rejected(self):
  a=synthetic();a[0]['sample_time_s']=1.001
  with self.assertRaises(ValueError):validate(a,CASES)
 def test_wrong_boundary_reported(self):
  a=synthetic();b=copy.deepcopy(a);r=next(x for x in b if x['case_id']=='early_256');r['reservation_after']=2
  result=compare(a,b,CASES);self.assertFalse(result['discrete_rows_match']);self.assertEqual(result['first_discrete_difference']['case_id'],'early_256')
 def test_nonfinite_time_rejected(self):
  a=synthetic();a[0]['tx_time_s']=float('nan')
  with self.assertRaises(ValueError):validate(a,CASES)
if __name__=='__main__':unittest.main()
