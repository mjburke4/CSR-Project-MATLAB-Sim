classdef TestQueuedRetryPolicy < matlab.unittest.TestCase
    % Controlled MAC callbacks isolate DATA retry custody from PHY outcomes.
    methods (Test)
        function defaultsAndExplicitActualTxProduceSameEvidence(test)
            a=exerciseDefault(struct());
            b=exerciseDefault(struct('DataQueuedRetryPolicy','actual-tx'));
            test.verifyEqual(csr.hop.Layer.defaults().DataQueuedRetryPolicy,'actual-tx');
            test.verifyEqual(a,b);
        end
        function policyValidationAcceptsOnlyDocumentedScalars(test)
            c=csr.hop.validateConfig(struct('Hop',struct( ...
                'DataQueuedRetryPolicy',"native-provisional")));
            test.verifyEqual(c.Hop.DataQueuedRetryPolicy,'native-provisional');
            for value={42,{},'',{'actual-tx'},["actual-tx" "native-provisional"], ...
                    'native','Actual-Tx',char('actual-tx','actual-tx')}
                config=struct('DataQueuedRetryPolicy',{value{1}});
                test.verifyError(@()harness(config),'csr:hop:InvalidConfig');
                test.verifyError(@()csr.hop.validateConfig(struct('Hop',config)), ...
                    'csr:hop:InvalidConfig');
            end
        end
        function initialQueuedDataNeverExpiresUnderExternalScans(test)
            for policy=policies()
                h=harness(struct('DataQueuedRetryPolicy',policy{1}));
                test.assertTrue(h.Hop.send(packet(1,4),2));
                controlScan(h,0,50); h.Clock.run(2.1);
                controlScan(h,5,51); h.Clock.run(20);
                test.verifyEqual(h.Hop.stats().Retransmissions,0);
                test.verifyEqual(h.Hop.stats().Failed,0);
                test.verifyEqual(h.Hop.PendingDataCount,1);
                test.verifyEmpty(h.Releases());
            end
        end
        function retryEnqueueDoesNotInstallItsOwnTimer(test)
            h=harness(struct('DataQueuedRetryPolicy','native-provisional'));
            [~,frame]=h.Hop.send(packet(1,4),2); h.Hop.notifySent(frame);
            h.Clock.run(100);
            test.verifyEqual(h.Hop.stats().Retransmissions,1);
            test.verifyEqual(h.Hop.stats().Failed,0);
            test.verifyEqual(h.Clock.PendingCount,0);
            test.verifyEqual(h.Hop.PendingDataCount,1);
        end
        function anotherActualTransmitScanAdvancesOnlyNativeQueuedRetry(test)
            for policy=policies()
                h=harness(struct('DataQueuedRetryPolicy',policy{1}));
                [~,frame]=h.Hop.send(packet(1,4),2,struct('Dscp',5));
                h.Hop.notifySent(frame); h.Clock.run(2.1);
                controlScan(h,3,50); h.Clock.run(5.1);
                expected=1+strcmp(policy{1},'native-provisional');
                test.verifyEqual(h.Hop.stats().Retransmissions,expected);
                data=h.DataFrames(); test.verifyNumElements(data,1+expected);
                test.verifyEqual(data{end}.Sequence,frame.Sequence);
                test.verifyEqual(data{end}.Dscp,5);
                test.verifyEqual(data{end}.RetryCount,expected);
                test.verifyEmpty(h.Releases());
            end
        end
        function finalQueuedExpiryReleasesCapacityForEitherFlowOrigin(test)
            % The reopened window accepts whichever NWK flow is served next.
            % This neither adds nor asserts a local-versus-relay preference.
            for origin=[1 4]
                for policy=policies()
                    h=harness(struct('DataQueuedRetryPolicy',policy{1}, ...
                        'MaxResends',1,'PendingThreshold',0));
                    [~,frame]=h.Hop.send(packet(1,4),2); h.Hop.notifySent(frame);
                    h.Clock.run(2.1);
                    test.verifyFalse(h.Hop.send(packet(2,origin),2));
                    controlScan(h,5,50); h.Clock.run(7.1);
                    native=strcmp(policy{1},'native-provisional');
                    test.verifyEqual(h.Hop.stats().Failed,double(native));
                    test.verifyEqual(h.Hop.PendingDataCount,1-double(native));
                    test.verifyNumElements(h.Releases(),double(native));
                    test.verifyEqual(h.Hop.send(packet(3,origin),2),native);
                    if native
                        releases=h.Releases();
                        test.verifyEqual(releases{1}.Reason,'retry_exhausted');
                        test.verifyEqual(releases{1}.App.SourceId,4);
                        test.verifyEqual(h.Wakes(),1);
                    end
                end
            end
        end
        function actualRetryTransmitReplacesProvisionalDeadline(test)
            h=harness(struct('DataQueuedRetryPolicy','native-provisional','MaxResends',1));
            [~,frame]=h.Hop.send(packet(1,4),2); h.Hop.notifySent(frame);
            h.Clock.run(2.1); data=h.DataFrames(); retry=data{end};
            controlScan(h,4,50); h.Clock.run(5); h.Hop.notifySent(retry);
            h.Clock.run(8.99);
            test.verifyEqual(h.Hop.stats().Failed,0);
            test.verifyEqual(h.Hop.PendingDataCount,1);
            h.Clock.run(9.1);
            test.verifyEqual(h.Hop.stats().Failed,1);
            test.verifyEqual(h.Hop.PendingDataCount,0);
        end
        function ackQueuedRetryCancelsAndReleasesExactlyOnce(test)
            h=harness(struct('DataQueuedRetryPolicy','native-provisional','MaxResends',1));
            [~,frame]=h.Hop.send(packet(1,4),2); h.Hop.notifySent(frame);
            h.Clock.run(2.1); data=h.DataFrames(); retry=data{end};
            h.Hop.receive(feedback(frame,false));
            test.verifyEqual(h.Hop.PendingDataCount,0);
            test.verifyNumElements(h.Cancelled(),1);
            h.Hop.notifySent(retry); h.Hop.receive(feedback(frame,false));
            h.Clock.run(50);
            test.verifyEqual(h.Hop.stats().Failed,0);
            test.verifyEqual(h.Hop.stats().Acknowledged,1);
            test.verifyNumElements(h.Releases(),1);
            test.verifyNumElements(h.Terminals(),1);
            test.verifyEqual(h.Hop.stats().ResendQueueDepth,0);
        end
        function dackQueuedRetryReleasesNsdpButRetainsDoubleHold(test)
            h=harness(struct('DataQueuedRetryPolicy','native-provisional','MaxResends',1));
            [~,frame]=h.Hop.send(packet(1,4),2); h.Hop.notifySent(frame);
            h.Clock.run(2.1); data=h.DataFrames(); retry=data{end};
            h.Hop.receive(feedback(frame,true)); h.Hop.notifySent(retry);
            releases=h.Releases(); test.assertNumElements(releases,1);
            test.verifyEqual(releases{1}.Reason,'dack');
            test.verifyEqual(h.Hop.PendingDataCount,1);
            test.verifyEqual(h.Hop.stats().DackHoldCount,1);
            h.Clock.run(42.1); test.verifyEqual(h.Hop.PendingDataCount,1);
            h.Clock.run(42.2); test.verifyEqual(h.Hop.PendingDataCount,0);
            test.verifyEqual(h.Hop.stats().DackExpired,1);
            test.verifyEqual(h.Hop.stats().Failed,0);
            test.verifyNumElements(h.Releases(),1);
            test.verifyNumElements(h.Terminals(),1);
        end
        function terminalCancellationCannotResurrectSelectedStaleCopy(test)
            h=harness(struct('DataQueuedRetryPolicy','native-provisional','MaxResends',1));
            [~,frame]=h.Hop.send(packet(1,4),2); h.Hop.notifySent(frame);
            h.Clock.run(2.1); h.ReplayCancelled(true);
            controlScan(h,5,50); h.Clock.run(20);
            test.verifyEqual(h.Hop.stats().Failed,1);
            test.verifyEqual(h.Hop.PendingDataCount,0);
            test.verifyNumElements(h.Terminals(),1);
            test.verifyNumElements(h.Releases(),1);
            test.verifyNumElements(h.Cancelled(),1);
            test.verifyEqual(h.Hop.stats().Transmitted,2);
        end
        function unmatchedDataOnlyAddsNativeFallbackAfterLatestScanFired(test)
            for policy=policies()
                h=harness(struct('DataQueuedRetryPolicy',policy{1}));
                [~,frame]=h.Hop.send(packet(1,4),2);
                h.Hop.receive(feedback(frame,false)); h.Clock.run(0.1);
                test.verifyEqual(h.Clock.PendingCount,0);
                h.Hop.notifySent(frame);
                test.verifyEqual(h.Clock.PendingCount,double(strcmp(policy{1},'native-provisional')));
                test.verifyEqual(h.Hop.PendingDataCount,0);
            end
        end
        function olderScanFiringDoesNotClearLatestPendingHandle(test)
            h=harness(struct('DataQueuedRetryPolicy','native-provisional'));
            [~,a]=h.Hop.send(packet(1,4),2); h.Hop.notifySent(a);
            h.Clock.run(1); [~,b]=h.Hop.send(packet(2,1),3); h.Hop.notifySent(b);
            h.Clock.run(2.1); h.Hop.receive(feedback(a,false)); h.Clock.run(2.2);
            test.verifyEqual(h.Clock.PendingCount,1);
            h.Hop.notifySent(a); test.verifyEqual(h.Clock.PendingCount,1);
            h.Clock.run(3.1); test.verifyEqual(h.Clock.PendingCount,0);
            h.Hop.notifySent(a); test.verifyEqual(h.Clock.PendingCount,1);
        end
        function latestInstalledMayFireBeforeOlderFinalGraceTimer(test)
            h=harness(struct('DataQueuedRetryPolicy','native-provisional','MaxResends',1));
            [~,a]=h.Hop.send(packet(1,4),2); h.Hop.notifySent(a);
            h.Clock.run(2.1); data=h.DataFrames(); h.Hop.notifySent(data{end});
            % Older final-grace timer is due at 6.100001; newest initial
            % timer is due earlier, at 4.200001.
            h.Clock.run(2.2); [~,b]=h.Hop.send(packet(2,1),3); h.Hop.notifySent(b);
            h.Clock.run(4.3); h.Hop.receive(feedback(b,false)); h.Clock.run(4.4);
            test.verifyEqual(h.Clock.PendingCount,1);
            h.Hop.notifySent(b); test.verifyEqual(h.Clock.PendingCount,2);
        end
        function deletionPassReleasesBeforeAnyResendAdmission(test)
            h=harness(struct('DataQueuedRetryPolicy','native-provisional','MaxResends',1));
            % Put the later-due retry ahead of the expiring owner in the list.
            [~,b]=h.Hop.send(packet(2,1),3);
            [~,a]=h.Hop.send(packet(1,4),2); h.Hop.notifySent(a);
            h.Clock.run(5); h.Hop.notifySent(b); h.Clock.run(7.1);
            order=h.Order();
            released=find(strcmp(order,'release:1'),1);
            retried=find(strcmp(order,'enqueue:2:1'),1);
            test.assertNotEmpty(released); test.assertNotEmpty(retried);
            test.verifyLessThan(released,retried);
            test.verifyEqual(h.Hop.stats().Failed,1);
        end
        function controlsStillWaitForEveryActualRetryTransmit(test)
            h=harness(struct('DataQueuedRetryPolicy','native-provisional'));
            [~,control]=h.Hop.sendControl(controlPacket(50),9); h.Hop.notifySent(control);
            h.Clock.run(2.1);
            h.Clock.run(3); [~,data]=h.Hop.send(packet(1,4),2); h.Hop.notifySent(data);
            h.Clock.run(20);
            test.verifyEqual(h.Hop.stats().ControlRetransmissions,1);
            test.verifyEqual(h.Hop.stats().ControlFailed,0);
            test.verifyEqual(h.Hop.stats().ControlPending,1);
            test.verifyEqual(h.Hop.stats().Retransmissions,1);
        end
        function rejectedRetryReleasesOnceForBothPolicies(test)
            for policy=policies()
                h=harness(struct('DataQueuedRetryPolicy',policy{1}));
                [~,frame]=h.Hop.send(packet(1,4),2); h.Hop.notifySent(frame);
                h.AcceptMac(false); h.Clock.run(3);
                test.verifyEqual(h.Hop.PendingDataCount,0);
                test.verifyEqual(h.Hop.stats().Failed,1);
                releases=h.Releases(); test.assertNumElements(releases,1);
                test.verifyEqual(releases{1}.Reason,'mac_queue_full');
                test.verifyNumElements(h.Cancelled(),1);
            end
        end
    end
