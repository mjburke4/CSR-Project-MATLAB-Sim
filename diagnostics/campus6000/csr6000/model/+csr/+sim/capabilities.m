function result = capabilities()
%CAPABILITIES Report the runtime that actually executes this function.
%   Symbol discovery does not certify toolbox licensing or adapter execution.
%   The portable scheduler is the implemented default backend. CSR's protocol
%   core has no dependency on an R2026a-only wireless class.

result = struct();
result.Runtime = 'MATLAB';
result.Version = version;
result.Release = version('-release');
result.HasWirelessNetworkSimulator = hasSymbol('wirelessNetworkSimulator');
result.HasWnetNode = hasSymbol('wnet.Node');
result.HasWirelessPacket = hasSymbol('wirelessPacket');
result.DefaultBackend = 'portable';
result.WirelessAdapterImplemented = true;
result.WirelessAdapterScope = 'Optional R2026a wireless-clock candidate; runtime validation pending';
result.NativePacketTransportIntegrated = false;
result.ProbeScope = 'Symbol discovery only; licenses and execution are not validated.';
end

function available = hasSymbol(name)
available = exist(name, 'class') == 8 || ...
    ismember(exist(name, 'file'), [2, 3, 6]) || exist(name, 'builtin') == 5;
end
