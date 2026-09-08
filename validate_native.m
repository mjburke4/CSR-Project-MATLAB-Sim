function validate_native(outputDirectory)
%VALIDATE_NATIVE Explicit R2026a optional tests; never silently fall back.
% Run after portable run_validation in a fresh R2026a MATLAB session with
% Wireless Network Toolbox. Native simulator initialization resets its global
% instance. This validates clock integration and a separate packet probe.
root = fileparts(mfilename('fullpath'));
addpath(root);
if nargin == 0
    outputDirectory = fullfile(root, 'results', 'native_validation');
end
if ~exist(outputDirectory, 'dir'), mkdir(outputDirectory); end
diary(fullfile(outputDirectory, 'native_validation.log'));
cleanup = onCleanup(@() diary('off')); %#ok<NASGU>
runtime = csr.sim.capabilities();
disp(runtime);
status = struct('Status', 'started', 'MatlabVersion', version, ...
    'MatlabRelease', version('-release'), ...
    'IntegratedBackend', 'wireless-clock', ...
    'IntegratedRFTransport', 'CSR SignalEngine / controlled fixture channel', ...
    'PacketTransportProbe', 'Separate controlled native lifecycle', ...
    'NativeCSRPacketTransportIntegrated', false);
try
    csr.sim.native.requireAvailable();
    testResults = runtests(fullfile(root, 'tests', 'native'));
    disp(testResults);
    save(fullfile(outputDirectory, 'native_test_results.mat'), ...
        'testResults', 'runtime');
    summary = table({testResults.Name}', [testResults.Passed]', ...
        [testResults.Failed]', [testResults.Incomplete]', ...
        [testResults.Duration]', 'VariableNames', ...
        {'Name', 'Passed', 'Failed', 'Incomplete', 'DurationSeconds'});
    writetable(summary, fullfile(outputDirectory, 'native_test_results.csv'));
    assertSuccess(testResults);
    probe = csr.sim.native.probePacketTransport();
    save(fullfile(outputDirectory, 'native_packet_probe.mat'), 'probe');
    status.Status = 'passed';
catch exception
    status.Status = 'failed';
    status.ExceptionIdentifier = exception.identifier;
    status.ExceptionMessage = exception.message;
    status.ExceptionReport = getReport(exception, 'extended', 'hyperlinks', 'off');
    writeStatus();
    rethrow(exception);
end
writeStatus();
fprintf(['Native clock and separate packet lifecycle validation passed on ' ...
    '%s (%s).\n'], version, version('-release'));

    function writeStatus()
        save(fullfile(outputDirectory, 'native_status.mat'), 'status');
        file = fopen(fullfile(outputDirectory, 'native_status.json'), 'w');
        if file < 0
            error('csr:sim:NativeReportFile', 'Cannot write native status report.');
        end
        closeFile = onCleanup(@() fclose(file)); %#ok<NASGU>
        fprintf(file, '%s\n', jsonencode(status, 'PrettyPrint', true));
    end
end
