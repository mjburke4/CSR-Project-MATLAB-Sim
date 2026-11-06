function bytes=controlWireBytes(kind,payload,destinationCount,profile)
%CONTROLWIREBYTES Isolated native compatibility-control envelope sizing.
% The source REQUEST builder puts its operation/sequence in a compatibility
% header. Payload.Bytes retains the equivalent ARL receiver semantics only.
% Generic real ARL sections (including seven-byte REQUESTs) remain raw bytes.
bytes=csr.nwk.controlWireBytes(kind,payload,destinationCount,profile);
if strcmpi(kind,'NEIGHBOR_CHECK') && isfield(payload,'Subtype') && ...
        strcmpi(payload.Subtype,'no_path')
    % TargetId is compatibility metadata, removed with CsrHelloHeader.
    % No raw NoPath body is produced by the portable NWK control builder.
    bytes=11+5;
end
if ~isfield(payload,'WireRepresentation'), return; end
representation=payload.WireRepresentation;
assert((ischar(representation) && isrow(representation)) || ...
    (isstring(representation) && isscalar(representation) && ~ismissing(representation)), ...
    'autocase:RequestRepresentation','Wire representation must be a nonmissing scalar name.');
representation=char(representation);
assert(strcmp(representation,'legacy_request_header') && strcmp(kind,'ROUTING') && ...
    destinationCount==1, 'autocase:RequestRepresentation', ...
    'Only a generated unicast ROUTING REQUEST can use the compact representation.');
section=reshape(double(payload.Bytes),1,[]);
assert(numel(section)==7 && isequal(section(5:7),[0 1 3]), ...
    'autocase:RequestRepresentation', ...
    'Compact REQUEST requires a single complete section containing only opcode REQUEST.');
bytes=11+5; % Native Routes fixed envelope plus Group16 security, zero raw body.
end
