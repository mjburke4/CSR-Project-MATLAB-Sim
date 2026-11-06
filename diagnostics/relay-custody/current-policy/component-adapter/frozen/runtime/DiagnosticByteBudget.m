classdef DiagnosticByteBudget < handle
    % Single-owner diagnostic file reservations; no model/event/RNG effects.
    properties (SetAccess=private)
        Root
        Capacity
        Charged
        Cluster
    end
    properties (Access=private)
        Claims
    end
    methods
        function obj=DiagnosticByteBudget(root,capacity,existingCharged,cluster)
            assert(ispc,'diag2490:Platform','Windows allocation plan required.');
            assert(all(cellfun(@(v)isnumeric(v)&&isreal(v)&&isscalar(v),{capacity,existingCharged,cluster})),'diag2490:Plan','Scalar numeric byte plan required.');
            values=[capacity existingCharged cluster];
            assert(all(isfinite(values)&values==fix(values)&values>=0),'diag2490:Plan','Integer byte plan required.');
            assert(capacity<=2^31 && existingCharged<=capacity && cluster>0 && cluster<=16*1024^2,'diag2490:Plan','Invalid explicit allocation plan.');
            obj.Root=char(System.IO.Path.GetFullPath(char(root)));
            assert(System.IO.Directory.Exists(obj.Root),'diag2490:Root','Root must exist.');
            obj.Capacity=capacity;obj.Charged=existingCharged;obj.Cluster=cluster;
            obj.Claims=containers.Map('KeyType','char','ValueType','logical');
            obj.assertPath(fullfile(obj.Root,'ownership_check'));
        end
        function path=assertPath(obj,path)
            path=char(System.IO.Path.GetFullPath(char(path)));
            assert(startsWith(lower(path),[lower(obj.Root) filesep]),'diag2490:Path','Path outside owned root.');
            node=path;
            while ~isempty(node)
                if System.IO.File.Exists(node)||System.IO.Directory.Exists(node)
                    attr=uint32(System.Convert.ToInt32(System.IO.File.GetAttributes(node)));
                    assert(bitand(attr,uint32(1024))==0,'diag2490:Reparse','Reparse paths forbidden.');
                end
                parent=fileparts(node);if strcmp(parent,node),break;end;node=parent;
            end
        end
        function charged=reserve(obj,path,payload,footer,temporary)
            path=obj.assertPath(path);assert(all(cellfun(@(v)isnumeric(v)&&isreal(v)&&isscalar(v),{payload,footer,temporary})),'diag2490:Plan','Scalar numeric writer allocation required.');values=[payload footer temporary];
            assert(all(isfinite(values)&values==fix(values)&values>=0&values<=obj.Capacity),'diag2490:Plan','Explicit bounded writer allocation required.');
            keys={lower(path)};if temporary>0,keys{end+1}=lower([path '.tmp']);end
            for k=1:numel(keys),assert(~isKey(obj.Claims,keys{k}),'diag2490:Duplicate','Path already reserved.');end
            charged=ceil((payload+footer)/obj.Cluster)*obj.Cluster+ceil(temporary/obj.Cluster)*obj.Cluster;
            assert(obj.Charged+charged<=obj.Capacity,'diag2490:AggregateCap','Aggregate reservation would exceed allocation.');
            obj.Charged=obj.Charged+charged;
            for k=1:numel(keys),obj.Claims(keys{k})=true;end
        end
    end
end
