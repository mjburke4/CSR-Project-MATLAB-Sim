function report = run_slot_vectors(root, outputDir)
%RUN_SLOT_VECTORS Compare production MATLAB selection with native execution.
% No random-stream matching is assumed. Both sides receive the same explicit
% initial integer draw and neighbor counters. The native implementation keeps
% its production probe loop; only its RNG call is replaced in a test overlay.
if nargin < 1 || isempty(root)
    root = fileparts(fileparts(fileparts(mfilename('fullpath'))));
end
if nargin < 2 || isempty(outputDir)
    outputDir = fullfile(root, 'out_mac', 'slot_vectors');
end
if ~isfolder(outputDir), mkdir(outputDir); end
folder = fileparts(mfilename('fullpath'));
vectors = readStrings(fullfile(folder, 'vectors.csv'));
reference = readStrings(fullfile(folder, 'native_reference.csv'));
if height(vectors) ~= height(reference) || any(vectors.case_id ~= reference.case_id)
    error('csr:diagnostic:SlotVectorBinding', 'Native reference IDs do not match vector IDs.');
end
profile = 'hist-2014-next-tslot-modulo-probe';
count = height(vectors);
actualClass = strings(count,1); actualSlot = nan(count,1);
actualActive = nan(count,1); actualRange = nan(count,1);
passed = false(count,1); messages = strings(count,1);
for index = 1:count
    row = vectors(index,:); native = reference(index,:);
    try
        local = str2double(row.local); reported = str2double(row.reported);
        reduction = str2double(row.reduction);
        actualActive(index) = csr.mac.SlotSelection.activeNodes(profile,local,reported);
        actualRange(index) = csr.mac.SlotSelection.slotRange(profile,actualActive(index),reduction);
        if row.kind == "range"
            actualClass(index) = "range";
        else
            counters = [];
            if ~ismissing(row.counters) && strlength(row.counters)>0
                counters = str2double(split(row.counters,';')).';
            end
            actualSlot(index) = csr.mac.SlotSelection.historicalSlot( ...
                profile,actualRange(index),counters,str2double(row.initial_draw));
            actualClass(index) = "slot";
        end
    catch exception
        if strcmp(exception.identifier,'csr:mac:HistoricalProbeExhausted')
            actualClass(index) = "probe_exhausted";
        else
            actualClass(index) = "unexpected_error";
            messages(index) = string(exception.identifier) + ": " + string(exception.message);
        end
    end
    passed(index) = actualClass(index) == native.status && native.fixture_pass == "true";
    if actualClass(index) == "slot" || actualClass(index) == "range"
        passed(index) = passed(index) && actualActive(index)==str2double(native.active_nodes) ...
            && actualRange(index)==str2double(native.range);
    end
    if actualClass(index) == "slot"
        passed(index) = passed(index) && actualSlot(index)==str2double(native.slot);
    end
    if ~passed(index) && strlength(messages(index))==0
        messages(index) = "Native and MATLAB result differ; inspect this row.";
    end
end
result = table(vectors.case_id,vectors.kind,reference.status,actualClass, ...
    str2double(reference.slot),actualSlot,str2double(reference.active_nodes),actualActive, ...
    str2double(reference.range),actualRange,passed,messages, ...
    'VariableNames',{'CaseId','Kind','NativeClass','MatlabClass','NativeSlot','MatlabSlot', ...
    'NativeActiveNodes','MatlabActiveNodes','NativeRange','MatlabRange','Pass','Message'});
writetable(result,fullfile(outputDir,'slot_vector_results.csv'));
report = struct('completed',true,'pass',all(passed),'cases',count, ...
    'passed',sum(passed),'failed',sum(~passed), ...
    'selection_cases',sum(vectors.kind=="select"),'range_cases',sum(vectors.kind=="range"), ...
    'probe_exhaustion_cases',sum(reference.status=="probe_exhausted"), ...
    'failed_case_ids',{cellstr(vectors.case_id(~passed))}, ...
    'profile',profile,'matlab_version',version, ...
    'scope','Historical slot selection and range rules; does not claim scheduling or network parity.');
fid = fopen(fullfile(outputDir,'slot_vector_summary.json'),'w');
if fid<0, error('csr:diagnostic:SlotVectorOutput','Cannot write slot summary.'); end
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid,'%s\n',jsonencode(report,'PrettyPrint',true));
fprintf('Slot vectors: %d/%d passed.\n',sum(passed),count);
end

function result = readStrings(path)
options = detectImportOptions(path,'TextType','string');
options = setvartype(options,options.VariableNames,'string');
result = readtable(path,options);
end
