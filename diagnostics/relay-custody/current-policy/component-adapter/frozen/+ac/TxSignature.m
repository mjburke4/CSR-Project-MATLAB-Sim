classdef TxSignature
    %TXSIGNATURE Semantic physical transmission identity, independent of IDs.
    methods (Static)
        function [actual,mismatches]=compare(frame,rows)
            if isfield(frame,'Segments') && ~isempty(frame.Segments)
                children=frame.Segments;
            else
                children={frame};
            end
            actual=struct('source',double(frame.SourceId),'rate_kbps',double(frame.RateKeyKbps), ...
                'tx_power_dbm',double(frame.TxPowerDbm),'preamble',double(strcmp(frame.Preamble,'long')), ...
                'reservation_slot',double(frame.ReservationSlot),'child_count',numel(children), ...
                'total_wire_bytes',double(frame.WirePayloadBytes),'children',{{}});
            mismatches={};
            if isempty(rows), mismatches={'missing_native_transmission'}; return; end
            parent=table2struct(rows(1,:)); fields=fieldnames(actual);
            for k=1:numel(fields)
                name=fields{k}; if strcmp(name,'children'), continue; end
                if ~isequaln(actual.(name),double(parent.(name)))
                    mismatches{end+1}=['parent.' name]; %#ok<AGROW>
                end
            end
            if height(rows)~=numel(children)
                mismatches{end+1}='ordered_child_count'; return;
            end
            for k=1:numel(children)
                child=children{k}; wanted=table2struct(rows(k,:));
                item=struct('child_index',k-1,'hop_source',double(child.SourceId), ...
                    'hop_destination',double(child.DestinationId),'hop_sequence',double(child.Sequence), ...
                    'kind',ac.TxSignature.kind(child),'wire_bytes',double(child.WirePayloadBytes), ...
                    'dscp',double(child.Dscp),'ackable',double(child.AckRequired), ...
                    'has_ack_window',double(child.HasAckWindow), ...
                    'ack_bitmap_hex',lower(dec2hex(child.AckBitmap,16)), ...
                    'dack_bitmap_hex',lower(dec2hex(child.DackBitmap,16)));
                if strcmp(child.Kind,'DATA')
                    item.network_source=double(child.App.SourceId);
                    item.network_destination=double(child.App.DestinationId);
                    item.network_dscp=double(child.App.Dscp);
                    item.application_bytes=double(child.App.ApplicationPayloadBytes);
                    item.app_generated_time_ns=round(double(child.App.GeneratedSeconds)*1e9);
                    assert(all(isfield(child.App,{'FlowOrdinal','FlowIndex'})), ...
                        'autocase:AppLineage','Missing source application attempt identity.');
                    item.app_attempt_index=double(child.App.FlowOrdinal);
                    item.app_flow_index=double(child.App.FlowIndex)-1;
                end
                targets='';
                if isfield(child,'DestinationIds') && numel(child.DestinationIds)>0
                    entries=cell(1,numel(child.DestinationIds));
                    for j=1:numel(entries), entries{j}=sprintf('%g:%g',child.DestinationIds(j),child.HopSequences(j)); end
                    targets=strjoin(entries,';');
                end
                if ~ismissing(wanted.destination_sequences) && strlength(wanted.destination_sequences)>0
                    item.destination_sequences=targets;
                elseif isfield(child,'DestinationIds') && numel(child.DestinationIds)>1
                    mismatches{end+1}=sprintf('child%d.unexpected_group',k); %#ok<AGROW>
                end
                if strcmp(child.Kind,'CONTROL')
                    item.control_type=child.Control.Type;
                    item.control_payload=child.Control.Payload;
                    if strcmp(child.Control.Type,'DISCOVER')
                        item.discover_subtype=char(child.Control.Payload.Subtype);
                        if strcmp(item.discover_subtype,'broadcast')
                            item.discover_sequence=double(child.Control.Payload.Sequence);
                        end
                        item.discover_active_peers='';
                        peers=sort(double(child.Control.Payload.ActivePeers));
                        if ~isempty(peers)
                            item.discover_active_peers=strjoin(arrayfun(@(n)sprintf('%g',n),peers,'UniformOutput',false),';');
                        end
                    end
                    if strcmp(child.Control.Type,'NEIGHBOR_CHECK')
                        item.check_subtype=char(child.Control.Payload.Subtype);
                        item.check_sequence=double(child.Control.Payload.Sequence);
                        if strcmp(item.check_subtype,'no_path')
                            item.check_target=double(child.Control.Payload.TargetId);
                        end
                        if strcmp(item.check_subtype,'discovery')
                            item.check_active=double(child.Control.Payload.Active);
                        end
                    end
                    if strcmp(child.Control.Type,'ROUTING')
                        item.routing_section_hex=lower(reshape(dec2hex(uint8(child.Control.Payload.Bytes),2).',1,[]));
                    end
                    if isfield(wanted,'snmp_command') && any(strcmp(child.Control.Type,{'SNMP_START','SNMP_DONE'}))
                        item.snmp_command=1+double(strcmp(child.Control.Type,'SNMP_DONE'));
                        item.snmp_source=double(child.Control.Payload.SourceId);
                        item.snmp_destination=double(child.Control.Payload.DestinationId);
                        item.snmp_value=0;
                        if isfield(child.Control.Payload,'DelaySeconds'), item.snmp_value=double(child.Control.Payload.DelaySeconds); end
                        item.snmp_nodes='';
                        if isfield(child.Control.Payload,'Nodes') && ~isempty(child.Control.Payload.Nodes)
                            item.snmp_nodes=strjoin(arrayfun(@(n)sprintf('%g',n),child.Control.Payload.Nodes,'UniformOutput',false),';');
                        end
                    end
                end
                fields=fieldnames(item);
                for j=1:numel(fields)
                    name=fields{j};
                    if endsWith(name,'_ns') || ~isfield(wanted,name), continue; end
                    supplied=item.(name); expected=wanted.(name);
                    if isnumeric(supplied)
                        equal=isequaln(double(supplied),double(expected));
                    else
                        if isstring(expected) && ismissing(expected), expected=''; end
                        if strcmp(name,'discover_active_peers') && strlength(string(expected))>0
                            peers=sort(str2double(strsplit(char(expected),';')));
                            expected=strjoin(arrayfun(@(n)sprintf('%g',n),peers,'UniformOutput',false),';');
                        end
                        equal=strcmp(char(supplied),char(expected));
                    end
                    if ~equal, mismatches{end+1}=sprintf('child%d.%s',k,name); end %#ok<AGROW>
                end
                actual.children{end+1}=item;
            end
        end
        function value=kind(frame)
            switch frame.Kind
                case 'DATA', value=0;
                case 'ACK', value=1;
                case 'DACK', value=2;
                case 'CONTROL'
                    switch frame.Control.Type
                        case 'DISCOVER', value=4;
                        case 'NEIGHBOR_CHECK', value=5;
                        case 'ROUTING', value=6;
                        case {'SNMP_START','SNMP_DONE'}, value=7;
                        case 'KEY_REQUEST', value=8;
                        case 'KEY_UPDATE', value=9;
                        otherwise, error('autocase:ControlKind','Unsupported control kind.');
                    end
                otherwise, error('autocase:ChildKind','Unsupported child kind.');
            end
        end
    end
end