end

function values=policies()
values={'actual-tx','native-provisional'};
end
function result=exerciseDefault(config)
h=harness(config); [~,frame]=h.Hop.send(packet(1,4),2); h.Hop.notifySent(frame);
h.Clock.run(2.1); controlScan(h,5,50); h.Clock.run(8);
h.Hop.receive(feedback(frame,false)); h.Clock.run(20);
result=struct('Stats',h.Hop.stats(),'Frames',{h.Frames()}, ...
    'Releases',{h.Releases()},'Terminals',{h.Terminals()},'Order',{h.Order()});
end
function controlScan(h,at,id)
h.Clock.run(at); [accepted,frame]=h.Hop.sendControl(controlPacket(id),9);
assert(accepted,'Controlled scan producer was refused.'); h.Hop.notifySent(frame);
end
function h=harness(config)
if nargin<1, config=struct(); end
config.TicSeconds=1e-6;
frames={}; releases={}; terminals={}; cancelled={}; order={}; wakes=0;
macAccepted=true; replayCancelled=false;
scheduler=csr.sim.EventScheduler();
callbacks=struct('EnqueueMac',@enqueue,'NsdpRelease',@release, ...
    'Terminal',@terminal,'CancelMac',@cancel,'Wake',@wake);
hop=csr.hop.Layer(1,scheduler,csr.sim.RandomStreams(128),config,callbacks);
h=struct('Hop',hop,'Clock',scheduler,'Frames',@getFrames,'DataFrames',@getDataFrames, ...
    'Releases',@getReleases,'Terminals',@getTerminals,'Cancelled',@getCancelled, ...
    'Order',@getOrder,'Wakes',@getWakes,'ReplayCancelled',@setReplay,'AcceptMac',@setMac);
    function accepted=enqueue(frame)
        accepted=macAccepted;
        if ~accepted, return; end
        frames{end+1}=frame;
        if strcmp(frame.Kind,'DATA'), id=frame.App.Id;
        else, id=frame.Control.Id; end
        order{end+1}=sprintf('enqueue:%u:%d',id,frame.RetryCount);
    end
    function release(app,reason)
        releases{end+1}=struct('App',app,'Reason',reason);
        order{end+1}=sprintf('release:%u',app.Id);
    end
    function terminal(app,success,reason)
        terminals{end+1}=struct('App',app,'Success',success,'Reason',reason);
        order{end+1}=sprintf('terminal:%u',app.Id);
    end
    function cancel(peer,sequence)
        cancelled{end+1}=[double(peer) double(sequence)];
        order{end+1}=sprintf('cancel:%d:%d',peer,sequence);
        if replayCancelled
            for n=numel(frames):-1:1
                frame=frames{n};
                if frame.DestinationId==peer && frame.Sequence==sequence
                    hop.notifySent(frame); break
                end
            end
        end
    end
    function wake(), wakes=wakes+1; order{end+1}='wake'; end
    function value=getFrames(), value=frames; end
    function value=getDataFrames()
        value=frames(cellfun(@(f)strcmp(f.Kind,'DATA'),frames));
    end
    function value=getReleases(), value=releases; end
    function value=getTerminals(), value=terminals; end
    function value=getCancelled(), value=cancelled; end
    function value=getOrder(), value=order; end
    function value=getWakes(), value=wakes; end
    function setReplay(value), replayCancelled=value; end
    function setMac(value), macAccepted=value; end
end
function app=packet(id,source)
flow=struct('SourceId',source,'DestinationId',5,'ApplicationPayloadBytes',64);
app=csr.packet(id,flow,0,struct('RateKeyKbps',8,'Preamble','long','EnvelopeProfile','bare'));
end
function control=controlPacket(id)
control=struct('Id',uint64(id),'Type','ROUTING', ...
    'Payload',struct('Bytes',uint8([1 2 3])),'WirePayloadBytes',64);
end
function frame=feedback(data,isDack)
options=struct(); if isDack, options.Kind='DACK'; end
frame=csr.hop.Frames.acknowledgment(data.DestinationId,data.SourceId,data.Sequence, ...
    uint64(~isDack),uint64(isDack),options);
end
