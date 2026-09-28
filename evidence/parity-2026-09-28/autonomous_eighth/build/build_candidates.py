"""Source-bound nanosecond relative receive timers and paired TX completion."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]/'kit/autocase';previous=Path(__file__).resolve().parents[2]/'autonomous_seventh/kit/autocase'
def sha(b):return hashlib.sha256(b).hexdigest()
proof=json.loads((previous/'candidate_transform.json').read_text())
def gen(source,target,edits):
 raw=(root/source).read_bytes();s=raw.decode()
 for old,new in edits:
  assert s.count(old)==1,(source,old[:100],s.count(old));s=s.replace(old,new)
 result=s.encode();(root/target).write_bytes(result);reverse=s
 for old,new in reversed(edits):
  assert reverse.count(new)==1,(source,new[:100],reverse.count(new));reverse=reverse.replace(new,old)
 assert reverse.encode()==raw
 proof['transforms'].append(dict(source=source,source_sha256=sha(raw),target=target,target_sha256=sha(result),reverse_recovers_source=True,edits=[dict(old=a,new=b) for a,b in edits]))
helper="""        function deadline=relativeDeadline(obj,index,delay,purpose)
            deadline=obj.Scheduler.Now+delay;
            if ~isempty(obj.TransportTiming) && strcmp(obj.TransportTiming.Mode,'nanoseconds')
                deadline=obj.RelativeTimer.plan(obj.Scheduler.Now,double(delay), ...
                    double(obj.Receivers(index).Id),purpose);
            end
        end
