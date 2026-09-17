"""T19 checker mutation tests. Synthetic metadata never claims real execution."""
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import analyze_tranche19_return as r


class ReturnCheckerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def test_inventory_singleton_scientific_count(self):
        p=self.root/'one.csv'; p.write_text('value\n1\n')
        record={'path':'one.csv','bytes':float(p.stat().st_size),'sha256':r.sha256(p),'row_count':'1e0'}
        self.assertEqual(set(r.inventory(self.root,record,'synthetic')),{'one.csv'})

    def test_inventory_rejects_unlisted_bytes(self):
        p=self.root/'one.csv'; p.write_text('value\n1\n')
        record={'path':'one.csv','bytes':p.stat().st_size,'sha256':r.sha256(p)}
        (self.root/'extra').write_text('extra')
        with self.assertRaisesRegex(ValueError,'Incomplete'): r.inventory(self.root,[record],'synthetic')

    def test_inventory_row_mutation_rejected_even_rehashed(self):
        p=self.root/'one.csv'; p.write_text('value\n1\n2\n')
        record={'path':'one.csv','bytes':p.stat().st_size,'sha256':r.sha256(p),'row_count':1}
        with self.assertRaisesRegex(ValueError,'row count'): r.inventory(self.root,[record],'synthetic')

    def test_inventory_digest_mutation_rejected(self):
        p=self.root/'one.csv'; p.write_text('value\n1\n')
        record={'path':'one.csv','bytes':p.stat().st_size,'sha256':'0'*64}
        with self.assertRaisesRegex(ValueError,'hash/size'): r.inventory(self.root,[record],'synthetic')

    def test_inventory_duplicate_and_traversal_rejected(self):
        p=self.root/'one.csv';p.write_text('v\n1\n')
        record={'path':'one.csv','bytes':p.stat().st_size,'sha256':r.sha256(p)}
        with self.assertRaisesRegex(ValueError,'Duplicate'): r.inventory(self.root,[record,record],'synthetic')
        with self.assertRaisesRegex(ValueError,'Unsafe'): r.inventory(self.root,[dict(record,path='../one.csv')],'synthetic')

    def test_local_artifact_omission_is_explicit(self):
        p=self.root/'one.csv';p.write_text('v\n1\n')
        record={'path':'one.csv','bytes':p.stat().st_size,'sha256':r.sha256(p)}
        local={'path':'result.mat','bytes':100,'sha256':'0'*64}
        r.inventory(self.root,record,'synthetic',local=local)
        with self.assertRaisesRegex(ValueError,'Invalid omitted'):
            r.inventory(self.root,record,'synthetic',local=dict(local,path='hidden.csv'))

    def test_configuration_only_declared_hop_field_may_change(self):
        scenario=self.root/'scenarios/campus.csv';scenario.parent.mkdir();scenario.write_text('original input\n')
        case={'scenario_file':'scenarios/campus.csv','scenario_sha256':r.sha256(scenario),'policy':'native-provisional'}
        shared={'SourcePath':str(scenario),'SourceSHA256':case['scenario_sha256']}
        baseline={'Hop':{'ResendSeconds':2},'SharedScenario':shared,'Seed':128}
        actual=copy.deepcopy(baseline);actual['Hop']['DataQueuedRetryPolicy']='native-provisional'
        self.assertTrue(r.verify_configuration(actual,baseline,case,self.root)['configuration_equal'])
        changed=copy.deepcopy(actual);changed['Hop']['ResendSeconds']=1
        with self.assertRaises(ValueError):r.verify_configuration(changed,baseline,case,self.root)
        changed=copy.deepcopy(actual);changed['Seed']=129
        with self.assertRaises(ValueError):r.verify_configuration(changed,baseline,case,self.root)
        changed=copy.deepcopy(actual);changed['Hop']['DataQueuedRetryPolicy']='actual-tx'
        with self.assertRaisesRegex(ValueError,'policy'):r.verify_configuration(changed,baseline,case,self.root)
        self.assertEqual(actual['Hop']['DataQueuedRetryPolicy'],'native-provisional')

    def test_default_regression_checks_every_original_csv(self):
        raw=self.root/'case/raw';raw.mkdir(parents=True)
        summary={'Statistics':{'Generated':1,'Received':1,'Dropped':0,'Pending':0}}
        (raw/'summary.json').write_text(json.dumps(summary))
        archive=self.root/'synthetic-baseline.zip'
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('campus/c/raw/summary.json',json.dumps(summary))
            for name in r.CORE_CSV:
                content='synthetic-only\n1\n';(raw/name).write_text(content);z.writestr('campus/c/raw/'+name,content)
        result=r.verify_default_regression(raw.parent,archive)
        self.assertTrue(result['raw_csv_bytes_equal'])
        (raw/'hop_nodes.csv').write_text('synthetic-only\n2\n')
        with self.assertRaisesRegex(ValueError,'hop_nodes.csv'):r.verify_default_regression(raw.parent,archive)

    def test_default_statistics_change_rejected_before_csv_checks(self):
        raw=self.root/'case/raw';raw.mkdir(parents=True)
        (raw/'summary.json').write_text(json.dumps({'Statistics':{'Generated':2}}))
        archive=self.root/'synthetic-baseline.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('campus/c/raw/summary.json',json.dumps({'Statistics':{'Generated':1}}))
        with self.assertRaisesRegex(ValueError,'statistics'):r.verify_default_regression(raw.parent,archive)

    def test_incomplete_identity_rejected(self):
        for status in ('failed','phase-completed-review-pending','completed'):
            with self.assertRaisesRegex(ValueError,'not finalized'):
                r.verify_identity(self.root,{'Schema':r.SCHEMA,'Tranche':19,'Status':status},self.root,{})

    def test_cli_rejects_output_inside_evidence_without_modifying(self):
        evidence=self.root/'evidence'; evidence.mkdir()
        result=r.main(['--evidence',str(evidence),'--source-root',str(self.root/'source'),'--output',str(evidence/'review')])
        self.assertEqual(result,1);self.assertFalse((evidence/'review').exists())

    def test_cli_missing_candidate_reports_failed_not_execution(self):
        source=self.root/'source';source.mkdir(); evidence=self.root/'owner.zip';evidence.write_bytes(b'incomplete')
        output=self.root/'review'
        self.assertEqual(r.main(['--evidence',str(evidence),'--source-root',str(source),'--output',str(output)]),1)
        report=json.loads((output/'review.json').read_text())
        self.assertEqual(report['status'],'review_failed');self.assertFalse(report['matlab_executed_by_reviewer'])


