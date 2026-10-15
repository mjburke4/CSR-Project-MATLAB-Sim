classdef PagedUtf16Column < handle
    % Prototype only: exact raw UTF16, lazy row metadata, bounded codec pages.
    properties (SetAccess=private)
        Count=0
        Capacity
        Closed=false
    end
    properties (Access=private)
        PageUnits=32768
        MetaRows=4096
        Pending
        PendingCount=0
        Pages={}
        PageCount=0
        Metadata={}
        TotalUnits=uint64(0)
        CacheId=0
        CacheUnits=uint16([])
    end
    methods
        function obj=PagedUtf16Column(capacity)
            validateattributes(capacity,{'double'},{'scalar','real','integer','nonnegative','finite','<=',flintmax});
            obj.Capacity=capacity;obj.Pending=zeros(1,obj.PageUnits,'uint16');
        end
        function append(obj,value)
            assert(~obj.Closed,'paged:Closed','Column is sealed.');
            assert(obj.Count<obj.Capacity,'paged:Capacity','Row capacity exceeded.');
            assert(ischar(value)&&(isrow(value)||isequal(size(value),[0 0])), 'paged:Type','Exact char row required.');
            units=numel(value);assert(double(obj.TotalUnits)<=flintmax-units,'paged:Offset','Exact offset domain exceeded.');
            oldPending=obj.Pending;oldPendingCount=obj.PendingCount;
            oldPages=obj.PageCount;oldTotal=obj.TotalUnits;
            try
                position=1;
                while position<=units
                    n=min(obj.PageUnits-obj.PendingCount,units-position+1);
                    obj.Pending(obj.PendingCount+(1:n))=uint16(value(position:position+n-1));
                    obj.PendingCount=obj.PendingCount+n;position=position+n;
                    if obj.PendingCount==obj.PageUnits,obj.flush();end
                end
                index=obj.Count+1;block=floor((index-1)/obj.MetaRows)+1;slot=mod(index-1,obj.MetaRows)+1;
                if block>numel(obj.Metadata)
                    n=min(obj.MetaRows,obj.Capacity-(block-1)*obj.MetaRows);
                    obj.Metadata{block}=struct('Offset',zeros(n,1,'uint64'),'Length',zeros(n,1,'uint64'),'EmptyZeroRows',false(n,1));
                end
                obj.Metadata{block}.Offset(slot)=oldTotal;obj.Metadata{block}.Length(slot)=uint64(units);
                obj.Metadata{block}.EmptyZeroRows(slot)=size(value,1)==0;
                obj.TotalUnits=oldTotal+uint64(units);obj.Count=index;
            catch e
                % Keep all earlier committed rows readable on a failed append.
                for j=oldPages+1:obj.PageCount,obj.Pages{j}=[];end
                obj.PageCount=oldPages;obj.Pending=oldPending;obj.PendingCount=oldPendingCount;
                obj.TotalUnits=oldTotal;obj.CacheId=0;obj.CacheUnits=uint16([]);rethrow(e);
            end
        end
        function values=rows(obj,first,last)
            validateattributes(first,{'double'},{'scalar','real','integer','positive','finite'});
            validateattributes(last,{'double'},{'scalar','real','integer','nonnegative','finite'});
            if first==1&&last==0,values=cell(0,1);return;end
            assert(first<=last&&last<=obj.Count,'paged:Range','Unavailable row range.');
            values=cell(last-first+1,1);
            for index=first:last
                block=floor((index-1)/obj.MetaRows)+1;slot=mod(index-1,obj.MetaRows)+1;m=obj.Metadata{block};
                offset=double(m.Offset(slot));n=double(m.Length(slot));
                assert(offset+n<=double(obj.TotalUnits),'paged:Offset','Invalid retained metadata.');
                if n==0
                    if m.EmptyZeroRows(slot),value='';else,value=reshape(char([]),1,0);end
                else
                    value=char(zeros(1,n,'uint16'));copied=0;
                    while copied<n
                        page=floor((offset+copied)/obj.PageUnits)+1;within=mod(offset+copied,obj.PageUnits);
                        data=obj.page(page);take=min(n-copied,numel(data)-within);
                        assert(take>0,'paged:Offset','Page does not cover row.');
                        value(copied+(1:take))=char(data(within+(1:take)));copied=copied+take;
                    end
                end
                values{index-first+1}=value;
            end
        end
        function seal(obj)
            if obj.Closed,return;end
            if obj.PendingCount>0,obj.flush();end
            obj.Closed=true;
        end
        function state=appendCheckpoint(obj)
            % Prototype owner transaction: bounded pending-page state only.
            state=struct('Count',obj.Count,'PageCount',obj.PageCount,'Pending',obj.Pending, ...
                'PendingCount',obj.PendingCount,'TotalUnits',obj.TotalUnits,'Closed',obj.Closed);
        end
        function rollbackAppend(obj,state)
            assert(~state.Closed&&state.Count<=obj.Count,'paged:Rollback','Invalid owner transaction.');
            for j=state.PageCount+1:obj.PageCount,obj.Pages{j}=[];end
            obj.Count=state.Count;obj.PageCount=state.PageCount;obj.Pending=state.Pending;
            obj.PendingCount=state.PendingCount;obj.TotalUnits=state.TotalUnits;obj.Closed=false;
            obj.CacheId=0;obj.CacheUnits=uint16([]);
        end
        function value=statistics(obj)
            compressed=0;for k=1:obj.PageCount,compressed=compressed+numel(obj.Pages{k}.Compressed);end
            meta=0;for k=1:numel(obj.Metadata),meta=meta+numel(obj.Metadata{k}.Offset)*17;end
            value=struct('Rows',obj.Count,'Capacity',obj.Capacity,'RawBytes',double(obj.TotalUnits)*2, ...
                'CompressedPages',obj.PageCount,'CompressedBytes',compressed,'PendingBytes',obj.PendingCount*2, ...
                'AllocatedMetadataPayloadBytes',meta,'FixedPendingPayloadBytes',obj.PageUnits*2, ...
                'CachePayloadBytes',numel(obj.CacheUnits)*2,'Closed',obj.Closed, ...
                'WrapperOverheadMeasured',false,'ProductionEligible',false);
        end
    end
    methods (Access=private)
        function flush(obj)
            item=csr.sim.PagedUtf16Column.encodePage(obj.Pending(1:obj.PendingCount));
            obj.Pages{obj.PageCount+1}=item;obj.PageCount=obj.PageCount+1;obj.PendingCount=0;
        end
        function units=page(obj,index)
            if index<=obj.PageCount
                if obj.CacheId~=index
                    obj.CacheUnits=csr.sim.PagedUtf16Column.decodePage(obj.Pages{index});obj.CacheId=index;
                end
                units=obj.CacheUnits;
            else
                assert(index==obj.PageCount+1&&~obj.Closed,'paged:Page','Missing page.');
                units=obj.Pending(1:obj.PendingCount);
            end
        end
    end
    methods (Static)
        function item=encodePage(units)
            assert(isa(units,'uint16')&&isrow(units)&&numel(units)>0&&numel(units)<=32768,'paged:Page','Bounded uint16 page required.');
            raw=typecast(units,'uint8');sink=java.io.ByteArrayOutputStream(numel(raw)+1024);
            codec=java.util.zip.Deflater(6,false);stream=java.util.zip.DeflaterOutputStream(sink,codec,65536);
            try
                stream.write(typecast(raw,'int8'),0,numel(raw));stream.finish();stream.close();
                compressed=typecast(sink.toByteArray(),'uint8');javaMethod('end',codec);
            catch e
                try,stream.close();catch,end
                javaMethod('end',codec);rethrow(e);
            end
            assert(numel(compressed)<=2*numel(raw)+1024,'paged:Size','Unexpected compressed output growth.');
            [~,~,endian]=computer;
            item=struct('Compressed',compressed(:),'RawBytes',numel(raw),'Endian',endian, ...
                'RawSHA256',csr.sim.PagedUtf16Column.digest(raw),'CompressedSHA256',csr.sim.PagedUtf16Column.digest(compressed));
        end
        function units=decodePage(item)
            assert(isstruct(item)&&isscalar(item)&&all(isfield(item,{'Compressed','RawBytes','Endian','RawSHA256','CompressedSHA256'})), 'paged:Schema','Incomplete page.');
            assert(isa(item.Compressed,'uint8')&&isvector(item.Compressed)&&numel(item.Compressed)<=132096,'paged:Size','Invalid compressed page.');
            n=item.RawBytes;assert(isa(n,'double')&&isscalar(n)&&isfinite(n)&&n>0&&n<=65536&&mod(n,2)==0,'paged:Size','Invalid decoded page size.');
            [~,~,endian]=computer;assert(strcmp(item.Endian,endian),'paged:Endian','Page byte order differs.');
            assert(strcmp(csr.sim.PagedUtf16Column.digest(item.Compressed),item.CompressedSHA256),'paged:Hash','Compressed hash mismatch.');
            input=java.io.ByteArrayInputStream(typecast(item.Compressed(:),'int8'));
            codec=java.util.zip.Inflater(false);stream=java.util.zip.InflaterInputStream(input,codec,65536);
            channel=java.nio.channels.Channels.newChannel(stream);buffer=java.nio.ByteBuffer.allocate(65536);
            raw=zeros(1,n,'uint8');count=0;
            try
                while true
                    got=channel.read(buffer);if got==-1,break;end
                    assert(got>0&&count+got<=n,'paged:Size','Decoded page exceeds declared length.');
                    bytes=buffer.array();raw(count+(1:got))=typecast(bytes(1:got),'uint8');count=count+got;buffer.clear();
                end
                assert(count==n&&codec.finished()&&codec.getRemaining()==0&&input.available()==0,'paged:Size','Truncated/trailing compressed data.');
                channel.close();javaMethod('end',codec);
            catch e
                try,channel.close();catch,end
                javaMethod('end',codec);rethrow(e);
            end
            assert(strcmp(csr.sim.PagedUtf16Column.digest(raw),item.RawSHA256),'paged:Hash','Raw page hash mismatch.');
            units=typecast(raw,'uint16');
        end
        function hex=digest(bytes)
            md=java.security.MessageDigest.getInstance('SHA-256');md.update(typecast(uint8(bytes(:)),'int8'));
            hex=lower(reshape(dec2hex(typecast(md.digest(),'uint8'),2).',1,[]));
        end
    end
end
