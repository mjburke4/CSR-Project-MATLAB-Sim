function [row,manifest] = exportResearchCase(result,directory,root,snapshot,scenarioPath)
%EXPORTRESEARCHCASE Completed case, complete traces and independently hashable inputs.
if nargin < 5, scenarioPath = ''; end
row = csr.analysis.researchSummary(result);
csr.validation.Artifacts.checkSnapshot(root,snapshot);
if isfolder(directory)
    error('csr:validation:ExistingCase','Case directory already exists: %s.',directory);
end
csr.analysis.exportResults(result,directory);
writetable(struct2table(row,'AsArray',true),fullfile(directory,'research_summary.csv'));
manifest = struct('schema','csr-matlab-research-case-v1','status','completed', ...
    'execution_completed',true,'source_files_stable',true, ...
    'completed_utc',csr.validation.Artifacts.utcNow(), ...
    'matlab_version',version,'matlab_release',version('-release'), ...
    'ns3_source_commit',result.Metadata.SourceCommit,'scenario',result.Config.Name, ...
    'seed',result.Config.Seed,'duration_s',result.Config.DurationSeconds, ...
    'application_profile',result.Config.ApplicationProfile, ...
    'structural_checks_passed',true,'data_drained',row.DataDrained, ...
    'numerical_parity_established',false,'source_files',snapshot, ...
    'comparison_scope','Research result; cross-simulator comparison has not run.');
if ~isempty(scenarioPath)
    if ~isfield(result.Config,'SharedScenario')
        error('csr:validation:SharedScenario','A canonical input requires imported SharedScenario provenance.');
    end
    shared = result.Config.SharedScenario;
    digest = csr.validation.Artifacts.sha256(scenarioPath);
    if ~strcmp(digest,shared.SourceSHA256)
        error('csr:validation:ScenarioChanged','Canonical scenario changed after import.');
    end
    [ok,message] = copyfile(scenarioPath,fullfile(directory,'scenario.csv'));
    if ~ok, error('csr:validation:CopyScenario','Cannot archive canonical input: %s.',message); end
    manifest.scenario_sha256 = digest;
    manifest.flow_limit = shared.FlowLimit;
    manifest.application_profile = shared.ApplicationProfile;
    manifest.mac_profile = shared.MacProfile;
    manifest.hop_security_profile = shared.HopSecurityProfile;
    manifest.run_options = shared.RunOptions;
    manifest.comparison_scope = ['Identical canonical input and explicit settings; ' ...
        'RNG sequences and full protocol timing are not identical across simulators.'];
end
files = csr.validation.Artifacts.fileInventory(directory);
% CSV counts bind complete row sets in addition to raw-byte hashes.
for k = 1:numel(files)
    files(k).row_count = [];
    switch files(k).path
        case {'protocol_trace.csv','trace.csv'}, files(k).row_count = height(result.ProtocolTrace);
        case 'phy_trace.csv', files(k).row_count = height(result.PhyTrace);
        case 'nodes.csv', files(k).row_count = height(result.NodeStatistics);
        case 'mac_nodes.csv', files(k).row_count = height(result.NodeMacStatistics);
        case 'hop_nodes.csv', files(k).row_count = height(result.NodeHopStatistics);
        case 'nwk_nodes.csv', files(k).row_count = height(result.NodeNwkStatistics);
        case 'routes.csv', files(k).row_count = height(result.Routes);
        case 'neighbors.csv', files(k).row_count = height(result.Neighbors);
        case 'application_admission_statistics.csv'
            files(k).row_count = height(result.ApplicationAdmissionStatistics);
        case 'application_admission_trace.csv'
            files(k).row_count = height(result.ApplicationAdmissionTrace);
        case 'research_summary.csv', files(k).row_count = 1;
        case 'scenario.csv'
            % The shared CSV parser rejects embedded newlines in fields.
            lines = regexp(fileread(fullfile(directory,'scenario.csv')),'\r\n|\n|\r','split');
            files(k).row_count = sum(~cellfun(@isempty,lines))-1;
    end
end
% MAT objects stay on the execution machine. The comparison inventory must
% contain only files actually carried in tranche4_evidence.zip.
local = endsWith({files.path},'.mat');
manifest.local_files = files(local);
manifest.files = files(~local);
csr.validation.Artifacts.checkSnapshot(root,snapshot);
csr.validation.Artifacts.writeJson(fullfile(directory,'case_manifest.json'),manifest);
end
