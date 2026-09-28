classdef PacketNode < wnet.Node
    %PACKETNODE Native abstract-packet lifecycle harness; not a CSR MAC/PHY.
    % Queue frames before simulation. All same-channel CSR packets, including
    % overheard packets, traverse the native channel. ReceptionCompleted means
    % the packet duration elapsed; this harness has no BER/ECC success decision.
    properties (SetAccess = private)
        CsrId
        NumPacketsTransmitted = 0
        NumPacketsPushed = 0
        NumPacketsCompleted = 0
        Completed = struct('CompletedSeconds', {}, 'Packet', {})
    end
    properties (Access = private)
        Radio
        Plan = struct('StartSeconds', {}, 'Frame', {})
        NextPlan = 1
        TransmitterBuffer = []
        ReceptionBuffer = []
        Started = false
    end
    methods
        function obj = PacketNode(csrId, position, radio)
            obj@wnet.Node('Name', sprintf('CSR %d', csrId), ...
                'Position', position);
            validateattributes(csrId, {'numeric'}, ...
                {'scalar', 'integer', 'nonnegative', '<', 2^24-1});
            validateattributes(radio.CenterFrequencyHz, {'numeric'}, ...
                {'scalar', 'finite', 'positive'});
            validateattributes(radio.BandwidthHz, {'numeric'}, ...
                {'scalar', 'finite', 'positive'});
            validateattributes(radio.TxPowerDbm, {'numeric'}, ...
                {'scalar', 'finite', 'real'});
            obj.CsrId = csrId;
            obj.Radio = radio;
        end
        function queueFrame(obj, frame, startSeconds)
            if obj.Started
                error('csr:sim:NativeProbePlanLocked', ...
                    'Queue native probe frames before simulation starts.');
            end
            validateattributes(startSeconds, {'numeric'}, ...
                {'scalar', 'finite', 'nonnegative'});
            if frame.SourceId ~= obj.CsrId
                error('csr:sim:NativeSourceMismatch', ...
                    'The logical CSR SourceId must match the transmitting node.');
            end
            obj.Plan(end+1) = struct('StartSeconds', double(startSeconds), ...
                'Frame', frame);
            [~, order] = sort([obj.Plan.StartSeconds]);
            obj.Plan = obj.Plan(order);
        end
        function nextInvokeTime = run(obj, currentTime)
            obj.Started = true;
            nextInvokeTime = Inf;
            while obj.NextPlan <= numel(obj.Plan) && ...
                    obj.Plan(obj.NextPlan).StartSeconds <= currentTime
                plan = obj.Plan(obj.NextPlan);
                if plan.StartSeconds ~= currentTime
                    error('csr:sim:NativeProbeMissedTransmission', ...
                        'Native node was invoked after its planned transmission.');
                end
                packet = csr.sim.native.wrapPacket(plan.Frame, obj, ...
                    obj.Radio, currentTime);
                if isempty(obj.TransmitterBuffer)
                    obj.TransmitterBuffer = packet;
                else
                    obj.TransmitterBuffer(end+1) = packet;
                end
                obj.NextPlan = obj.NextPlan + 1;
                obj.NumPacketsTransmitted = obj.NumPacketsTransmitted + 1;
            end
            if obj.NextPlan <= numel(obj.Plan)
                nextInvokeTime = obj.Plan(obj.NextPlan).StartSeconds;
            end
            retained = true(1, numel(obj.ReceptionBuffer));
            for index = 1:numel(obj.ReceptionBuffer)
                packet = obj.ReceptionBuffer(index);
                completion = packet.StartTime + packet.Duration;
                if completion <= currentTime
                    obj.NumPacketsCompleted = obj.NumPacketsCompleted + 1;
                    obj.Completed(end+1) = struct( ...
                        'CompletedSeconds', currentTime, 'Packet', packet);
                    retained(index) = false;
                else
                    nextInvokeTime = min(nextInvokeTime, completion);
                end
            end
            obj.ReceptionBuffer = obj.ReceptionBuffer(retained);
        end
        function packet = pullTransmittedPacket(obj)
            packet = obj.TransmitterBuffer;
            obj.TransmitterBuffer = [];
        end
        function pushReceivedPacket(obj, packets)
            for index = 1:numel(packets)
                if isempty(obj.ReceptionBuffer)
                    obj.ReceptionBuffer = packets(index);
                else
                    obj.ReceptionBuffer(end+1) = packets(index);
                end
            end
            obj.NumPacketsPushed = obj.NumPacketsPushed + numel(packets);
        end
        function [flag, receiverInfo] = isPacketRelevant(obj, packets)
            % Relevance includes interference/overhearing, not just addresses.
            flag = false;
            receiverInfo = [];
            for index = 1:numel(packets)
                packet = packets(index);
                spectralOverlap = abs(packet.CenterFrequency - ...
                    obj.Radio.CenterFrequencyHz) < ...
                    (packet.Bandwidth + obj.Radio.BandwidthHz)/2;
                flag = flag || (packet.TechnologyType == ...
                    wnet.TechnologyType.Custom1 && ...
                    packet.TransmitterID ~= obj.ID && spectralOverlap);
            end
            if flag
                receiverInfo = struct('ID', obj.ID, ...
                    'Position', obj.Position, 'Velocity', obj.Velocity, ...
                    'NumReceiveAntennas', 1);
            end
        end
        function result = statistics(obj)
            result = struct('ID', obj.ID, 'CsrId', obj.CsrId, ...
                'NumPacketsTransmitted', obj.NumPacketsTransmitted, ...
                'NumPacketsPushed', obj.NumPacketsPushed, ...
                'NumPacketsCompleted', obj.NumPacketsCompleted);
        end
    end
end
