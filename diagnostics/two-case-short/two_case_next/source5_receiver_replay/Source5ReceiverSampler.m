classdef Source5ReceiverSampler < handle
    %SOURCE5RECEIVERSAMPLER Consume every captured node-4 PHY draw once.
    % Validation-only seam for DiscoverySignalEngine. Draw order, timestamp,
    % TX identity, BER component and interval ordinal must all match exactly.
    properties (SetAccess=private)
        Rows
        Consumed
    end
    properties (Access=private)
        Clock
    end
    methods
        function obj=Source5ReceiverSampler(path,clock)
            if ~isa(clock,'function_handle')
                error('source5_receiver:Clock','Supply a replay scheduler clock.');
            end
            obj.Clock=clock;
            obj.Rows=readtable(path,'TextType','string','VariableNamingRule','preserve');
            names={'time_ns','event_order','node','tx_id','interval_ordinal', ...
                   'purpose','value','draw_ordinal','component','interval_start_ns', ...
                   'interval_end_ns','bits','probability'};
            if ~isequal(obj.Rows.Properties.VariableNames,names)
                error('source5_receiver:DrawSchema','Native draw schema differs.');
            end
            obj.Consumed=false(height(obj.Rows),1);
            if isempty(obj.Rows) || any(obj.Rows.node~=4) || ...
                    any(~isfinite(obj.Rows.value)) || ...
                    any(~ismember(string(obj.Rows.purpose), ...
                    ["sync_threshold_db","header_uniform","payload_uniform"]))
                error('source5_receiver:DrawDomain','Invalid receiver draw tape.');
            end
            keys=string(obj.Rows.tx_id)+"/"+string(obj.Rows.interval_ordinal)+ ...
                "/"+string(obj.Rows.purpose);
            if numel(unique(keys))~=numel(keys) || ...
                    any(diff(double(obj.Rows.event_order))<=0) || ...
                    any(diff(double(obj.Rows.time_ns))<0)
                error('source5_receiver:DrawOrder','Duplicate or unordered PHY draw.');
            end
            regular=string(obj.Rows.purpose)~="sync_threshold_db";
            if any(obj.Rows.interval_ordinal(~regular)~=0) || ...
                    any(obj.Rows.interval_ordinal(regular)<1) || ...
                    any(obj.Rows.value(regular)<0 | obj.Rows.value(regular)>1)
                error('source5_receiver:DrawDomain','PHY draw component/domain differs.');
            end
            if any((string(obj.Rows.purpose(regular))=="header_uniform") ~= ...
                    (string(obj.Rows.component(regular))=="header")) || ...
                    any((string(obj.Rows.purpose(regular))=="payload_uniform") ~= ...
                    (string(obj.Rows.component(regular))=="payload"))
                error('source5_receiver:DrawComponent','Unlabeled BER draw.');
            end
        end
        function tf=owns(~,node)
            tf=double(node)==4;
        end
        function value=syncThreshold(obj,node,txId)
            value=obj.take(node,txId,0,"sync_threshold_db");
        end
        function value=uniform(obj,node,txId,ordinal,purpose)
            value=obj.take(node,txId,ordinal,string(purpose));
        end
        function verifyExhausted(obj)
            if any(~obj.Consumed)
                first=find(~obj.Consumed,1);
                error('source5_receiver:UnconsumedDraw', ...
                    'Unconsumed native PHY draw at event %g.',obj.Rows.event_order(first));
            end
        end
        function out=usage(obj)
            out=struct('captured',height(obj.Rows),'consumed',sum(obj.Consumed), ...
                'unused',sum(~obj.Consumed),'receiver',4);
        end
    end
    methods (Access=private)
        function value=take(obj,node,txId,ordinal,purpose)
            pick=find(obj.Rows.node==double(node) & ...
                obj.Rows.tx_id==double(txId) & ...
                obj.Rows.interval_ordinal==double(ordinal) & ...
                string(obj.Rows.purpose)==purpose);
            if numel(pick)~=1
                error('source5_receiver:MissingDraw', ...
                    'Missing node=%g TX=%g interval=%g component=%s draw.', ...
                    node,txId,ordinal,char(purpose));
            end
            index=pick(1);
            if obj.Consumed(index) || index~=find(~obj.Consumed,1)
                error('source5_receiver:DrawOrderMismatch', ...
                    'Native draw order differs at event %g.',obj.Rows.event_order(index));
            end
            if abs(round(obj.Clock()*1e9)-double(obj.Rows.time_ns(index)))>2
                error('source5_receiver:DrawTimeMismatch', ...
                    'Native PHY draw time differs at event %g.',obj.Rows.event_order(index));
            end
            obj.Consumed(index)=true;
            value=double(obj.Rows.value(index));
        end
    end
end
