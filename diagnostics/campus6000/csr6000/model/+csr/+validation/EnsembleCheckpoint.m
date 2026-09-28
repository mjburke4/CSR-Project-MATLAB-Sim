classdef EnsembleCheckpoint
    %ENSEMBLECHECKPOINT Immutable full-campus ensemble experiment stages.
    % Receipts resume completed evidence, never a partially executed simulator.
    methods (Static)
        function options = options(given)
            options=struct('Phase','all');
            if nargin==0, return; end
            if ~isstruct(given) || ~isscalar(given) || ...
                    ~all(ismember(fieldnames(given),{'Phase'}))
                error('csr:t25:Options','Only the scalar Phase option is supported.');
            end
            if isfield(given,'Phase'), options.Phase=given.Phase; end
            if isstring(options.Phase) && isscalar(options.Phase)
                options.Phase=char(options.Phase);
            end
            if ~ischar(options.Phase) || ~isrow(options.Phase) || ...
                    ~ismember(options.Phase,{'all','tests','s131','s132','finalize'})
                error('csr:t25:Options','Phase must be all, tests, s131, s132 or finalize.');
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
                'seed_override_after_import','reused_campus_file','reused_campus_sha256', ...
                'reused_seeds','fresh_seeds','fresh_native_reference_seeds', ...
                'reused_native_reference_seeds','runtime_must_equal_parent'};
            if ~isstruct(plan) || ~isscalar(plan) || ~all(isfield(plan,required))
                error('csr:t25:Plan','The ensemble experiment plan is incomplete.');
            end
            if ~strcmp(plan.schema,'csr-tranche25-ensemble-plan-v1') || plan.tranche~=25 || ...
                    ~strcmp(plan.ns3_source_commit,'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b') || ...
                    ~strcmp(plan.engine_commit,'6b5cd24ea80713ce16d88575869aedd6f432bdae') || ...
                    ~isequal(cellstr(string(plan.execution_order(:))),{'s131';'s132'}) || ...
                    ~isstruct(plan.cases) || numel(plan.cases)~=2 || ...
                    plan.planned_simulated_seconds~=12000 || plan.comparison_band_percent~=10 || ...
                    ~strcmp(plan.scenario_file,item.ScenarioFile) || ...
                    ~strcmp(plan.scenario_sha256,item.ScenarioSHA256) || ...
                    ~strcmp(plan.native_reference_directory,item.ReferenceDirectory) || ...
                    ~strcmp(plan.timing_policy,'continuous') || ...
                    ~isequal(plan.default_policy_changed,false) || ~isequal(plan.phy_ecc_changed,false) || ...
                    ~isequal(plan.observer_enabled,false) || ~isequal(plan.post_horizon_drain,false) || ...
                    ~isequal(plan.full_portable_regression,true) || ~isequal(plan.native_tests_included,false) || ...
                    ~isequal(plan.numerical_parity_required,false) || ...
                    ~isequal(plan.common_random_numbers_claimed,false) || ~isequal(plan.single_seed_scope,false) || ...
                    ~isequal(double(plan.comparison_seeds(:)),[128;129;130;131;132]) || ...
                    ~isequal(double(plan.fresh_seeds(:)),[131;132]) || ...
                    ~isequal(double(plan.reused_seeds(:)),[128;129;130]) || ...
                    ~isequal(double(plan.fresh_native_reference_seeds(:)),[131;132]) || ...
                    ~isequal(double(plan.reused_native_reference_seeds(:)),[128;129;130]) || ...
                    ~isequal(plan.seed_override_after_import,true) || ~isequal(plan.runtime_must_equal_parent,false)
                error('csr:t25:Plan','The fixed two-fresh-seed campus experiment scope changed.');
            end
            if ~strcmp(plan.reused_campus_file,'evidence/t25/reused-campus.json') || ...
                    isempty(regexp(plan.reused_campus_sha256,'^[a-f0-9]{64}$','once'))
                error('csr:t25:Plan','The accepted three-seed campus reuse record must be frozen.');
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
                error('csr:t25:Plan','The complete original campus workload or evidence budget changed.');
            end
            keys={'s131','s132'}; seeds=[131 132];
            for k=1:2
                entry=plan.cases(k);
                requiredCase={'case_id','policy','seed','duration_s','scenario','scenario_file', ...
                    'scenario_sha256','reference_directory','bucket_width_s'};
                if ~all(isfield(entry,requiredCase)) || ~strcmp(entry.case_id,keys{k}) || ...
                        ~strcmp(entry.policy,'actual-tx') || entry.seed~=seeds(k) || entry.duration_s~=6000 || ...
                        ~strcmp(entry.scenario,item.Scenario) || ~strcmp(entry.scenario_file,item.ScenarioFile) || ...
                        ~strcmp(entry.scenario_sha256,item.ScenarioSHA256) || ...
                        ~strcmp(entry.reference_directory,['evidence/tranche-25-ns3-reference/' keys{k}]) || ...
                        entry.bucket_width_s~=item.BucketWidthSeconds
                    error('csr:t25:Plan','Case %d does not preserve the original campus with its declared seed.',k);
                end
            end
        end

        function [identity,candidate] = identity(root)
            root=csr.validation.Artifacts.canonicalPath(root);
            candidateFile='evidence/tranche-25-candidate.json';
            path=fullfile(root,candidateFile);
            candidate=jsondecode(fileread(path));
            if ~strcmp(candidate.Schema,'csr-tranche-25-candidate-v1') || candidate.Tranche~=25 || ...
                    ~strcmp(candidate.SourceCommit,'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b') || ...
                    ~isequal(cellstr(string(candidate.SourceFilesExcludedPaths)),{candidateFile})
                error('csr:t25:Candidate','Unexpected candidate identity or excluded source paths.');
            end
            sources=csr.validation.Artifacts.sourceSnapshot(root);
            bound=sources(~strcmp({sources.path},candidateFile));
            if ~isequal(bound,candidate.SourceFiles)
                error('csr:t25:Candidate','Candidate source membership or hashes changed.');
            end
            baselinePath=csr.validation.EnsembleCheckpoint.checkedPath(root,candidate.BaselineSourceSnapshot);
            if ~strcmp(csr.validation.Artifacts.sha256(baselinePath),candidate.BaseSourceSnapshotSHA256)
                error('csr:t25:Baseline','The immutable Tranche 23 source snapshot changed.');
            end
            baseline=jsondecode(fileread(baselinePath));
            if numel(baseline)~=404 || numel(unique({baseline.path}))~=404 || ...
                    candidate.BaselineSourceFiles~=404 || ...
                    candidate.BaselineMatlabFiles~=sum(endsWith({baseline.path},'.m'))
                error('csr:t25:Baseline','Expected the complete 404-file accepted T23 source snapshot.');
            end
            if ~isempty(candidate.AllowedModifiedSourceFiles) || candidate.BaselineMatlabFiles~=181
                error('csr:t25:Baseline','All 404 accepted sources and 181 MATLAB files must remain unchanged.');
            end
            for k=1:numel(baseline)
                found=find(strcmp({sources.path},baseline(k).path));
                if numel(found)~=1 || ~strcmp(sources(found).sha256,baseline(k).sha256)
                    error('csr:t25:Baseline','Unexpected previous-source modification: %s.',baseline(k).path);
                end
            end
            if ~strcmp(candidate.Plan,'scenarios/t25/plan.json') || ...
                    ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,candidate.Plan)),candidate.PlanSHA256)
                error('csr:t25:Plan','The frozen release plan changed.');
            end
            listing=dir(fullfile(root,'tests','*.m'));
            testFiles=strcat('tests/',{listing.name});
            if ~isequal(sort(string(testFiles(:))),sort(string(candidate.TestFiles(:)))) || ...
                    numel(unique(string(candidate.ExpectedTestNames)))~=numel(candidate.ExpectedTestNames) || ...
                    isempty(candidate.ExpectedTestNames)
                error('csr:t25:Tests','The full top-level portable test inventory changed.');
            end
            names=cellstr(string(candidate.ReferenceFiles));
            if isempty(names) || numel(unique(names))~=numel(names) || ...
                    (isfield(candidate,'ReferenceRoots') && ~isempty(candidate.ReferenceRoots))
                error('csr:t25:Reference','Explicit, distinct reference files are required.');
            end
            references=repmat(struct('path','','sha256','','bytes',0),numel(names),1);
            for k=1:numel(names)
                actual=csr.validation.EnsembleCheckpoint.checkedPath(root,names{k});
                details=dir(actual);
                references(k)=struct('path',names{k}, ...
                    'sha256',csr.validation.Artifacts.sha256(actual),'bytes',details.bytes);
            end
            [~,order]=sort({references.path}); references=references(order);
            if ~isfield(candidate,'ReferenceFileInventory') || ...
                    ~isequal(references,candidate.ReferenceFileInventory)
                error('csr:t25:Reference','Frozen reference membership, hashes or sizes changed.');
            end
            csr.validation.EnsembleCheckpoint.reusedCases(root,csr.sim.capabilities(),sources,references);
            identity=struct('CandidateSHA256',csr.validation.Artifacts.sha256(path), ...
                'SourceCommit',candidate.SourceCommit,'Runtime',csr.sim.capabilities(), ...
                'SourceFiles',sources,'ReferenceFiles',references);
        end

        function reused = reusedCases(root,runtime,sources,references)
            % The frozen record preserves each old run's original identity.
            % Historical release differences are reported, not relabeled or rerun.
            plan=jsondecode(fileread(fullfile(root,'scenarios','t25','plan.json')));
            path=csr.validation.EnsembleCheckpoint.boundReference(root, ...
                plan.reused_campus_file,plan.reused_campus_sha256,references);
            record=jsondecode(fileread(path));
            if ~isstruct(record) || ~isscalar(record) || ...
                    ~all(isfield(record,{'schema','seeds','cases'})) || ...
                    ~strcmp(record.schema,'csr-tranche25-reused-campus-v1') || ...
                    ~isequal(double(record.seeds(:)),[128;129;130]) || ...
                    ~isstruct(record.cases) || numel(record.cases)~=3
                error('csr:t25:Reuse','Expected exactly three accepted campus runs for seeds 128-130.');
            end
            template=struct('CaseId','','Seed',0,'Policy','','DurationSeconds',0, ...
                'ScenarioSHA256','','OwnerFile','','OwnerSHA256','', ...
                'CandidateFile','','CandidateSHA256','','AcceptanceFile','','AcceptanceSHA256','', ...
                'SourceSnapshotFile','','SourceSnapshotSHA256','','Runtime',struct(), ...
                'RuntimeMatchesCurrent',false,'SourceBindingsUnchanged',true,'FreshlyExecuted',false);
            reused=repmat(template,3,1); keys={'a128','s129','s130'}; seeds=[128 129 130];
            for k=1:3
                value=record.cases(k);
                required={'case_id','seed','policy','fresh_execution','duration_s','scenario_sha256', ...
                    'owner_file','owner_sha256','candidate_file','candidate_sha256', ...
                    'acceptance_file','acceptance_sha256','source_snapshot_file','source_snapshot_sha256','runtime'};
                if ~all(isfield(value,required)) || ~strcmp(value.case_id,keys{k}) || value.seed~=seeds(k) || ...
                        ~strcmp(value.policy,'actual-tx') || ~isequal(value.fresh_execution,false) || ...
                        value.duration_s~=6000 || ~strcmp(value.scenario_sha256,plan.scenario_sha256)
                    error('csr:t25:Reuse','Reused cases must preserve accepted policy, seed and full campus scope.');
                end
                for role={'owner','candidate','acceptance','source_snapshot'}
                    csr.validation.EnsembleCheckpoint.boundReference(root, ...
                        value.([role{1} '_file']),value.([role{1} '_sha256']),references);
                end
                historic=jsondecode(fileread(fullfile(root,value.source_snapshot_file)));
                if ~isstruct(historic) || isempty(historic) || ~all(isfield(historic,{'path','sha256'})) || ...
                        numel(unique({historic.path}))~=numel(historic)
                    error('csr:t25:Reuse','The historical source snapshot is not complete and distinct.');
                end
                for j=1:numel(historic)
                    found=find(strcmp({sources.path},historic(j).path));
                    if numel(found)~=1 || ~strcmp(sources(found).sha256,historic(j).sha256)
                        error('csr:t25:Reuse','A reused run source is missing or changed: %s.',historic(j).path);
                    end
                end
                matches=csr.validation.EnsembleCheckpoint.validateRuntime(runtime,value.runtime);
                reused(k)=struct('CaseId',value.case_id,'Seed',value.seed,'Policy',value.policy, ...
                    'DurationSeconds',value.duration_s,'ScenarioSHA256',value.scenario_sha256, ...
                    'OwnerFile',value.owner_file,'OwnerSHA256',value.owner_sha256, ...
                    'CandidateFile',value.candidate_file,'CandidateSHA256',value.candidate_sha256, ...
                    'AcceptanceFile',value.acceptance_file,'AcceptanceSHA256',value.acceptance_sha256, ...
                    'SourceSnapshotFile',value.source_snapshot_file, ...
                    'SourceSnapshotSHA256',value.source_snapshot_sha256, ...
                    'Runtime',value.runtime,'RuntimeMatchesCurrent',matches, ...
                    'SourceBindingsUnchanged',true,'FreshlyExecuted',false);
            end
        end

        function same = validateRuntime(runtime,parentRuntime)
            required={'Runtime','Version','Release','DefaultBackend'};
            for value={runtime,parentRuntime}
                item=value{1};
                if ~isstruct(item) || ~isscalar(item) || ~all(isfield(item,required)) || ...
                        ~strcmp(item.Runtime,'MATLAB') || ~strcmp(item.DefaultBackend,'portable') || ...
                        isempty(item.Version) || isempty(item.Release)
                    error('csr:t25:Runtime','Every run must retain its original portable MATLAB runtime identity.');
                end
            end
            same=isequal(runtime,parentRuntime);
        end

        function path = boundReference(root,relative,expected,references)
            path=csr.validation.EnsembleCheckpoint.checkedPath(root,relative);
            if ~ischar(expected) || isempty(regexp(expected,'^[a-f0-9]{64}$','once'))
                error('csr:t25:Reuse','Reused evidence requires a complete SHA-256 binding.');
            end
            found=find(strcmp({references.path},relative));
            if numel(found)~=1 || ~strcmp(references(found).sha256,expected)
                error('csr:t25:Reuse','Reused artifact is not bound by the current reference inventory: %s.',relative);
            end
        end

        function preflight(directory,root,identity,candidate)
            % Reject unrelated or damaged outputs before metadata/log writes.
            if ~isfolder(directory), return; end
            entries=dir(directory); entries=entries(~ismember({entries.name},{'.','..'}));
            if isempty(entries), return; end
            fixed={'source.json','references.json','candidate.json','plan.json','metadata.json', ...
                't25.zip','.active','tests','s131','s132'};
            names={entries.name};
            logs=~cellfun(@isempty,regexp(names,'^run_[A-Za-z0-9_]+\.log$','once'));
            stageNames=ismember(names,{'tests','s131','s132'});
            if any(~ismember(names,fixed) & ~logs) || ...
                    any(stageNames & ~[entries.isdir]) || any(~stageNames & [entries.isdir])
                error('csr:t25:OutputIdentity','Output contains unrelated files; select a new evidence directory.');
            end
            for name={'source.json','references.json','candidate.json','plan.json','metadata.json'}
                if ~isfile(fullfile(directory,name{1}))
                    error('csr:t25:OutputIdentity','Existing output has no complete T25 identity; preserve it and choose a new directory.');
                end
            end
            metadata=jsondecode(fileread(fullfile(directory,'metadata.json')));
            if ~strcmp(metadata.Schema,'csr-matlab-tranche-25-validation-v1') || ...
                    ~isequal(metadata.Runtime,identity.Runtime)
                error('csr:t25:OutputIdentity','Existing evidence has a different tranche or MATLAB runtime.');
            end
            bindings={'source.json',identity.SourceFiles;'references.json',identity.ReferenceFiles};
            for k=1:size(bindings,1)
                if ~isequal(jsondecode(fileread(fullfile(directory,bindings{k,1}))),bindings{k,2})
                    error('csr:t25:OutputIdentity','Existing evidence source/reference identity differs.');
                end
            end
            copies={'candidate.json','evidence/tranche-25-candidate.json';'plan.json',candidate.Plan};
            for k=1:size(copies,1)
                if ~strcmp(csr.validation.Artifacts.sha256(fullfile(directory,copies{k,1})), ...
                        csr.validation.Artifacts.sha256(fullfile(root,copies{k,2})))
                    error('csr:t25:OutputIdentity','Existing frozen candidate or plan differs.');
                end
            end
            for phase={'tests','s131','s132'}
                if isfolder(fullfile(directory,phase{1}))
                    csr.validation.EnsembleCheckpoint.verify(directory,phase{1},identity);
                end
            end
        end

        function [receipt,reused] = begin(directory,phase,identity)
            csr.validation.EnsembleCheckpoint.phase(phase);
            stage=fullfile(directory,phase);
            if isfolder(stage)
                receipt=csr.validation.EnsembleCheckpoint.verify(directory,phase,identity);
                reused=true;
                return
            end
            [ok,message]=mkdir(stage);
            if ~ok, error('csr:t25:Output','Cannot create stage: %s.',message); end
            csr.validation.Artifacts.writeJson(fullfile(stage,'start.json'), ...
                struct('schema','csr-tranche25-stage-start-v1','phase',phase, ...
                'status','started','started_utc',csr.validation.Artifacts.utcNow(), ...
                'identity',identity));
            receipt=struct(); reused=false;
        end

        function receipt = seal(directory,phase,identity,summary)
            csr.validation.EnsembleCheckpoint.phase(phase);
            stage=fullfile(directory,phase);
            if ~isfile(fullfile(stage,'start.json')) || ...
                    isfile(fullfile(stage,'receipt.json')) || isfile(fullfile(stage,'receipt.sha256'))
                error('csr:t25:Stage','A fresh started stage is required for sealing.');
            end
            started=jsondecode(fileread(fullfile(stage,'start.json')));
            if ~isequal(started.identity,identity) || ~strcmp(started.phase,phase)
                error('csr:t25:Stage','Stage identity changed before completion.');
            end
            inventory=csr.validation.Artifacts.fileInventory(stage);
            local=endsWith({inventory.path},'.mat') | endsWith({inventory.path},'.zip');
            receipt=struct('schema','csr-tranche25-stage-receipt-v1','phase',phase, ...
                'status','completed','completed_utc',csr.validation.Artifacts.utcNow(), ...
                'identity',identity,'summary',summary, ...
                'SourceCommit',identity.SourceCommit, ...
                'SourceFilesStableDuringRun',true,'ReferenceFilesStableDuringRun',true, ...
                'SourceFilesFinal',identity.SourceFiles,'ReferenceFilesFinal',identity.ReferenceFiles, ...
                'artifacts',inventory(~local), ...
                'local_artifacts',inventory(local));
            receiptPath=fullfile(stage,'receipt.json');
            csr.validation.Artifacts.writeJson(receiptPath,receipt);
            csr.validation.EnsembleCheckpoint.writeText(fullfile(stage,'receipt.sha256'), ...
                csr.validation.Artifacts.sha256(receiptPath));
        end

        function receipt = verify(directory,phase,identity)
            csr.validation.EnsembleCheckpoint.phase(phase);
            stage=fullfile(directory,phase);
            receiptPath=fullfile(stage,'receipt.json');
            checksumPath=fullfile(stage,'receipt.sha256');
            if ~isfile(receiptPath) || ~isfile(checksumPath)
                error('csr:t25:IncompleteStage', ...
                    'Stage %s is missing or partial. Preserve it and restart in a new output directory.',phase);
            end
            if ~strcmp(strtrim(fileread(checksumPath)),csr.validation.Artifacts.sha256(receiptPath))
                error('csr:t25:Receipt','The %s receipt checksum changed.',phase);
            end
            receipt=jsondecode(fileread(receiptPath));
            if ~strcmp(receipt.schema,'csr-tranche25-stage-receipt-v1') || ...
                    ~strcmp(receipt.status,'completed') || ~strcmp(receipt.phase,phase) || ...
                    ~isequal(receipt.identity,identity) || ...
                    ~strcmp(receipt.SourceCommit,identity.SourceCommit) || ...
                    ~isequal(receipt.SourceFilesStableDuringRun,true) || ...
                    ~isequal(receipt.ReferenceFilesStableDuringRun,true) || ...
                    ~isequal(receipt.SourceFilesFinal,identity.SourceFiles) || ...
                    ~isequal(receipt.ReferenceFilesFinal,identity.ReferenceFiles)
                error('csr:t25:Receipt','The completed stage has a different candidate/source/reference identity.');
            end
            actual=csr.validation.Artifacts.fileInventory(stage,{'receipt.json','receipt.sha256'});
            local=endsWith({actual.path},'.mat') | endsWith({actual.path},'.zip');
            if ~isequal(actual(~local),receipt.artifacts)
                error('csr:t25:Receipt','Completed stage artifacts are missing, extra or changed.');
            end
            % MAT snapshots stay local and are optional on transported evidence.
            % Any retained local snapshot must still have its original bytes.
            for k=find(local(:))'
                if isempty(receipt.local_artifacts)
                    error('csr:t25:Receipt','An undeclared local MAT snapshot was added.');
                end
                found=find(strcmp({receipt.local_artifacts.path},actual(k).path));
                if numel(found)~=1 || ~isequal(actual(k),receipt.local_artifacts(found))
                    error('csr:t25:Receipt','A retained local MAT snapshot changed.');
                end
            end
            started=jsondecode(fileread(fullfile(stage,'start.json')));
            if ~strcmp(started.phase,phase) || ~strcmp(started.status,'started') || ...
                    ~isequal(started.identity,identity)
                error('csr:t25:Receipt','The stage start identity does not match its completed receipt.');
            end
        end

        function summary = testResults(results,expectedNames,testFiles)
            required={'Name','Passed','Failed','Incomplete','DurationSeconds'};
            if ~istable(results) || ~all(ismember(required,results.Properties.VariableNames))
                error('csr:t25:TestIdentity','A complete test-result table is required.');
            end
            actual=string(results.Name); expected=string(expectedNames);
            if isempty(actual) || numel(unique(actual))~=height(results) || ...
                    ~isequal(sort(actual(:)),sort(expected(:)))
                error('csr:t25:TestIdentity','Full portable test names differ from the frozen candidate.');
            end
            flags=[double(results.Passed),double(results.Failed),double(results.Incomplete)];
            if any(~ismember(flags(:),[0 1])) || ...
                    any(~isfinite(results.DurationSeconds) | results.DurationSeconds<0)
                error('csr:t25:Tests','Test result flags or durations are invalid.');
            end
            if nargin<3
                classes=regexprep(cellstr(expected(:)),'/.*$','');
                testFiles=strcat('tests/',unique(classes),'.m');
            end
            summary=struct('Schema','csr-tranche25-portable-tests-summary-v1', ...
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
                error('csr:t25:Path','Expected a canonical contained relative file path.');
            end
            root=csr.validation.Artifacts.canonicalPath(root);
            path=csr.validation.Artifacts.canonicalPath(fullfile(root,relative));
            if ~startsWith(path,[root filesep]) || ~isfile(path)
                error('csr:t25:Path','Required artifact is missing or outside the installation: %s.',relative);
            end
        end

        function writeText(path,value)
            fid=fopen(path,'w');
            if fid<0, error('csr:t25:Output','Cannot write %s.',path); end
            cleanup=onCleanup(@()fclose(fid)); %#ok<NASGU>
            fprintf(fid,'%s\n',value);
        end
    end
    methods (Static, Access=private)
        function phase(value)
            if ~ischar(value) || ~ismember(value,{'tests','s131','s132'})
                error('csr:t25:Stage','Only tests, s131 and s132 have reusable receipts.');
            end
        end
    end
end
