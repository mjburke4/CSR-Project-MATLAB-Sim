classdef Streams < handle
    %STREAMS Source-bound validation provider. Only draws are external inputs.
    properties (SetAccess=private)
        Mode
        MappingVersion = 2
        FirstTimeDifference = []
        FirstMismatch = []
        Count = 0
    end
    properties (Access=private)
        Original
        Scheduler
        Cache
        Ordinals
        Consumed
        Native
        NativeRows
        TxRows
        TxExpected
        TxChecked = 0
        TxOrdinals
        TxMap
        Folder
        File = -1
    end
    methods
        function obj=Streams(seed,scheduler,mode,fixture,folder)
            obj.Mode=mode; obj.Scheduler=scheduler; obj.Folder=folder;
            obj.Original=csr.sim.RandomStreams(seed);
            obj.Cache=containers.Map('KeyType','char','ValueType','any');
            obj.Ordinals=containers.Map('KeyType','char','ValueType','double');
            obj.Consumed=containers.Map('KeyType','char','ValueType','double');
            obj.Native=containers.Map('KeyType','char','ValueType','double');
            obj.TxExpected=containers.Map('KeyType','double','ValueType','any');
            obj.TxOrdinals=containers.Map('KeyType','double','ValueType','double');
            obj.TxMap=containers.Map('KeyType','char','ValueType','double');
            obj.File=fopen(fullfile(folder,'random_requests.jsonl'),'w');
            assert(obj.File>=0,'autocase:DrawOpen','Cannot open random request trace.');
            if strcmp(mode,'native')
                opts=detectImportOptions(fixture,'TextType','string');
                obj.NativeRows=readtable(fixture,opts);
                required={'event_order','time_ns','node','purpose','ordinal','value','low','high','mean','variance','tx_id','interval_ordinal','component','bits','probability','rng_consumed'};
                assert(all(ismember(required,obj.NativeRows.Properties.VariableNames)), ...
                    'autocase:NativeSchema','Native random fixture has an unexpected schema.');
                txFixture=fullfile(fileparts(fixture),'tx_signatures.csv');
                txOptions=detectImportOptions(txFixture,'TextType','string');
                textColumns={'ack_bitmap_hex','dack_bitmap_hex','destination_sequences','payload_hex','packet_hex','routing_section_hex','snmp_nodes','discover_active_peers','discover_subtype','check_subtype'};
                textColumns=intersect(textColumns,txOptions.VariableNames);
                txOptions=setvartype(txOptions,textColumns,'string');
                obj.TxRows=readtable(txFixture,txOptions);
                requiredTx={'tx_id','child_index','app_attempt_index','app_generated_time_ns','app_flow_index', ...
                    'application_bytes','routing_section_hex','snmp_command','ack_bitmap_hex','dack_bitmap_hex', ...
                    'discover_subtype','discover_sequence','discover_active_peers', ...
                    'check_subtype','check_sequence','check_target','check_active'};
                assert(all(ismember(requiredTx,obj.TxRows.Properties.VariableNames)), ...
                    'autocase:TxSchema','Native TX fixture lacks required semantic lineage fields.');
                identities=unique(obj.TxRows.tx_id);
                for k=1:numel(identities)
                    obj.TxExpected(identities(k))=find(obj.TxRows.tx_id==identities(k));
                end
                for k=1:height(obj.NativeRows)
                    row=obj.NativeRows(k,:);
                    if ~logical(row.rng_consumed), continue; end
                    key=sprintf('%g:%s:%g',row.node,char(row.purpose),row.ordinal);
                    assert(~isKey(obj.Native,key),'autocase:DuplicateDraw','Duplicate native draw key.');
                    obj.Native(key)=k;
                end
            else
                assert(strcmp(mode,'natural'),'autocase:Mode','Unknown random mode.');
            end
        end
        function stream=get(obj,node,subsystem)
            if strcmp(subsystem,'mac')
                key=sprintf('%g:mac',node);
                if ~isKey(obj.Cache,key)
                    obj.Cache(key)=ac.MacStream(obj,node,obj.Original.get(node,subsystem));
                end
                stream=obj.Cache(key);
            else
                % Traffic is fixed-destination in this scenario, so its lazy
                % supplier is not called. PHY/SYNC use named seams below.
                stream=obj.Original.get(node,subsystem);
            end
        end
        function registerTx(obj,frame)
            node=double(frame.SourceId); ordinal=0;
            if isKey(obj.TxOrdinals,node), ordinal=obj.TxOrdinals(node); end
            ordinal=ordinal+1; obj.TxOrdinals(node)=ordinal;
            key=sprintf('%u',frame.Id); value=node*4294967296+ordinal;
            assert(~isKey(obj.TxMap,key),'autocase:TxIdentity','Duplicate local physical transmission ID.');
            if strcmp(obj.Mode,'native')
                rows=obj.TxRows([],:);
                if isKey(obj.TxExpected,value), rows=obj.TxRows(obj.TxExpected(value),:); end
                [actual,mismatches]=ac.TxSignature.compare(frame,rows);
                ac.Trace.record(obj.Scheduler.Now,'physical_tx_context',node, ...
                    struct('native_semantic_tx_id',value,'actual',actual, ...
                    'expected',{table2struct(rows)},'mismatches',{mismatches}));
                if ~isempty(mismatches)
                    obj.FirstMismatch=struct('node',node,'purpose','physical_tx','ordinal',ordinal, ...
                        'actual_time_s',obj.Scheduler.Now,'fields',{mismatches}, ...
                        'actual',actual,'expected',{table2struct(rows)});
                    ac.writeJson(fullfile(obj.Folder,'first_divergence.json'),obj.FirstMismatch);
                    error('autocase:TxContextDivergence', ...
                        'Physical transmission context diverged at %.17g s, node %g, TX #%g (%s).', ...
                        obj.Scheduler.Now,node,ordinal,strjoin(mismatches,','));
                end
                obj.TxChecked=obj.TxChecked+1;
            end
            obj.TxMap(key)=value;
            ac.Trace.record(obj.Scheduler.Now,'physical_tx_identity',node, ...
                struct('local_id',frame.Id,'native_semantic_tx_id',value,'source_tx_ordinal',ordinal));
        end
        function value=txId(obj,frame)
            key=sprintf('%u',frame.Id);
            assert(isKey(obj.TxMap,key),'autocase:TxIdentity','Unknown local physical transmission ID.');
            value=obj.TxMap(key);
        end
        function threshold=threshold(obj,node,profile,frame)
            details=struct('mean',profile.SyncSnrThresholdDb, ...
                'variance',profile.SyncSnrThresholdVarianceDb2,'tx_id',obj.txId(frame));
            if strcmp(obj.Mode,'natural')
                % Preserve original expression order, one original randn.
                normal=randn(obj.Original.get(node,'sync'));
                threshold=profile.SyncSnrThresholdDb+sqrt(profile.SyncSnrThresholdVarianceDb2)*normal;
                details.standard_normal=normal;
                obj.observe(node,'sync_threshold',threshold,details);
            else
                threshold=obj.take(node,'sync_threshold',details);
            end
        end
        function sampler=phy(obj,node,frame,ordinal,interval)
            context=struct('tx_id',obj.txId(frame),'interval_ordinal',ordinal, ...
                'interval_start_ns',round(interval.StartSec*1e9), ...
                'interval_end_ns',round(interval.EndSec*1e9));
            sampler=ac.PhySampler(obj,node,obj.Original.get(node,'phy'),context);
        end
        function observe(obj,node,purpose,value,details)
            ordinal=obj.next(node,purpose);
            obj.markConsumed(node,purpose);
            obj.log(node,purpose,ordinal,value,details,[],true);
        end
        function value=take(obj,node,purpose,details)
            ordinal=obj.next(node,purpose);
            key=sprintf('%g:%s:%g',node,purpose,ordinal);
            expected=[]; mismatches={};
            if ~isKey(obj.Native,key)
                mismatches={'missing_native_draw'};
            else
                expected=table2struct(obj.NativeRows(obj.Native(key),:));
                expected.purpose=char(expected.purpose); expected.component=char(expected.component);
                fields=fieldnames(details);
                for k=1:numel(fields)
                    name=fields{k};
                    % Request/interval times are endogenous diagnostics. Do
                    % not inject times or stop solely for timing differences.
                    if endsWith(name,'_ns') || strcmp(name,'reported_nodes') || ~isfield(expected,name), continue; end
                    actual=details.(name); wanted=expected.(name);
                    if ischar(actual) || isstring(actual)
                        equal=strcmp(char(actual),char(wanted));
                    elseif strcmp(name,'probability')
                        equal=abs(double(actual)-double(wanted))<=1e-12*max(abs(double(actual)),abs(double(wanted)));
                    else
                        equal=isequaln(double(actual),double(wanted));
                    end
                    if ~equal, mismatches{end+1}=name; end %#ok<AGROW>
                end
                delta=round(obj.Scheduler.Now*1e9)-expected.time_ns;
                if delta~=0 && isempty(obj.FirstTimeDifference)
                    obj.FirstTimeDifference=struct('node',node,'purpose',purpose,'ordinal',ordinal, ...
                        'actual_time_s',obj.Scheduler.Now,'expected_time_ns',expected.time_ns,'rounded_delta_ns',delta);
                end
            end
            if isempty(mismatches)
                value=expected.value; obj.markConsumed(node,purpose);
            else
                value=NaN;
            end
            obj.log(node,purpose,ordinal,value,details,expected,isempty(mismatches));
            if ~isempty(mismatches)
                obj.FirstMismatch=struct('node',node,'purpose',purpose,'ordinal',ordinal, ...
                    'actual_time_s',obj.Scheduler.Now,'fields',{mismatches}, ...
                    'actual',details,'expected',expected);
                ac.writeJson(fullfile(obj.Folder,'first_divergence.json'),obj.FirstMismatch);
                error('autocase:DrawContextDivergence', ...
                    'Native random request context diverged at %.17g s, node %g, %s #%g (%s). Partial evidence is preserved.', ...
                    obj.Scheduler.Now,node,purpose,ordinal,strjoin(mismatches,','));
            end
        end
        function output=summary(obj)
            used=keys(obj.Ordinals); nativeKeys=keys(obj.Native);
            nativeChannels=cell(size(nativeKeys));
            for k=1:numel(nativeKeys)
                fields=strsplit(nativeKeys{k},':'); nativeChannels{k}=strjoin(fields(1:2),':');
            end
            allChannels=sort(unique([used nativeChannels]));
            counts=struct('key',{},'requested',{},'consumed',{},'native_available',{},'unused',{});
            totalUnused=0;
            for k=1:numel(allChannels)
                key=allChannels{k}; prefix=[key ':']; count=sum(startsWith(nativeKeys,prefix));
                requested=0; if isKey(obj.Ordinals,key), requested=obj.Ordinals(key); end
                consumed=0; if isKey(obj.Consumed,key), consumed=obj.Consumed(key); end
                unused=count-consumed; totalUnused=totalUnused+max(0,unused);
                counts(end+1)=struct('key',key,'requested',requested,'consumed',consumed,'native_available',count,'unused',unused); %#ok<AGROW>
            end
            output=struct('mode',obj.Mode,'draw_count',obj.Count,'counts',counts, ...
                'native_unrequested_draws',totalUnused, ...
                'native_transmissions_available',obj.TxExpected.Count,'native_transmissions_checked',obj.TxChecked, ...
                'native_transmissions_unused',double(obj.TxExpected.Count)-obj.TxChecked, ...
                'native_tape_exhausted',strcmp(obj.Mode,'native') && totalUnused==0 && obj.TxChecked==obj.TxExpected.Count, ...
                'first_time_difference',obj.FirstTimeDifference,'first_context_mismatch',obj.FirstMismatch, ...
                'strict_context_matched',isempty(obj.FirstMismatch), ...
                'numeric_parity_established',false,'time_is_endogenous',true, ...
                'probability_absolute_tolerance',0,'probability_relative_tolerance',1e-12, ...
                'reported_population_gate','Recorded only; fixed native MAC profile 4 does not use this field');
        end
        function close(obj)
            if obj.File>=0, fclose(obj.File); obj.File=-1; end
        end
        function delete(obj), obj.close(); end
    end
    methods (Access=private)
        function markConsumed(obj,node,purpose)
            key=sprintf('%g:%s',node,purpose); count=0;
            if isKey(obj.Consumed,key), count=obj.Consumed(key); end
            obj.Consumed(key)=count+1;
        end
        function ordinal=next(obj,node,purpose)
            key=sprintf('%g:%s',node,purpose); ordinal=1;
            if isKey(obj.Ordinals,key), ordinal=obj.Ordinals(key)+1; end
            obj.Ordinals(key)=ordinal;
        end
        function log(obj,node,purpose,ordinal,value,actual,expected,matched)
            obj.Count=obj.Count+1;
            row=struct('time_s',obj.Scheduler.Now,'node',node,'purpose',purpose, ...
                'ordinal',ordinal,'value',value,'actual',actual,'expected',expected,'context_matched',matched);
            n=fprintf(obj.File,'%s\n',jsonencode(row));
            assert(n>0,'autocase:DrawWrite','Cannot write random request trace.');
            ac.Trace.record(obj.Scheduler.Now,'random_request',node,row);
        end
    end
end
