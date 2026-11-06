classdef BoundedJsonlWriter < handle
    % Exact jsonencode + UTF8 LF, exclusive file creation and fail-before-write.
    properties (SetAccess=private)
        Bytes=0
        FooterBytes=0
        TemporaryBytes=0
        Closed=false
    end
    properties (Access=private)
        File=[]
        Temporary=[]
        Path
        Pool
        PayloadLimit
        FooterLimit
        TemporaryLimit
        FooterStarted=false
        RecordLimits
    end
    methods
        function obj=BoundedJsonlWriter(path,pool,payload,footer,temporary,recordLimits)
            assert(nargin==6,'diag2490:Plan','Explicit record bounds required.');
            BoundedJsonlWriter.validateLimits(recordLimits);obj.RecordLimits=recordLimits;
            assert(isa(pool,'DiagnosticByteBudget'),'diag2490:Pool','Shared byte budget required.');
            obj.Path=pool.assertPath(path);obj.Pool=pool;
            assert(~System.IO.File.Exists(obj.Path),'diag2490:Exists','Preserve existing diagnostic evidence.');
            pool.reserve(obj.Path,payload,footer,temporary);
            obj.PayloadLimit=payload;obj.FooterLimit=footer;obj.TemporaryLimit=temporary;
            obj.File=System.IO.FileStream(obj.Path,System.IO.FileMode.CreateNew,System.IO.FileAccess.Write,System.IO.FileShare.Read);
        end
        function n=write(obj,value)
            bytes=BoundedJsonlWriter.encodeBounded(value,obj.RecordLimits);
            n=obj.writeBytes(bytes);
        end
        function n=writeBytes(obj,bytes)
            assert(isa(bytes,'uint8')&&(isvector(bytes)||isempty(bytes)),'diag2490:Bytes','Explicit byte vector required.');
            assert(~obj.Closed && ~obj.FooterStarted,'diag2490:Closed','Writer closed or footer begun.');
            n=numel(bytes);assert(obj.Bytes+n<=obj.PayloadLimit,'diag2490:PayloadCap','Payload reservation exceeded before write.');
            obj.File.Write(bytes,0,n);obj.Bytes=obj.Bytes+n;
        end
        function writeFooter(obj,bytes)
            assert(isa(bytes,'uint8') && (isvector(bytes)||isempty(bytes)) && ~obj.Closed,'diag2490:Closed','Footer writer closed.');
            n=numel(bytes);assert(obj.FooterBytes+n<=obj.FooterLimit,'diag2490:FooterCap','Footer reservation exceeded before write.');
            obj.FooterStarted=true;obj.File.Write(bytes,0,n);obj.FooterBytes=obj.FooterBytes+n;
        end
        function writeTemporary(obj,bytes)
            assert(isa(bytes,'uint8') && (isvector(bytes)||isempty(bytes)) && ~obj.Closed,'diag2490:Closed','Temporary writer closed.');
            assert(obj.TemporaryLimit>0,'diag2490:TemporaryCap','No temporary allocation declared.');
            n=numel(bytes);assert(obj.TemporaryBytes+n<=obj.TemporaryLimit,'diag2490:TemporaryCap','Temporary reservation exceeded before write.');
            if isempty(obj.Temporary)
                path=obj.Pool.assertPath([obj.Path '.tmp']);
                obj.Temporary=System.IO.FileStream(path,System.IO.FileMode.CreateNew,System.IO.FileAccess.Write,System.IO.FileShare.Read);
            end
            obj.Temporary.Write(bytes,0,n);obj.TemporaryBytes=obj.TemporaryBytes+n;
        end
        function close(obj)
            if obj.Closed,return;end
            obj.Closed=true;
            if ~isempty(obj.File),obj.File.Dispose();obj.File=[];end
            if ~isempty(obj.Temporary),obj.Temporary.Dispose();obj.Temporary=[];end
        end
        function delete(obj),obj.close();end
    end
    methods (Static)
        function validateLimits(limits)
            keys={'MaxNodes','MaxTextUnits','MaxDepth','MaxEncodedBytes'};
            for k=1:numel(keys)
                assert(isfield(limits,keys{k}),'diag2490:Plan','Missing reviewed record bound.');
                v=limits.(keys{k});assert(isnumeric(v)&&isreal(v)&&isscalar(v)&&isfinite(v)&&v==fix(v)&&v>0&&v<=flintmax,'diag2490:Plan','Invalid record bound.');
            end
            assert(limits.MaxDepth<=64,'diag2490:Depth','Decoder implementation depth ceiling.');
        end
        function bytes=encodeBounded(value,limits)
            BoundedJsonlWriter.validateLimits(limits);
            nodes=0;text=0;
            visit(value,0);
            bytes=[unicode2native(jsonencode(value),'UTF-8') uint8(10)];
            assert(numel(bytes)<=limits.MaxEncodedBytes,'diag2490:RecordBytes','Encoded row exceeds reviewed bound.');
            function visit(v,depth)
                assert(depth<=limits.MaxDepth,'diag2490:Depth','Record nesting bound.');
                nodes=nodes+1+numel(v);assert(nodes<=limits.MaxNodes,'diag2490:Nodes','Record element bound before encoding.');
                if ischar(v)
                    text=text+numel(v);
                elseif isstring(v)
                    lengths=strlength(v);lengths(ismissing(v))=0;text=text+sum(lengths(:));
                elseif isstruct(v)
                    names=fieldnames(v);text=text+sum(cellfun(@numel,names))*numel(v);
                    assert(text<=limits.MaxTextUnits,'diag2490:Text','Record text bound.');
                    for a=1:numel(v),for b=1:numel(names),visit(v(a).(names{b}),depth+1);end;end
                elseif iscell(v)
                    for a=1:numel(v),visit(v{a},depth+1);end
                else
                    assert(isnumeric(v)||islogical(v),'diag2490:Type','Unsupported JSON diagnostic value type.');
                end
                assert(text<=limits.MaxTextUnits,'diag2490:Text','Record text bound before encoding.');
            end
        end
    end
end
