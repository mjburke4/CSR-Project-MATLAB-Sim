classdef Fixture
    %FIXTURE Typed native CSV import and purpose-specific field validation.
    % Blank text is valid only outside a field's required row scope, or for
    % an explicitly empty list. It is normalized to "", never a fabricated
    % component, control type, numeric zero, or random value.
    methods (Static)
        function rows=readRandom(path)
            textFields={'purpose','component','state','cause'};
            required={'event_order','time_ns','node','purpose','ordinal','value','low','high', ...
                'mean','variance','tx_id','interval_ordinal','component','interval_start_ns', ...
                'interval_end_ns','component_start_ns','component_end_ns','bits','probability', ...
                'rng_consumed','active_nodes','reported_nodes','reservation_counter', ...
                'reservation_slot','profile','state','cause'};
            rows=ac.Fixture.readTyped(path,textFields,required);
            ac.Fixture.validateRandom(rows);
        end
        function rows=readTx(path)
            textFields={'ack_bitmap','dack_bitmap','ack_bitmap_hex','dack_bitmap_hex', ...
                'destination_sequences','payload_hex','packet_hex','routing_section_hex', ...
                'routing_section_origin','snmp_nodes','discover_active_peers','discover_subtype', ...
                'check_subtype','control_payload_origin'};
            required={'tx_id','time_ns','event_order','source','source_tx_ordinal','rate_kbps', ...
                'tx_power_dbm','preamble','reservation_slot','child_count','total_wire_bytes', ...
                'child_index','hop_source','hop_destination','hop_sequence','kind','wire_bytes', ...
                'dscp','ackable','has_ack_window','ack_bitmap_hex','dack_bitmap_hex', ...
                'destination_sequences','network_source','network_destination','network_dscp', ...
                'application_bytes','app_attempt_index','app_flow_index','app_generated_time_ns', ...
                'routing_section_hex','snmp_command','snmp_source','snmp_destination','snmp_value', ...
                'snmp_nodes','discover_subtype','discover_sequence','discover_active_peers', ...
                'check_subtype','check_sequence','check_target','check_active'};
            rows=ac.Fixture.readTyped(path,textFields,required);
            ac.Fixture.validateTx(rows);
        end
        function validateRandom(rows)
            ac.Fixture.need(rows,{'event_order','time_ns','node','purpose','ordinal','value','rng_consumed'});
            assert(all(ismember(rows.purpose,["mac_slot","sync_threshold","phy_binomial"])), ...
                'autocase:FixturePurpose','Unsupported native random purpose.');
            assert(all(rows.rng_consumed==1),'autocase:FixtureConsumption', ...
                'This fixture contract contains consumed random samples only.');
            for purpose=["mac_slot","sync_threshold","phy_binomial"]
                part=rows(rows.purpose==purpose,:);
                if isempty(part), continue; end
                switch purpose
                    case "mac_slot"
                        ac.Fixture.need(part,{'low','high','active_nodes','reported_nodes', ...
                            'reservation_counter','reservation_slot','profile','state'});
                        assert(all(part.component==""),'autocase:FixtureComponent', ...
                            'MAC samples must not have a PHY component.');
                        assert(all(part.value==floor(part.value) & part.value>=part.low & part.value<=part.high), ...
                            'autocase:FixtureInteger','Invalid native integer draw.');
                    case "sync_threshold"
                        ac.Fixture.need(part,{'mean','variance','tx_id'});
                        assert(all(part.component==""),'autocase:FixtureComponent', ...
                            'SYNC samples must not have a PHY component.');
                        assert(all(part.variance>=0),'autocase:FixtureVariance','Invalid normal variance.');
                    case "phy_binomial"
                        ac.Fixture.need(part,{'tx_id','interval_ordinal','component', ...
                            'interval_start_ns','interval_end_ns','component_start_ns', ...
                            'component_end_ns','bits','probability'});
                        assert(all(ismember(part.component,["header","payload"])), ...
                            'autocase:FixtureComponent','A PHY sample requires header or payload.');
                        assert(all(part.bits>0 & part.bits==floor(part.bits) & ...
                            part.probability>0 & part.probability<1 & part.value>=0 & part.value<=1), ...
                            'autocase:FixtureUniform','Invalid consumed PHY sample.');
                end
            end
        end
        function validateTx(rows)
            ac.Fixture.need(rows,{'tx_id','time_ns','event_order','source','source_tx_ordinal', ...
                'rate_kbps','tx_power_dbm','preamble','reservation_slot','child_count', ...
                'total_wire_bytes','child_index','hop_source','hop_destination','hop_sequence', ...
                'kind','wire_bytes','dscp','ackable','has_ack_window','ack_bitmap_hex','dack_bitmap_hex'});
            for name={'ack_bitmap_hex','dack_bitmap_hex'}
                values=rows.(name{1});
                assert(all(~cellfun('isempty',regexp(cellstr(values),'^[0-9a-fA-F]{16}$','once'))), ...
                    'autocase:FixtureBitmap','Each bitmap requires exactly sixteen hexadecimal digits.');
            end
            ac.Fixture.need(rows(rows.kind==0,:),{'network_source','network_destination', ...
                'network_dscp','application_bytes','app_attempt_index','app_flow_index','app_generated_time_ns'});
            ac.Fixture.need(rows(rows.kind==4,:),{'discover_subtype','discover_sequence'});
            ac.Fixture.need(rows(rows.kind==5,:),{'check_subtype','check_sequence'});
            ac.Fixture.need(rows(rows.kind==5 & rows.check_subtype=="discovery",:),{'check_active'});
            ac.Fixture.need(rows(rows.kind==5 & rows.check_subtype=="no_path",:),{'check_target'});
            ac.Fixture.need(rows(rows.kind==6,:),{'routing_section_hex'});
            ac.Fixture.need(rows(rows.kind==7,:),{'snmp_command','snmp_source','snmp_destination','snmp_value'});
            % Empty target lists, peer sets and SNMP node lists are valid.
            % Required per-kind scalar fields above may never be blank/NaN.
        end
    end
    methods (Static, Access=private)
        function rows=readTyped(path,textFields,required)
            opts=detectImportOptions(path,'TextType','string');
            assert(all(ismember(required,opts.VariableNames)), ...
                'autocase:FixtureSchema','Native fixture is missing a required column: %s.',path);
            textFields=intersect(textFields,opts.VariableNames);
            opts=setvartype(opts,textFields,'string');
            numericFields=setdiff(opts.VariableNames,textFields);
            opts=setvartype(opts,numericFields,'double');
            rows=readtable(path,opts);
            for k=1:numel(textFields)
                name=textFields{k}; values=rows.(name);
                values(ismissing(values))=""; rows.(name)=values;
            end
        end
        function need(rows,names)
            for k=1:numel(names)
                name=names{k};
                assert(ismember(name,rows.Properties.VariableNames),'autocase:FixtureSchema', ...
                    'Missing required native field %s.',name);
                value=rows.(name);
                if isstring(value)
                    okay=all(~ismissing(value) & strlength(value)>0);
                else
                    okay=isnumeric(value) && all(isfinite(value));
                end
                assert(okay,'autocase:FixtureRequired','Missing or invalid required native field %s.',name);
            end
        end
    end
end
