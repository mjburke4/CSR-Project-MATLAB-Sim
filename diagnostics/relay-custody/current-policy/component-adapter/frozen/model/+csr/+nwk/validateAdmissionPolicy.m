function policy=validateAdmissionPolicy(options,implementation)
%VALIDATEADMISSIONPOLICY Supported implementation declaration, not authority.
if nargin<2, implementation=''; end
if ~isstruct(options) || ~isscalar(options)
    error('csr:nwk:InvalidConfig','Expected scalar NWK options.');
end
policy='portable-bounded';
if isfield(options,'AdmissionPolicy'), policy=options.AdmissionPolicy; end
if ~ischar(policy) || ~isrow(policy) || ~any(strcmp(policy,{'portable-bounded','opnet-reference'}))
    error('csr:nwk:InvalidConfig','Unknown NWK admission policy.');
end
if ~ischar(implementation) || (~isempty(implementation) && ~isrow(implementation))
    error('csr:nwk:InvalidConfig','Invalid NWK implementation declaration.');
end
if strcmp(policy,'opnet-reference') && ~strcmp(implementation,'ac.DiscoveryMembershipNwk')
    error('csr:nwk:UnsupportedAdmissionPolicy','Reference policy requires supported DiscoveryMembershipNwk.');
end
end
