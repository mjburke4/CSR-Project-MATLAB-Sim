function bytes = controlWireBytes(kind,payload,destinationCount,securityProfile)
%CONTROLWIREBYTES Modeled production-behavioral NWK control envelope size.
% Matches frozen csr-opnet-envelope.h, not compatibility-header serialization.
% This is byte accounting only. It does not authenticate or encrypt controls.
if nargin < 2 || isempty(payload), payload = struct(); end
if nargin < 3, destinationCount = 1; end
if nargin < 4, securityProfile = 'behavioral-production-pairwise16-size-only'; end
if ~ischar(securityProfile) || ...
        ~strcmp(securityProfile,'behavioral-production-pairwise16-size-only')
    error('csr:nwk:InvalidSecurityProfile','Unsupported control security profile.');
end
validateattributes(destinationCount,{'numeric'}, ...
    {'scalar','real','finite','integer','>=',1,'<=',10});
if ~isstruct(payload) || ~isscalar(payload)
    error('csr:nwk:InvalidControl','Control payload must be a scalar struct.');
end
kind = upper(char(kind));
switch kind
    case 'DISCOVER'
        bytes = 12+7; % Standalone Hello model plus GroupEstablish record.
    case 'KEY_REQUEST'
        bytes = 11+7; % Standalone Routes model plus KeyRequest record.
    case 'KEY_UPDATE'
        bytes = 11+51; % Standalone Routes model plus KeyUpdate record.
    case 'NEIGHBOR_CHECK'
        bytes = 11+5; % Standalone Routes model plus Pairwise16 record.
        if strcmpi(fieldOr(payload,'Subtype',''),'no_path'), bytes = bytes+3; end
    case 'ROUTING'
        if ~isfield(payload,'Bytes') || ~isnumeric(payload.Bytes) || ...
                (~isvector(payload.Bytes) && ~isempty(payload.Bytes)) || ...
                any(~isfinite(payload.Bytes(:))) || any(payload.Bytes(:)<0 | ...
                payload.Bytes(:)>255 | fix(payload.Bytes(:))~=payload.Bytes(:))
            error('csr:nwk:InvalidControl','ROUTING requires a byte-vector payload.');
        end
        bytes = 11+5+numel(payload.Bytes); % Routes, Group16 and raw ARL section.
    case {'SNMP_START','SNMP_DONE'}
        nodes = fieldOr(payload,'Nodes',[]);
        if ~isnumeric(nodes) || (~isvector(nodes) && ~isempty(nodes)) || ...
                numel(nodes)>10 || any(~isfinite(nodes(:))) || ...
                any(nodes(:)<0 | nodes(:)>=16777215 | fix(nodes(:))~=nodes(:))
            error('csr:nwk:InvalidControl','SNMP Nodes must be a numeric vector.');
        end
        % Source annotation uses the fixed br_SNMP model, not compatibility
        % metadata (including the scan node list) as extra on-air bytes.
        bytes = 17+8+6; % Mac -> Hop -> Snmp.
    otherwise
        error('csr:nwk:InvalidControl','Unknown control kind.');
end
% Destination/sequence lists belong to the compatibility CsrHeader removed
% before source envelope sizing. Validate the group bound without charging
% invented per-target or common MAC/HOP bytes to standalone control models.
end

function value = fieldOr(record,name,fallback)
value = fallback;
if isfield(record,name), value = record.(name); end
end
