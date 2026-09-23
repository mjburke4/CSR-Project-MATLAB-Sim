classdef DrawTape < handle
    %DRAWTAPE Exact native uniform inputs, scoped by signal/interval/phase.
    % A mismatch stops the run. It never invents a replacement random draw.
    properties (SetAccess=private)
        UsedCount=0
        Rows
        Failure=struct()
    end
    properties (Access=private)
        Index
        Used
        Signal=0
        StartNs=0
        EndNs=0
    end
    methods
        function obj=DrawTape(path)
            obj.Rows=readtable(path,'TextType','string','VariableNamingRule','preserve');
            obj.Index=containers.Map('KeyType','char','ValueType','double');
            obj.Used=false(height(obj.Rows),1);
            for k=1:height(obj.Rows)
                r=obj.Rows(k,:);
                key=obj.key(r.signal_id,r.interval_start_ns,r.interval_end_ns,char(r.phase));
                if isKey(obj.Index,key), error('receiver_replay:DuplicateDraw','Duplicate draw key %s.',key); end
                obj.Index(key)=k;
            end
        end
        function beginInterval(obj,signal,startSec,endSec)
            obj.Signal=signal; obj.StartNs=round(startSec*1e9); obj.EndNs=round(endSec*1e9);
        end
        function errors=draw(obj,phase,bits,probability)
            if bits==0 || probability<=0, errors=0; return; end
            if probability>=1, errors=bits; return; end
            key=obj.key(obj.Signal,obj.StartNs,obj.EndNs,phase);
            obj.Failure=struct('signal_id',obj.Signal,'interval_start_ns',obj.StartNs, ...
                'interval_end_ns',obj.EndNs,'phase',phase,'bits',bits,'probability',probability);
            if ~isKey(obj.Index,key)
                error('receiver_replay:MissingDraw','No common random input for %s; receiver interval ordering has diverged.',key);
            end
            k=obj.Index(key); row=obj.Rows(k,:);
            obj.Failure.reference_bits=row.bits; obj.Failure.reference_probability=row.probability;
            if obj.Used(k), error('receiver_replay:ReusedDraw','Draw %s consumed twice.',key); end
            if bits~=row.bits || abs(probability-row.probability)>max(1e-18,1e-10*abs(row.probability))
                error('receiver_replay:DrawContext','Different bit/BER context at %s: bits %.0f/%.0f, p %.17g/%.17g.', ...
                    key,bits,row.bits,probability,row.probability);
            end
            u=row.uniform;
            validateattributes(u,{'numeric'},{'scalar','finite','>=',0,'<=',1});
            obj.Used(k)=true; obj.UsedCount=obj.UsedCount+1;
            errors=csr.phy.Model.sampleSourceBinomial(bits,probability,u);
            obj.Failure=struct();
        end
        function table=usage(obj)
            table=obj.Rows; table.used=obj.Used;
        end
    end
    methods (Static,Access=private)
        function value=key(signal,startNs,endNs,phase)
            value=sprintf('%.0f:%.0f:%.0f:%s',signal,startNs,endNs,phase);
        end
    end
end
