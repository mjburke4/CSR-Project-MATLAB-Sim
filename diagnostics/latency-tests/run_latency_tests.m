function report=run_latency_tests(mode, outputRoot)
%RUN_LATENCY_TESTS Start with run_latency_tests; optional mode 'hop', 'load' or 'all'.
% Uses an isolated byte-verified T27 core included in this diagnostic kit.
root=fileparts(mfilename('fullpath'));
if nargin<1 || isempty(mode), mode='focused'; end
assert(ismember(string(mode),["focused","hop","load","all"]),'Mode must be focused, hop, load or all');
oldPath=path; cleanup=onCleanup(@()path(oldPath)); %#ok<NASGU>
core=fullfile(root,'core'); addpath(core,'-begin');
addpath(fullfile(root,'mac'),fullfile(root,'replay'),fullfile(root,'load'));
if nargin<2 || isempty(outputRoot)
 [~,token]=fileparts(tempname); outputRoot=fullfile(root,['out_' char(mode) '_' token]);
end
outputRoot=csr.validation.Artifacts.canonicalPath(outputRoot);
assert(~isfolder(outputRoot)&&~isfile(outputRoot),'Use a fresh output path');
assert(~isfile([outputRoot '.zip']),'Evidence archive already exists');
assert(strcmp(csr.validation.Artifacts.canonicalPath(which('csr.mac.Layer')), ...
 csr.validation.Artifacts.canonicalPath(fullfile(core,'+csr','+mac','Layer.m'))),'Another csr package is active');
package=jsondecode(fileread(fullfile(root,'PACKAGE_FILES.json')));
for k=1:numel(package)
 assert(strcmp(csr.validation.Artifacts.sha256(fullfile(root,package(k).path)),package(k).sha256), ...
  'Test package changed: %s',package(k).path);
end
expected=jsondecode(fileread(fullfile(root,'accepted-core.json')));
for k=1:numel(expected)
 assert(strcmp(csr.validation.Artifacts.sha256(fullfile(core,expected(k).path)),expected(k).sha256), ...
  'Accepted core mismatch: %s',expected(k).path);
end
mkdir(outputRoot);
report=struct('status','running','mode',char(mode),'version',version, ...
 'release',version('-release'),'matlab_executed',true,'native_executed',false, ...
 'production_changes',false,'parity_established',false,'output',outputRoot);
failure=[];
try
 if ismember(string(mode),["focused","all"])
  fprintf('Running 11 controlled MAC cases.\n');
  report.mac=run_mac_tests(core,fullfile(outputRoot,'mac'));
 end
 if ismember(string(mode),["focused","hop","all"])
  fprintf('Running 4 controlled MAC/HOP cases.\n');
  diary(fullfile(outputRoot,'replay.log'));
  replay=run_hop_replay(fullfile(root,'replay','inputs.csv'),fullfile(outputRoot,'hop.csv'));
  diary('off');
  cases=readtable(fullfile(root,'replay','inputs.csv'),'TextType','string');
  checks=check_hop_results(replay,cases);
  writetable(checks,fullfile(outputRoot,'hop-checks.csv'));
  report.hop_cases=height(cases); report.hop_checks_passed=all(checks.pass);
  assert(report.hop_checks_passed,'HOP checks failed; inspect hop-checks.csv.');
 end
 if ismember(string(mode),["load","all"])
  report.load=run_load_matlab(core,fullfile(outputRoot,'load'));
 end
 report.status='completed-native-comparison-pending';
catch err
 diary('off'); report.status='failed';report.error=err.message;failure=err;
end
csr.validation.Artifacts.writeJson(fullfile(outputRoot,'metadata.json'),report);
csr.validation.Artifacts.writeJson(fullfile(outputRoot,'files.json'), ...
 csr.validation.Artifacts.fileInventory(outputRoot,{'files.json'}));
zip([outputRoot '.zip'],{'*'},outputRoot);
fprintf('Return this evidence archive: %s.zip\n',outputRoot);
if ~isempty(failure), rethrow(failure); end
end
