function report = run_hop_window(root, outputDir)
%RUN_HOP_WINDOW Exercise production HOP ACK/retry/capacity behavior.
% This is a MATLAB regression with an oracle sourced from native trace
% history and the native HOP source, not a native common-input runtime replay.
% All state changes use public send/notifySent/receive and scheduler APIs.
if nargin < 2, outputDir = fullfile(root,'out','hop_window'); end
if ~exist(outputDir,'dir'), mkdir(outputDir); end
addpath(fullfile(root,'core'));
report=struct('schema','csr-hop-window-history-v1','completed',false, ...
    'pass',false,'policies',{{'actual-tx','native-provisional'}}, ...
    'cases',0,'checks',0,'failed_checks',0,'runtime',version, ...
    'scope','MATLAB production HOP regression; native-history oracle', ...
    'oracle','hop_window_oracle.json', ...
    'error','');
records=struct('Policy',{},'Case',{},'Action',{},'RetryCount',{}, ...
    'Window',{},'AckCount',{},'Outstanding',{},'Pending',{},'DackHolds',{});
queued={}; hop=[]; scheduler=[]; policy=''; caseIndex=0; appId=uint64(0);
try
    oracle=jsondecode(fileread(fullfile(fileparts(mfilename('fullpath')), ...
        'hop_window_oracle.json')));
    for policyIndex=1:numel(report.policies)
        policy=report.policies{policyIndex}; queued={}; caseIndex=0;
        scheduler=csr.sim.EventScheduler();
        hop=csr.hop.Layer(4,scheduler,[], ...
            struct('DataQueuedRetryPolicy',policy),struct('EnqueueMac',@enqueue));
        % Native seq70,71,72 then73,74,76,77,75. The final ACK of each
        % growth streak completes a retransmission and must grow BEFORE reset.
        retries=[oracle.native_growth_history.retries];
        windows=[oracle.native_growth_history.window_after];
        streaks=[oracle.native_growth_history.streak_after];
        for k=1:numel(retries)
            exercise('ack',retries(k),windows(k),streaks(k),0,0);
        end
        exercise('ack',0,3,1,0,0);
        exercise('ack',0,3,2,0,0);
        exercise('fail',2,2,0,0,0); % Failure clears a two-ACK streak.
        exercise('ack',0,2,1,0,0);
        exercise('dack',0,2,0,1,1); % Custody changes, capacity is held.
        scheduler.run(scheduler.Now+20+1e-6);
        record('dack_expiry',0,2,0,0,0);
        exercise('fail',2,1,0,0,0);
        exercise('fail',2,1,0,0,0); % Window remains at its floor of one.
        st=hop.stats();
        check(st.Acknowledged==11,'Unexpected ACK count.');
        check(st.Failed==3 && st.Dacked==1 && st.DackExpired==1, ...
            'Unexpected completion/hold counts.');
        check(st.Retransmissions==10,'Unexpected retry count.');
        check(st.PendingData==0 && st.ResendQueueDepth==0 && st.DackHoldCount==0, ...
            'Unfinished owners remain after the regression.');
    end
    report.completed=true;
    report.pass=report.failed_checks==0;
catch exception
    report.error=getReport(exception,'extended','hyperlinks','off');
end
if ~isempty(records), writetable(struct2table(records),fullfile(outputDir,'hop_window.csv')); end
fid=fopen(fullfile(outputDir,'hop_window_report.json'),'w');
assert(fid>=0,'csr:test:Output','Cannot write HOP window report.');
cleaner=onCleanup(@()fclose(fid)); %#ok<NASGU>
fprintf(fid,'%s\n',jsonencode(report));

    function accepted=enqueue(frame)
        queued{end+1}=frame; accepted=true;
    end
    function exercise(action,retryCount,expectedWindow,expectedStreak,outstanding,holds)
        appId=appId+uint64(1);
        app=struct('Id',appId,'SourceId',4,'DestinationId',1, ...
            'GeneratedSeconds',scheduler.Now,'ApplicationPayloadBytes',185);
        before=hop.stats();
        [accepted,frame]=hop.send(app,5);
        check(accepted,'DATA admission unexpectedly blocked.');
        hop.notifySent(frame);
        for retry=1:retryCount
            previousQueued=numel(queued);
            scheduler.run(scheduler.Now+2+1e-6);
            check(numel(queued)==previousQueued+1,'Expected exactly one retry admission.');
            check(queued{end}.RetryCount==retry,'Retry count differs from requested history.');
            hop.notifySent(queued{end});
        end
        after=hop.stats();
        check(after.Retransmissions-before.Retransmissions==retryCount, ...
            'Actual scheduled retries differ from requested history.');
        if strcmp(action,'fail')
            scheduler.run(scheduler.Now+4+1e-6);
        else
            scheduler.run(scheduler.Now+0.1);
            ack=uint64(1); dack=uint64(0);
            if strcmp(action,'dack'), ack=uint64(0); dack=uint64(1); end
            feedback=csr.hop.Frames.acknowledgment(5,4,frame.Sequence,ack,dack);
            hop.receive(feedback);
        end
        record(action,retryCount,expectedWindow,expectedStreak,outstanding,holds);
    end
    function record(action,retries,expectedWindow,expectedStreak,outstanding,holds)
        s=hop.state(5); caseIndex=caseIndex+1; report.cases=report.cases+1;
        check(s.NeighborThreshold+1==expectedWindow,'Wrong effective DATA window.');
        check(s.AckCount==expectedStreak,'Wrong ACK streak.');
        check(s.NeighborOutstanding==outstanding && s.PendingData==outstanding, ...
            'Wrong outstanding/pending DATA capacity.');
        check(s.DackHoldCount==holds,'Wrong DACK hold ownership.');
        records(end+1)=struct('Policy',policy,'Case',caseIndex,'Action',action, ...
            'RetryCount',retries,'Window',s.NeighborThreshold+1, ...
            'AckCount',s.AckCount,'Outstanding',s.NeighborOutstanding, ...
            'Pending',s.PendingData,'DackHolds',s.DackHoldCount);
    end
    function check(ok,message)
        report.checks=report.checks+1;
        if ~ok
            report.failed_checks=report.failed_checks+1;
            error('csr:test:HopWindow','%s Policy=%s, case=%d.',message,policy,caseIndex+1);
        end
    end
end
