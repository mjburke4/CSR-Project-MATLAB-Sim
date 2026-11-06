function result=run_congestion_candidate(configPath,outputPath)
% PREPARATION CANDIDATE. Invoke only through separately admitted owned wrapper.
config=jsondecode(fileread(configPath));
assert(strcmp(config.Nwk.AdmissionPolicy,'opnet-reference'));
assert(strcmp(config.Hop.DataQueuedRetryPolicy,'native-provisional'));
assert(config.Nwk.Neighbor.AdmissionEnabled&&config.Hop.TicSeconds==1/36e6);
assert(config.Hop.PendingThreshold==16&&config.Hop.NsdpLimit==16&&config.Hop.ResendSeconds==2);
assert(config.Hop.DackHoldSeconds==20&&config.Hop.MaxResends==2);
assert(strcmp(config.Radio.EnvelopeProfile,'bare'));
assert(isempty(ac.Trace.holder()));cleanup=onCleanup(@()ac.Trace.holder('clear',[]));
main=CongestionHarness(config,'main');ac.Trace.holder('set',main);main.setup();
s=main.S;ticSeconds=config.Hop.TicSeconds;
s.scheduleAt(1,@()main.offer(0));s.scheduleAt(1.1,@()main.sent(8,0));
s.scheduleAt(1.2,@()main.feedback(8,0,true));s.scheduleAt(1.3,@()main.relay());
s.scheduleAt(1.4,@()main.offer16());s.scheduleAt(1.5,@()main.offer(17));
s.scheduleAt(21.3,@()main.sent(7,1));s.scheduleAt(21.4,@()main.feedback(7,1,false));
s.scheduleAt(21.5,@()main.sent(8,1));s.scheduleAt(21.6,@()main.feedback(8,1,false));
s.scheduleAt(21.7,@()main.sent(8,2));s.scheduleAt(24,@()main.sent(8,2));
s.scheduleAt(24.1,@()main.feedback(8,2,false));
times=[.9 1 1.000001 1.1 1.2 1.200001 1.3 1.4 1.400001 1.5 21.199999 ...
 21.2+ticSeconds+1e-9 21.2+2*ticSeconds+1e-6 21.3 21.4 21.400001 ...
 21.5 21.6 21.600001 21.7 23.699999 23.700001 24 24.1 24.100001];
labels={'setup','warm_offer','warm_submitted','warm_sent','warm_dack','after_dack_wake', ...
 'relay_arrival','own16_arrival','blocked_backlog','offer17_rejected','before_hold_expiry', ...
 'credit_released_before_wake','relay_selected','relay_sent','relay_ack','own1_selected', ...
 'own1_sent','own1_ack','own2_selected','own2_sent','before_retry','retry_queued','retry_sent', ...
 'third_ack_retried','two_own_selected'};
for k=1:numel(times),scheduleSnapshot(main,times(k),labels{k});end
s.run(24.100002);ac.Trace.holder('clear',[]);
boundary=HopBoundaryHarness(config);ac.Trace.holder('set',boundary);boundary.execute();
ac.Trace.holder('clear',[]);
result=struct('schema','matched-nwk-hop-component-matlab-v1','main',{main.Rows}, ...
 'boundary',{boundary.Rows},'main_bijection',{main.Identities},'boundary_bijection',{boundary.Identities}, ...
 'scope','Actual NWK/HOP; scripted MAC sent/control acknowledgments; no PHY; read-only snapshot overlays', ...
 'boundary_scope','Isolated HOP-only send/notifySent; no NWK or neighbor setup', ...
 'boundary_public_service_call',false,'full_network_parity_claimed',false);
result.raw_matlab=exact(result);
bytes=uint8(unicode2native([jsonencode(ids(result)) newline],'UTF-8'));assert(numel(bytes)<=16*1024^2);
f=System.IO.FileStream(outputPath,System.IO.FileMode.CreateNew,System.IO.FileAccess.Write,System.IO.FileShare.Read);
closer=onCleanup(@()f.Dispose());f.Write(bytes,0,numel(bytes));f.Flush(true);
end
function scheduleSnapshot(h,t,label)
h.S.scheduleAt(t,@()h.snapshot(label));
end
function y=exact(x)
% Preserve every binary64 (including Inf) and integer ID without JSON rounding.
if isa(x,'double')
 y=struct('matlab_class','double','size',size(x),'hex',{arrayfun(@num2hex,x,'UniformOutput',false)}, ...
  'decimal',{arrayfun(@(v)sprintf('%.17g',v),x,'UniformOutput',false)});
elseif isa(x,'uint64')
 y=struct('matlab_class','uint64','size',size(x),'decimal',{arrayfun(@(v)sprintf('%u',v),x,'UniformOutput',false)});
elseif isstruct(x)
 y=x;names=fieldnames(x);for k=1:numel(x),for j=1:numel(names),y(k).(names{j})=exact(x(k).(names{j}));end,end
elseif iscell(x)
 y=cell(size(x));for k=1:numel(x),y{k}=exact(x{k});end
else,y=x;end
end
function y=ids(x)
if isa(x,'uint64')
 if isscalar(x),y=sprintf('%u',x);else,y=arrayfun(@(v)sprintf('%u',v),x,'UniformOutput',false);end
elseif isstruct(x)
 y=x;names=fieldnames(x);for k=1:numel(x),for j=1:numel(names),y(k).(names{j})=ids(x(k).(names{j}));end,end
elseif iscell(x)
 y=cell(size(x));for k=1:numel(x),y{k}=ids(x{k});end
else,y=x;end
end
