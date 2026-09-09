classdef Frames
    %FRAMES Logical HOP frames and explicit legacy packet-model byte layouts.
    % Protocol observations stay separate from modeled on-air byte counts.
    % Sequence is the live ns-3 uint16; legacy br_Hop.sequence8 is a separate
    % serializer field and is never obtained by silently narrowing Sequence.
    methods (Static)
        function frame = data(app, sourceId, destinationId, sequence, radio)
            if nargin < 5, radio = struct(); end
            frame = csr.hop.Frames.base(sourceId, destinationId, sequence, radio);
            required = {'Id','SourceId','DestinationId','GeneratedSeconds', ...
                'ApplicationPayloadBytes'};
            if ~isstruct(app) || ~isscalar(app) || ~all(isfield(app,required))
                error('csr:hop:InvalidApplication', 'DATA requires a logical application packet.');
            end
            csr.hop.Frames.number(app.ApplicationPayloadBytes, 0, 65535, 'application bytes');
            validateattributes(app.GeneratedSeconds, {'numeric'}, ...
                {'scalar','real','finite','nonnegative'});
            frame.Kind = 'DATA';
            frame.App = app;
            frame.GeneratedSeconds = double(app.GeneratedSeconds);
            frame.ApplicationPayloadBytes = double(app.ApplicationPayloadBytes);
            frame.WirePayloadBytes = frame.ApplicationPayloadBytes + 32 + ...
                csr.hop.Frames.securityBytes(frame.EnvelopeProfile);
            frame.Dscp = csr.hop.Frames.option(radio, 'Dscp', ...
                csr.hop.Frames.option(app, 'Dscp', 0));
            csr.hop.Frames.number(frame.Dscp, 0, 255, 'DSCP');
            frame.Dscp = double(frame.Dscp);
            frame.AckRequired = csr.hop.Frames.boolean(csr.hop.Frames.option(radio, ...
                'AckRequired', true),'AckRequired');
        end

        function frame = acknowledgment(sourceId, destinationId, sequence, ackBitmap, dackBitmap, radio)
            if nargin < 6, radio = struct(); end
            frame = csr.hop.Frames.base(sourceId, destinationId, sequence, radio);
            frame.Kind = upper(char(csr.hop.Frames.option(radio,'Kind','ACK')));
            if ~any(strcmp(frame.Kind, {'ACK','DACK'}))
                error('csr:hop:InvalidKind', 'Acknowledgment Kind must be ACK or DACK.');
            end
            frame.Dscp = 7; % Source feedback constructor; aggregate metadata excludes ACKs.
            frame.HasAckWindow = csr.hop.Frames.boolean(csr.hop.Frames.option(radio, ...
                'HasAckWindow', true),'HasAckWindow');
            frame.AckBitmap = csr.hop.Frames.bitmap(ackBitmap);
            frame.DackBitmap = csr.hop.Frames.bitmap(dackBitmap);
            frame.WirePayloadBytes = 25 + 16 * double(frame.HasAckWindow) + ...
                csr.hop.Frames.securityBytes(frame.EnvelopeProfile);
        end

        function frame = aggregate(members, preamble)
            % Source concatenation retains every member's complete MAC envelope.
            if ~iscell(members), members = num2cell(members); end
            if isempty(members)
                error('csr:hop:EmptyAggregate', 'A transmission requires at least one member.');
            end
            frame = members{1};
            frame.Segments = reshape(members,1,[]);
            frame.WirePayloadBytes = 0;
            frame.ApplicationPayloadBytes = 0;
            frame.Dscp = 0;
            frame.AckRequired = false;
            chosenRate = Inf;
            chosenPower = [];
            for k = 1:numel(members)
                member = members{k};
                if member.SourceId ~= frame.SourceId
                    error('csr:hop:MixedAggregateSources', 'Every aggregate member must share a transmitter.');
                end
                frame.WirePayloadBytes = frame.WirePayloadBytes + member.WirePayloadBytes;
                frame.ApplicationPayloadBytes = frame.ApplicationPayloadBytes + member.ApplicationPayloadBytes;
                frame.AckRequired = frame.AckRequired || member.AckRequired;
                if strcmp(member.Kind, 'DATA'), frame.Dscp = max(frame.Dscp,member.Dscp); end
                if member.RateKeyKbps < chosenRate
                    chosenRate = member.RateKeyKbps;
                    chosenPower = member.TxPowerDbm;
                elseif member.RateKeyKbps == chosenRate && ~isempty(member.TxPowerDbm)
                    if isempty(chosenPower), chosenPower = member.TxPowerDbm;
                    else, chosenPower = max(chosenPower,member.TxPowerDbm); end
                end
            end
            frame.RateKeyKbps = chosenRate;
            frame.TxPowerDbm = chosenPower;
            if nargin >= 2, frame.Preamble = char(preamble); end
        end

        function bytes = fixedSize(format)
            [~, widths, ~, preamble] = csr.hop.Frames.layout(format);
            bytes = sum(widths) + preamble;
        end

        function bytes = serializeModel(format, fields, payload)
            % Exact csr-opnet-packet-model.cc layout, without simulator metadata.
            if nargin < 3, payload = uint8([]); end
            payload = csr.hop.Frames.byteVector(payload);
            [names,widths,inherited,preamble,tail] = csr.hop.Frames.layout(format);
            if ~inherited && ~isempty(payload)
                error('csr:hop:UnexpectedPayload', 'This fixed packet model has no inherited payload.');
            end
            bytes = zeros(1,preamble,'uint8');
            for k = 1:numel(names)
                if k == tail, bytes = [bytes payload]; end %#ok<AGROW>
                value = csr.hop.Frames.option(fields,names{k},0);
                bytes = [bytes csr.hop.Frames.pack(value,widths(k))]; %#ok<AGROW>
            end
            if inherited && tail == 0, bytes = [bytes payload]; end
        end

        function [fields, payload] = deserializeModel(format, bytes)
            bytes = csr.hop.Frames.byteVector(bytes);
            [names,widths,inherited,preamble,tail] = csr.hop.Frames.layout(format);
            minimum = sum(widths) + preamble;
            if numel(bytes) < minimum || (~inherited && numel(bytes) ~= minimum)
                error('csr:hop:InvalidWireLength', 'Packet bytes do not fit the selected model.');
            end
            payloadSize = numel(bytes) - minimum;
            fields = struct();
            payload = uint8([]);
            offset = preamble + 1;
            for k = 1:numel(names)
                if k == tail
                    payload = bytes(offset:offset+payloadSize-1);
                    offset = offset + payloadSize;
                end
                fields.(names{k}) = double(csr.hop.Frames.unpack(bytes(offset:offset+widths(k)-1)));
                offset = offset + widths(k);
            end
            if inherited && tail == 0, payload = bytes(offset:end); end
        end

        function bytes = serializeAckBody(frame)
            % The current source extends the eight-byte br_Ack with two
            % 64-bit registers. No MAC/security/observation fields are added.
            fields = struct('source',frame.SourceId,'destination',frame.DestinationId, ...
                'sequence16',frame.Sequence);
            bytes = csr.hop.Frames.serializeModel('Ack',fields);
            if frame.HasAckWindow
                bytes = [bytes csr.hop.Frames.pack(frame.AckBitmap,8) ...
                    csr.hop.Frames.pack(frame.DackBitmap,8)];
            end
        end

        function fields = deserializeAckBody(bytes)
            bytes = csr.hop.Frames.byteVector(bytes);
            if ~ismember(numel(bytes),[8 24])
                error('csr:hop:InvalidWireLength', 'ACK body must contain 8 or 24 bytes.');
            end
            decoded = csr.hop.Frames.deserializeModel('Ack',bytes(1:8));
            fields = struct('SourceId',decoded.source,'DestinationId',decoded.destination, ...
                'Sequence',uint16(decoded.sequence16),'HasAckWindow',numel(bytes)==24, ...
                'AckBitmap',uint64(0),'DackBitmap',uint64(0));
            if fields.HasAckWindow
                fields.AckBitmap = csr.hop.Frames.unpack(bytes(9:16));
                fields.DackBitmap = csr.hop.Frames.unpack(bytes(17:24));
            end
        end

        function encoded = encodeRateKey(rate)
            csr.hop.Frames.number(rate,0,1000,'rate key');
            if rate == 500, encoded = uint8(129);
            elseif rate == 1000, encoded = uint8(130);
            elseif rate <= 255 && ~ismember(rate,[129 130]), encoded = uint8(rate);
            else, error('csr:hop:InvalidRateCode','Rate key has no unambiguous compact code.'); end
        end

        function rate = decodeRateKey(encoded)
            csr.hop.Frames.number(encoded,0,255,'compact rate');
            if encoded == 129, rate = 500;
            elseif encoded == 130, rate = 1000;
            else, rate = double(encoded); end
        end
    end

    methods (Static, Access = private)
        function frame = base(sourceId,destinationId,sequence,radio)
            csr.hop.Frames.number(sourceId,0,16777214,'source ID');
            csr.hop.Frames.number(destinationId,0,16777215,'destination ID');
            csr.hop.Frames.number(sequence,0,65535,'sequence');
            profile = char(csr.hop.Frames.option(radio,'EnvelopeProfile','bare'));
            csr.hop.Frames.securityBytes(profile);
            rate = csr.hop.Frames.option(radio,'RateKeyKbps',8);
            csr.phy.rateDefinition(rate);
            preamble = char(csr.hop.Frames.option(radio,'Preamble','long'));
            csr.phy.airtime(0,rate,preamble);
            power = csr.hop.Frames.option(radio,'TxPowerDbm',[]);
            if ~isempty(power), validateattributes(power,{'numeric'},{'scalar','real','finite'}); end
            retry = csr.hop.Frames.option(radio,'RetryCount',0);
            csr.hop.Frames.number(retry,0,65535,'retry count');
            generated = csr.hop.Frames.option(radio,'GeneratedSeconds',0);
            validateattributes(generated,{'numeric'},{'scalar','real','finite','nonnegative'});
            frame = struct('Id',uint64(0),'SourceId',double(sourceId), ...
                'DestinationId',double(destinationId),'GeneratedSeconds',double(generated), ...
                'ApplicationPayloadBytes',0,'WirePayloadBytes',0, ...
                'RateKeyKbps',double(rate),'Preamble',preamble,'TxPowerDbm',power, ...
                'EnvelopeProfile',profile,'Kind','DATA','Sequence',uint16(sequence), ...
                'Dscp',0,'AckRequired',false,'HasAckWindow',false, ...
                'AckBitmap',uint64(0),'DackBitmap',uint64(0),'App',struct(), ...
                'RetryCount',double(retry));
        end

        function bytes = securityBytes(profile)
            switch profile
                case 'bare', bytes = 0;
                case 'pairwise16-size-only', bytes = 5;
                otherwise
                    error('csr:hop:InvalidEnvelope','Envelope must be bare or pairwise16-size-only.');
            end
        end

        function value = option(options,name,fallback)
            if isfield(options,name) && ~isempty(options.(name)), value = options.(name);
            else, value = fallback; end
        end

        function number(value,minimum,maximum,label)
            if ~isnumeric(value) || ~isscalar(value) || ~isreal(value) || ...
                    ~isfinite(value) || value < minimum || value > maximum || fix(value) ~= value
                error('csr:hop:InvalidField','Invalid %s.',label);
            end
        end

        function value = bitmap(value)
            if isa(value,'uint64') && isscalar(value), return; end
            csr.hop.Frames.number(value,0,flintmax,'bitmap (use uint64 above flintmax)');
            value = uint64(value);
        end

        function value = boolean(value,label)
            if ~(isnumeric(value) || islogical(value)) || ~isscalar(value) || ...
                    ~isreal(value) || ~ismember(value,[0 1])
                error('csr:hop:InvalidField','%s must be a scalar logical or 0/1.',label);
            end
            value = logical(value);
        end

        function bytes = pack(value,width)
            if width == 8
                value = csr.hop.Frames.bitmap(value);
            else
                csr.hop.Frames.number(value,0,2^(8*width)-1,'wire field');
                value = uint64(value);
            end
            bytes = zeros(1,width,'uint8');
            for k = width:-1:1
                bytes(k) = uint8(bitand(value,uint64(255)));
                value = bitshift(value,-8);
            end
        end

        function value = unpack(bytes)
            value = uint64(0);
            for byte = bytes, value = bitor(bitshift(value,8),uint64(byte)); end
        end

        function bytes = byteVector(bytes)
            if ~isnumeric(bytes) || (~isvector(bytes) && ~isempty(bytes)) || ...
                    ~isreal(bytes) || any(~isfinite(bytes(:))) || ...
                    any(bytes(:)<0 | bytes(:)>255 | fix(bytes(:))~=bytes(:))
                error('csr:hop:InvalidBytes','Payload must be a byte vector.');
            end
            bytes = reshape(uint8(bytes),1,[]);
        end

        function [names,widths,inherited,preamble,tail] = layout(format)
            % Widths in BYTES; names deliberately match C++ reference fields.
            inherited = false; preamble = 0; tail = 0;
            switch lower(char(format))
                case {'ack','machopinstance'}
                    names = {'source','destination','sequence16'}; widths = [3 3 2];
                case 'hop'
                    names = {'source','numberOfDestinations','destination','sequence8'};
                    widths = [3 1 3 1]; inherited = true;
                case 'mac'
                    names = {'globalTime','globalAddress','globalCost','txPower','rxPower', ...
                        'active','source','payloadLength','type'};
                    widths = [4 3 1 1 1 1 3 2 1]; inherited = true;
                case 'network'
                    names = {'source','destination','dscp'}; widths = [3 3 1];
                    inherited = true; tail = 3;
                case {'otalongpreamble','otashortpreamble'}
                    names = {'startOfFrame','speed','length','fcs'}; widths = [2 2 2 4];
                    inherited = true; tail = 4; preamble = 13;
                    if strcmpi(format,'OtaLongPreamble'), preamble = 986; end
                case 'hello'
                    names = {'sequence8','nodeId','capabilityNumber','capability','cost','timeOffset'};
                    widths = [1 3 1 1 2 4];
                case 'routes'
                    names = {'nodeId','capabilityNumber','capability','cost','timeOffset'};
                    widths = [3 1 1 2 4];
                case 'snmp'
                    names = {'message','value'}; widths = [2 4];
                case 'sentinfo'
                    names = {'source'}; widths = 3;
                otherwise, error('csr:hop:InvalidFormat','Unknown OPNET packet model.');
            end
        end
    end
end
