from pathlib import Path
import sys,json,hashlib,shutil
sys.path.insert(0,str(Path('autonomous/design').resolve()))
from instrument_observers import instrument_model
root=Path('autonomous/kit/autocase');model=root/'model';baseline=Path('return6000/kit/csr6000/model')
shutil.copytree(baseline,model,dirs_exist_ok=True)
observer_receipt=instrument_model(model)
changes=[]
def replace(path,old,new):
 p=model/path;s=p.read_text();assert s.count(old)==1,(path,s.count(old),old[:100]);p.write_text(s.replace(old,new,1));changes.append({'path':path,'before':old,'after':new})
replace('+csr/+sim/NetworkSimulation.m','function obj = NetworkSimulation(config,linkObserver,transportTiming)','function obj = NetworkSimulation(config,linkObserver,transportTiming,autonomousOptions)')
replace('+csr/+sim/NetworkSimulation.m','            obj.Streams = csr.sim.RandomStreams(config.Seed);', '''            assert(nargin==4 && isstruct(autonomousOptions), ...
                'autocase:Options','This validation copy requires explicit autonomous options.');
            obj.Streams = ac.Streams(config.Seed,obj.Scheduler, ...
                autonomousOptions.Mode,autonomousOptions.Fixture,autonomousOptions.Folder);''')
replace('+csr/+sim/NetworkSimulation.m',"            metadata.Rng = struct('Generator','mt19937ar','MappingVersion',obj.Streams.MappingVersion);",'''            metadata.Rng = struct('Generator','mt19937ar','MappingVersion',obj.Streams.MappingVersion);
            metadata.AutonomousValidationMode=obj.Streams.Mode;
            if strcmp(obj.Streams.Mode,'native'), metadata.Rng.Generator='captured-ns3-samples'; end''')
replace('+csr/+sim/NetworkSimulation.m','        function protocolEvent(obj,nodeId,event,frame,details)\n','''        function protocolEvent(obj,nodeId,event,frame,details)
            ac.Trace.record(obj.Scheduler.Now,'protocol',nodeId, ...
                struct('event',event,'frame',frame,'details',details));
''')
replace('+csr/+sim/NetworkSimulation.m','        function recordPhy(obj,event,frame,nodeId,details)\n','''        function recordPhy(obj,event,frame,nodeId,details)
            ac.Trace.record(obj.Scheduler.Now,'phy',nodeId, ...
                struct('event',event,'frame',frame,'details',details));
''')
replace('+csr/+sim/NetworkSimulation.m','        function recordAdmission(obj,row)\n','''        function recordAdmission(obj,row)
            ac.Trace.record(obj.Scheduler.Now,'application_attempt',row.SourceId,row);
''')
replace('+csr/+sim/NetworkSimulation.m','    methods (Access = private)\n        function generate(obj,flowIndex,ordinal)','''    methods
        function value=autonomousRandomSummary(obj)
            value=obj.Streams.summary();
        end
        function autonomousClose(obj)
            obj.Streams.close();
        end
        function value=autonomousPartial(obj)
            % Saved observations only. This does not complete, advance or
            % recompute application outcomes after a failed simulation.
            value=struct('ProtocolTrace',struct2table(obj.TraceRows(1:obj.TraceCount),'AsArray',true), ...
                'PhyTrace',struct2table(obj.PhyRows(1:obj.PhyCount),'AsArray',true), ...
                'ApplicationAdmissionTrace',struct2table(obj.AdmissionRows(1:obj.AdmissionCount),'AsArray',true), ...
                'Statistics',obj.Counters,'Config',obj.Config);
        end
    end
    methods (Access = private)
        function generate(obj,flowIndex,ordinal)''')
replace('+csr/+mac/Layer.m', '''            range = csr.mac.SlotSelection.slotRange(obj.Config.SlotProfile, ...
                active,obj.Config.SlotReduction);''','''            range = csr.mac.SlotSelection.slotRange(obj.Config.SlotProfile, ...
                active,obj.Config.SlotReduction);
            profiles=csr.mac.SlotSelection.profiles();
            obj.Stream.setContext(struct('profile',find(strcmp(obj.Config.SlotProfile,profiles))-1, ...
                'active_nodes',obj.Config.ActiveNodes,'reported_nodes',obj.Config.ReportedActiveNodes, ...
                'reservation_counter',obj.ReservationCounter,'reservation_slot',obj.ReservationSlot, ...
                'state',lower(obj.State)));''')
replace('+csr/+phy/SignalEngine.m','        function transmit(obj,frame,duration)\n','''        function transmit(obj,frame,duration)
            obj.Streams.registerTx(frame);
''')
replace('+csr/+phy/SignalEngine.m', '''                    threshold=threshold+sqrt(profile.SyncSnrThresholdVarianceDb2)* ...
                        randn(obj.Streams.get(obj.Receivers(index).Id,'sync'));''','''                    threshold=obj.Streams.threshold(obj.Receivers(index).Id,profile,incoming.Frame);''')
replace('+csr/+phy/SignalEngine.m',"signal.Frame.RateKeyKbps,interval,obj.Streams.get(obj.Receivers(index).Id,'phy'));",'''signal.Frame.RateKeyKbps,interval,obj.Streams.phy( ...
                        obj.Receivers(index).Id,signal.Frame,signal.IntervalCount+1,interval));''')
replace('+csr/+phy/Model.m',"if ~isa(stream, 'RandStream') && ~isa(stream, 'function_handle')", "if ~isa(stream, 'RandStream') && ~isa(stream, 'function_handle') && ~isa(stream,'ac.PhySampler')")
replace('+csr/+phy/Model.m', '''                headerErrors = csr.phy.Model.drawBinomial( ...
                    headerCount, values.HeaderBer, stream);
                payloadErrors = csr.phy.Model.drawBinomial( ...
                    payloadCount, values.PayloadBer, stream);''','''                if isa(stream,'ac.PhySampler')
                    headerErrors=stream.draw(headerCount,values.HeaderBer,'header',headerBegin,headerEnd);
                    payloadErrors=stream.draw(payloadCount,values.PayloadBer,'payload',payloadBegin,intervalEnd);
                else
                    headerErrors = csr.phy.Model.drawBinomial( ...
                        headerCount, values.HeaderBer, stream);
                    payloadErrors = csr.phy.Model.drawBinomial( ...
                        payloadCount, values.PayloadBer, stream);
                end''')
(root/'source_transform.json').write_text(json.dumps({'schema':'csr-autonomous-validation-transform-v1','observer_receipt':observer_receipt,'random_and_export_edits':changes,'production_fix':False},indent=2)+'\n')
# Prefix excludes simulation-stop time, matching canonical native capture.
import csv
for name in ['protocol_trace.csv','phy_trace.csv','application_admission_trace.csv']:
 src=Path('return6000/data/s132/attempt_001/raw')/name;dst=root/'ref/matlab'/name
 with src.open(newline='') as fi,dst.open('w',newline='') as fo:
  reader=csv.DictReader(fi);writer=csv.DictWriter(fo,fieldnames=reader.fieldnames);writer.writeheader()
  writer.writerows(r for r in reader if float(r['TimeSeconds'])<330)
print('Generated source-bound model; original model remains unchanged.')
