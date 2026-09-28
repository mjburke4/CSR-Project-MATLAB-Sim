classdef MultiSeedCheckpoint
    %MULTISEEDCHECKPOINT Immutable full-campus multi-seed experiment stages.
    % Receipts resume completed evidence, never a partially executed simulator.
    methods (Static)
        function options = options(given)
            options=struct('Phase','all');
            if nargin==0, return; end
            if ~isstruct(given) || ~isscalar(given) || ...
                    ~all(ismember(fieldnames(given),{'Phase'}))
                error('csr:t20:Options','Only the scalar Phase option is supported.');
            end
            if isfield(given,'Phase'), options.Phase=given.Phase; end
            if isstring(options.Phase) && isscalar(options.Phase)
                options.Phase=char(options.Phase);
            end
            if ~ischar(options.Phase) || ~isrow(options.Phase) || ...
                    ~ismember(options.Phase,{'all','tests','s129','s130','finalize'})
                error('csr:t20:Options','Phase must be all, tests, s129, s130 or finalize.');
            end
        end

        function validatePlan(plan,item)
            required={'schema','tranche','ns3_source_commit','engine_commit','cases', ...
                'execution_order','planned_simulated_seconds','comparison_band_percent', ...
                'scenario_file','scenario_sha256','native_reference_directory', ...
                'trace_limits','max_events','expected_admission_attempts','node_ids','flow_sources', ...
                'timing_policy','default_policy_changed','phy_ecc_changed','observer_enabled', ...
                'post_horizon_drain','full_portable_regression','numerical_parity_required', ...
                'common_random_numbers_claimed','single_seed_scope','native_tests_included','comparison_seeds', ...
                'seed_override_after_import','reused_baseline','runtime_must_equal_parent'};
            if ~isstruct(plan) || ~isscalar(plan) || ~all(isfield(plan,required))
                error('csr:t20:Plan','The multi-seed experiment plan is incomplete.');
            end
            if ~strcmp(plan.schema,'csr-tranche20-multi-seed-plan-v1') || plan.tranche~=20 || ...
                    ~strcmp(plan.ns3_source_commit,'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b') || ...
                    ~strcmp(plan.engine_commit,'6b5cd24ea80713ce16d88575869aedd6f432bdae') || ...
                    ~isequal(cellstr(string(plan.execution_order(:))),{'s129';'s130'}) || ...
                    ~isstruct(plan.cases) || numel(plan.cases)~=2 || ...
                    plan.planned_simulated_seconds~=12000 || plan.comparison_band_percent~=5 || ...
                    ~strcmp(plan.scenario_file,item.ScenarioFile) || ...
                    ~strcmp(plan.scenario_sha256,item.ScenarioSHA256) || ...
                    ~strcmp(plan.native_reference_directory,item.ReferenceDirectory) || ...
                    ~strcmp(plan.timing_policy,'continuous') || ...
                    ~isequal(plan.default_policy_changed,false) || ~isequal(plan.phy_ecc_changed,false) || ...
                    ~isequal(plan.observer_enabled,false) || ~isequal(plan.post_horizon_drain,false) || ...
                    ~isequal(plan.full_portable_regression,true) || ~isequal(plan.native_tests_included,false) || ...
                    ~isequal(plan.numerical_parity_required,false) || ...
                    ~isequal(plan.common_random_numbers_claimed,false) || ~isequal(plan.single_seed_scope,false) || ...
                    ~isequal(double(plan.comparison_seeds(:)),[128;129;130]) || ...
                    ~isequal(plan.seed_override_after_import,true) || ~isequal(plan.runtime_must_equal_parent,true)
                error('csr:t20:Plan','The fixed two-fresh-seed campus experiment scope changed.');
            end
            reuse=plan.reused_baseline;
            if ~isstruct(reuse) || ~isscalar(reuse) || ...
                    ~all(isfield(reuse,{'case_id','seed','owner_file','acceptance_file','candidate_file','policy','fresh_execution', ...
                    'owner_sha256','acceptance_sha256','candidate_sha256'})) || ...
                    ~strcmp(reuse.case_id,'a128') || reuse.seed~=128 || ...
                    ~strcmp(reuse.owner_file,'evidence/t19/owner.zip') || ...
                    ~strcmp(reuse.acceptance_file,'evidence/t19/acceptance.json') || ...
                    ~strcmp(reuse.candidate_file,'evidence/t19/candidate.json') || ...
                    ~strcmp(reuse.policy,'actual-tx') || ~isequal(reuse.fresh_execution,false) || ...
                    ~strcmp(reuse.owner_sha256,'525758669b8f84fa5dada46e293b8482980ef389efc5408ff056aac0e804ee30') || ...
                    ~strcmp(reuse.acceptance_sha256,'a0f2bcce6c8cc3d05b05bedbd80fc4426bcfbf2c505f0d0ac07d751573aba2f8') || ...
                    ~strcmp(reuse.candidate_sha256,'37b87a253a217824b0160f14b23f2b498e9df7a99cdc46648f3d9785a2fda777')
                error('csr:t20:Plan','Only the accepted T19 default seed 128 may be reused.');
            end
            c=item.Config;
            if ~strcmp(item.CaseId,'campus_multihop_6000') || ...
                    ~strcmp(c.Backend,'portable') || ~strcmp(c.Stack,'network') || ...
                    ~strcmp(c.Channel.Model,'csr-phy') || c.DurationSeconds~=6000 || c.Seed~=128 || ...
                    ~strcmp(c.Hop.DataQueuedRetryPolicy,'actual-tx') || ...
                    ~strcmp(c.ApplicationGenerator,'historical-opnet-gated') || c.ApplicationFlowLimit~=0 || ...
                    ~isequal([c.Nodes.Id],[1 2 3 4 5 7 8]) || ...
                    ~isequal([c.Traffic.SourceId],[2 3 4 5 7 8]) || ...
                    ~isequal(double(plan.node_ids(:)),[c.Nodes.Id]') || ...
                    ~isequal(double(plan.flow_sources(:)),[c.Traffic.SourceId]') || ...
                    plan.expected_admission_attempts~=1710000 || sum([c.Traffic.PacketCount])~=1710000 || ...
                    ~c.Trace.Enabled || c.Trace.MaxRecords~=1500000 || c.Trace.MaxPhyRecords~=1500000 || ...
                    c.Trace.MaxApplicationAdmissionRecords~=100000 || c.MaxEvents~=12000000 || ...
                    plan.trace_limits.protocol~=1500000 || plan.trace_limits.phy~=1500000 || ...
                    plan.trace_limits.admission~=100000 || plan.max_events~=12000000
                error('csr:t20:Plan','The complete original campus workload or evidence budget changed.');
            end
            keys={'s129','s130'}; seeds=[129 130];
            for k=1:2
                entry=plan.cases(k);
                requiredCase={'case_id','policy','seed','duration_s','scenario','scenario_file', ...
                    'scenario_sha256','reference_directory','bucket_width_s'};
                if ~all(isfield(entry,requiredCase)) || ~strcmp(entry.case_id,keys{k}) || ...
                        ~strcmp(entry.policy,'actual-tx') || entry.seed~=seeds(k) || entry.duration_s~=6000 || ...
                        ~strcmp(entry.scenario,item.Scenario) || ~strcmp(entry.scenario_file,item.ScenarioFile) || ...
                        ~strcmp(entry.scenario_sha256,item.ScenarioSHA256) || ...
                        ~strcmp(entry.reference_directory,['evidence/tranche-20-ns3-reference/' keys{k}]) || ...
                        entry.bucket_width_s~=item.BucketWidthSeconds
                    error('csr:t20:Plan','Case %d does not preserve the original campus with its declared seed.',k);
                end
            end
        end

        function [identity,candidate] = identity(root)
            root=csr.validation.Artifacts.canonicalPath(root);
            candidateFile='evidence/tranche-20-candidate.json';
            path=fullfile(root,candidateFile);
            candidate=jsondecode(fileread(path));
            if ~strcmp(candidate.Schema,'csr-tranche-20-candidate-v1') || candidate.Tranche~=20 || ...
                    ~strcmp(candidate.SourceCommit,'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b') || ...
                    ~isequal(cellstr(string(candidate.SourceFilesExcludedPaths)),{candidateFile})
                error('csr:t20:Candidate','Unexpected candidate identity or excluded source paths.');
            end
            sources=csr.validation.Artifacts.sourceSnapshot(root);
            bound=sources(~strcmp({sources.path},candidateFile));
            if ~isequal(bound,candidate.SourceFiles)
                error('csr:t20:Candidate','Candidate source membership or hashes changed.');
            end
            baselinePath=csr.validation.MultiSeedCheckpoint.checkedPath(root,candidate.BaselineSourceSnapshot);
            if ~strcmp(csr.validation.Artifacts.sha256(baselinePath),candidate.BaseSourceSnapshotSHA256)
                error('csr:t20:Baseline','The immutable Tranche 19 source snapshot changed.');
            end
            baseline=jsondecode(fileread(baselinePath));
            if numel(baseline)~=358 || numel(unique({baseline.path}))~=358 || ...
                    candidate.BaselineSourceFiles~=358 || ...
                    candidate.BaselineMatlabFiles~=sum(endsWith({baseline.path},'.m'))
                error('csr:t20:Baseline','Expected the complete 358-file accepted T19 source snapshot.');
            end
            if ~isempty(candidate.AllowedModifiedSourceFiles) || candidate.BaselineMatlabFiles~=170
                error('csr:t20:Baseline','All 358 accepted sources and 170 MATLAB files must remain unchanged.');
            end
            for k=1:numel(baseline)
                found=find(strcmp({sources.path},baseline(k).path));
                if numel(found)~=1 || ~strcmp(sources(found).sha256,baseline(k).sha256)
                    error('csr:t20:Baseline','Unexpected previous-source modification: %s.',baseline(k).path);
                end
            end
            if ~strcmp(candidate.Plan,'scenarios/t20/plan.json') || ...
                    ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,candidate.Plan)),candidate.PlanSHA256)
                error('csr:t20:Plan','The frozen release plan changed.');
            end
            listing=dir(fullfile(root,'tests','*.m'));
            testFiles=strcat('tests/',{listing.name});
            if ~isequal(sort(string(testFiles(:))),sort(string(candidate.TestFiles(:)))) || ...
                    numel(unique(string(candidate.ExpectedTestNames)))~=numel(candidate.ExpectedTestNames) || ...
                    isempty(candidate.ExpectedTestNames)
                error('csr:t20:Tests','The full top-level portable test inventory changed.');
            end
            names=cellstr(string(candidate.ReferenceFiles));
            if isempty(names) || numel(unique(names))~=numel(names) || ...
                    (isfield(candidate,'ReferenceRoots') && ~isempty(candidate.ReferenceRoots))
                error('csr:t20:Reference','Explicit, distinct reference files are required.');
            end
            references=repmat(struct('path','','sha256','','bytes',0),numel(names),1);
            for k=1:numel(names)
                actual=csr.validation.MultiSeedCheckpoint.checkedPath(root,names{k});
                details=dir(actual);
                references(k)=struct('path',names{k}, ...
                    'sha256',csr.validation.Artifacts.sha256(actual),'bytes',details.bytes);
            end
            [~,order]=sort({references.path}); references=references(order);
            if ~isfield(candidate,'ReferenceFileInventory') || ...
                    ~isequal(references,candidate.ReferenceFileInventory)
                error('csr:t20:Reference','Frozen reference membership, hashes or sizes changed.');
            end
            csr.validation.MultiSeedCheckpoint.reusedBaseline(root,csr.sim.capabilities());
            identity=struct('CandidateSHA256',csr.validation.Artifacts.sha256(path), ...
                'SourceCommit',candidate.SourceCommit,'Runtime',csr.sim.capabilities(), ...
                'SourceFiles',sources,'ReferenceFiles',references);
        end

        function reused = reusedBaseline(root,runtime)
            acceptanceFile='evidence/t19/acceptance.json';
            ownerFile='evidence/t19/owner.zip'; candidateFile='evidence/t19/candidate.json';
            acceptancePath=csr.validation.MultiSeedCheckpoint.checkedPath(root,acceptanceFile);
            if ~strcmp(csr.validation.Artifacts.sha256(acceptancePath),'a0f2bcce6c8cc3d05b05bedbd80fc4426bcfbf2c505f0d0ac07d751573aba2f8')
                error('csr:t20:Reuse','The accepted parent review record changed.');
            end
            acceptance=jsondecode(fileread(acceptancePath));
            ownerHash=csr.validation.Artifacts.sha256(csr.validation.MultiSeedCheckpoint.checkedPath(root,ownerFile));
            candidateHash=csr.validation.Artifacts.sha256(csr.validation.MultiSeedCheckpoint.checkedPath(root,candidateFile));
            if ~strcmp(acceptance.schema,'csr-tranche19-acceptance-v1') || ...
                    ~strcmp(acceptance.status,'accepted_for_portable_regression_and_policy_experiment') || ...
                    ~strcmp(ownerHash,'525758669b8f84fa5dada46e293b8482980ef389efc5408ff056aac0e804ee30') || ...
                    ~strcmp(candidateHash,'37b87a253a217824b0160f14b23f2b498e9df7a99cdc46648f3d9785a2fda777') || ...
                    ~strcmp(acceptance.owner_evidence_sha256,ownerHash) || ...
                    ~strcmp(acceptance.candidate_sha256,candidateHash) || ...
                    ~acceptance.default_reproduces_t17_statistics_and_12_core_csvs || ...
                    ~strcmp(acceptance.default_policy,'actual-tx') || acceptance.experimental_policy_promoted
                error('csr:t20:Reuse','Accepted T19 default evidence identity changed.');
            end
            csr.validation.MultiSeedCheckpoint.validateRuntime(runtime,acceptance.runtime);
            reused=struct('CaseId','a128','Seed',128,'Policy','actual-tx', ...
                'OwnerFile',ownerFile,'OwnerSHA256',ownerHash, ...
                'CandidateFile',candidateFile,'CandidateSHA256',candidateHash, ...
                'AcceptanceFile',acceptanceFile, ...
                'AcceptanceSHA256',csr.validation.Artifacts.sha256(fullfile(root,acceptanceFile)), ...
                'SourceSnapshotSHA256',acceptance.source_snapshot_sha256, ...
                'Runtime',acceptance.runtime,'FreshlyExecuted',false);
        end

        function validateRuntime(runtime,parentRuntime)
            if ~isequal(runtime,parentRuntime)
                error('csr:t20:Runtime','T20 requires the exact accepted T19 MATLAB runtime (R2025a 25.1.0.2943329) for seed comparison.');
            end
        end

        function preflight(directory,root,identity,candidate)
            % Reject unrelated or damaged outputs before metadata/log writes.
            if ~isfolder(directory), return; end
            entries=dir(directory); entries=entries(~ismember({entries.name},{'.','..'}));
            if isempty(entries), return; end
            fixed={'source.json','references.json','candidate.json','plan.json','metadata.json', ...
                't20.zip','.active','tests','s129','s130'};
            names={entries.name};
            logs=~cellfun(@isempty,regexp(names,'^run_[A-Za-z0-9_]+\.log$','once'));
            stageNames=ismember(names,{'tests','s129','s130'});
            if any(~ismember(names,fixed) & ~logs) || ...
                    any(stageNames & ~[entries.isdir]) || any(~stageNames & [entries.isdir])
                error('csr:t20:OutputIdentity','Output contains unrelated files; select a new evidence directory.');
            end
            for name={'source.json','references.json','candidate.json','plan.json','metadata.json'}
                if ~isfile(fullfile(directory,name{1}))
                    error('csr:t20:OutputIdentity','Existing output has no complete T20 identity; preserve it and choose a new directory.');
                end
            end
            metadata=jsondecode(fileread(fullfile(directory,'metadata.json')));
            if ~strcmp(metadata.Schema,'csr-matlab-tranche-20-validation-v1') || ...
                    ~isequal(metadata.Runtime,identity.Runtime)
                error('csr:t20:OutputIdentity','Existing evidence has a different tranche or MATLAB runtime.');
            end
            bindings={'source.json',identity.SourceFiles;'references.json',identity.ReferenceFiles};
            for k=1:size(bindings,1)
                if ~isequal(jsondecode(fileread(fullfile(directory,bindings{k,1}))),bindings{k,2})
                    error('csr:t20:OutputIdentity','Existing evidence source/reference identity differs.');
                end
            end
            copies={'candidate.json','evidence/tranche-20-candidate.json';'plan.json',candidate.Plan};
            for k=1:size(copies,1)
                if ~strcmp(csr.validation.Artifacts.sha256(fullfile(directory,copies{k,1})), ...
                        csr.validation.Artifacts.sha256(fullfile(root,copies{k,2})))
                    error('csr:t20:OutputIdentity','Existing frozen candidate or plan differs.');
                end
            end
            for phase={'tests','s129','s130'}
                if isfolder(fullfile(directory,phase{1}))
                    csr.validation.MultiSeedCheckpoint.verify(directory,phase{1},identity);
                end
            end
        end

        function [receipt,reused] = begin(directory,phase,identity)
            csr.validation.MultiSeedCheckpoint.phase(phase);
            stage=fullfile(directory,phase);
            if isfolder(stage)
                receipt=csr.validation.MultiSeedCheckpoint.verify(directory,phase,identity);
                reused=true;
                return
            end
            [ok,message]=mkdir(stage);
            if ~ok, error('csr:t20:Output','Cannot create stage: %s.',message); end
            csr.validation.Artifacts.writeJson(fullfile(stage,'start.json'), ...
                struct('schema','csr-tranche20-stage-start-v1','phase',phase, ...
                'status','started','started_utc',csr.validation.Artifacts.utcNow(), ...
                'identity',identity));
            receipt=struct(); reused=false;
        end

        function receipt = seal(directory,phase,identity,summary)
            csr.validation.MultiSeedCheckpoint.phase(phase);
            stage=fullfile(directory,phase);
            if ~isfile(fullfile(stage,'start.json')) || ...
                    isfile(fullfile(stage,'receipt.json')) || isfile(fullfile(stage,'receipt.sha256'))
                error('csr:t20:Stage','A fresh started stage is required for sealing.');
            end
            started=jsondecode(fileread(fullfile(stage,'start.json')));
            if ~isequal(started.identity,identity) || ~strcmp(started.phase,phase)
                error('csr:t20:Stage','Stage identity changed before completion.');
            end
            inventory=csr.validation.Artifacts.fileInventory(stage);
            local=endsWith({inventory.path},'.mat') | endsWith({inventory.path},'.zip');
            receipt=struct('schema','csr-tranche20-stage-receipt-v1','phase',phase, ...
                'status','completed','completed_utc',csr.validation.Artifacts.utcNow(), ...
                'identity',identity,'summary',summary, ...
                'SourceCommit',identity.SourceCommit, ...
                'SourceFilesStableDuringRun',true,'ReferenceFilesStableDuringRun',true, ...
                'SourceFilesFinal',identity.SourceFiles,'ReferenceFilesFinal',identity.ReferenceFiles, ...
                'artifacts',inventory(~local), ...
                'local_artifacts',inventory(local));
            receiptPath=fullfile(stage,'receipt.json');
            csr.validation.Artifacts.writeJson(receiptPath,receipt);
            csr.validation.MultiSeedCheckpoint.writeText(fullfile(stage,'receipt.sha256'), ...
                csr.validation.Artifacts.sha256(receiptPath));
        end

        function receipt = verify(directory,phase,identity)
            csr.validation.MultiSeedCheckpoint.phase(phase);
            stage=fullfile(directory,phase);
            receiptPath=fullfile(stage,'receipt.json');
            checksumPath=fullfile(stage,'receipt.sha256');
            if ~isfile(receiptPath) || ~isfile(checksumPath)
                error('csr:t20:IncompleteStage', ...
                    'Stage %s is missing or partial. Preserve it and restart in a new output directory.',phase);
            end
            if ~strcmp(strtrim(fileread(checksumPath)),csr.validation.Artifacts.sha256(receiptPath))
                error('csr:t20:Receipt','The %s receipt checksum changed.',phase);
            end
            receipt=jsondecode(fileread(receiptPath));
            if ~strcmp(receipt.schema,'csr-tranche20-stage-receipt-v1') || ...
                    ~strcmp(receipt.status,'completed') || ~strcmp(receipt.phase,phase) || ...
                    ~isequal(receipt.identity,identity) || ...
                    ~strcmp(receipt.SourceCommit,identity.SourceCommit) || ...
                    ~isequal(receipt.SourceFilesStableDuringRun,true) || ...
                    ~isequal(receipt.ReferenceFilesStableDuringRun,true) || ...
                    ~isequal(receipt.SourceFilesFinal,identity.SourceFiles) || ...
                    ~isequal(receipt.ReferenceFilesFinal,identity.ReferenceFiles)
                error('csr:t20:Receipt','The completed stage has a different candidate/source/reference identity.');
            end
            actual=csr.validation.Artifacts.fileInventory(stage,{'receipt.json','receipt.sha256'});
            local=endsWith({actual.path},'.mat') | endsWith({actual.path},'.zip');
            if ~isequal(actual(~local),receipt.artifacts)
                error('csr:t20:Receipt','Completed stage artifacts are missing, extra or changed.');
            end
            % MAT snapshots stay local and are optional on transported evidence.
            % Any retained local snapshot must still have its original bytes.
            for k=find(local(:))'
                if isempty(receipt.local_artifacts)
                    error('csr:t20:Receipt','An undeclared local MAT snapshot was added.');
                end
                found=find(strcmp({receipt.local_artifacts.path},actual(k).path));
                if numel(found)~=1 || ~isequal(actual(k),receipt.local_artifacts(found))
                    error('csr:t20:Receipt','A retained local MAT snapshot changed.');
                end
            end
            started=jsondecode(fileread(fullfile(stage,'start.json')));
            if ~strcmp(started.phase,phase) || ~strcmp(started.status,'started') || ...
                    ~isequal(started.identity,identity)
                error('csr:t20:Receipt','The stage start identity does not match its completed receipt.');
            end
        end

        function summary = testResults(results,expectedNames,testFiles)
            required={'Name','Passed','Failed','Incomplete','DurationSeconds'};
            if ~istable(results) || ~all(ismember(required,results.Properties.VariableNames))
                error('csr:t20:TestIdentity','A complete test-result table is required.');
            end
            actual=string(results.Name); expected=string(expectedNames);
            if isempty(actual) || numel(unique(actual))~=height(results) || ...
                    ~isequal(sort(actual(:)),sort(expected(:)))
                error('csr:t20:TestIdentity','Full portable test names differ from the frozen candidate.');
            end
            flags=[double(results.Passed),double(results.Failed),double(results.Incomplete)];
            if any(~ismember(flags(:),[0 1])) || ...
                    any(~isfinite(results.DurationSeconds) | results.DurationSeconds<0)
                error('csr:t20:Tests','Test result flags or durations are invalid.');
            end
            if nargin<3
                classes=regexprep(cellstr(expected(:)),'/.*$','');
                testFiles=strcat('tests/',unique(classes),'.m');
            end
            summary=struct('Schema','csr-tranche20-portable-tests-summary-v1', ...
                'TestsExecuted',true,'TestsPassed',all(results.Passed & ~results.Failed & ~results.Incomplete), ...
                'TestCount',height(results),'PassedTests',sum(results.Passed), ...
                'FailedTests',sum(results.Failed),'IncompleteTests',sum(results.Incomplete), ...
                'TestResultsFile','results.csv','TestFiles',{cellstr(string(testFiles(:)))}, ...
                'ExpectedTestNames',{cellstr(expected(:))});
        end

        function path = checkedPath(root,relative)
            if isstring(relative) && isscalar(relative), relative=char(relative); end
            if ~ischar(relative) || ~isrow(relative) || isempty(relative) || ...
                    contains(relative,'\') || contains(relative,'//') || startsWith(relative,'/') || endsWith(relative,'/') || ...
                    ~isempty(regexp(relative,'(^|/)\.\.?(/|$)|^[A-Za-z]:','once'))
                error('csr:t20:Path','Expected a canonical contained relative file path.');
            end
            root=csr.validation.Artifacts.canonicalPath(root);
            path=csr.validation.Artifacts.canonicalPath(fullfile(root,relative));
            if ~startsWith(path,[root filesep]) || ~isfile(path)
                error('csr:t20:Path','Required artifact is missing or outside the installation: %s.',relative);
            end
        end

        function writeText(path,value)
            fid=fopen(path,'w');
            if fid<0, error('csr:t20:Output','Cannot write %s.',path); end
            cleanup=onCleanup(@()fclose(fid)); %#ok<NASGU>
            fprintf(fid,'%s\n',value);
        end
    end
    methods (Static, Access=private)
        function phase(value)
            if ~ischar(value) || ~ismember(value,{'tests','s129','s130'})
                error('csr:t20:Stage','Only tests, s129 and s130 have reusable receipts.');
            end
        end
    end
end
