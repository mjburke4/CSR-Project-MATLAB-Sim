classdef ReplayLineageTap < handle
    % Review-only passive observer. No entrypoint, launcher, or model accessor.
    % Requires the original Autonomous6000Sink and qualified bounded writer.
    properties (SetAccess=private)
        Enabled
        Closed=false
        Faulted=false
        EndpointObserved=false
        CallbackOrdinal=uint64(0)
        Rows=0
        Attempted=0
        Filtered=0
        Counts=zeros(1,4)
    end
    properties (Access=private)
        Base
        Writer
        Identity
        Plan
        LastTime=-Inf
    end
    methods
        function obj=ReplayLineageTap(base,writer,identity,plan,enabled)
            assert(isa(base,'Autonomous6000Sink') && isscalar(base));
            assert(islogical(enabled) && isscalar(enabled));
            ReplayLineageTap.validateIdentity(identity);
            ReplayLineageTap.validatePlan(plan);
            initial=base.summary();
            assert(~initial.Closed && strcmp(initial.CallbackCount,'0'), ...
                'replayTap:LateInstall','Install before the first callback.');
            if enabled
                assert(isa(writer,'BoundedJsonlWriter') && isscalar(writer) && ~writer.Closed);
            else
                assert(isempty(writer),'replayTap:DisabledWriter','Disabled capture must own no sidecar writer.');
            end
            obj.Base=base;obj.Writer=writer;obj.Identity=identity;obj.Plan=plan;obj.Enabled=enabled;
        end

        function record(obj,time,kind,node,details)
            assert(~obj.Closed && ~obj.Faulted,'replayTap:Stopped','Closed or faulted tap cannot resume.');
            % The original sink always runs FIRST, exactly once. Its exclusive
            % endpoint and all pre-existing guards remain authoritative.
            try
                obj.Base.record(time,kind,node,details);
            catch problem
                if obj.Enabled && strcmp(problem.identifier,'naturalCausal:Endpoint') && ...
                        strcmp(kind,'scheduler_fire') && isequal(time,600)
                    obj.EndpointObserved=true;
                else
                    obj.Faulted=true;
                end
                rethrow(problem);
            end
            if ~obj.Enabled,return;end
            try
                assert(obj.CallbackOrdinal<intmax('uint64'),'replayTap:Ordinal','Callback ordinal exhausted.');
                obj.CallbackOrdinal=obj.CallbackOrdinal+uint64(1);
                validateattributes(time,{'double'},{'scalar','real','finite','nonnegative','<',600});
                assert(time>=obj.LastTime,'replayTap:Time','Callback time moved backwards.');
                obj.LastTime=time;
                kinds={'application_attempt','protocol','phy','physical_tx_identity'};
                category=find(strcmp(kind,kinds));
                if isempty(category),return;end
                assert(isscalar(category));
                obj.Attempted=obj.Attempted+1;
                % Bound the ORIGINAL value before inspecting/copying it.
                BoundedJsonlWriter.encodeBounded(details,obj.Plan.RecordLimits);
                keep=obj.selected(kind,details);
                if ~keep,obj.Filtered=obj.Filtered+1;return;end
                assert(obj.Rows<obj.Plan.MaxRows,'replayTap:Rows','Sidecar row cap exhausted; never truncate.');
                row=struct('schema','csr-replay-lineage-row-v1', ...
                    'case_id',obj.Identity.case_id,'seed',obj.Identity.seed,'rng_run',obj.Identity.rng_run, ...
                    'token',obj.Identity.token,'config_sha256',obj.Identity.config_sha256, ...
                    'row_ordinal',obj.Rows+1,'source_callback_ordinal',sprintf('%u',obj.CallbackOrdinal), ...
                    'time_s',time,'time_binary64_hex',num2hex(time),'kind',kind,'node',node, ...
                    'details',Autonomous6000Sink.exactIds(details));
                bytes=BoundedJsonlWriter.encodeBounded(row,obj.Plan.RecordLimits);
                obj.Writer.writeBytes(bytes);
                obj.Rows=obj.Rows+1;obj.Counts(category)=obj.Counts(category)+1;
            catch problem
                obj.Faulted=true;
                rethrow(problem);
            end
        end

        function close(obj)
            if obj.Closed,return;end
            first=[];
            if obj.Enabled
                try,obj.Writer.close();catch problem,obj.Faulted=true;first=problem;end
            end
            try,obj.Base.close();catch problem,obj.Faulted=true;if isempty(first),first=problem;end;end
            obj.Closed=true;
            if ~isempty(first),rethrow(first);end
        end

        function value=summary(obj)
            writerClosed=~obj.Enabled;
            if obj.Enabled,writerClosed=obj.Writer.Closed;end
            value=struct('schema','csr-replay-lineage-receipt-v1','identity',obj.Identity, ...
                'plan',obj.Plan,'enabled',obj.Enabled,'closed',obj.Closed,'faulted',obj.Faulted, ...
                'endpoint_observed',obj.EndpointObserved,'writer_closed',writerClosed, ...
                'source_callback_count',sprintf('%u',obj.CallbackOrdinal), ...
                'attempted',obj.Attempted,'emitted',obj.Rows,'filtered',obj.Filtered, ...
                'dropped',obj.Attempted-obj.Rows-obj.Filtered,'counts_by_kind',obj.Counts, ...
                'complete',obj.Enabled && obj.Closed && writerClosed && obj.EndpointObserved && ...
                    ~obj.Faulted && obj.Attempted==obj.Rows+obj.Filtered, ...
                'scope','Existing callbacks only; missing events are not refusal/loss evidence', ...
                'explicit_deferral_reason_coverage',false,'scientific_invariance_verified',false, ...
                'scheduled_events',0,'random_draws',0,'additional_model_state_reads',0);
        end
    end
    methods (Access=private)
        function keep=selected(obj,kind,details)
            if strcmp(kind,'physical_tx_identity')
                % All-node identity linkage is necessary for shared frames.
                keep=true;return;
            end
            if strcmp(kind,'application_attempt')
                assert(isstruct(details) && isscalar(details) && isfield(details,'SourceId'));
                source=ReplayLineageTap.nodeId(details.SourceId);
                assert(ismember(source,2:15),'replayTap:Source','Unexpected admission source.');
                keep=true;return;
            end
            assert(isstruct(details) && isscalar(details) && isfield(details,'event') && ...
                ischar(details.event) && isfield(details,'frame'));
            % Never confuse the radio sender with the application source.
            sources=ReplayLineageTap.applicationSources(details.frame,0);
            keep=any(ismember(sources,obj.Plan.ApplicationSources));
        end
    end
    methods (Static)
        function validateIdentity(v)
            assert(isstruct(v) && isscalar(v));
            assert(isequal(sort(fieldnames(v)),sort({'case_id';'seed';'rng_run';'token';'config_sha256'})));
            assert(isequal(v.case_id,'synthetic_three_relay15_i30_v1') && isequal(v.seed,10025) && isequal(v.rng_run,1));
            for name={'token','config_sha256'}
                x=v.(name{1});assert(ischar(x) && isrow(x) && numel(x)==64 && all(ismember(x,'0123456789abcdef')));
            end
        end

        function validatePlan(p)
            assert(isstruct(p) && isscalar(p));
            assert(isequal(sort(fieldnames(p)),sort({'Schema';'ApplicationSources';'MaxRows';'PayloadBytes';'RecordLimits'})));
            assert(strcmp(p.Schema,'csr-replay-lineage-plan-v1') && isequal(p.ApplicationSources,8:12));
            assert(isequal(p.MaxRows,65536) && isequal(p.PayloadBytes,16777216));
            assert(isequal(p.RecordLimits,struct('MaxNodes',65536,'MaxTextUnits',65536, ...
                'MaxDepth',32,'MaxEncodedBytes',262144)));
            BoundedJsonlWriter.validateLimits(p.RecordLimits);
        end

        function sources=applicationSources(frame,depth)
            assert(depth<=8,'replayTap:Shape','Frame nesting cap exhausted.');
            assert(isstruct(frame) && isscalar(frame),'replayTap:Shape','Unqualified frame shape.');
            if isfield(frame,'Segments')
                members=frame.Segments;
                assert(iscell(members) && isrow(members) && ...
                    ~isempty(members) && numel(members)<=1024, ...
                    'replayTap:Shape','Aggregate requires a bounded nonempty cell row of members.');
                sources=[];
                for k=1:numel(members)
                    sources=[sources ReplayLineageTap.applicationSources(members{k},depth+1)]; %#ok<AGROW>
                end
                return;
            end
            assert(~(isfield(frame,'Kind') && strcmp(frame.Kind,'AGGREGATE')), ...
                'replayTap:Shape','Aggregate kind without member cells is invalid.');
            if isfield(frame,'App')
                app=frame.App;
                if isempty(app) || (isstruct(app) && isscalar(app) && isempty(fieldnames(app)))
                    sources=[];return;
                end
                assert(isstruct(app) && isscalar(app) && isfield(app,'Id') && isfield(app,'SourceId'), ...
                    'replayTap:Shape','Unqualified embedded application shape.');
                sources=ReplayLineageTap.nodeId(app.SourceId);return;
            end
            if all(isfield(frame,{'Id','SourceId','DestinationId','ApplicationPayloadBytes'}))
                sources=ReplayLineageTap.nodeId(frame.SourceId);return;
            end
            % Known non-application protocol records (e.g. neighbor events)
            % carry no packet. They are outside this packet-lineage sidecar.
            assert(~isfield(frame,'Kind') || any(strcmp(frame.Kind,{'ACK','DACK','CONTROL'})), ...
                'replayTap:Shape','Unknown packet shape cannot be silently filtered.');
            sources=[];
        end

        function n=nodeId(n)
            assert(isnumeric(n) && ~islogical(n) && isscalar(n) && isreal(n) && ...
                isfinite(n) && n==fix(n) && n>=1 && n<=15,'replayTap:Source','Invalid application source.');
            n=double(n);
        end
    end
end
