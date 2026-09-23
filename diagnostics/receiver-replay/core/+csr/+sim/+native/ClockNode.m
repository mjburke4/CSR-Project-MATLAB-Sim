classdef ClockNode < wnet.Node
    %CLOCKNODE Native clock anchor. It never transports or receives RF frames.
    % The shared CSR SignalEngine owns RF on the wireless-clock backend.
    properties (Access = private)
        Advance
    end
    methods
        function obj = ClockNode(advance)
            obj@wnet.Node('Name', 'CSR clock', 'Position', [0 0 0]);
            obj.Advance = advance;
        end
        function nextInvokeTime = run(obj, currentTime)
            nextInvokeTime = obj.Advance(currentTime);
        end
        function packet = pullTransmittedPacket(~)
            packet = [];
        end
        function pushReceivedPacket(~, ~)
            error('csr:sim:ClockNodeReceivedPacket', ...
                'The CSR clock anchor must never receive wireless packets.');
        end
        function [flag, receiverInfo] = isPacketRelevant(~, ~)
            flag = false;
            receiverInfo = [];
        end
    end
end
