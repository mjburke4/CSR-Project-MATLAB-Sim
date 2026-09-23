"""Opt-in temporary T25 schema fixture. Never evidence of MATLAB execution.

It reuses accepted seed128 raw bytes in two synthetic131/132 case envelopes.
The authentic archived128 parent is separately verified by the real checker.
"""
import csv
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import analyze_tranche25_return as r

@unittest.skipUnless(os.environ.get('CSR_T25_FULL_FIXTURE') == '1',
                    'Opt-in schema fixture replays archived T19 bytes; does not execute MATLAB')
class FullSchemaIntegrationFixture(unittest.TestCase):
    """Temporary SYNTHETIC T25 envelope, using accepted T19 output for both fresh cases.

    Test CSVs and fresh-seed results below are fixtures. They must never
    leave TemporaryDirectory or be reported as MATLAB execution/acceptance.
    """
    def test_full_return_schema_with_authenticated_parent_and_two_fresh_envelopes(self):
        source_root = Path(__file__).resolve().parents[2]
        candidate = r.json_object(source_root/r.CANDIDATE)
        # Construct the fixture cheaply; review() itself runs all real source,
        # reference, native lineage and preparation checks without a bypass.
        prepared = {'source':r.candidate_snapshot(source_root),
                    'plan':r.json_object(source_root/r.PLAN)}
        with tempfile.TemporaryDirectory(prefix='SYNTHETIC-T25-SCHEMA-ONLY-') as temp:
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
            with zipfile.ZipFile(source_root/'evidence/t19/owner.zip') as original:
                oldmeta=json.loads(original.read('metadata.json')); runtime=oldmeta['Runtime']
                old_summary=json.loads(original.read('a128/summary.json'))
                for case in prepared['plan']['cases']:
                    directory=owner/case['case_id'];directory.mkdir()
                    for name in original.namelist():
                        prefix='a128/'
                        if name.startswith(prefix) and not name.endswith('/'):
                            suffix=name[len(prefix):]
                            if suffix.startswith(('raw/','analysis/')) and not suffix.endswith('.mat'):
                                path=directory/suffix;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(original.read(name))
                    raw=r.json_object(directory/'raw/summary.json')
                    raw['Config']['Hop']['DataQueuedRetryPolicy']=case['policy']
                    raw['Config']['Seed']=case['seed']
                    write(directory/'raw/summary.json',raw)
                    research_path=directory/'raw/research_summary.csv'
                    if research_path.exists():
                        research=list(r.metrics.rows(research_path))
                        for row in research:
                            if 'Seed' in row: row['Seed']=case['seed']
                        if research:
                            with research_path.open('w',newline='') as stream:
                                writer=csv.DictWriter(stream,fieldnames=list(research[0]))
                                writer.writeheader();writer.writerows(research)
                    raw_manifest=r.json_object(directory/'raw/case_manifest.json')
                    raw_manifest['source_files']=sources
                    raw_manifest['imported_seed']=128
                    raw_manifest['seed_override_after_import']=True
                    raw_manifest['files']=inv(directory/'raw',('case_manifest.json',))
                    raw_manifest['local_files']=[]
                    write(directory/'raw/case_manifest.json',raw_manifest)
                    provenance=r.json_object(directory/'analysis/aggregate_provenance.json')
                    provenance['source_snapshot_sha256']=r.sha256(owner/'source.json')
                    write(directory/'analysis/aggregate_provenance.json',provenance)
                    performance=list(r.metrics.rows(directory/'analysis/performance_summary.csv'))[0]
                    performance['Seed']=case['seed']
                    with (directory/'analysis/performance_summary.csv').open('w',newline='') as stream:
                        writer=csv.DictWriter(stream,fieldnames=list(performance));writer.writeheader();writer.writerow(performance)
                    benchmark={'CaseId':case['case_id'],'Policy':case['policy'],
                               **{key:raw['Statistics'][key] for key in r.t7.COUNTS},
                               'Attempts':1710000,'AdmissionBlocked':1710000-raw['Statistics']['Generated']}
                    with (directory/'benchmark_summary.csv').open('w',newline='') as stream:
                        writer=csv.DictWriter(stream,fieldnames=list(benchmark));writer.writeheader();writer.writerow(benchmark)
                    manifest={'schema':'csr-tranche25-ensemble-case-v1','status':'completed',
                        'synthetic_fixture_not_execution':True,'case_id':case['case_id'],'policy':case['policy'],
                        'case':case,'original_case_id':'campus_multihop_6000',
                        **{key:case[key] for key in ('scenario','scenario_sha256','seed','duration_s','bucket_width_s','reference_directory')},
                        'runtime':runtime,'matlab_version':runtime['Version'],'matlab_release':runtime['Release'],
                        'ns3_source_commit':r.t7.PIN,'source_files':sources,'source_snapshot_sha256':r.sha256(owner/'source.json'),
                        'scheduler_stop_s':6000,'mode':'continuous','imported_seed':128,'seed_override_after_import':True,
                        'opnet_same_seed_reference_available':False,'opnet_scope':'archived-seed128-aggregate-context-only','structural_checks_passed':True,
                        'admission_counts_complete':True,'original_admission_trace_prefix':True,
                        'observer_enabled':False,'post_horizon_drain':False,'numerical_parity_established':False,
                        'result_metadata':raw['Metadata'],'admission_trace_omitted_records':1610000,
                        'files':inv(directory),'local_files':[]}
                    write(directory/'case.json',manifest)
                    entry={'CaseId':case['case_id'],'Directory':case['case_id'],'ManifestSHA256':r.sha256(directory/'case.json')}
                    summary={'Schema':'csr-tranche25-ensemble-summary-v1','CaseId':case['case_id'],'Policy':case['policy'],
                        'OriginalBenchmarkCaseId':'campus_multihop_6000','CompletedCaseCount':1,'DurationSeconds':6000,
                        'SchedulerStopSeconds':6000,'Seed':case['seed'],'ImportedSeed':128,'SeedOverrideAfterImport':True,'RequestedPolicySameAsDefault':True,
                        'StructuralChecksPassed':True,'DefaultContinuousTiming':True,'RealPHY':True,'AutonomousRouting':True,
                        'OriginalAdmissionTracePrefix':True,'ObserverEnabled':False,'PostHorizonDrain':False,
                        'AcceptanceEstablished':False,'NumericalParityEstablished':False,'FiniteStopPendingIsFailure':False,
                        'ProtocolTraceOmissions':0,'PhyTraceOmissions':0,'ElapsedWallSeconds':1,
                        'Admissions':old_summary['Admissions'],'Performance':dict(old_summary['Performance'],Seed=case['seed']),'Case':entry}
                    write(directory/'summary.json',summary)
            tests=owner/'tests';tests.mkdir();names=candidate['ExpectedTestNames']
            with (tests/'results.csv').open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=['Name','Passed','Failed','Incomplete','DurationSeconds']);writer.writeheader()
                writer.writerows({'Name':name,'Passed':'true','Failed':'false','Incomplete':'false','DurationSeconds':'0'} for name in names)
            test_summary={'Schema':'csr-tranche25-portable-tests-summary-v1','TestResultsFile':'results.csv',
                'TestFiles':candidate['TestFiles'],'ExpectedTestNames':names,'TestsExecuted':True,'TestsPassed':True,
                'TestCount':len(names),'PassedTests':len(names),'FailedTests':0,'IncompleteTests':0}
            write(tests/'summary.json',test_summary)
            identity={'CandidateSHA256':r.sha256(owner/'candidate.json'),'SourceCommit':r.t7.PIN,'Runtime':runtime,
                      'SourceFiles':sources,'ReferenceFiles':references}
            stage_entries=[]
            for phase in r.PHASES:
                directory=owner/phase
                write(directory/'start.json',{'schema':'csr-tranche25-stage-start-v1','phase':phase,'status':'started',
                    'started_utc':'2026-09-16T00:00:00Z','identity':identity})
                receipt={'schema':'csr-tranche25-stage-receipt-v1','phase':phase,'status':'completed',
                    'completed_utc':'2026-09-16T00:01:00Z','identity':identity,'SourceFilesStableDuringRun':True,
                    'ReferenceFilesStableDuringRun':True,'SourceFilesFinal':sources,'ReferenceFilesFinal':references,
                    'artifacts':inv(directory),'local_artifacts':[],'summary':r.json_object(directory/'summary.json')}
                write(directory/'receipt.json',receipt)
                (directory/'receipt.sha256').write_text(r.sha256(directory/'receipt.json')+'\n')
                stage_entries.append({'Phase':phase,'File':phase+'/receipt.json','SHA256':r.sha256(directory/'receipt.json')})
            metadata={'Schema':r.SCHEMA,'Tranche':25,'Status':'completed-review-required','synthetic_fixture_not_execution':True,
                'CandidateFile':r.CANDIDATE,'CandidateSHA256':identity['CandidateSHA256'],'Runtime':runtime,
                'MATLABExecuted':True,'NativeExecuted':False,'SourceCommit':r.t7.PIN,'FullAcceptanceGateExecuted':True,
                'AcceptanceEstablished':False,'NumericalParityEstablished':False,'CompletedCaseCount':2,
                'CampusStructuralChecksPassed':True,'StartedUTC':'2026-09-16T00:00:00Z','CompletedUTC':'2026-09-16T00:02:00Z',
                'EvidenceArchive':'t25.zip','SourceFilesFinal':sources,'SourceFilesStableDuringRun':True,
                'SourceSnapshotSHA256':r.sha256(owner/'source.json'),'ReferenceFilesFinal':references,
                'ReferenceFilesStableDuringRun':True,'ReferenceSnapshotSHA256':r.sha256(owner/'references.json'),
                'AllBaselineSourcesUnchanged':True,'UnmodifiedBaselineSourcesUnchanged':True,
                'AllowedBaselineModificationsVerified':True,'AllowedModifiedSourceFiles':candidate['AllowedModifiedSourceFiles'],
                'BaselineSourceFilesVerified':404,'BaselineMatlabFilesVerified':181,'StageReceipts':stage_entries,
                'Cases':[r.json_object(owner/key/'summary.json')['Case'] for key in ('s131','s132')],
                **{key:test_summary[key] for key in ('TestsExecuted','TestsPassed','TestCount','PassedTests','FailedTests','IncompleteTests')},
                'Artifacts':inv(owner),'LocalArtifacts':[],
                'ComparisonSeeds':[128,129,130,131,132],'ReusedCaseCount':3,'ReusedSeeds':[128,129,130],'SingleSeedScope':False,
                'ReusedCampusFile':r.REUSED,'ReusedCampusSHA256':r.sha256(source_root/r.REUSED),
                'ReusedCases':r.reused_report_rows(r.json_object(source_root/r.REUSED),runtime),
                'MatlabRuntimeHomogeneousAcrossSeeds':True,'HistoricalRuntimeEqualityRequired':False,
                'StatisticalEquivalenceClaimed':False,'CommonRandomNumbersClaimed':False,'ComparisonBandPercent':10,
                'PlannedCaseCount':2,'SimulatedSecondsCompleted':12000,'PlannedSimulatedSeconds':12000,
                'TestFiles':candidate['TestFiles'],'ExpectedTestNames':names,'TestResultsFile':'tests/results.csv'}

            write(owner/'metadata.json',metadata)
            result=r.review(owner,source_root,temp/'SYNTHETIC-REVIEW-ONLY')
            self.assertTrue(result['full_structural_gate_completed'])
            self.assertFalse(result['matlab_executed_by_reviewer'])
            self.assertEqual(result['tests']['count'],len(names))
            self.assertEqual(len(result['reused_cases']),3)
            self.assertEqual(result['reused_cases'][0]['matlab']['totals']['unique_delivered'],11825)
            self.assertEqual(len(result['comparisons']['rows']),105)
            self.assertEqual(len(result['comparisons']['summaries']),21)
            self.assertFalse(result['comparisons']['statistical_equivalence_established'])
            self.assertTrue(result['engine_ensemble']['runtime_homogeneous'])
            self.assertEqual(set(result['cases']),{'s131','s132'})
            results_path=owner/'tests/results.csv'
            original_test_bytes=results_path.read_bytes()
            rows=list(r.metrics.rows(results_path))
            rows[-1]['Name']=rows[0]['Name']
            with results_path.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            with self.assertRaisesRegex(ValueError,'Missing or duplicate'):
                r.verify_tests(owner,metadata,source_root,candidate,test_summary)
            results_path.write_bytes(original_test_bytes)
            # Runtime-mixed reuse is allowed but cannot be marked homogeneous.
            bad_metadata=dict(metadata,MatlabRuntimeHomogeneousAcrossSeeds=False)
            with self.assertRaisesRegex(ValueError,'homogeneity'):
                r.verify_identity(owner,bad_metadata,source_root,candidate)
            # Substantive mutation bypasses only inventories to target case accounting:
            # changing a raw endpoint counter must fail its reconstructions.
            directory=owner/'s132';path=directory/'raw/hop_nodes.csv'
            rows=list(r.metrics.rows(path));rows[0]['PendingData']=str(int(rows[0]['PendingData'])+1)
            with path.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            with self.assertRaisesRegex(ValueError,'endpoint'):
                r.metrics.analyze_case(directory,prepared['plan']['cases'][1])
            # Full checker also rejects unchanged receipt inventory after any byte edit.
            with self.assertRaisesRegex(ValueError,'hash/size'):
                r.inventory(owner,metadata['Artifacts'],'synthetic mutation',excluded=('metadata.json',))


if __name__ == '__main__':unittest.main()
