classdef ReplayStreams < handle
    %REPLAYSTREAMS Ordered per-node raw MAC draws for controlled validation.
    % Tape columns: node,ordinal,min,max,draw. The optional case column must
    % already be filtered to one case. Consumption times are observations,
    % not replay inputs. Unused suffixes are reported; exhaustion is fatal.
    properties (SetAccess = private)
        CaseName
    end
    properties (Access = private)
        Tape
        Clock
        Streams
        Consumed
        Rows
    end
    methods
        function obj = ReplayStreams(tape,clock,caseName)
            if nargin<3, caseName = 'test'; end
            if ~isa(clock,'function_handle')
                error('csr:validation:ReplayClock','Replay requires a simulation clock callback.');
            end
            if ~(ischar(caseName) && isrow(caseName)) && ...
                    ~(isstring(caseName) && isscalar(caseName))
                error('csr:validation:ReplayCase','Replay case must be a scalar name.');
            end
            required = {'node','ordinal','min','max','draw'};
            if ~istable(tape) || isempty(tape) || ~all(ismember(required,tape.Properties.VariableNames))
                error('csr:validation:ReplayTape','Replay requires a nonempty tape table.');
            end
            for n=1:numel(required)
                value = tape.(required{n});
                if ~isnumeric(value) || ~iscolumn(value) || ~isreal(value) || ...
                        any(~isfinite(value)) || any(fix(value)~=value)
                    error('csr:validation:ReplayTape','Tape values must be finite integer columns.');
                end
            end
            if any(tape.node<0 | tape.node>16777214 | tape.ordinal<1 | ...
                    tape.min<0 | tape.max>255 | tape.min>tape.max | ...
                    tape.draw<tape.min | tape.draw>tape.max)
                error('csr:validation:ReplayTape','Tape contains invalid IDs, ordinals or raw support.');
            end
            if ismember('case',tape.Properties.VariableNames) && ...
                    any(string(tape.('case'))~=string(caseName))
                error('csr:validation:ReplayCase','Filter the tape to the requested case.');
            end
            for node=reshape(unique(tape.node),1,[])
                ordinal = double(tape.ordinal(tape.node==node));
                if ~isequal(ordinal,(1:numel(ordinal))')
                    error('csr:validation:ReplayOrdinal','Each node tape must begin at one and have contiguous ordered ordinals.');
                end
            end
            obj.Tape = tape; obj.Clock = clock; obj.CaseName = char(caseName);
            obj.Streams = containers.Map('KeyType','double','ValueType','any');
            obj.Consumed = containers.Map('KeyType','double','ValueType','double');
            obj.Rows = repmat(struct('case','','node',0,'ordinal',0,'time_ns',0, ...
                'min',0,'max',0,'draw',0,'resolved',-1,'purpose','unresolved'),0,1);
        end
        function stream = get(obj,nodeId,subsystem)
            if ~(isnumeric(nodeId) && isscalar(nodeId) && isreal(nodeId) && ...
                    isfinite(nodeId) && nodeId>=0 && nodeId<=16777214 && fix(nodeId)==nodeId)
                error('csr:validation:ReplayNode','Replay node ID must be an unsigned 24-bit unicast ID.');
            end
            if ~(ischar(subsystem) && isrow(subsystem)) && ...
                    ~(isstring(subsystem) && isscalar(subsystem))
                error('csr:validation:ReplaySubsystem','Replay supports MAC scalar integer requests only.');
            end
            if ~strcmp(char(subsystem),'mac')
                error('csr:validation:ReplaySubsystem','Replay supports MAC scalar integer requests only.');
            end
            nodeId = double(nodeId);
            if ~any(obj.Tape.node==nodeId)
                error('csr:validation:ReplayNode','No explicit tape exists for this node.');
            end
            if ~isKey(obj.Streams,nodeId)
                obj.Streams(nodeId) = csr.validation.ReplayStream(obj,nodeId);
                obj.Consumed(nodeId) = 0;
            end
            stream = obj.Streams(nodeId);
        end
        function value = draw(obj,node,lower,upper)
            if ~isKey(obj.Consumed,node)
                error('csr:validation:ReplayNode','Obtain the cached MAC stream before drawing.');
            end
            ordinal = obj.Consumed(node)+1;
            selected = obj.Tape.node==node & obj.Tape.ordinal==ordinal;
            if ~any(selected)
                error('csr:validation:ReplayExhausted','Raw draw tape exhausted for node %d at ordinal %d.',node,ordinal);
            end
            entry = obj.Tape(selected,:);
            if entry.min~=lower || entry.max~=upper
                error('csr:validation:ReplaySupport','Requested support differs from the explicit tape at node %d ordinal %d.',node,ordinal);
            end
            time = obj.Clock();
            if ~(isnumeric(time) && isscalar(time) && isreal(time) && isfinite(time) && time>=0)
                error('csr:validation:ReplayClock','Simulation clock returned an invalid time.');
            end
            value = double(entry.draw); obj.Consumed(node) = ordinal;
            obj.Rows(end+1,1) = struct('case',obj.CaseName,'node',node, ...
                'ordinal',ordinal,'time_ns',round(double(time)*1e9), ...
                'min',lower,'max',upper,'draw',value,'resolved',-1,'purpose','unresolved');
        end
        function marked = resolve(obj,node,purpose,slot)
            % Called only after real production selection returns. No extra
            % draw or historicalSlot invocation occurs in this observer.
            marked = false;
            if isempty(obj.Rows), return; end
            index = find([obj.Rows.node]==node,1,'last');
            if isempty(index) || ~strcmp(obj.Rows(index).purpose,'unresolved'), return; end
            if ~any(strcmp(purpose,{'prepare','advertise'})) || ...
                    ~isnumeric(slot) || ~isscalar(slot) || ~isfinite(slot) || ...
                    fix(slot)~=slot || slot<0 || slot>255
                error('csr:validation:ReplayResolved','Invalid production slot observation.');
            end
            obj.Rows(index).resolved = double(slot);
            obj.Rows(index).purpose = char(purpose); marked = true;
        end
        function output = draws(obj), output = struct2table(obj.Rows); end
        function output = usage(obj)
            rows = repmat(struct('case',obj.CaseName,'node',0,'supplied',0,'consumed',0,'unused',0),0,1);
            for node=reshape(unique(obj.Tape.node),1,[])
                count = 0; if isKey(obj.Consumed,double(node)), count = obj.Consumed(double(node)); end
                supplied = sum(obj.Tape.node==node);
                rows(end+1,1) = struct('case',obj.CaseName,'node',double(node), ...
                    'supplied',supplied,'consumed',count,'unused',supplied-count); %#ok<AGROW>
            end
            output = struct2table(rows);
        end
    end
end
