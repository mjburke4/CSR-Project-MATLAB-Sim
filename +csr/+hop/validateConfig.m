function config = validateConfig(config)
%VALIDATECONFIG Normalize MAC/HOP options using each layer's authoritative defaults.
% Tunable limits retain source defaults; scenario tests may deliberately lower
% limits or retry counts. Unknown options fail rather than silently doing nothing.
config.Mac = merge(config,'Mac',csr.mac.Layer.defaults());
config.Hop = merge(config,'Hop',csr.hop.Layer.defaults());
mac = config.Mac;
mac.SlotProfile = csr.mac.SlotSelection.normalizeProfile(mac.SlotProfile);
integerPositive = {'DataQueueLimit','AckQueueLimit','AckTransmissions','MaxConcatSegments'};
integerZero = {'ActiveNodes','ReportedActiveNodes','SlotReduction'};
positive = {'SlotSeconds','WakeCycleSeconds','SearchSeconds'};
nonnegative = {'HoldoffSeconds','BootSeconds','PostTxBaseSeconds', ...
    'PostTxPerNodeSeconds','PostTxGuardSeconds'};
for name = integerPositive, mac.(name{1}) = numeric(mac.(name{1}),1,flintmax,true,name{1}); end
for name = integerZero, mac.(name{1}) = numeric(mac.(name{1}),0,flintmax,true,name{1}); end
for name = positive, mac.(name{1}) = numeric(mac.(name{1}),realmin,flintmax,false,name{1}); end
for name = nonnegative, mac.(name{1}) = numeric(mac.(name{1}),0,flintmax,false,name{1}); end
mac.ReservationSlotOverride = numeric(mac.ReservationSlotOverride,-1,255,true,'ReservationSlotOverride');
for name = {'DutyCycleEnabled','ConcatenationEnabled'}
    value = mac.(name{1});
    if ~(islogical(value) || isnumeric(value)) || ~isscalar(value) || ...
            ~isreal(value) || ~ismember(value,[0 1])
        error('csr:hop:InvalidConfig','%s must be a scalar logical or 0/1.',name{1});
    end
    mac.(name{1}) = logical(value);
end
if mac.BootSeconds + mac.SearchSeconds > mac.WakeCycleSeconds
    error('csr:hop:InvalidConfig','BootSeconds + SearchSeconds must fit within WakeCycleSeconds.');
end
hop = config.Hop;
for name = {'ResendSeconds','DackHoldSeconds','TicSeconds'}
    hop.(name{1}) = numeric(hop.(name{1}),realmin,flintmax,false,name{1});
end
for name = {'MaxResends','PendingThreshold','FlowThresholdMax','NsdpLimit'}
    hop.(name{1}) = numeric(hop.(name{1}),0,flintmax,true,name{1});
end
hop.ResendQueueLimit = numeric(hop.ResendQueueLimit,1,flintmax,true,'ResendQueueLimit');
config.Mac = mac;
config.Hop = hop;
end

function normalized = merge(config, name, normalized)
if ~isfield(config,name), return; end
supplied = config.(name);
if ~isstruct(supplied) || ~isscalar(supplied)
    error('csr:hop:InvalidConfig','%s configuration must be a scalar struct.',name);
end
fields = fieldnames(supplied);
for k = 1:numel(fields)
    field = fields{k};
    if ~isfield(normalized,field)
        error('csr:hop:InvalidConfig','Unknown %s option: %s.',name,field);
    end
    normalized.(field) = supplied.(field);
end
end

function value = numeric(value,lower,upper,integer,label)
if ~isnumeric(value) || ~isscalar(value) || ~isreal(value) || ...
        ~isfinite(value) || value < lower || value > upper || (integer && fix(value)~=value)
    error('csr:hop:InvalidConfig','Invalid numeric MAC/HOP option: %s.',label);
end
value = double(value);
end
