function [arrival,record] = transportArrival(tx,duration,propagation,mode)
%TRANSPORTARRIVAL Compare two explicit local validation transport policies.
% This helper does not alter the global clock, MAC completion event, input
% tapes or startup phase. Integer nanoseconds are added before conversion
% back to scheduler seconds. Continuous mode retains the original ordering.
if nargin~=4 || ~((ischar(mode) && isrow(mode)) || ...
        (isstring(mode) && isscalar(mode) && ~ismissing(mode))) || ...
        ~any(strcmp(mode,{'continuous','nanoseconds'}))
    error('csr:validation:TransportMode','Mode must be continuous or nanoseconds.');
end
values = {tx,duration,propagation}; rounded = zeros(1,3);
for k=1:3
    value = values{k};
    if ~isa(value,'double') || ~isscalar(value) || ~isreal(value) || ...
            ~isfinite(value) || value<0 || value>flintmax/1e9
        error('csr:validation:TransportTime','Times must be finite nonnegative scalar doubles within the exact nanosecond bound.');
    end
    rounded(k) = round(value*1e9);
    if rounded(k)>flintmax
        error('csr:validation:TransportTime','Rounded component exceeds the exact integer bound.');
    end
end
sumNs = 0;
for k=1:3
    if rounded(k)>flintmax-sumNs
        error('csr:validation:TransportTime','Rounded component sum exceeds the exact integer bound.');
    end
    sumNs = sumNs+rounded(k);
end
continuous = tx+duration+propagation;
nanoseconds = sumNs/1e9;
arrival = continuous;
if strcmp(mode,'nanoseconds'), arrival = nanoseconds; end
if arrival<tx
    error('csr:validation:TransportPast','Local conversion would schedule arrival before the actual transmit time.');
end
delta = arrival-continuous;
record = struct('tx_seconds',sprintf('%.17g',tx),'tx_hex',num2hex(tx), ...
    'duration_seconds',sprintf('%.17g',duration),'duration_hex',num2hex(duration), ...
    'propagation_seconds',sprintf('%.17g',propagation),'propagation_hex',num2hex(propagation), ...
    'continuous_seconds',sprintf('%.17g',continuous),'continuous_hex',num2hex(continuous), ...
    'nanoseconds_seconds',sprintf('%.17g',nanoseconds),'nanoseconds_hex',num2hex(nanoseconds), ...
    'arrival_seconds',sprintf('%.17g',arrival),'arrival_hex',num2hex(arrival), ...
    'delta_seconds',sprintf('%.17g',delta),'delta_hex',num2hex(delta), ...
    'tx_ns',uint64(rounded(1)),'duration_ns',uint64(rounded(2)), ...
    'propagation_ns',uint64(rounded(3)),'sum_ns',uint64(sumNs));
end
