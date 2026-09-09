classdef RoutingCodec
    %ROUTINGCODEC Legacy ARL record stream, independent of HOP metadata.
    % Source: csr-arl-routing-message.{h,cc}, ns-3 486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b.
    % Multi-byte values are big endian. Record boundaries need not coincide
    % with the 694-byte section-body boundary. Decode only after reassembly.
    methods (Static)
        function bytes = encodeRecords(records)
            if isstruct(records), records = num2cell(records); end
            if ~iscell(records)
                error('csr:nwk:InvalidRoutingRecord','Records must be a struct array or cell array.');
            end
            bytes = uint8([]);
            for k = 1:numel(records)
                record = records{k};
                if ~isstruct(record) || ~isscalar(record) || ~isfield(record,'Operation')
                    error('csr:nwk:InvalidRoutingRecord','A record requires Operation.');
                end
                operation = upper(char(record.Operation));
                switch operation
                    case 'FLUSH', encoded = uint8(0);
                    case 'DELETE'
                        csr.nwk.RoutingCodec.requireFields(record,{'NodeId'});
                        encoded = [uint8(1) csr.nwk.RoutingCodec.pack(record.NodeId,3)];
                    case 'UPDATE'
                        csr.nwk.RoutingCodec.requireFields(record, ...
                            {'NodeId','Capability','HopCount','Cost','Path'});
                        path = record.Path;
                        csr.nwk.RoutingCodec.integer(record.HopCount,0,65535);
                        if ~isnumeric(path) || (~isvector(path) && ~isempty(path)) || ...
                                numel(path) ~= double(record.HopCount)
                            error('csr:nwk:InvalidRoutingRecord','UPDATE path length must equal HopCount.');
                        end
                        encoded = [uint8(2) csr.nwk.RoutingCodec.pack(record.NodeId,3) ...
                            csr.nwk.RoutingCodec.pack(record.Capability,1) ...
                            csr.nwk.RoutingCodec.pack(record.HopCount,2) ...
                            csr.nwk.RoutingCodec.pack(record.Cost,4)];
                        for hop = reshape(path,1,[])
                            encoded = [encoded csr.nwk.RoutingCodec.pack(hop,3)]; %#ok<AGROW>
                        end
                    case 'REQUEST', encoded = uint8(3);
                    case 'INFO'
                        names = csr.nwk.RoutingCodec.infoFields();
                        csr.nwk.RoutingCodec.requireFields(record,{'Info'});
                        csr.nwk.RoutingCodec.requireFields(record.Info,names);
                        encoded = uint8(4);
                        for field = 1:numel(names)
                            value = record.Info.(names{field});
                            if field > 2
                                csr.nwk.RoutingCodec.integer(value,-32768,32767);
                                value = mod(double(value),65536);
                            end
                            encoded = [encoded csr.nwk.RoutingCodec.pack(value,2)]; %#ok<AGROW>
                        end
                    otherwise
                        error('csr:nwk:InvalidRoutingRecord','Unknown routing operation.');
                end
                bytes = [bytes encoded]; %#ok<AGROW>
            end
        end

        function records = decodeRecords(stream)
            stream = csr.nwk.RoutingCodec.byteVector(stream);
            records = {};
            offset = 1;
            while offset <= numel(stream)
                operation = double(stream(offset)); offset = offset+1;
                switch operation
                    case 0, record = struct('Operation','FLUSH');
                    case 1
                        csr.nwk.RoutingCodec.requireBytes(stream,offset,3);
                        record = struct('Operation','DELETE','NodeId', ...
                            csr.nwk.RoutingCodec.unpack(stream(offset:offset+2)));
                        offset = offset+3;
                    case 2
                        csr.nwk.RoutingCodec.requireBytes(stream,offset,10);
                        record = struct('Operation','UPDATE','NodeId', ...
                            csr.nwk.RoutingCodec.unpack(stream(offset:offset+2)), ...
                            'Capability',double(stream(offset+3)), ...
                            'HopCount',csr.nwk.RoutingCodec.unpack(stream(offset+4:offset+5)), ...
                            'Cost',csr.nwk.RoutingCodec.unpack(stream(offset+6:offset+9)), ...
                            'Path',[]);
                        offset = offset+10;
                        csr.nwk.RoutingCodec.requireBytes(stream,offset,3*record.HopCount);
                        if record.HopCount > 0
                            record.Path = zeros(1,record.HopCount);
                        end
                        for hop = 1:record.HopCount
                            record.Path(hop) = csr.nwk.RoutingCodec.unpack(stream(offset:offset+2));
                            offset = offset+3;
                        end
                    case 3, record = struct('Operation','REQUEST');
                    case 4
                        csr.nwk.RoutingCodec.requireBytes(stream,offset,16);
                        names = csr.nwk.RoutingCodec.infoFields(); info = struct();
                        for field = 1:numel(names)
                            value = csr.nwk.RoutingCodec.unpack(stream(offset:offset+1));
                            if field > 2 && value >= 32768, value = value-65536; end
                            info.(names{field}) = value;
                            offset = offset+2;
                        end
                        record = struct('Operation','INFO','Info',info);
                    otherwise
                        error('csr:nwk:MalformedRouting','Unknown routing operation in byte stream.');
                end
                records{end+1} = record; %#ok<AGROW>
            end
        end

        function output = sections(stream,sequence)
            stream = csr.nwk.RoutingCodec.byteVector(stream);
            prefix = csr.nwk.RoutingCodec.pack(sequence,4);
            count = ceil(numel(stream)/694);
            if count < 1 || count > 255
                error('csr:nwk:InvalidRoutingSections','A routing stream must occupy 1 to 255 sections.');
            end
            output = cell(1,count);
            for index = 0:count-1
                first = index*694+1; last = min(numel(stream),(index+1)*694);
                output{index+1} = [prefix uint8(index) uint8(count) stream(first:last)];
            end
        end

        function section = decodeSection(bytes)
            bytes = csr.nwk.RoutingCodec.byteVector(bytes);
            if numel(bytes) < 6 || numel(bytes) > 700
                error('csr:nwk:MalformedRouting','A routing section must contain 6 to 700 bytes.');
            end
            section = struct('Sequence',csr.nwk.RoutingCodec.unpack(bytes(1:4)), ...
                'Section',double(bytes(5)),'TotalSections',double(bytes(6)), ...
                'Body',bytes(7:end));
            if section.TotalSections == 0 || section.Section >= section.TotalSections
                error('csr:nwk:MalformedRouting','Invalid routing section index or total.');
            end
        end
    end

    methods (Static, Access = private)
        function names = infoFields()
            names = {'MinSpeedKbps','MaxSpeedKbps','MinPowerDbmX10','MaxPowerDbmX10', ...
                'LinkMarginDbX10','LowPowerDbmX10','TempLowCx10','TempHighCx10'};
        end
        function requireFields(record,names)
            if ~isstruct(record) || ~isscalar(record) || ~all(isfield(record,names))
                error('csr:nwk:InvalidRoutingRecord','Routing record is missing required fields.');
            end
        end
        function integer(value,minimum,maximum)
            if ~isnumeric(value) || ~isscalar(value) || ~isreal(value) || ...
                    ~isfinite(value) || value < minimum || value > maximum || fix(value) ~= value
                error('csr:nwk:InvalidRoutingRecord','Routing wire field is outside its integer range.');
            end
        end
        function bytes = pack(value,width)
            csr.nwk.RoutingCodec.integer(value,0,2^(8*width)-1);
            value = double(value); bytes = zeros(1,width,'uint8');
            for index = width:-1:1
                bytes(index) = uint8(mod(value,256)); value = floor(value/256);
            end
        end
        function value = unpack(bytes)
            value = 0;
            for byte = bytes, value = 256*value+double(byte); end
        end
        function bytes = byteVector(bytes)
            if ~isnumeric(bytes) || (~isvector(bytes) && ~isempty(bytes)) || ...
                    ~isreal(bytes) || any(~isfinite(bytes(:))) || ...
                    any(bytes(:)<0 | bytes(:)>255 | fix(bytes(:))~=bytes(:))
                error('csr:nwk:MalformedRouting','Routing bytes must be an integer byte vector.');
            end
            bytes = reshape(uint8(bytes),1,[]);
        end
        function requireBytes(stream,offset,count)
            if offset+count-1 > numel(stream)
                error('csr:nwk:MalformedRouting','Truncated routing record.');
            end
        end
    end
end
