function [cost, detail] = linkCost(pathlossDb, failures, options)
%LINKCOST Recovered CSR link_calc cost, rate and transmit power selection.
% Path loss is measured from received traffic. This calculation is policy,
% not a replacement for the CSR PHY's receive/error calculation.
if nargin < 2, failures = 0; end
if nargin < 3, options = struct(); end
config = struct('RxS0BaseLevelDbm',-115,'LinkMarginDb',10, ...
    'MinSpeedKbps',8,'MaxSpeedKbps',128,'MinPowerDbm',0, ...
    'MaxPowerDbm',30,'LowPowerDbm',14);
if ~isstruct(options) || ~isscalar(options)
    error('csr:nwk:InvalidConfig','Link cost options must be a scalar struct.');
end
names = fieldnames(options);
for k = 1:numel(names)
    if ~isfield(config,names{k})
        error('csr:nwk:InvalidConfig','Unknown link cost option: %s.',names{k});
    end
    value = options.(names{k});
    validateattributes(value,{'numeric'},{'scalar','real','finite'});
    config.(names{k}) = double(value);
end
rates = [8 16 32 64 128 500 1000];
offsets = [0 3 6 9 12 20 23];
if ~ismember(config.MinSpeedKbps,rates) || ~ismember(config.MaxSpeedKbps,rates) || ...
        config.MinSpeedKbps > config.MaxSpeedKbps || config.MinPowerDbm > config.MaxPowerDbm
    error('csr:nwk:InvalidConfig','Invalid link rate or transmit power limits.');
end
validateattributes(pathlossDb,{'numeric'},{'scalar','real','finite','nonnegative'});
validateattributes(failures,{'numeric'},{'scalar','real','finite','integer','nonnegative'});
tx0 = config.RxS0BaseLevelDbm + config.LinkMarginDb + double(pathlossDb);
txm = tx0 + offsets(rates == config.MinSpeedKbps);
margin = config.MaxPowerDbm - tx0;
eligible = rates(offsets <= margin);
if isempty(eligible), speed = config.MinSpeedKbps;
else, speed = eligible(end); end
speed = min(config.MaxSpeedKbps,max(config.MinSpeedKbps,speed));
requiredPower = tx0 + offsets(rates == speed);
power = min(config.MaxPowerDbm,max(config.MinPowerDbm,requiredPower));
if power <= config.LowPowerDbm, distance = 75;
else, distance = floor(10^((power-config.LowPowerDbm)/40)*100); end
cost = floor(distance*100/speed);
if config.MaxPowerDbm-txm-3*double(failures) < 0, cost = cost*2; end
if config.MaxPowerDbm-power-3*double(failures) > 3, cost = floor(cost/2); end
cost = max(1,cost);
detail = struct('RateKeyKbps',speed,'TxPowerDbm',ceil(power), ...
    'EstimatedDistance',distance,'SpeedMarginDb',config.MaxPowerDbm-requiredPower, ...
    'TotalMarginDb',config.MaxPowerDbm-txm,'Config',config);
end