@unittest.skipUnless(os.environ.get('CSR_T19_FULL_FIXTURE') == '1',
                    'Opt-in schema fixture replays archived T17 bytes; does not execute MATLAB')
class FullSchemaIntegrationFixture(unittest.TestCase):
    """Temporary SYNTHETIC T19 envelope, using accepted T17 output for both cases.

    Test CSVs and experimental-case results below are fixtures. They must never
    leave TemporaryDirectory or be reported as MATLAB execution/acceptance.
    """
    def test_temporary_schema_replay_and_bound_mutations(self):
        source_root = Path(__file__).resolve().parents[2]
        prepared = r.verify_preparation(source_root)
        candidate = r.json_object(source_root/r.CANDIDATE)
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-T19-SCHEMA-ONLY-') as temp:
            temp = Path(temp); owner = temp/'SYNTHETIC-NOT-A-MATLAB-RUN'; owner.mkdir()
            def write(path,value):
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
            def inv(directory,exclude=()):
                return [{'path':p.relative_to(directory).as_posix(),'sha256':r.sha256(p),'bytes':p.stat().st_size}
                        for p in sorted(directory.rglob('*')) if p.is_file() and p.relative_to(directory).as_posix() not in exclude]
            sources = [{'path':name,'sha256':digest} for name,digest in sorted(prepared['source'].items())]
            references = candidate['ReferenceFileInventory']
            write(owner/'source.json',sources);write(owner/'references.json',references)
            (owner/'candidate.json').write_bytes((source_root/r.CANDIDATE).read_bytes())
            (owner/'plan.json').write_bytes((source_root/r.PLAN).read_bytes())
            with zipfile.ZipFile(source_root/'evidence/t17/owner.zip') as original:
                oldmeta=json.loads(original.read('metadata.json')); runtime=oldmeta['Runtime']
                old_summary=json.loads(original.read('campus/summary.json'))
                for case in prepared['plan']['cases']:
                    directory=owner/case['case_id'];directory.mkdir()
                    for name in original.namelist():
                        prefix='campus/c/'
                        if name.startswith(prefix) and not name.endswith('/'):
                            suffix=name[len(prefix):]
                            if suffix.startswith(('raw/','analysis/')) and not suffix.endswith('.mat'):
                                path=directory/suffix;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(original.read(name))
                    raw=r.json_object(directory/'raw/summary.json')
                    raw['Config']['Hop']['DataQueuedRetryPolicy']=case['policy']
                    write(directory/'raw/summary.json',raw)
                    raw_manifest=r.json_object(directory/'raw/case_manifest.json')
                    raw_manifest['source_files']=sources
                    raw_manifest['files']=inv(directory/'raw',('case_manifest.json',))
                    raw_manifest['local_files']=[]
                    write(directory/'raw/case_manifest.json',raw_manifest)
                    provenance=r.json_object(directory/'analysis/aggregate_provenance.json')
                    provenance['source_snapshot_sha256']=r.sha256(owner/'source.json')
                    write(directory/'analysis/aggregate_provenance.json',provenance)
                    performance=list(r.metrics.rows(directory/'analysis/performance_summary.csv'))[0]
                    benchmark={'CaseId':case['case_id'],'Policy':case['policy'],
                               **{key:raw['Statistics'][key] for key in r.t7.COUNTS},
                               'Attempts':1710000,'AdmissionBlocked':1710000-raw['Statistics']['Generated']}
                    with (directory/'benchmark_summary.csv').open('w',newline='') as stream:
                        writer=csv.DictWriter(stream,fieldnames=list(benchmark));writer.writeheader();writer.writerow(benchmark)
                    manifest={'schema':'csr-tranche19-queued-retry-case-v1','status':'completed',
                        'synthetic_fixture_not_execution':True,'case_id':case['case_id'],'policy':case['policy'],
                        'case':case,'original_case_id':'campus_multihop_6000',
                        **{key:case[key] for key in ('scenario','scenario_sha256','seed','duration_s','bucket_width_s','reference_directory')},
                        'runtime':runtime,'matlab_version':runtime['Version'],'matlab_release':runtime['Release'],
                        'ns3_source_commit':r.t7.PIN,'source_files':sources,'source_snapshot_sha256':r.sha256(owner/'source.json'),
                        'scheduler_stop_s':6000,'mode':'continuous','structural_checks_passed':True,
                        'admission_counts_complete':True,'original_admission_trace_prefix':True,
                        'observer_enabled':False,'post_horizon_drain':False,'numerical_parity_established':False,
                        'result_metadata':raw['Metadata'],'admission_trace_omitted_records':1610000,
                        'files':inv(directory),'local_files':[]}
                    write(directory/'case.json',manifest)
                    entry={'CaseId':case['case_id'],'Directory':case['case_id'],'ManifestSHA256':r.sha256(directory/'case.json')}
                    summary={'Schema':'csr-tranche19-queued-retry-summary-v1','CaseId':case['case_id'],'Policy':case['policy'],
                        'OriginalBenchmarkCaseId':'campus_multihop_6000','CompletedCaseCount':1,'DurationSeconds':6000,
                        'SchedulerStopSeconds':6000,'Seed':128,'RequestedPolicySameAsDefault':case['policy']=='actual-tx',
                        'StructuralChecksPassed':True,'DefaultContinuousTiming':True,'RealPHY':True,'AutonomousRouting':True,
                        'OriginalAdmissionTracePrefix':True,'ObserverEnabled':False,'PostHorizonDrain':False,
                        'AcceptanceEstablished':False,'NumericalParityEstablished':False,'FiniteStopPendingIsFailure':False,
                        'ProtocolTraceOmissions':0,'PhyTraceOmissions':0,'ElapsedWallSeconds':1,
                        'Admissions':old_summary['Admissions'],'Performance':old_summary['Performance'],'Case':entry}
                    write(directory/'summary.json',summary)
            tests=owner/'tests';tests.mkdir();names=candidate['ExpectedTestNames']
            with (tests/'results.csv').open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=['Name','Passed','Failed','Incomplete','DurationSeconds']);writer.writeheader()
                writer.writerows({'Name':name,'Passed':'true','Failed':'false','Incomplete':'false','DurationSeconds':'0'} for name in names)
            test_summary={'Schema':'csr-tranche19-portable-tests-summary-v1','TestResultsFile':'results.csv',
                'TestFiles':candidate['TestFiles'],'ExpectedTestNames':names,'TestsExecuted':True,'TestsPassed':True,
                'TestCount':len(names),'PassedTests':len(names),'FailedTests':0,'IncompleteTests':0}
            write(tests/'summary.json',test_summary)
            identity={'CandidateSHA256':r.sha256(owner/'candidate.json'),'SourceCommit':r.t7.PIN,'Runtime':runtime,
                      'SourceFiles':sources,'ReferenceFiles':references}
            stage_entries=[]
            for phase in r.PHASES:
                directory=owner/phase
                write(directory/'start.json',{'schema':'csr-tranche19-stage-start-v1','phase':phase,'status':'started',
                    'started_utc':'2026-09-16T00:00:00Z','identity':identity})
                receipt={'schema':'csr-tranche19-stage-receipt-v1','phase':phase,'status':'completed',
                    'completed_utc':'2026-09-16T00:01:00Z','identity':identity,'SourceFilesStableDuringRun':True,
                    'ReferenceFilesStableDuringRun':True,'SourceFilesFinal':sources,'ReferenceFilesFinal':references,
                    'artifacts':inv(directory),'local_artifacts':[],'summary':r.json_object(directory/'summary.json')}
                write(directory/'receipt.json',receipt)
                (directory/'receipt.sha256').write_text(r.sha256(directory/'receipt.json')+'\n')
                stage_entries.append({'Phase':phase,'File':phase+'/receipt.json','SHA256':r.sha256(directory/'receipt.json')})
            metadata={'Schema':r.SCHEMA,'Tranche':19,'Status':'completed-review-required','synthetic_fixture_not_execution':True,
                'CandidateFile':r.CANDIDATE,'CandidateSHA256':identity['CandidateSHA256'],'Runtime':runtime,
                'MATLABExecuted':True,'NativeExecuted':False,'SourceCommit':r.t7.PIN,'FullAcceptanceGateExecuted':True,
                'AcceptanceEstablished':False,'NumericalParityEstablished':False,'CompletedCaseCount':2,
                'CampusStructuralChecksPassed':True,'StartedUTC':'2026-09-16T00:00:00Z','CompletedUTC':'2026-09-16T00:02:00Z',
                'EvidenceArchive':'t19.zip','SourceFilesFinal':sources,'SourceFilesStableDuringRun':True,
                'SourceSnapshotSHA256':r.sha256(owner/'source.json'),'ReferenceFilesFinal':references,
                'ReferenceFilesStableDuringRun':True,'ReferenceSnapshotSHA256':r.sha256(owner/'references.json'),
                'AllBaselineSourcesUnchanged':False,'UnmodifiedBaselineSourcesUnchanged':True,
                'AllowedBaselineModificationsVerified':True,'AllowedModifiedSourceFiles':candidate['AllowedModifiedSourceFiles'],
                'BaselineSourceFilesVerified':346,'BaselineMatlabFilesVerified':164,'StageReceipts':stage_entries,
                'Cases':[r.json_object(owner/key/'summary.json')['Case'] for key in ('a128','p128')],
                **{key:test_summary[key] for key in ('TestsExecuted','TestsPassed','TestCount','PassedTests','FailedTests','IncompleteTests')},
                'Artifacts':inv(owner),'LocalArtifacts':[]}
            write(owner/'metadata.json',metadata)
            result=r.review(owner,source_root,temp/'SYNTHETIC-REVIEW-ONLY')
            self.assertTrue(result['full_structural_gate_completed'])
            self.assertFalse(result['matlab_executed_by_reviewer'])
            self.assertEqual(result['tests']['count'],len(names))
            self.assertTrue(result['default_regression']['raw_csv_bytes_equal'])
            # Substantive mutation bypasses only inventories to target case accounting:
            # changing a raw endpoint counter must fail its reconstructions.
            directory=owner/'p128';path=directory/'raw/hop_nodes.csv'
            rows=list(r.metrics.rows(path));rows[0]['PendingData']=str(int(rows[0]['PendingData'])+1)
            with path.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            with self.assertRaisesRegex(ValueError,'endpoint'):
                r.metrics.analyze_case(directory,prepared['plan']['cases'][1])
            # Full checker also rejects unchanged receipt inventory after any byte edit.
            with self.assertRaisesRegex(ValueError,'hash/size'):
                r.inventory(owner,metadata['Artifacts'],'synthetic mutation',excluded=('metadata.json',))


if __name__ == '__main__':unittest.main()
