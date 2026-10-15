classdef TypedTraceBuffer < handle
    % STAGED ONLY. Same logical cap, lazy 4096-row scalar pages.
    properties (SetAccess=private)
        Count=0
        Capacity
        Template
    end
    properties (Access=private)
        Names
        Columns
        IsChar
        PageRows=4096
        EmptyTable
    end
    methods
        function obj=TypedTraceBuffer(template,capacity)
            validateattributes(capacity,{'double'},{'scalar','real','integer','finite','nonnegative','<=',flintmax});
            assert(isstruct(template)&&isscalar(template),'csr:trace:Template','Scalar template required.');
            obj.Template=template;obj.Capacity=capacity;obj.Names=fieldnames(template);
            assert(~isempty(obj.Names),'csr:trace:Template','Nonempty template required.');
            obj.Columns=cell(numel(obj.Names),1);obj.IsChar=false(numel(obj.Names),1);
            for k=1:numel(obj.Names)
                v=template.(obj.Names{k});obj.validate(v,k);obj.IsChar(k)=ischar(v);
                if obj.IsChar(k),obj.Columns{k}=csr.sim.PagedUtf16Column(capacity);else,obj.Columns{k}={};end
            end
            obj.EmptyTable=struct2table(repmat(template,0,1),'AsArray',true);
        end
        function append(obj,row)
            assert(isstruct(row)&&isscalar(row)&&isequal(fieldnames(row),obj.Names),'csr:trace:Schema','Ordered schema differs.');
            assert(obj.Count<obj.Capacity,'csr:trace:Capacity','Logical row capacity exceeded.');
            for k=1:numel(obj.Names),obj.validate(row.(obj.Names{k}),k);end
            states=cell(size(obj.Columns));
            for k=find(obj.IsChar)',states{k}=obj.Columns{k}.appendCheckpoint();end
            index=obj.Count+1;page=floor((index-1)/obj.PageRows)+1;slot=mod(index-1,obj.PageRows)+1;
            try
                for k=1:numel(obj.Names)
                    v=row.(obj.Names{k});
                    if obj.IsChar(k),obj.Columns{k}.append(v);
                    else
                        if page>numel(obj.Columns{k})
                            n=min(obj.PageRows,obj.Capacity-(page-1)*obj.PageRows);
                            if isstring(v),obj.Columns{k}{page}=strings(n,1);
                            else,obj.Columns{k}{page}=zeros(n,1,'like',v);end
                        end
                        obj.Columns{k}{page}(slot)=v;
                    end
                end
                obj.Count=index;
            catch e
                for k=find(obj.IsChar)',obj.Columns{k}.rollbackAppend(states{k});end
                rethrow(e);
            end
        end
        function value=tableRows(obj,first,last)
            validateattributes(first,{'double'},{'scalar','real','integer','positive','finite'});
            validateattributes(last,{'double'},{'scalar','real','integer','nonnegative','finite'});
            if first==1&&last==0,value=obj.EmptyTable;return;end
            assert(first<=last&&last<=obj.Count,'csr:trace:Range','Requested uncommitted rows.');
            columns=cell(1,numel(obj.Names));n=last-first+1;
            for k=1:numel(obj.Names)
                if obj.IsChar(k),columns{k}=obj.Columns{k}.rows(first,last);continue;end
                template=obj.Template.(obj.Names{k});
                if isstring(template),values=strings(n,1);else,values=zeros(n,1,'like',template);end
                index=first;
                while index<=last
                    page=floor((index-1)/obj.PageRows)+1;slot=mod(index-1,obj.PageRows)+1;
                    take=min(last-index+1,obj.PageRows-slot+1);
                    values(index-first+(1:take))=obj.Columns{k}{page}(slot:slot+take-1);index=index+take;
                end
                columns{k}=values;
            end
            value=table(columns{:},'VariableNames',reshape(obj.Names,1,[]));
        end
        function receipt=exportCsv(obj,path,chunkSize,transform,checkpoint)
            if nargin<4,transform=[];end
            if nargin<5,checkpoint=[];end
            assert(isempty(transform)||isa(transform,'function_handle'),'csr:trace:Transform','Function handle required.');
            initialCount=obj.Count;
            receipt=csr.sim.TypedTraceBuffer.exportRows(path,initialCount,chunkSize,@getRows,checkpoint);
            function part=getRows(first,last)
                assert(obj.Count==initialCount,'csr:trace:ConcurrentAppend','Buffer changed during export.');
                part=obj.tableRows(first,last);
                if ~isempty(transform)
                    original=part;part=transform(part,first,last);
                    assert(istable(part)&&isequal(part.Properties.VariableNames,original.Properties.VariableNames), ...
                        'csr:trace:Transform','Transform changed column schema.');
                    for column=1:width(original)
                        name=original.Properties.VariableNames{column};
                        assert(strcmp(class(part.(name)),class(original.(name)))&& ...
                            isequal(size(part.(name)),size(original.(name))), ...
                            'csr:trace:Transform','Transform changed column class/shape.');
                    end
                end
                assert(obj.Count==initialCount,'csr:trace:ConcurrentAppend','Buffer changed during export.');
            end
        end
        function value=textStatistics(obj)
            value=struct();
            for k=find(obj.IsChar)',value.(obj.Names{k})=obj.Columns{k}.statistics();end
        end
    end
    methods (Static)
        function receipt=exportRows(path,count,chunkSize,rowGetter,checkpoint)
            if nargin<5,checkpoint=[];end
            validateattributes(count,{'double'},{'scalar','real','finite','integer','nonnegative','<=',flintmax});
            validateattributes(chunkSize,{'double'},{'scalar','real','finite','integer','positive','<=',flintmax});
            assert(isa(rowGetter,'function_handle')&&(isempty(checkpoint)||isa(checkpoint,'function_handle')), ...
                'csr:trace:Callback','Bounded getter/checkpoint handles required.');
            path=char(path);[folder,~,extension]=fileparts(path);
            assert(strcmpi(extension,'.csv'),'csr:trace:CsvPath','Explicit .csv path required.');
            if isempty(folder),folder=pwd;end
            assert(isfolder(folder),'csr:trace:CsvPath','Existing output directory required.');
            assert(~isfile(path)&&~isfolder(path),'csr:trace:Existing','Refusing existing output.');
            if ~isempty(checkpoint),checkpoint();end
            reserved=java.io.File(path).createNewFile();
            assert(reserved,'csr:trace:Existing','Refusing existing output.');
            % MATLAB R2026a writeTextFile computes minimal quotes per WHOLE
            % text variable, not per row/chunk. Discover those flags boundedly.
            names={};classes={};quoted=[];header=[];
            ending=newline;if ispc,ending=sprintf('\r\n');end
            for first=1:chunkSize:max(1,count)
                if ~isempty(checkpoint),checkpoint();end
                last=min(count,first+chunkSize-1);part=rowGetter(first,last);
                assert(istable(part)&&height(part)==max(0,last-first+1),'csr:trace:Transform','Getter changed row count.');
                currentClasses=cellfun(@(n)class(part.(n)),part.Properties.VariableNames,'UniformOutput',false);
                if isempty(names)
                    names=part.Properties.VariableNames;classes=currentClasses;
                    header=part([],:);quoted=false(1,width(part));
                else
                    assert(isequal(names,part.Properties.VariableNames)&&isequal(classes,currentClasses), ...
                        'csr:trace:Transform','CSV chunk schema/classes changed.');
                end
                for k=1:width(part)
                    v=part.(names{k});
                    assert(size(v,2)==1||isempty(v),'csr:trace:CsvType','Scalar diagnostic columns required.');
                    if isstring(v)||(iscell(v)&&all(cellfun(@ischar,v),'all'))
                        quoted(k)=quoted(k)||any(contains(v,{',',ending,'"'}),'all');
                    else
                        assert(isnumeric(v)||islogical(v),'csr:trace:CsvType','Unsupported diagnostic CSV column type.');
                    end
                end
                if ~isempty(checkpoint),checkpoint();end
            end
            if ~isempty(checkpoint),checkpoint();end
            % Header retains MATLAB's own minimal-quote policy and UTF-8/CRLF.
            writetable(header,path,'FileType','text','Delimiter',',','WriteMode','overwrite');
            written=0;batches=0;
            for first=1:chunkSize:max(1,count)
                if ~isempty(checkpoint),checkpoint();end
                last=min(count,first+chunkSize-1);part=rowGetter(first,last);
                assert(istable(part)&&height(part)==max(0,last-first+1),'csr:trace:Transform','Getter changed row count.');
                currentClasses=cellfun(@(n)class(part.(n)),part.Properties.VariableNames,'UniformOutput',false);
                assert(isequal(names,part.Properties.VariableNames)&&isequal(classes,currentClasses), ...
                    'csr:trace:Transform','CSV chunk schema/classes changed.');
                for k=find(quoted)
                    v=part.(names{k});missingStrings=false(size(v));
                    if isstring(v)
                        missingStrings=ismissing(v);v(missingStrings)='';v=cellstr(v);
                    end
                    % Match installed MATLAB stringify, including strcat's
                    % existing whitespace behavior and unquoted missing text.
                    v(~missingStrings)=strcat('"',strrep(v(~missingStrings),'"','""'),'"');
                    part.(names{k})=v;
                end
                if ~isempty(checkpoint),checkpoint();end
                if height(part)>0
                    % Leave numeric classes/formatting entirely to MATLAB.
                    writetable(part,path,'FileType','text','Delimiter',',','WriteMode','append', ...
                        'WriteVariableNames',false,'QuoteStrings','none');
                end
                written=written+height(part);batches=batches+1;
                if ~isempty(checkpoint),checkpoint();end
            end
            assert(written==count,'csr:trace:ExportCount','Incomplete export.');
            info=dir(path);assert(isscalar(info)&&info.bytes>0,'csr:trace:ExportFile','Missing CSV header/output.');
            receipt=struct('Rows',written,'Batches',batches,'ChunkSize',chunkSize,'Bytes',info.bytes,'Complete',true);
        end
    end
    methods (Access=private)
        function validate(obj,value,k)
            template=obj.Template.(obj.Names{k});
            assert(strcmp(class(value),class(template)),'csr:trace:Type','Scalar class differs.');
            if ischar(value),ok=isrow(value)||isequal(size(value),[0 0]);
            elseif isstring(value),ok=isscalar(value);
            else,ok=(isnumeric(value)||islogical(value))&&isscalar(value)&&isreal(value)&&~issparse(value);end
            assert(ok,'csr:trace:Shape','Unsupported scalar/text shape.');
        end
    end
end
