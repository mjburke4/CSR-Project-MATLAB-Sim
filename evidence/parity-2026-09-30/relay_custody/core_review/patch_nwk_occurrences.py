from pathlib import Path
root=Path('/workspace/scratch/db3d3caa011d/relay_custody/kit/node8case')
paths=[root/'model/+csr/+nwk/Layer.m',root/'+ac/DiscoveryMembershipNwk.m']
for path in paths:
    text=path.read_text()
    def replace(old,new):
        global text
        assert text.count(old)==1,(path,old[:120],text.count(old))
        text=text.replace(old,new)
    replace('        Pending = {}\n','        Pending = {}\n        NextCustodyId = uint64(1)\n')
    replace('''            if isKey(obj.Seen,key)
                obj.Counters.DuplicateApplications=obj.Counters.DuplicateApplications+1;
                accepted=true; return
            end
''','''            % HOP owns its ACK/DACK receive window. A copy that HOP offers
            % again (including a DACK-marked retry) needs distinct relay
            % custody. Only the final destination deduplicates applications.
            if app.DestinationId==obj.NodeId && isKey(obj.Seen,key)
                obj.Counters.DuplicateApplications=obj.Counters.DuplicateApplications+1;
                accepted=true; return
            end
''')
    replace('''            accepted=obj.enqueueApplication(onward);
            if ~accepted, reason='network_queue_full'; end
            if accepted
                obj.Seen(key)=true;
''','''            [accepted,onward]=obj.enqueueApplication(onward);
            if ~accepted, reason='network_queue_full'; end
            if accepted
''')
    replace('''        function release(obj,app,reason)
            position=obj.pendingPosition(app);
            if position>0
                obj.Pending(position)=[];
                obj.emit('network_custody_release',app,struct('Reason',reason));
            end
            obj.wake();
        end
''','''        function release(obj,app,reason)
            position=obj.pendingPosition(app);
            if position==0, return; end
            obj.Pending(position)=[];
            obj.emit('network_custody_release',app,struct('Reason',reason));
            obj.wake();
        end
''')
    replace('''        function accepted = enqueueApplication(obj,app)
            if obj.pendingPosition(app)>0, accepted=true; return; end
            accepted=numel(obj.Pending)<obj.Config.QueueLimit;
''','''        function [accepted,app] = enqueueApplication(obj,app)
            accepted=numel(obj.Pending)<obj.Config.QueueLimit;
''')
    replace('''            row=struct('App',app,'Submitted',false,'PeerId',NaN);
''','''            % This is local custody metadata, not application or wire
            % identity. Always replace the upstream node's token, even when
            % another accepted occurrence of the same application is live.
            if obj.NextCustodyId==intmax('uint64')
                error('csr:nwk:CustodyIdExhausted','Local custody identifiers are exhausted.');
            end
            app.NwkCustodyNodeId=obj.NodeId;
            app.NwkCustodyId=obj.NextCustodyId;
            obj.NextCustodyId=obj.NextCustodyId+uint64(1);
            row=struct('App',app,'Submitted',false,'PeerId',NaN);
''')
    replace('''        function position = pendingPosition(obj,app)
            position=0;
            for index=1:numel(obj.Pending)
                if strcmp(appKey(obj.Pending{index}.App),appKey(app)), position=index; return; end
            end
        end
''','''        function position = pendingPosition(obj,app)
            % A delayed callback must identify its exact local occurrence.
            % There is deliberately no application-identity fallback: after
            % one copy leaves, such a fallback could release its sibling.
            position=0;
            if ~isstruct(app) || ~isscalar(app) || ...
                    ~all(isfield(app,{'NwkCustodyNodeId','NwkCustodyId','SourceId','Id'})) || ...
                    ~isnumeric(app.NwkCustodyNodeId) || ~isscalar(app.NwkCustodyNodeId) || ...
                    ~isreal(app.NwkCustodyNodeId) || app.NwkCustodyNodeId~=obj.NodeId || ...
                    ~isa(app.NwkCustodyId,'uint64') || ~isscalar(app.NwkCustodyId) || ...
                    app.NwkCustodyId==0
                return
            end
            for index=1:numel(obj.Pending)
                other=obj.Pending{index}.App;
                if other.NwkCustodyId==app.NwkCustodyId && ...
                        strcmp(appKey(other),appKey(app))
                    position=index; return
                end
            end
        end
''')
    replace('        function state = applicationState(obj,destination)\n','''        function count = custodyCount(obj,app)
            % Read-only live occurrence count for unique-application accounting.
            % NSDP uses a source/destination pair; this query uses the original
            % source/application identity and includes submitted HOP owners.
            count=0; key=appKey(app);
            for index=1:numel(obj.Pending)
                count=count+double(strcmp(appKey(obj.Pending{index}.App),key));
            end
        end

        function state = applicationState(obj,destination)
''')
    path.write_text(text)
