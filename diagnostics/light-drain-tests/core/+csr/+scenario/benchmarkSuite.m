function [cases,plan] = benchmarkSuite(options)
%BENCHMARKSUITE Hash-bound campus and focused ns-3 benchmark configurations.
% Canonical timing, offered attempts, geometry and profiles are fixed by the
% catalog. Cases selects recorded names; it never shortens an OPNET run.
if nargin<1, options=struct(); end
if ~isstruct(options) || ~isscalar(options) || ...
        ~all(ismember(fieldnames(options),{'Cases'}))
    error('csr:benchmark:Options','Benchmark options accept only Cases.');
end
selected = {};
if isfield(options,'Cases'), selected=options.Cases; end
if ischar(selected), selected={selected}; end
if isstring(selected), selected=cellstr(selected); end
if ~iscell(selected) || ~all(cellfun(@(x)ischar(x)&&isrow(x)&&~isempty(x),selected)) || ...
        numel(unique(selected))~=numel(selected)
    error('csr:benchmark:Options','Cases must contain distinct catalog names.');
end
root=fileparts(fileparts(fileparts(mfilename('fullpath'))));
catalogPath=fullfile(root,'scenarios','benchmarks','catalog.json');
catalog=jsondecode(fileread(catalogPath));
pin='486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b';
if ~strcmp(catalog.schema,'csr-benchmark-catalog-v1') || ...
        ~strcmp(catalog.ns3_source_commit,pin) || isempty(catalog.cases)
    error('csr:benchmark:Catalog','Unsupported benchmark catalog or source pin.');
end
entries=catalog.cases;
% JSON objects have case-specific provenance fields. MATLAB decodes such
% heterogeneous arrays as cells, while a uniform selection may be a struct.
if isstruct(entries), entries=num2cell(entries); end
if ~iscell(entries) || ~all(cellfun(@(x)isstruct(x)&&isscalar(x),entries))
    error('csr:benchmark:Catalog','Benchmark cases must be JSON objects.');
end
names=cellfun(@(x)x.case_id,entries,'UniformOutput',false);
defaults=cellfun(@(x)isequal(x.default,true),entries);
if numel(unique(names))~=numel(names) || ~all(ismember(selected,names))
    error('csr:benchmark:Selection','Unknown, deferred or duplicate benchmark case.');
end
if isempty(selected), selected=names(defaults); end
if isempty(selected), error('csr:benchmark:Selection','At least one benchmark is required.'); end
template=struct('CaseId','','Scenario','','ScenarioFile','','ScenarioSHA256','', ...
    'ProfileId','','DurationSeconds',0,'Seed',0,'BucketWidthSeconds',0, ...
    'SourceKind','','OpnetAvailable',false,'ReferenceDirectory','','Config',struct());
cases=repmat(template,numel(selected),1);
index=0;
for k=1:numel(entries)
    entry=entries{k};
    if ~ismember(entry.case_id,selected), continue; end
    if isempty(regexp(entry.case_id,'^[a-zA-Z0-9_-]+$','once')) || ...
            isempty(regexp(entry.scenario_file,'^scenarios/benchmarks/[a-zA-Z0-9_-]+\.csv$','once')) || ...
            isempty(regexp(entry.reference_directory,'^evidence/tranche-7-ns3-reference/[a-zA-Z0-9_-]+$','once'))
        error('csr:benchmark:Catalog','Benchmark names and paths must be canonical relative paths.');
    end
    input=fullfile(root,entry.scenario_file);
    digest=csr.validation.Artifacts.sha256(input);
    if ~strcmp(digest,entry.scenario_sha256)
        error('csr:benchmark:InputChanged','Benchmark input hash differs from its catalog: %s.',entry.case_id);
    end
    config=csr.scenario.importNs3(input,struct('HistoricalBenchmark',true, ...
        'FlowLimit',entry.flow_limit,'Backend','portable'));
    if ~strcmp(config.Name,entry.scenario) || config.DurationSeconds~=entry.duration_s || ...
            config.Seed~=entry.seed || ...
            ~strcmp(config.SharedScenario.HopSecurityProfile,entry.profile_id)
        error('csr:benchmark:Catalog','Imported identity differs from the recorded benchmark.');
    end
    validateattributes(entry.bucket_width_s,{'numeric'},{'scalar','real','finite','positive'});
    count=config.DurationSeconds/entry.bucket_width_s;
    if abs(count-round(count))>1e-10
        error('csr:benchmark:Catalog','Benchmark duration must contain complete aggregate buckets.');
    end
    % Explicit evidence budgets, not altered traffic or a physical shortcut.
    % The 1.71-million-attempt campus case retains complete admission counters
    % and a bounded admission trace; full protocol/PHY trace omissions fail.
    config.Trace.MaxRecords=1500000;
    config.Trace.MaxPhyRecords=1500000;
    config.Trace.MaxApplicationAdmissionRecords=100000;
    config.MaxEvents=12000000;
    config.Benchmark=struct('Schema','csr-matlab-benchmark-v1', ...
        'CaseId',entry.case_id,'SourceKind',entry.source_kind, ...
        'ProfileId',entry.profile_id,'OpnetAvailable',entry.opnet_available, ...
        'BucketWidthSeconds',entry.bucket_width_s,'ReferenceDirectory',entry.reference_directory, ...
        'CatalogSHA256',csr.validation.Artifacts.sha256(catalogPath), ...
        'HistoricalOutcomeEquivalenceEstablished',false);
    config=csr.scenario.validate(config);
    index=index+1;
    cases(index)=struct('CaseId',entry.case_id,'Scenario',entry.scenario, ...
        'ScenarioFile',entry.scenario_file,'ScenarioSHA256',digest, ...
        'ProfileId',entry.profile_id,'DurationSeconds',entry.duration_s, ...
        'Seed',entry.seed,'BucketWidthSeconds',entry.bucket_width_s, ...
        'SourceKind',entry.source_kind,'OpnetAvailable',entry.opnet_available, ...
        'ReferenceDirectory',entry.reference_directory,'Config',config);
end
plan=struct('Schema','csr-matlab-benchmark-plan-v1','Status','planned-not-executed', ...
    'SourceCommit',pin,'CatalogSHA256',csr.validation.Artifacts.sha256(catalogPath), ...
    'CaseCount',numel(cases),'TotalSimulatedSeconds',sum([cases.DurationSeconds]), ...
    'Cases',rmfield(cases,'Config'),'DefaultCases',{names(defaults)}, ...
    'ApplicationCountsAreAdmittedOutcomes',true, ...
    'NumericalParityEstablished',false,'DeferredCases',{catalog.deferred_cases});
end
