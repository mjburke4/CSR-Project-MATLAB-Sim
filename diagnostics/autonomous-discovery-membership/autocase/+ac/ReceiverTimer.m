classdef ReceiverTimer < handle
    %RECEIVERTIMER Native integer-nanosecond relative targets and passive log.
    % No event or random draw is created by this helper. Continuous physical
    % signal geometry and the unchanged Model bit truncation remain separate.
    properties (SetAccess=private)
        Count = 0
        Omitted = 0
        MaxRecords = 200000
        MaxAbsShiftSeconds = 0
    end
    properties (Access=private)
        Data = {}
    end
    methods
        function obj=ReceiverTimer(maxRecords)
            if nargin>0
                validateattributes(maxRecords,{'double'},{'scalar','real','finite','integer','positive','<=',flintmax});
                obj.MaxRecords=maxRecords;
            end
        end
        function deadline=plan(obj,now,delay,node,purpose)
            [deadline,details]=ac.ReceiverTimer.target(now,delay);
            validateattributes(node,{'double'},{'scalar','real','finite','integer','nonnegative'});
            assert(ischar(purpose) && isrow(purpose) && ~isempty(purpose), ...
                'autocase:ReceiverTimerPurpose','Receiver timer requires a purpose name.');
            row=struct('NodeId',node,'Purpose',string(purpose),'NowSeconds',details.NowSeconds, ...
                'DelaySeconds',details.DelaySeconds,'NowNanoseconds',details.NowNanoseconds, ...
                'DelayNanoseconds',details.DelayNanoseconds,'TargetNanoseconds',details.TargetNanoseconds, ...
                'BaselineTargetSeconds',details.BaselineTargetSeconds,'TargetSeconds',deadline, ...
                'ShiftSeconds',details.ShiftSeconds);
            obj.Count=obj.Count+1;
            obj.MaxAbsShiftSeconds=max(obj.MaxAbsShiftSeconds,abs(details.ShiftSeconds));
            if numel(obj.Data)<obj.MaxRecords
                obj.Data{end+1}=row;
            else
                % Observation overflow cannot interrupt a mutated simulator.
                % The runner treats omitted timing evidence as incomplete.
                obj.Omitted=obj.Omitted+1;
            end
            ac.Trace.record(now,'relative_timer_target',node,row);
        end
        function result=snapshot(obj)
            if isempty(obj.Data)
                template=struct('NodeId',0,'Purpose',"",'NowSeconds',0,'DelaySeconds',0, ...
                    'NowNanoseconds',0,'DelayNanoseconds',0,'TargetNanoseconds',0, ...
                    'BaselineTargetSeconds',0,'TargetSeconds',0,'ShiftSeconds',0);
                records=struct2table(repmat(template,0,1));
            else
                records=struct2table([obj.Data{:}]);
            end
            result=struct('Count',obj.Count,'Omitted',obj.Omitted,'MaxRecords',obj.MaxRecords, ...
                'MaxAbsShiftSeconds',obj.MaxAbsShiftSeconds,'Records',records, ...
                'PolicyScope','Acquisition, rejected-return 28 ns, PHY TxUntil/finish and paired MAC finish use integer-nanosecond addition; generic MAC after remains unchanged. This supplements unchanged TransportTiming arrival/preamble/end plans. Physical geometry and Model allocation are unchanged. Records describe scheduling targets, not executed callbacks.', ...
                'ClockConversion','Exact integer tick sum divided by 1e9. Native GetSeconds fixed-point conversion can differ by 1 ULP at some other ticks; fixture arithmetic coverage is recorded separately.');
        end
    end
    methods (Static)
        function [deadline,details]=target(now,delay)
            validateattributes(now,{'double'},{'scalar','real','finite','nonnegative','<=',flintmax/1e9});
            validateattributes(delay,{'double'},{'scalar','real','finite','nonnegative','<=',flintmax/1e9});
            nowNs=round(now*1e9); delayNs=round(delay*1e9);
            assert(delayNs<=flintmax-nowNs,'autocase:ReceiverTimerRange', ...
                'Relative timer tick sum exceeds exact integer range.');
            targetNs=nowNs+delayNs; deadline=targetNs/1e9;
            baseline=now+delay;
            details=struct('NowSeconds',now,'DelaySeconds',delay,'NowNanoseconds',nowNs, ...
                'DelayNanoseconds',delayNs,'TargetNanoseconds',targetNs, ...
                'BaselineTargetSeconds',baseline,'TargetSeconds',deadline,'ShiftSeconds',deadline-baseline);
        end
    end
end
