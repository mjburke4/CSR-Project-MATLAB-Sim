classdef DiscoveryReplaySampler < handle
    %DISCOVERYREPLAYSAMPLER Consume captured receiver PHY draws exactly once.
    % Captured threshold is the actual sampled threshold in dB; header and
    % payload uniforms are keyed by native input TX identity and interval.
    properties (SetAccess=private)
        Rows
        Consumed
        ReceiverIds
    end
    properties (Access=private)
        Clock
    end
    methods
        function obj=DiscoveryReplaySampler(drawFile,receiverIds,clock)
            if ~isa(clock,'function_handle')
                error('discovery_replay:DrawClock','Supply replay scheduler clock.');
            end
            obj.Clock=clock;
            obj.ReceiverIds=reshape(double(receiverIds),1,[]);
            obj.Rows=readtable(drawFile,'TextType','string','VariableNamingRule','preserve');
            expected={'time_ns','event_order','node','tx_id','interval_ordinal','purpose','value'};
            if ~isequal(obj.Rows.Properties.VariableNames,expected)
                error('discovery_replay:DrawSchema','Expected PHY draw CSV columns: %s',strjoin(expected,','));
            end
            obj.Consumed=false(height(obj.Rows),1);
            if any(~ismember(double(obj.Rows.node),obj.ReceiverIds)) || ...
                    any(~isfinite(double(obj.Rows.value))) || ...
                    any(~ismember(string(obj.Rows.purpose), ...
                    ["sync_threshold_db","header_uniform","payload_uniform"]))
                error('discovery_replay:DrawDomain','Capture has invalid receiver, draw or purpose.');
            end
            keys=string(obj.Rows.node)+"/"+string(obj.Rows.tx_id)+"/"+ ...
                string(obj.Rows.interval_ordinal)+"/"+string(obj.Rows.purpose);
            if numel(unique(keys))~=numel(keys) || ...
                    any(obj.Rows.event_order(2:end)<=obj.Rows.event_order(1:end-1))
                error('discovery_replay:DrawOrder','Duplicate keyed draw or nonmonotone capture order.');
            end
            uniform=string(obj.Rows.purpose)~="sync_threshold_db";
            if any(obj.Rows.value(uniform)<0 | obj.Rows.value(uniform)>1) || ...
                    any(obj.Rows.interval_ordinal(~uniform)~=0)
                error('discovery_replay:DrawDomain','Bad PHY uniform or threshold interval.');
            end
        end
        function tf=owns(obj,node), tf=any(obj.ReceiverIds==double(node)); end
        function threshold=syncThreshold(obj,node,txId)
            threshold=obj.take(node,txId,0,"sync_threshold_db");
        end
        function value=uniform(obj,node,txId,ordinal,purpose)
            value=obj.take(node,txId,ordinal,string(purpose));
        end
        function verifyExhausted(obj)
            if any(~obj.Consumed)
                left=find(~obj.Consumed,1);
                error('discovery_replay:UnconsumedDraw', ...
                    'Unconsumed PHY draw at event order %g.',obj.Rows.event_order(left));
            end
        end
        function result=usage(obj)
            result=struct('total',height(obj.Rows),'consumed',sum(obj.Consumed), ...
                'unconsumed',sum(~obj.Consumed),'receivers',obj.ReceiverIds);
        end
    end
    methods (Access=private)
        function value=take(obj,node,txId,ordinal,purpose)
            pick=double(obj.Rows.node)==double(node) & ...
                double(obj.Rows.tx_id)==double(txId) & ...
                double(obj.Rows.interval_ordinal)==double(ordinal) & ...
                string(obj.Rows.purpose)==purpose;
            if sum(pick)~=1
                error('discovery_replay:MissingDraw', ...
                    'Missing draw node=%g TX=%g interval=%g purpose=%s.', ...
                    node,txId,ordinal,char(purpose));
            end
            index=find(pick,1);
            if obj.Consumed(index)
                error('discovery_replay:DuplicateDrawUse','PHY draw consumed twice.');
            end
            if index~=find(~obj.Consumed,1)
                error('discovery_replay:DrawOrderMismatch', ...
                    'Native PHY draw order differs at event %g.',obj.Rows.event_order(index));
            end
            if abs(round(obj.Clock()*1e9)-double(obj.Rows.time_ns(index)))>2
                error('discovery_replay:DrawTimeMismatch', ...
                    'Native PHY draw time differs at event %g.',obj.Rows.event_order(index));
            end
            obj.Consumed(index)=true;
            value=obj.Rows.value(index);
        end
    end
end
