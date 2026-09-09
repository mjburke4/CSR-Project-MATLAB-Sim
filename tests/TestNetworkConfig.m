classdef TestNetworkConfig < matlab.unittest.TestCase
    % Configuration failures must be detected before autonomous work starts.
    methods (Test)
        function partialNestedOverridesRetainDefaultsWithoutInjectingPaths(test)
            config=csr.scenario.routedNetwork('autonomous');
            config.Nwk=struct('Neighbor',struct('AdmissionRetrySeconds',7), ...
                'Routing',struct('LocalInfo',struct('LinkMarginDbX10',80)), ...
                'Reassembly',struct('MaxMessagesPerPeer',4));
            config.Nodes=rmfield(config.Nodes,{'Capability','TransitForwardingEnabled'});
            config.Traffic=rmfield(config.Traffic,{'Dscp','AckRequired'});
            normalized=csr.scenario.validate(config); defaults=csr.nwk.defaults();
            test.verifyEqual(normalized.Stack,'network');
            test.verifyEqual(normalized.Nwk.Neighbor.AdmissionRetrySeconds,7);
            test.verifyEqual(normalized.Nwk.Neighbor.DiscoveryIntervalSeconds, ...
                defaults.Neighbor.DiscoveryIntervalSeconds);
            test.verifyEqual(normalized.Nwk.Routing.LocalInfo.LinkMarginDbX10,80);
            test.verifyEqual(normalized.Nwk.Routing.LocalInfo.MinSpeedKbps,8);
            test.verifyEqual(normalized.Nwk.Reassembly.MaxMessagesPerPeer,4);
            test.verifyEqual(normalized.Nwk.Reassembly.MaxMessages,defaults.Reassembly.MaxMessages);
            test.verifyEqual([normalized.Nodes.Capability],[1 1 1]);
            test.verifyTrue(all([normalized.Nodes.TransitForwardingEnabled]));
            test.verifyEqual(normalized.Traffic.Dscp,0); test.verifyTrue(normalized.Traffic.AckRequired);
            test.verifyFalse(isfield(normalized.Traffic,'Path'));
        end
        function acceptedIntegerStoragePreservesFractionalUnits(test)
            config=csr.scenario.routedNetwork('autonomous');
            config.Nwk.Neighbor.DiscoveryIntervalSeconds=uint8(5);
            config.Nwk.Routing.LocalInfo.MinPowerDbmX10=int16(7);
            config.Nwk.Routing.LocalInfo.MaxSpeedKbps=uint16(128);
            normalized=csr.scenario.validate(config);
            test.verifyEqual(0.25+normalized.Nwk.Neighbor.DiscoveryIntervalSeconds,5.25);
            test.verifyEqual(normalized.Nwk.Routing.LocalInfo.MinPowerDbmX10/10,0.7,'AbsTol',1e-12);
            test.verifyEqual(normalized.Nwk.Routing.LocalInfo.MaxSpeedKbps,128);
        end
        function networkDispatchUsesAutonomousStackWithNoTraffic(test)
            config=csr.scenario.routedNetwork('autonomous');
            config.DurationSeconds=0.01; config.Traffic.PacketCount=0;
            config.Nwk.StartupMode='manual'; config.Trace.Enabled=false;
            result=csr.runScenario(config);
            test.verifyTrue(isfield(result,'NodeNwkStatistics'));
            test.verifyTrue(isfield(result,'Routes')); test.verifyTrue(isfield(result,'Neighbors'));
            test.verifyEqual(height(result.NodeNwkStatistics),3);
            test.verifyEqual(result.Statistics.Generated,0);
            test.verifyEqual(result.Statistics.PhysicalTransmissions,0);
            test.verifyEqual(result.Metadata.ModelStage,'tranche-3-autonomous-network-routing');
        end
        function explicitPathsAndInvalidCapabilitiesAreRejected(test)
            config=csr.scenario.routedNetwork('autonomous');
            config.Traffic.Path=[3 2 1];
            test.verifyError(@()csr.scenario.validate(config),'csr:nwk:ExplicitPath');
            for invalid={-1,3,0.5,NaN,[0 1]}
                config=csr.scenario.routedNetwork('autonomous');
                config.Nodes(2).Capability=invalid{1}; verifyRejected(test,config);
            end
            config=csr.scenario.routedNetwork('autonomous');
            config.Nodes(2).Capability=0; % Source capability zero remains valid.
            normalized=csr.scenario.validate(config);
            test.verifyEqual([normalized.Nodes.Capability],[2 0 1]);
            test.verifyTrue(normalized.Nodes(2).TransitForwardingEnabled);
            config.Nodes(2).TransitForwardingEnabled=false;
            normalized=csr.scenario.validate(config);
            test.verifyFalse(normalized.Nodes(2).TransitForwardingEnabled);
            config.Nodes(2).TransitForwardingEnabled=2; verifyRejected(test,config);
        end
        function unknownNestedOptionsAndInvalidBooleansAreRejected(test)
            config=csr.scenario.routedNetwork('autonomous');
            config.Nwk.Neighbor.FreshnessTimeoutSecond=20;
            test.verifyError(@()csr.scenario.validate(config),'csr:nwk:InvalidConfig');
            config=csr.scenario.routedNetwork('autonomous');
            config.Nwk.Routing.LocalInfo.MinRate=8;
            test.verifyError(@()csr.scenario.validate(config),'csr:nwk:InvalidConfig');
            for invalid={struct('Reassembly',struct('MaxMesages',4)), ...
                    struct('AdaptiveLinkControl',2),struct('SendOnlyToGateway',NaN), ...
                    struct('Neighbor',[]),struct('StartupMode','periodic')}
                config=csr.scenario.routedNetwork('autonomous');
                config.Nwk=invalid{1}; verifyRejected(test,config);
            end
        end
        function linkEventsRequireExistingUniquePeersTimeAndBoolean(test)
            config=csr.scenario.routedNetwork('autonomous');
            config.LinkEvents=struct('TimeSeconds',uint16(10),'NodeIds',uint8([2;3]),'Enabled',false);
            normalized=csr.scenario.validate(config);
            test.verifyEqual(normalized.LinkEvents.NodeIds,[2 3]);
            test.verifyEqual(normalized.LinkEvents.TimeSeconds,10);
            test.verifyFalse(normalized.LinkEvents.Enabled);
            invalid={struct('TimeSeconds',10,'NodeIds',99,'Enabled',false), ...
                struct('TimeSeconds',10,'NodeIds',[2 2],'Enabled',false), ...
                struct('TimeSeconds',-1,'NodeIds',2,'Enabled',false), ...
                struct('TimeSeconds',301,'NodeIds',2,'Enabled',false), ...
                struct('TimeSeconds',NaN,'NodeIds',2,'Enabled',false), ...
                struct('TimeSeconds',10,'NodeIds',2,'Enabled',2), ...
                struct('TimeSeconds',10,'NodeIds',2,'Enabled',[true false])};
            for k=1:numel(invalid)
                config.LinkEvents=invalid{k}; verifyRejected(test,config);
            end
        end
        function discoveryEventsRequireExplicitValidRequestCoordinates(test)
            config=csr.scenario.routedNetwork('autonomous');
            config.DiscoveryEvents=struct('TimeSeconds',0,'NodeIds',[1;3]);
            normalized=csr.scenario.validate(config);
            test.verifyEqual(normalized.DiscoveryEvents.NodeIds,[1 3]);
            invalid={struct('TimeSeconds',10,'NodeIds',99), ...
                struct('TimeSeconds',10,'NodeIds',[1 1]), ...
                struct('TimeSeconds',10,'NodeIds',[]), ...
                struct('TimeSeconds',-1,'NodeIds',1), ...
                struct('TimeSeconds',Inf,'NodeIds',1), ...
                struct('TimeSeconds',301,'NodeIds',1), ...
                struct('TimeSeconds',10,'NodeIds',1,'Enabled',true)};
            for k=1:numel(invalid)
                config.DiscoveryEvents=invalid{k}; verifyRejected(test,config);
            end
        end
        function controlFaultFilterIsValidatedAndOldFiltersGainWildcard(test)
            config=csr.scenario.routedNetwork('control_loss');
            normalized=csr.scenario.validate(config);
            test.verifyEqual(normalized.Faults.Kind,'CONTROL');
            test.verifyEqual(normalized.Faults.ControlType,'ROUTING');
            config.Faults.ControlType='ROUTNG';
            test.verifyError(@()csr.scenario.validate(config),'csr:scenario:Faults');
            config=csr.scenario.routedNetwork('control_loss');
            config.Faults=rmfield(config.Faults,'ControlType'); config.Faults.Kind='ACK';
            normalized=csr.scenario.validate(config);
            test.verifyEqual(normalized.Faults.ControlType,'*');
            test.verifyEqual(normalized.Faults.Kind,'ACK');
        end
        function operatingInfoRejectsUnusableRatesAndInvertedLimits(test)
            invalid={struct('MinSpeedKbps',1000,'MaxSpeedKbps',8), ...
                struct('MinSpeedKbps',7),struct('MaxSpeedKbps',129), ...
                struct('MinPowerDbmX10',301,'MaxPowerDbmX10',300)};
            for k=1:numel(invalid)
                config=csr.scenario.routedNetwork('autonomous');
                config.Nwk=struct('Routing',struct('LocalInfo',invalid{k}));
                verifyRejected(test,config);
            end
            for rate=[500 1000]
                config=csr.scenario.routedNetwork(sprintf('high_rate_%d',rate));
                normalized=csr.scenario.validate(config);
                test.verifyEqual(normalized.Nwk.Routing.LocalInfo.MinSpeedKbps,rate);
                test.verifyEqual(normalized.Nwk.Routing.LocalInfo.MaxSpeedKbps,rate);
                test.verifyEqual(normalized.Traffic.RateKeyKbps,rate);
                test.verifyFalse(normalized.Nwk.AdaptiveLinkControl);
            end
        end
    end
end

function verifyRejected(test,config)
% Numeric validateattributes identifiers differ by violated constraint; the
% stable requirement is rejection during normalization, before any run starts.
rejected=false;
try
    csr.scenario.validate(config);
catch exception
    % Missing implementations or typoed method calls are not validation proof.
    rejected=(startsWith(exception.identifier,'csr:') || startsWith(exception.identifier,'MATLAB:')) && ...
        ~any(strcmp(exception.identifier,{'MATLAB:UndefinedFunction','MATLAB:nonExistentField', ...
        'MATLAB:noSuchMethodOrField'}));
    test.verifyTrue(rejected,sprintf('Unexpected normalization exception: %s',exception.identifier));
end
test.verifyTrue(rejected,'Invalid network configuration was accepted.');
end
