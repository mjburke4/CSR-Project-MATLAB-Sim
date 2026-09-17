"""Synthetic mutation checks; no MATLAB execution represented."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import analyze_tranche20_return as r
import tranche20_metrics as m

class T20MutationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        p=self.root/'scenarios/campus.csv';p.parent.mkdir();p.write_text('original\n')
        self.case={'seed':129,'policy':'actual-tx','scenario_file':'scenarios/campus.csv','scenario_sha256':r.sha256(p)}
        self.base={'Seed':128,'Hop':{'DataQueuedRetryPolicy':'actual-tx','Capacity':10},'SharedScenario':{'SourcePath':str(p),'SourceSHA256':r.sha256(p)}}
        self.actual=copy.deepcopy(self.base);self.actual['Seed']=129
    def tearDown(self): self.tmp.cleanup()
    def test_seed_only_config_passes(self):
        self.assertEqual(r.verify_configuration(self.actual,self.base,self.case,self.root)['seed_override'],{'before':128,'after':129})
    def test_policy_change_rejected(self):
        self.actual['Hop']['DataQueuedRetryPolicy']='native-provisional'
        with self.assertRaisesRegex(ValueError,'policy'):r.verify_configuration(self.actual,self.base,self.case,self.root)
    def test_capacity_change_rejected(self):
        self.actual['Hop']['Capacity']=11
        with self.assertRaises(ValueError):r.verify_configuration(self.actual,self.base,self.case,self.root)
    def test_wrong_seed_rejected(self):
        self.actual['Seed']=130
        with self.assertRaisesRegex(ValueError,'seed'):r.verify_configuration(self.actual,self.base,self.case,self.root)
    def test_input_bytes_change_rejected(self):
        (self.root/'scenarios/campus.csv').write_text('changed\n')
        with self.assertRaises(ValueError):r.verify_configuration(self.actual,self.base,self.case,self.root)
    def test_incomplete_status_rejected(self):
        with self.assertRaisesRegex(ValueError,'not finalized'):
            r.verify_identity(self.root,{'Schema':r.SCHEMA,'Tranche':20,'Status':'failed'},self.root,{})
    def test_inventory_rejects_unlisted(self):
        p=self.root/'file.txt';p.write_text('a')
        with self.assertRaisesRegex(ValueError,'Incomplete'):r.inventory(self.root,[{'path':'file.txt','bytes':1,'sha256':r.sha256(p)}],'test')
    def test_native_seed_only_derivation(self):
        a=self.root/'a.csv';b=self.root/'b.csv';a.write_text('record,seed,duration\nrun,128,6000\n');b.write_text('record,seed,duration\nrun,129,6000\n')
        self.assertEqual(m.verify_seed_derivation(a,b,129),[[0,'seed','128','129']])
        b.write_text('record,seed,duration\nrun,129,900\n')
        with self.assertRaisesRegex(ValueError,'beyond'):m.verify_seed_derivation(a,b,129)
    def test_extra_native_row_rejected(self):
        a=self.root/'a.csv';b=self.root/'b.csv';a.write_text('record,seed\nrun,128\n');b.write_text('record,seed\nrun,129\nrun,129\n')
        with self.assertRaisesRegex(ValueError,'shape'):m.verify_seed_derivation(a,b,129)

class T20ComparisonTests(unittest.TestCase):
    def cases(self):
        return {s:{'totals':{'admitted':60,'delivered':60},'flows':[{'source':n,'admitted':10,'delivered':10} for n in (2,3,4,5,7,8)]} for s in (128,129,130)}
    def test_all_seeds_and_flows_reported(self):
        report=m.compare_seeds(self.cases(),self.cases())
        self.assertEqual(len(report['rows']),42);self.assertEqual(len(report['summaries']),14)
        self.assertFalse(report['band_is_acceptance_gate'])
    def test_pooled_ratio_differs_from_mean_percentage(self):
        a=self.cases();n=self.cases()
        a[128]['totals']['delivered']=20;n[128]['totals']['delivered']=10
        a[129]['totals']['delivered']=100;n[129]['totals']['delivered']=100
        a[130]['totals']['delivered']=100;n[130]['totals']['delivered']=100
        row=next(x for x in m.compare_seeds(a,n)['summaries'] if x['source'] is None and x['metric']=='delivered')
        self.assertAlmostEqual(row['per_seed_residual_percent']['mean'],100/3)
        self.assertAlmostEqual(row['pooled_ratio_of_sums_percent'],1000/210)
    def test_missing_seed_rejected(self):
        a=self.cases();del a[128]
        with self.assertRaisesRegex(ValueError,'three seeds'):m.compare_seeds(a,self.cases())
    def test_missing_flow_rejected(self):
        a=self.cases();a[129]['flows'].pop()
        with self.assertRaisesRegex(ValueError,'populations'):m.compare_seeds(a,self.cases())
    def test_outside_band_is_descriptive(self):
        a=self.cases();a[129]['totals']['delivered']=10
        report=m.compare_seeds(a,self.cases())
        self.assertTrue(any(x['within_descriptive_band'] is False for x in report['rows']))
    def test_zero_denominator_is_undefined(self):
        n=self.cases();n[128]['totals']['admitted']=0
        report=m.compare_seeds(self.cases(),n)
        self.assertIsNone(next(x for x in report['rows'] if x['source'] is None and x['seed']==128 and x['metric']=='admitted')['residual_percent'])
    def test_negative_counts_rejected(self):
        a=self.cases();a[129]['totals']['delivered']=-1
        with self.assertRaisesRegex(ValueError,'counts'):m.compare_seeds(a,self.cases())
    def test_sign_consistency(self):
        a=self.cases()
        for row in a.values():row['totals']['admitted']=61
        report=m.compare_seeds(a,self.cases())
        row=next(x for x in report['summaries'] if x['source'] is None and x['metric']=='admitted')
        self.assertEqual(row['signed_residual_consistency'],'positive_all')

if __name__=='__main__':unittest.main()
