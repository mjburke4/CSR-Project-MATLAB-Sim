function report = probeWirelessScheduler()
%PROBEWIRELESSSCHEDULER Observe callback-only wireless simulator behavior.
%   REPORT = csr.sim.probeWirelessScheduler() tests a simulator with no
%   native nodes. It checks initial scheduling, a callback-scheduled event,
%   and cancellation. It does not select or implement a CSR backend.
%
%   Run in a fresh MATLAB session or before creating any wireless scenario:
%   wirelessNetworkSimulator.init resets an existing simulator instance.
%
%   REPORT.status is 'supported', 'failed', or 'unavailable'. 'supported'
%   means this probe succeeded on this installation, not a documented
%   guarantee of zero-node operation or validation of a CSR adapter.
%
%   API references verified 2026-09-08:
%   https://www.mathworks.com/help/wireless-network/ref/wirelessnetworksimulator.html
%   https://www.mathworks.com/help/wireless-network/ref/wirelessnetworksimulator.scheduleaction.html
%   https://www.mathworks.com/help/wireless-network/ref/wirelessnetworksimulator.cancelaction.html

report = struct();
report.status = 'unavailable';
report.matlabRelease = version('-release');
report.matlabVersion = version;
report.description = 'Wireless network simulator was not found on the MATLAB path.';
report.events = struct('actionID', {}, 'timeSeconds', {}, 'name', {});
report.exception = struct('identifier', '', 'message', '', 'report', '');
report.documentationVerified = '2026-09-08';
report.documentation = { ...
    'https://www.mathworks.com/help/wireless-network/ref/wirelessnetworksimulator.html', ...
    'https://www.mathworks.com/help/wireless-network/ref/wirelessnetworksimulator.scheduleaction.html', ...
    'https://www.mathworks.com/help/wireless-network/ref/wirelessnetworksimulator.cancelaction.html'};

if exist('wirelessNetworkSimulator', 'class') ~= 8 && ...
        exist('wirelessNetworkSimulator', 'file') == 0
    return;
end

try
    simulator = wirelessNetworkSimulator.init;
    scheduleAction(simulator, @observe, struct('name', 'initial'), 0.125);
    cancelledID = scheduleAction(simulator, @observe, ...
        struct('name', 'cancelled'), 0.375);
    cancelAction(simulator, cancelledID);
    run(simulator, 0.5);

    expectedTimes = [0.125 0.25];
    expectedNames = {'initial', 'follow-up'};
    if numel(report.events) ~= 2 || ...
            ~isequal({report.events.name}, expectedNames) || ...
            any(abs([report.events.timeSeconds] - expectedTimes) > 8 * eps(1))
        error('csr:sim:WirelessSchedulerProbeMismatch', ...
            ['Expected callbacks at 0.125 s and 0.25 s, with the 0.375 s ' ...
            'callback cancelled. Actual observations are in report.events.']);
    end

    report.status = 'supported';
    report.description = ['Zero-node scheduling, callback-created scheduling, ' ...
        'and cancellation passed this installation-specific probe. ' ...
        'This is not CSR adapter validation.'];
catch exception
    report.status = 'failed';
    report.description = ['The installed simulator did not complete the ' ...
        'zero-node scheduling probe successfully.'];
    report.exception.identifier = exception.identifier;
    report.exception.message = exception.message;
    report.exception.report = getReport(exception, 'extended', 'hyperlinks', 'off');
end

    function observe(actionID, userData)
        report.events(end + 1) = struct('actionID', actionID, ...
            'timeSeconds', simulator.CurrentTime, 'name', userData.name);
        if strcmp(userData.name, 'initial')
            scheduleAction(simulator, @observe, struct('name', 'follow-up'), 0.25);
        end
    end
end
