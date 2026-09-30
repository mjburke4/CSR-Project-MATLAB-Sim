classdef TransportTiming < handle
    %TRANSPORTTIMING Optional, bounded receiver callback timing experiment.
    % Physical signal times and PHY/header/ECC formulas remain continuous.
    % This object schedules no events and owns no random stream. Empty
    % injection retains the previous production path without instrumentation.
    properties (SetAccess = private)
        Mode
        MaxRecords
        Count = 0
        MaxAbsShiftSeconds = 0
    end
    properties (Access = private)
        Data
        FrameIds
        Attached = false
    end
    methods
        function obj = TransportTiming(mode,maxRecords)
            if nargin<1, mode='continuous'; end
            if nargin<2, maxRecords=100000; end
            if isstring(mode) && isscalar(mode) && ~ismissing(mode), mode=char(mode); end
            if ~ischar(mode) || ~isrow(mode) || ~any(strcmp(mode,{'continuous','nanoseconds'}))
                error('csr:sim:TransportMode','Mode must be continuous or nanoseconds.');
            end
            validateattributes(maxRecords,{'double'},{'scalar','real','finite','integer','positive','<=',flintmax});
            obj.Mode=mode; obj.MaxRecords=maxRecords;
            capacity=min(1024,maxRecords);
            obj.Data=zeros(capacity,numel(obj.numericNames()));
            obj.FrameIds=zeros(capacity,1,'uint64');
        end
        function attach(obj)
            if obj.Attached || obj.Count~=0
                error('csr:sim:TransportReuse','Create a fresh timing object for each signal engine.');
            end
            obj.Attached=true;
        end
        function verifyCapacity(obj,count)
            validateattributes(count,{'double'},{'scalar','finite','integer','nonnegative'});
            if count>obj.MaxRecords-obj.Count
                error('csr:sim:TransportLimit','Transport timing record limit would be exceeded.');
            end
        end
        function plan = plan(obj,tx,propagation,duration,preamble,sourceId,receiverId,frameId)
            % Pure preflight: all receiver plans are validated before the
            % engine changes state, appends observations or schedules events.
            values={tx,propagation,duration,preamble};
            for k=1:4
                value=values{k};
                if ~isa(value,'double') || ~isscalar(value) || ~isreal(value) || ...
                        ~isfinite(value) || value<0 || value>flintmax/1e9
                    error('csr:sim:TransportTime','Times must be finite nonnegative scalar doubles within the exact nanosecond bound.');
                end
            end
            if duration<=0 || preamble<=0 || preamble>duration
                error('csr:sim:TransportTime','Require 0 < preamble duration <= packet duration.');
            end
            validateattributes(sourceId,{'double'},{'scalar','real','finite','integer','nonnegative','<=',flintmax});
            validateattributes(receiverId,{'double'},{'scalar','real','finite','integer','nonnegative','<=',flintmax});
            if isa(frameId,'double') && isscalar(frameId) && isreal(frameId) && ...
                    isfinite(frameId) && frameId>=0 && frameId<=flintmax && frameId==floor(frameId)
                frameId=uint64(frameId);
            end
            if ~isa(frameId,'uint64') || ~isscalar(frameId)
                error('csr:sim:TransportIdentity','Frame identity must be uint64 or an exactly representable nonnegative integer double.');
            end
            components=[tx propagation duration preamble];
            ns=round(components*1e9);
            if any(ns>flintmax) || ns(2)>flintmax-ns(1)
                error('csr:sim:TransportTime','Rounded component sum exceeds the exact integer bound.');
            end
            startNs=ns(1)+ns(2);
            if ns(3)>flintmax-startNs || ns(4)>flintmax-startNs
                error('csr:sim:TransportTime','Rounded component sum exceeds the exact integer bound.');
            end
            preambleNs=startNs+ns(4); endNs=startNs+ns(3);
            % Preserve the actual SignalEngine operand order, including its
            % binary64 residuals; the T15 controlled helper uses another order.
            physicalStart=tx+propagation;
            physicalPreamble=tx+propagation+preamble;
            physicalEnd=tx+propagation+duration;
            start=physicalStart; preambleEnd=physicalPreamble; finish=physicalEnd;
            if strcmp(obj.Mode,'nanoseconds')
                start=startNs/1e9; preambleEnd=preambleNs/1e9; finish=endNs/1e9;
            end
            if start<tx
                error('csr:sim:TransportPast','Rounded receive start would precede the actual transmit callback.');
            end
            if preambleEnd<start || finish<preambleEnd || finish<=start
                error('csr:sim:TransportOrder','Transport callback boundaries must preserve positive duration and ordering.');
            end
            plan=struct('SourceId',sourceId,'ReceiverId',receiverId,'FrameId',frameId, ...
                'TxSeconds',tx,'PropagationSeconds',propagation,'DurationSeconds',duration, ...
                'PreambleSeconds',preamble,'PhysicalStartSeconds',physicalStart, ...
                'PhysicalPreambleEndSeconds',physicalPreamble,'PhysicalEndSeconds',physicalEnd, ...
                'StartSeconds',start,'PreambleEndSeconds',preambleEnd,'EndSeconds',finish, ...
                'TxNanoseconds',ns(1),'PropagationNanoseconds',ns(2), ...
                'DurationNanoseconds',ns(3),'PreambleNanoseconds',ns(4), ...
                'StartNanoseconds',startNs,'PreambleEndNanoseconds',preambleNs,'EndNanoseconds',endNs, ...
                'StartShiftSeconds',start-physicalStart,'PreambleEndShiftSeconds',preambleEnd-physicalPreamble, ...
                'EndShiftSeconds',finish-physicalEnd);
        end
        function record(obj,plans)
            % Called once after a complete transmission's pure preflight.
            if ~iscell(plans), error('csr:sim:TransportPlan','Expected a cell array of receiver plans.'); end
            obj.verifyCapacity(double(numel(plans)));
            needed=obj.Count+numel(plans);
            if needed>size(obj.Data,1)
                capacity=min(obj.MaxRecords,max(needed,2*size(obj.Data,1)));
                obj.Data(capacity,numel(obj.numericNames()))=0;
                obj.FrameIds(capacity,1)=uint64(0);
            end
            names=obj.numericNames();
            for k=1:numel(plans)
                row=plans{k}; index=obj.Count+k;
                for j=1:numel(names), obj.Data(index,j)=row.(names{j}); end
                obj.FrameIds(index)=row.FrameId;
                obj.MaxAbsShiftSeconds=max(obj.MaxAbsShiftSeconds, ...
                    max(abs([row.StartShiftSeconds row.PreambleEndShiftSeconds row.EndShiftSeconds])));
            end
            obj.Count=needed;
        end
        function result = snapshot(obj)
            data=array2table(obj.Data(1:obj.Count,:),'VariableNames',obj.numericNames());
            Ordinal=uint64((1:obj.Count)'); FrameId=obj.FrameIds(1:obj.Count);
            records=[table(Ordinal),data(:,1:2),table(FrameId),data(:,3:end)];
            result=struct('Mode',obj.Mode,'Records',records,'Count',obj.Count,'Omitted',0, ...
                'MaxRecords',obj.MaxRecords,'MaxAbsShiftSeconds',obj.MaxAbsShiftSeconds, ...
                'PolicyScope',['Receiver callback start/preamble/end only; physical signal and header/ECC ' ...
                'formulas, TX/MAC completion, acquisition and scheduler defaults unchanged. ' ...
                'Optional receive intervals begin at the actual callback time. Off-grid past arrivals are rejected. ' ...
                'Records describe scheduled targets, including future targets; they do not establish callback execution.']);
        end
    end
    methods (Static, Access=private)
        function names = numericNames()
            names={'SourceId','ReceiverId','TxSeconds','PropagationSeconds','DurationSeconds', ...
                'PreambleSeconds','PhysicalStartSeconds','PhysicalPreambleEndSeconds','PhysicalEndSeconds', ...
                'StartSeconds','PreambleEndSeconds','EndSeconds','TxNanoseconds','PropagationNanoseconds', ...
                'DurationNanoseconds','PreambleNanoseconds','StartNanoseconds','PreambleEndNanoseconds', ...
                'EndNanoseconds','StartShiftSeconds','PreambleEndShiftSeconds','EndShiftSeconds'};
        end
    end
end
