classdef ControlWireProbe < handle
    %CONTROLWIREPROBE Public NWK callback recorder with real HOP frame creation.
    properties
        Layer
        Scheduler
        NodeId = 1
        Accept = true
        Calls = {}
    end
    methods
        function accepted=send(obj,control,peers,options)
            sequence=uint16(numel(obj.Calls)+1);
            frame=csr.hop.Frames.control(control,obj.NodeId,peers, ...
                repmat(sequence,size(peers)),options);
            accepted=logical(obj.Accept);
            obj.Calls{end+1}=struct('control',control,'peers',peers,'options',options, ...
                'frame',frame,'time_s',obj.Scheduler.Now,'accepted',accepted);
        end
        function row=last(obj,kind,subtype)
            for k=numel(obj.Calls):-1:1
                row=obj.Calls{k};
                if ~strcmp(row.control.Type,kind), continue; end
                if nargin>2 && (~isfield(row.control.Payload,'Subtype') || ...
                        ~strcmp(row.control.Payload.Subtype,subtype)), continue; end
                return
            end
            error('autocase:ControlWirePreflight','Expected public %s callback was not observed.',kind);
        end
        function rows=requests(obj)
            rows={};
            for k=1:numel(obj.Calls)
                row=obj.Calls{k}; payload=row.control.Payload;
                if strcmp(row.control.Type,'ROUTING') && isfield(payload,'WireRepresentation') && ...
                        strcmp(payload.WireRepresentation,'legacy_request_header')
                    rows{end+1}=row; %#ok<AGROW>
                end
            end
        end
        function activatePeer(obj,peer)
            % Same public callback boundary used by reliable HOP completion;
            % no private neighbor state or successful RF receive is invented.
            obj.Layer.receiveControl(struct('Type','KEY_UPDATE','Payload',struct('Generation',0)),peer);
            obj.Scheduler.run(0); own=obj.last('KEY_UPDATE');
            obj.Layer.controlResult(own.control,peer,true,true,[]);
            obj.Scheduler.run(0); own=obj.last('NEIGHBOR_CHECK','overheard');
            obj.Layer.controlResult(own.control,peer,true,true,[]);
            obj.Scheduler.run(0);
            peers=obj.Layer.neighborsSnapshot(); peerState=peers([peers.PeerId]==peer);
            assert(isscalar(peerState) && peerState.Active, ...
                'autocase:ControlWirePreflight','Public proof completion did not activate the peer.');
        end
    end
    methods (Static)
        function [layer,clock,probe]=fixture(config,transitEnabled)
            config.Nodes([config.Nodes.Id]==1).TransitForwardingEnabled=logical(transitEnabled);
            clock=csr.sim.EventScheduler(500); probe=ac.ControlWireProbe(); probe.Scheduler=clock;
            callbacks=struct('SendControl',@(control,peers,options)probe.send(control,peers,options), ...
                'CanSendControl',@(peers)true);
            streams=csr.sim.RandomStreams(config.Seed);
            layer=ac.DiscoveryMembershipNwk(1,clock,streams,config,callbacks); probe.Layer=layer;
        end
    end
end
