function [cases, plan] = researchSweep(options)
%RESEARCHSWEEP Bounded, controlled experiments over synthetic Tranche 4 layouts.
% [cases, plan] = csr.scenario.researchSweep(options) constructs configurations;
% it does not execute simulations or certify delivery. Cases are a column
% struct array with CaseId, Experiment, Parameter, Value, Seed and Config.
% See docs/tranche-5-research-sweeps.md for controls, limits and interpretation.
if nargin < 1, options = struct(); end
options = normalizeOptions(options);
countPerSeed = double(options.IncludeLongRun);
if any(strcmp(options.Experiments,'offered_load'))
    countPerSeed = countPerSeed+numel(options.LoadMultipliers);
end
if any(strcmp(options.Experiments,'recovery_freshness'))
    countPerSeed = countPerSeed+numel(options.FreshnessTimeoutSeconds);
end
caseCount = countPerSeed*numel(options.Seeds);
if caseCount > 200
    error('csr:scenario:SweepCaseLimit','A sweep may contain at most 200 cases.');
end

template = struct('CaseId','','Experiment','','Parameter','','Value',0, ...
    'Seed',0,'Config',struct());
cases = repmat(template,caseCount,1);
index = 0;
for experiment = options.Experiments
    switch experiment{1}
        case 'offered_load'
            values = options.LoadMultipliers;
            fixture = 'hidden_node';
            parameter = 'LoadMultiplier';
            token = 'x';
            hypothesis = ['Compare hidden-source contention as generation intervals shorten; ' ...
                'delivery, collisions and latency are measured outcomes.'];
        case 'recovery_freshness'
            values = options.FreshnessTimeoutSeconds;
            fixture = 'route_recovery';
            parameter = 'FreshnessTimeoutSeconds';
            token = 's';
            hypothesis = ['Compare freshness expiry and route churn under the same administrative ' ...
                'receive blackout and explicit rediscovery requests.'];
    end
    for value = values
        for seed = options.Seeds
            config = csr.scenario.researchNetwork(fixture,struct('Seed',seed));
            if strcmp(experiment{1},'offered_load')
                for flow = 1:numel(config.Traffic)
                    % Preserve the first and final generation instants exactly
                    % in the configured arithmetic: (N'-1)*dt'=(N-1)*dt.
                    config.Traffic(flow).PacketCount = ...
                        1+(config.Traffic(flow).PacketCount-1)*value;
                    config.Traffic(flow).IntervalSeconds = ...
                        config.Traffic(flow).IntervalSeconds/value;
                end
            else
                config.Nwk.Neighbor.FreshnessTimeoutSeconds = value;
            end
            config.Trace.MaxRecords = 250000;
            config.Trace.MaxPhyRecords = 250000;
            index = index+1;
            cases(index) = makeCase(config,experiment{1},parameter,value, ...
                token,seed,hypothesis);
        end
    end
end
if options.IncludeLongRun
    for seed = options.Seeds
        config = csr.scenario.researchNetwork('long_run_6000',struct('Seed',seed));
        % These are finite evidence capacities, not a completeness guarantee.
        % Keep traffic, topology, protocol settings and MaxEvents unchanged.
        config.Trace.MaxRecords = 1000000;
        config.Trace.MaxPhyRecords = 500000;
        index = index+1;
        cases(index) = makeCase(config,'long_run','DurationSeconds',6000,'s',seed, ...
            ['Measure bounded-storage, accounting and finite-stop custody over the ' ...
            'synthetic 6000-second line workload; no campus parity claim.']);
    end
end
totalSeconds = 0;
totalApplications = 0;
for k = 1:numel(cases)
    totalSeconds = totalSeconds+cases(k).Config.DurationSeconds;
    totalApplications = totalApplications+sum([cases(k).Config.Traffic.PacketCount]);
end
plan = struct('Schema','csr-matlab-research-sweep-plan-v1', ...
    'Status','planned-not-executed', ...
    'Description','Controlled synthetic offered-load and recovery-freshness experiments over repeated seeds.', ...
    'Options',options,'CaseCount',caseCount,'MaxCaseCount',200, ...
    'LongRunCaseCount',double(options.IncludeLongRun)*numel(options.Seeds), ...
    'TotalSimulatedSeconds',totalSeconds,'TotalApplications',totalApplications, ...
    'Ordering','Requested experiment order, requested parameter order, requested seed order; long runs last.', ...
    'SeedInterpretation',['Paired seed identities reproduce each configuration; changed event order ' ...
        'can consume random draws differently across parameter values.'], ...
    'TracePolicy',['Short cases: 250000 protocol and 250000 PHY records. Long cases: ' ...
        '1000000 protocol and 500000 PHY records. Omitted counters must be checked.'], ...
    'DeliveryCertified',false,'NumericalParityCertified',false);
plan.Cases = rmfield(cases,'Config');
end

function row = makeCase(config,experiment,parameter,value,token,seed,hypothesis)
id = sprintf('%s_%s%d_seed%.0f',experiment,token,value,seed);
config.Name = id;
config.Research.Sweep = struct('Schema','csr-matlab-research-sweep-case-v1', ...
    'Experiment',experiment,'Parameter',parameter,'Value',value,'Seed',seed, ...
    'BaselineFixture',config.Research.FixtureName,'Hypothesis',hypothesis, ...
    'ControlledComparison',true,'OutcomeCertified',false);
% All traffic finishes inside the existing warmup/drain contract. Compute the
% metadata from the final configuration instead of relying on stale fields.
config.Research.WarmupSeconds = min([config.Traffic.StartSeconds]);
config.Research.TrafficEndSeconds = max([config.Traffic.StartSeconds]+ ...
    ([config.Traffic.PacketCount]-1).*[config.Traffic.IntervalSeconds]);
config.Research.DrainSeconds = config.DurationSeconds-config.Research.TrafficEndSeconds;
config = csr.scenario.validate(config);
row = struct('CaseId',id,'Experiment',experiment,'Parameter',parameter, ...
    'Value',value,'Seed',seed,'Config',config);
end

function out = normalizeOptions(given)
out = struct('Seeds',[128 129 130], ...
    'Experiments',{{'offered_load','recovery_freshness'}}, ...
    'IncludeLongRun',false,'LoadMultipliers',[1 2 4], ...
    'FreshnessTimeoutSeconds',[60 180 300]);
if ~isstruct(given) || ~isscalar(given)
    error('csr:scenario:SweepOptions','Sweep options must be a scalar struct.');
end
unknown = setdiff(fieldnames(given),fieldnames(out));
if ~isempty(unknown)
    error('csr:scenario:SweepOptions','Unknown sweep option: %s.',unknown{1});
end
for name = fieldnames(given)'
    out.(name{1}) = given.(name{1});
end
if ~islogical(out.IncludeLongRun) || ~isscalar(out.IncludeLongRun)
    error('csr:scenario:SweepOptions','IncludeLongRun must be a logical scalar.');
end
out.Seeds = integerChoices(out.Seeds,0,2^32-1,20,'Seeds');
out.LoadMultipliers = integerChoices(out.LoadMultipliers,1,8,8,'LoadMultipliers');
out.FreshnessTimeoutSeconds = integerChoices( ...
    out.FreshnessTimeoutSeconds,30,600,8,'FreshnessTimeoutSeconds');
names = out.Experiments;
if ischar(names) && isrow(names), names = {names};
elseif isstring(names) && (isvector(names) || isempty(names)), names = cellstr(names); end
if ~iscell(names) || (~isvector(names) && ~isempty(names)) || numel(names) > 2
    error('csr:scenario:SweepOptions','Experiments must contain distinct supported names.');
end
names = reshape(names,1,[]);
for k = 1:numel(names)
    name = names{k};
    if isstring(name) && isscalar(name), name = char(name); end
    if ~ischar(name) || ~isrow(name) || ...
            ~any(strcmp(name,{'offered_load','recovery_freshness'}))
        error('csr:scenario:SweepOptions','Unsupported sweep experiment.');
    end
    names{k} = name;
end
if numel(unique(names)) ~= numel(names) || (isempty(names) && ~out.IncludeLongRun)
    error('csr:scenario:SweepOptions', ...
        'Experiments must be distinct and nonempty unless IncludeLongRun is true.');
end
out.Experiments = names;
end

function values = integerChoices(values,minimum,maximum,maxCount,label)
if ~isnumeric(values) || ~isreal(values) || ~isvector(values) || ...
        issparse(values) || isempty(values) || numel(values) > maxCount
    error('csr:scenario:SweepOptions', ...
        '%s must contain between one and %d distinct integers.',label,maxCount);
end
values = reshape(double(values),1,[]);
if any(~isfinite(values) | values < minimum | values > maximum | fix(values) ~= values) || ...
        numel(unique(values)) ~= numel(values)
    error('csr:scenario:SweepOptions','%s contains duplicate, noninteger or out-of-range values.',label);
end
end