"""
gen('model/+csr/+phy/SignalEngine.m','+ac/ReceiverTimerSignalEngine.m',[
 ('classdef SignalEngine < handle','classdef ReceiverTimerSignalEngine < handle'),
 ('function obj = SignalEngine(config, scheduler, streams, onReceive, onTrace, onState, transportTiming)','function obj = ReceiverTimerSignalEngine(config, scheduler, streams, onReceive, onTrace, onState, transportTiming, relativeTimer)'),
 ('        TransportTiming = []','        TransportTiming = []\n        RelativeTimer = []'),
 ('            obj.Config=config; obj.Scheduler=scheduler; obj.Streams=streams;',"""            if nargin>7 && ~isempty(relativeTimer)
                assert(isa(relativeTimer,'ac.ReceiverTimer') && isscalar(relativeTimer), ...
                    'autocase:ReceiverTimer','Expected one relative timer recorder.');
                obj.RelativeTimer=relativeTimer;
            else
                obj.RelativeTimer=ac.ReceiverTimer();
            end
            obj.Config=config; obj.Scheduler=scheduler; obj.Streams=streams;"""),
 ('        function count=get.ActiveSignalCount(obj)',"""        function value=receiverTimingSnapshot(obj)
            value=obj.RelativeTimer.snapshot();
        end
        function count=get.ActiveSignalCount(obj)"""),
 ('            id=obj.NextSignalId; obj.NextSignalId=id+1;',"            txDeadline=obj.relativeDeadline(txIndex,duration,'phy_tx_finish');\n            id=obj.NextSignalId; obj.NextSignalId=id+1;"),
 ('obj.Receivers(txIndex).TxUntil=now+duration;','obj.Receivers(txIndex).TxUntil=txDeadline;'),
 ('obj.Receivers(txIndex).TxEvent=obj.Scheduler.scheduleAt(now+duration,@()obj.finishTx(txIndex));','obj.Receivers(txIndex).TxEvent=obj.Scheduler.scheduleAt(txDeadline,@()obj.finishTx(txIndex));'),
 ('        function index=nodeIndex(obj,id)',helper+'        function index=nodeIndex(obj,id)'),
 ('obj.Scheduler.Now+obj.SyncToTrackSeconds,@()obj.acquire(index));',"obj.relativeDeadline(index,obj.SyncToTrackSeconds,'acquisition'),@()obj.acquire(index));"),
 ('obj.Scheduler.scheduleAt(obj.Scheduler.Now+28e-9,@()obj.returnRejectedToSearch(index));',"obj.Scheduler.scheduleAt(obj.relativeDeadline(index,28e-9,'rejected_return'), ...\n                        @()obj.returnRejectedToSearch(index));")])
gen('model/+csr/+mac/Layer.m','+ac/ReceiverTimerMac.m',[
 ('classdef Layer < handle','classdef ReceiverTimerMac < handle'),
 ('function obj = Layer(nodeId, scheduler, streams, config, callbacks)','function obj = ReceiverTimerMac(nodeId, scheduler, streams, config, callbacks, relativeTimer)'),
 ('        Scheduler\n        Stream','        Scheduler\n        RelativeTimer = []\n        Stream'),
 ('            obj.NodeId = double(nodeId);',"""            if nargin>5 && ~isempty(relativeTimer)
                assert(isa(relativeTimer,'ac.ReceiverTimer') && isscalar(relativeTimer), ...
                    'autocase:ReceiverTimer','Expected one relative timer recorder.');
                obj.RelativeTimer=relativeTimer;
            end
            obj.NodeId = double(nodeId);"""),
 ('            obj.FinishEvent = obj.after(duration, @() obj.finishTx());',"""            if isempty(obj.RelativeTimer)
                obj.FinishEvent = obj.after(duration, @() obj.finishTx());
            else
                deadline=obj.RelativeTimer.plan(obj.Scheduler.Now,double(duration), ...
                    obj.NodeId,'mac_tx_finish');
                obj.FinishEvent=obj.Scheduler.scheduleAt(deadline,@()obj.finishTx());
            end""")])
gen('+ac/DiscoveryIdentitySimulation.m','+ac/ReceiverTimerSimulation.m',[
 ('classdef DiscoveryIdentitySimulation < handle','classdef ReceiverTimerSimulation < handle'),
 ('    % Each node owns independent NWK, HOP and MAC state. The unchanged source',
  '    % Each node owns independent NWK, HOP and MAC state. The isolated timer'),
 ('function obj = DiscoveryIdentitySimulation(config,linkObserver,transportTiming,autonomousOptions)','function obj = ReceiverTimerSimulation(config,linkObserver,transportTiming,autonomousOptions)'),
 ('        TransportTiming = []','        TransportTiming = []\n        RelativeTimer = []'),
 ('            obj.Engine = csr.phy.SignalEngine(config,obj.Scheduler,obj.Streams, ...',"""            obj.RelativeTimer=ac.ReceiverTimer();
            macRelativeTimer=[];
            if ~isempty(obj.TransportTiming) && strcmp(obj.TransportTiming.Mode,'nanoseconds')
                macRelativeTimer=obj.RelativeTimer;
            end
            obj.Engine = ac.ReceiverTimerSignalEngine(config,obj.Scheduler,obj.Streams, ..."""),
 ('@(nodeId,state)obj.receiverChanged(nodeId,state),obj.TransportTiming);','@(nodeId,state)obj.receiverChanged(nodeId,state),obj.TransportTiming,obj.RelativeTimer);'),
 ('obj.Macs{k} = csr.mac.Layer(nodeId,obj.Scheduler,obj.Streams,config,macCallbacks);','obj.Macs{k} = ac.ReceiverTimerMac(nodeId,obj.Scheduler,obj.Streams,config,macCallbacks,macRelativeTimer);'),
 ('        function value=autonomousRandomSummary(obj)',"""        function value=autonomousReceiverTimingSummary(obj)
            value=obj.RelativeTimer.snapshot();
        end
        function value=autonomousRandomSummary(obj)""")])
proof.pop('new_J_matlab_executed',None)
proof.update(schema='csr-isolated-relative-timer-candidate-v1',matlab_executed=False,
 prior_J_owner_executed=True,new_K_matlab_executed=False,production_model_changed=False,natural_path_changed=False,
 scope='K retains J protocol and comparator; source-confirmed acquisition and rejected-return targets plus paired PHY/MAC TX finish use integer nanosecond addition. PHY TxUntil shares its deadline. Physical geometry, Model truncation and generic MAC after are unchanged.',
 current_limitation='Nanosecond tick sum divided by1e9 is not universally bit-identical to native fixed-point GetSeconds (2 of10301 captured ticks differ1ULP); all captured allocation counts are separately checked. No other MAC timer is changed.')
(root/'candidate_transform.json').write_text(json.dumps(proof,indent=2)+'\n')
print('Built K: 22 exact reversible transforms; MAC generic after and physical geometry preserved.')
