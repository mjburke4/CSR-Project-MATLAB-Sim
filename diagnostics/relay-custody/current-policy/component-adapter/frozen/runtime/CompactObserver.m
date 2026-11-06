classdef CompactObserver < csr.sim.AckServiceDiagnostics
    % Passive aggregate observer. Raw service journal intentionally not captured.
    properties (SetAccess=private)
        Admissions=0
        Counts=struct('service',0,'decision',0,'transmission',0,'cancellation',0)
        Pending=[]
    end
    methods
        function obj=CompactObserver(stop)
            obj@csr.sim.AckServiceDiagnostics(0,[0 stop+1]);
        end
        function observeAdmission(obj,varargin),obj.Admissions=obj.Admissions+1;end
        function observeService(obj,varargin),obj.Counts.service=obj.Counts.service+1;end
        function observeDecision(obj,varargin),obj.Counts.decision=obj.Counts.decision+1;end
        function observeTransmission(obj,varargin),obj.Counts.transmission=obj.Counts.transmission+1;end
        function observeCancellation(obj,time,node,event,peer,seq,type,varargin)
            if endsWith(event,'_before')
                assert(isempty(obj.Pending));obj.Pending={time,node,peer,seq,type,strrep(event,'_before','_after')};
            else
                assert(isequaln(obj.Pending,{time,node,peer,seq,type,event}));obj.Pending=[];
            end
            obj.Counts.cancellation=obj.Counts.cancellation+1;
        end
        function assertComplete(obj),assert(isempty(obj.Pending));end
        function value=snapshot(obj,varargin)
            obj.assertComplete();s=struct('AdmissionRecords',obj.Admissions,'CallbackCounts',obj.Counts, ...
                'RawServiceCaptured',false,'FullServiceParityClaimed',false,'ScheduledEvents',0,'RandomDraws',0);
            value=struct('LinkDiagnostics',s,'ServiceDiagnostics',s,'LinkDecisionTrace',table(), ...
                'ActualFeedbackTrace',table(),'ServiceTrace',table());
        end
    end
end
