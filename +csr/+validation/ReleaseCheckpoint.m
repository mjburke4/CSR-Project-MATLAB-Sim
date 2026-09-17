classdef ReleaseCheckpoint
    %RELEASECHECKPOINT Immutable completed stages for the campus release gate.
    % Receipts resume completed evidence, never a partially executed simulator.
    methods (Static)
        function options = options(given)
            options=struct('Phase','all');
            if nargin==0, return; end
            if ~isstruct(given) || ~isscalar(given) || ...
                    ~all(ismember(fieldnames(given),{'Phase'}))
                error('csr:t17:Options','Only the scalar Phase option is supported.');
            end
            if isfield(given,'Phase'), options.Phase=given.Phase; end
            if isstring(options.Phase) && isscalar(options.Phase)
                options.Phase=char(options.Phase);
            end
            if ~ischar(options.Phase) || ~isrow(options.Phase) || ...
                    ~ismember(options.Phase,{'all','tests','campus','finalize'})
                error('csr:t17:Options','Phase must be all, tests, campus or finalize.');
            end
        end

        function validatePlan(plan,item,catalogHash)
            required={'schema','case_id','storage_key','ns3_source_commit', ...
                'duration_s','seed','timing_policy','observer_enabled','stimuli_changed', ...
                'phy_ecc_changed','default_policy_changed','post_horizon_drain', ...
                'full_portable_regression','native_tests_included','scenario_file', ...
                'scenario_sha256','catalog_sha256','reference_directory'};
            if ~isstruct(plan) || ~isscalar(plan) || ~all(isfield(plan,required))
                error('csr:t17:Plan','The campus release plan is incomplete.');
            end
            if ~strcmp(plan.schema,'csr-tranche17-campus-release-plan-v1') || ...
                    ~strcmp(plan.case_id,'campus_multihop_6000') || ...
                    ~strcmp(plan.storage_key,'c') || ...
                    ~strcmp(plan.ns3_source_commit,'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b') || ...
                    ~isequal(plan.duration_s,6000) || ~isequal(plan.seed,128) || ...
                    ~strcmp(plan.timing_policy,'continuous') || ...
                    ~isequal(plan.observer_enabled,false) || ~isequal(plan.stimuli_changed,false) || ...
                    ~isequal(plan.phy_ecc_changed,false) || ~isequal(plan.default_policy_changed,false) || ...
                    ~isequal(plan.post_horizon_drain,false) || ...
                    ~isequal(plan.full_portable_regression,true) || ...
                    ~isequal(plan.native_tests_included,false) || ...
                    ~strcmp(plan.catalog_sha256,catalogHash) || ...
                    ~strcmp(plan.scenario_file,item.ScenarioFile) || ...
                    ~strcmp(plan.scenario_sha256,item.ScenarioSHA256) || ...
                    ~strcmp(plan.reference_directory,item.ReferenceDirectory) || ...
                    ~strcmp(item.CaseId,plan.case_id) || ...
                    item.DurationSeconds~=6000 || item.Seed~=128
                error('csr:t17:Plan','The unchanged campus workload or release scope differs from the plan.');
            end
            c=item.Config;
            if ~strcmp(c.Backend,'portable') || ~strcmp(c.Stack,'network') || ...
                    ~strcmp(c.Channel.Model,'csr-phy') || c.DurationSeconds~=6000 || c.Seed~=128 || ...
                    ~strcmp(c.ApplicationGenerator,'historical-opnet-gated') || c.ApplicationFlowLimit~=0 || ...
                    ~c.Trace.Enabled || c.Trace.MaxRecords~=1500000 || ...
                    c.Trace.MaxPhyRecords~=1500000 || ...
                    c.Trace.MaxApplicationAdmissionRecords~=100000 || c.MaxEvents~=12000000
                error('csr:t17:Plan','The campus backend, application generator or original evidence budgets changed.');
            end
        end

        function [identity,candidate] = identity(root)
            root=csr.validation.Artifacts.canonicalPath(root);
            candidateFile='evidence/tranche-17-candidate.json';
            path=fullfile(root,candidateFile);
            candidate=jsondecode(fileread(path));
            if ~strcmp(candidate.Schema,'csr-tranche-17-candidate-v1') || ...
                    ~strcmp(candidate.SourceCommit,'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b') || ...
                    ~isequal(cellstr(string(candidate.SourceFilesExcludedPaths)),{candidateFile})
                error('csr:t17:Candidate','Unexpected candidate identity or excluded source paths.');
            end
            sources=csr.validation.Artifacts.sourceSnapshot(root);
            bound=sources(~strcmp({sources.path},candidateFile));
            if ~isequal(bound,candidate.SourceFiles)
                error('csr:t17:Candidate','Candidate source membership or hashes changed.');
            end
            baselinePath=csr.validation.ReleaseCheckpoint.checkedPath(root,candidate.BaselineSourceSnapshot);
            if ~strcmp(csr.validation.Artifacts.sha256(baselinePath),candidate.BaseSourceSnapshotSHA256)
                error('csr:t17:Baseline','The immutable Tranche 16 source snapshot changed.');
            end
            baseline=jsondecode(fileread(baselinePath));
            if numel(baseline)~=304 || sum(endsWith({baseline.path},'.m'))~=155 || ...
                    numel(unique({baseline.path}))~=304
                error('csr:t17:Baseline','Expected all 304 Tranche 16 sources, including 155 MATLAB files.');
            end
            for k=1:numel(baseline)
                found=find(strcmp({sources.path},baseline(k).path));
                if numel(found)~=1 || ~strcmp(sources(found).sha256,baseline(k).sha256)
                    error('csr:t17:Baseline','Previous source changed: %s.',baseline(k).path);
                end
            end
            if ~strcmp(candidate.Plan,'scenarios/t17/plan.json') || ...
                    ~strcmp(csr.validation.Artifacts.sha256(fullfile(root,candidate.Plan)),candidate.PlanSHA256)
                error('csr:t17:Plan','The frozen release plan changed.');
            end
            listing=dir(fullfile(root,'tests','*.m'));
            testFiles=strcat('tests/',{listing.name});
            if ~isequal(sort(string(testFiles(:))),sort(string(candidate.TestFiles(:)))) || ...
                    numel(unique(string(candidate.ExpectedTestNames)))~=numel(candidate.ExpectedTestNames) || ...
                    isempty(candidate.ExpectedTestNames)
                error('csr:t17:Tests','The full top-level portable test inventory changed.');
            end
            names=cellstr(string(candidate.ReferenceFiles));
            if isempty(names) || numel(unique(names))~=numel(names) || ...
                    (isfield(candidate,'ReferenceRoots') && ~isempty(candidate.ReferenceRoots))
                error('csr:t17:Reference','Explicit, distinct reference files are required.');
            end
            references=repmat(struct('path','','sha256','','bytes',0),numel(names),1);
            for k=1:numel(names)
                actual=csr.validation.ReleaseCheckpoint.checkedPath(root,names{k});
                details=dir(actual);
                references(k)=struct('path',names{k}, ...
                    'sha256',csr.validation.Artifacts.sha256(actual),'bytes',details.bytes);
            end
            [~,order]=sort({references.path}); references=references(order);
            if ~isfield(candidate,'ReferenceFileInventory') || ...
                    ~isequal(references,candidate.ReferenceFileInventory)
                error('csr:t17:Reference','Frozen reference membership, hashes or sizes changed.');
            end
            identity=struct('CandidateSHA256',csr.validation.Artifacts.sha256(path), ...
                'SourceCommit',candidate.SourceCommit,'Runtime',csr.sim.capabilities(), ...
                'SourceFiles',sources,'ReferenceFiles',references);
        end

        function [receipt,reused] = begin(directory,phase,identity)
            csr.validation.ReleaseCheckpoint.phase(phase);
            stage=fullfile(directory,phase);
            if isfolder(stage)
                receipt=csr.validation.ReleaseCheckpoint.verify(directory,phase,identity);
                reused=true;
                return
            end
            [ok,message]=mkdir(stage);
            if ~ok, error('csr:t17:Output','Cannot create stage: %s.',message); end
            csr.validation.Artifacts.writeJson(fullfile(stage,'start.json'), ...
                struct('schema','csr-tranche17-stage-start-v1','phase',phase, ...
                'status','started','started_utc',csr.validation.Artifacts.utcNow(), ...
                'identity',identity));
            receipt=struct(); reused=false;
        end

        function receipt = seal(directory,phase,identity,summary)
            csr.validation.ReleaseCheckpoint.phase(phase);
            stage=fullfile(directory,phase);
            if ~isfile(fullfile(stage,'start.json')) || ...
                    isfile(fullfile(stage,'receipt.json')) || isfile(fullfile(stage,'receipt.sha256'))
                error('csr:t17:Stage','A fresh started stage is required for sealing.');
            end
            started=jsondecode(fileread(fullfile(stage,'start.json')));
            if ~isequal(started.identity,identity) || ~strcmp(started.phase,phase)
                error('csr:t17:Stage','Stage identity changed before completion.');
            end
            inventory=csr.validation.Artifacts.fileInventory(stage);
            local=endsWith({inventory.path},'.mat');
            receipt=struct('schema','csr-tranche17-stage-receipt-v1','phase',phase, ...
                'status','completed','completed_utc',csr.validation.Artifacts.utcNow(), ...
                'identity',identity,'summary',summary, ...
                'SourceCommit',identity.SourceCommit, ...
                'SourceFilesStableDuringRun',true,'ReferenceFilesStableDuringRun',true, ...
                'SourceFilesFinal',identity.SourceFiles,'ReferenceFilesFinal',identity.ReferenceFiles, ...
                'artifacts',inventory(~local), ...
                'local_artifacts',inventory(local));
            receiptPath=fullfile(stage,'receipt.json');
            csr.validation.Artifacts.writeJson(receiptPath,receipt);
            csr.validation.ReleaseCheckpoint.writeText(fullfile(stage,'receipt.sha256'), ...
                csr.validation.Artifacts.sha256(receiptPath));
        end

        function receipt = verify(directory,phase,identity)
            csr.validation.ReleaseCheckpoint.phase(phase);
            stage=fullfile(directory,phase);
            receiptPath=fullfile(stage,'receipt.json');
            checksumPath=fullfile(stage,'receipt.sha256');
            if ~isfile(receiptPath) || ~isfile(checksumPath)
                error('csr:t17:IncompleteStage', ...
                    'Stage %s is missing or partial. Preserve it and restart in a new output directory.',phase);
            end
            if ~strcmp(strtrim(fileread(checksumPath)),csr.validation.Artifacts.sha256(receiptPath))
                error('csr:t17:Receipt','The %s receipt checksum changed.',phase);
            end
            receipt=jsondecode(fileread(receiptPath));
            if ~strcmp(receipt.schema,'csr-tranche17-stage-receipt-v1') || ...
                    ~strcmp(receipt.status,'completed') || ~strcmp(receipt.phase,phase) || ...
                    ~isequal(receipt.identity,identity) || ...
                    ~strcmp(receipt.SourceCommit,identity.SourceCommit) || ...
                    ~isequal(receipt.SourceFilesStableDuringRun,true) || ...
                    ~isequal(receipt.ReferenceFilesStableDuringRun,true) || ...
                    ~isequal(receipt.SourceFilesFinal,identity.SourceFiles) || ...
                    ~isequal(receipt.ReferenceFilesFinal,identity.ReferenceFiles)
                error('csr:t17:Receipt','The completed stage has a different candidate/source/reference identity.');
            end
            actual=csr.validation.Artifacts.fileInventory(stage,{'receipt.json','receipt.sha256'});
            local=endsWith({actual.path},'.mat');
            if ~isequal(actual(~local),receipt.artifacts)
                error('csr:t17:Receipt','Completed stage artifacts are missing, extra or changed.');
            end
            % MAT snapshots stay local and are optional on transported evidence.
            % Any retained local snapshot must still have its original bytes.
            for k=find(local(:))'
                if isempty(receipt.local_artifacts)
                    error('csr:t17:Receipt','An undeclared local MAT snapshot was added.');
                end
                found=find(strcmp({receipt.local_artifacts.path},actual(k).path));
                if numel(found)~=1 || ~isequal(actual(k),receipt.local_artifacts(found))
                    error('csr:t17:Receipt','A retained local MAT snapshot changed.');
                end
            end
            started=jsondecode(fileread(fullfile(stage,'start.json')));
            if ~strcmp(started.phase,phase) || ~strcmp(started.status,'started') || ...
                    ~isequal(started.identity,identity)
                error('csr:t17:Receipt','The stage start identity does not match its completed receipt.');
            end
        end

        function summary = testResults(results,expectedNames,testFiles)
            required={'Name','Passed','Failed','Incomplete','DurationSeconds'};
            if ~istable(results) || ~all(ismember(required,results.Properties.VariableNames))
                error('csr:t17:TestIdentity','A complete test-result table is required.');
            end
            actual=string(results.Name); expected=string(expectedNames);
            if isempty(actual) || numel(unique(actual))~=height(results) || ...
                    ~isequal(sort(actual(:)),sort(expected(:)))
                error('csr:t17:TestIdentity','Full portable test names differ from the frozen candidate.');
            end
            flags=[double(results.Passed),double(results.Failed),double(results.Incomplete)];
            if any(~ismember(flags(:),[0 1])) || ...
                    any(~isfinite(results.DurationSeconds) | results.DurationSeconds<0)
                error('csr:t17:Tests','Test result flags or durations are invalid.');
            end
            if nargin<3
                classes=regexprep(cellstr(expected(:)),'/.*$','');
                testFiles=strcat('tests/',unique(classes),'.m');
            end
            summary=struct('Schema','csr-tranche17-portable-tests-summary-v1', ...
                'TestsExecuted',true,'TestsPassed',all(results.Passed & ~results.Failed & ~results.Incomplete), ...
                'TestCount',height(results),'PassedTests',sum(results.Passed), ...
                'FailedTests',sum(results.Failed),'IncompleteTests',sum(results.Incomplete), ...
                'TestResultsFile','results.csv','TestFiles',{cellstr(string(testFiles(:)))}, ...
                'ExpectedTestNames',{cellstr(expected(:))});
        end

        function path = checkedPath(root,relative)
            if isstring(relative) && isscalar(relative), relative=char(relative); end
            if ~ischar(relative) || ~isrow(relative) || isempty(relative) || ...
                    contains(relative,'\') || startsWith(relative,'/') || ...
                    ~isempty(regexp(relative,'(^|/)\.\.?(/|$)|^[A-Za-z]:','once'))
                error('csr:t17:Path','Expected a canonical contained relative file path.');
            end
            root=csr.validation.Artifacts.canonicalPath(root);
            path=csr.validation.Artifacts.canonicalPath(fullfile(root,relative));
            if ~startsWith(path,[root filesep]) || ~isfile(path)
                error('csr:t17:Path','Required artifact is missing or outside the installation: %s.',relative);
            end
        end

        function writeText(path,value)
            fid=fopen(path,'w');
            if fid<0, error('csr:t17:Output','Cannot write %s.',path); end
            cleanup=onCleanup(@()fclose(fid)); %#ok<NASGU>
            fprintf(fid,'%s\n',value);
        end
    end
    methods (Static, Access=private)
        function phase(value)
            if ~ischar(value) || ~ismember(value,{'tests','campus'})
                error('csr:t17:Stage','Only tests and campus have reusable receipts.');
            end
        end
    end
end
