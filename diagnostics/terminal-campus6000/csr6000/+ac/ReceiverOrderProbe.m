classdef ReceiverOrderProbe < handle
    %RECEIVERORDERPROBE Passive public PHY callback ledger; no model mutation.
    properties
        Streams
        Records = {}
    end
    methods
        function obj=ReceiverOrderProbe(streams), obj.Streams=streams; end
        function record(obj,name,frame,node,details)
            obj.Records{end+1}=struct('event',name,'node',double(node), ...
                'source',double(frame.SourceId),'tx_id',obj.Streams.txId(frame), ...
                'time_ns',round(details.TimeSeconds*1e9),'details',details);
        end
    end
end
