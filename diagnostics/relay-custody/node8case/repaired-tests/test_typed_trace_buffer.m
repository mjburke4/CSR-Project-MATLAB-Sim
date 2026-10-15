function report=test_typed_trace_buffer(repairRoot,outputFolder,guard) %#ok<INUSD>
assert(isa(guard,'function_handle'));guard();
% Small helper-only qualification. Caller owns cutoff/resource supervision.
assert(~isfolder(outputFolder)&&~isfile(outputFolder));mkdir(outputFolder);
template=struct('Id',uint64(0),'Time',0,'Single',single(0),'Flag',false, ...
    'Signed',int16(0),'Text','','Purpose',string(''),'DetailsJSON','');
rows=repmat(template,11,1);
texts={'','a','a,b','a"b',sprintf('line1\nline2'),sprintf('x\r\ny'),char([937 20013]),'tail',char(zeros(1,0)),'trailing   ',sprintf('tab\tend\t')};
times=[0 -0 NaN Inf -Inf realmin realmax 0.1 1012.62 -realmin 1/3];
for k=1:numel(rows)
    rows(k).Id=bitshift(uint64(1),53)+uint64(k);
    rows(k).Time=times(k);rows(k).Single=single(k/3);
    rows(k).Flag=mod(k,2)==0;rows(k).Signed=int16(-k);
    rows(k).Text=texts{k};rows(k).Purpose=string(texts{k});rows(k).DetailsJSON=jsonencode(struct('Id',rows(k).Id,'text',texts{k}));
end
rows(2).Time=-1/Inf;rows(9).Id=intmax('uint64');rows(8).Purpose=string(missing);
checks={};
for count=[0 1 2 7 9 11]
    guard();
    b=csr.sim.TypedTraceBuffer(template,double(count));
    for k=1:count,b.append(rows(k));end
    expected=struct2table(rows(1:count),'AsArray',true);
    actual=b.tableRows(1,double(count));exactTable(actual,expected);
    if count>=2,assert(typecast(actual.Time(2),'uint64')==bitshift(uint64(1),63));end
    baseline=fullfile(outputFolder,sprintf('legacy_%d.csv',count));writetable(expected,baseline);
    for chunk=[1 2 7 32]
        path=fullfile(outputFolder,sprintf('typed_%d_chunk_%d.csv',count,chunk));
        receipt=b.exportCsv(path,double(chunk),[],guard);assert(receipt.Complete&&receipt.Rows==count);
        assert(isequal(readBytes(path),readBytes(baseline)),'typedtest:Csv','Legacy CSV bytes differ.');
        mustFail(@()b.exportCsv(path,double(chunk)),'csr:trace:Existing');
    end
    if count>0
        for first=1:count
            last=min(count,first+2);exactTable(b.tableRows(double(first),double(last)),expected(first:last,:));
        end
    end
    mustFail(@()b.append(template),'csr:trace:Capacity');
    assert(b.Count==count);checks{end+1}=sprintf('exact tables/CSV/ranges/capacity count%d',count); %#ok<AGROW>
end
b=csr.sim.TypedTraceBuffer(template,3);b.append(rows(1));before=b.tableRows(1,1);
bad=rows(2);bad.DetailsJSON=string('wrongclass');atomicFailure(b,bad,before,'csr:trace:Type');
bad=rows(2);bad.Id=double(2^53);atomicFailure(b,bad,before,'csr:trace:Type');
bad=rows(2);bad.Time=[1 2];atomicFailure(b,bad,before,'csr:trace:Shape');
bad=rows(2);bad.Time=complex(1,2);atomicFailure(b,bad,before,'csr:trace:Shape');
bad=rows(2);bad.Purpose=["a" "b"];atomicFailure(b,bad,before,'csr:trace:Shape');
bad=rows(2);bad.Text=['ab';'cd'];atomicFailure(b,bad,before,'csr:trace:Shape');
bad=rmfield(rows(2),'Flag');atomicFailure(b,bad,before,'csr:trace:Schema');
bad=rows(2);bad.Extra=1;atomicFailure(b,bad,before,'csr:trace:Schema');
bad=orderfields(rows(2),flipud(fieldnames(rows(2))));atomicFailure(b,bad,before,'csr:trace:Schema');
mustFail(@()b.tableRows(1,2),'csr:trace:Range');mustFail(@()b.tableRows(2,1),'csr:trace:Range');
mustFail(@()b.tableRows(0,0),'');mustFail(@()b.tableRows(1.5,1),'');
mustFail(@()b.exportCsv(fullfile(outputFolder,'invalid_chunk.csv'),0),'');
assert(~isfile(fullfile(outputFolder,'invalid_chunk.csv')));
checks{end+1}='atomic schema/type/shape and invalid ranges/chunks';
b.append(rows(2));b.append(rows(3));
transformed=b.tableRows(1,3);transformed.Id=transformed.Id+uint64(20);
path=fullfile(outputFolder,'transform.csv');baseline=fullfile(outputFolder,'transform_legacy.csv');
b.exportCsv(path,2,@remap,guard);writetable(transformed,baseline);
assert(isequal(readBytes(path),readBytes(baseline)));exactTable(b.tableRows(1,3),struct2table(rows(1:3),'AsArray',true));
checks{end+1}='bounded transform remaps exactuint64 without storage mutation';
mustFail(@()b.exportCsv(fullfile(outputFolder,'transform_wrong_type.csv'),2,@wrongType,guard),'csr:trace:Transform');
stopPath=fullfile(outputFolder,'guard_stopped.csv');
mustFail(@()b.exportCsv(stopPath,2,[],@stopGuard),'typedtest:Stop');
assert(~isfile(stopPath));
failurePath=fullfile(outputFolder,'transform_failure_preserved.csv');
mustFail(@()b.exportCsv(failurePath,1,@failTransform),'typedtest:Injected');guard();
assert(isfile(failurePath));checks{end+1}='export failure propagates and preserves partial artifact';
% Full-column quoting must also leave LF-only columns exactly as legacy does.
lfrow=template;lfrow.Text=sprintf('LFonly\nend');lfrow.Purpose=string(lfrow.Text);
lf=csr.sim.TypedTraceBuffer(template,1);lf.append(lfrow);
lfbase=fullfile(outputFolder,'lf_only_legacy.csv');lfout=fullfile(outputFolder,'lf_only_typed.csv');
writetable(struct2table(lfrow,'AsArray',true),lfbase);lf.exportCsv(lfout,1,[],guard);
assert(isequal(readBytes(lfbase),readBytes(lfout)));
% Stop only after a completed first body batch, preserving its exact prefix.
prefixBase=fullfile(outputFolder,'prefix_legacy.csv');writetable(struct2table(rows(1:3),'AsArray',true),prefixBase);
prefixBytes=readBytes(prefixBase);lineEnds=find(prefixBytes==10);assert(numel(lineEnds)>=2);
partialPath=fullfile(outputFolder,'stopped_after_first_batch.csv');
mustFail(@()b.exportCsv(partialPath,1,[],@()stopAfterWrite(partialPath,lineEnds(1),guard)), 'typedtest:AfterBatchStop');
assert(isequal(readBytes(partialPath),prefixBytes(1:lineEnds(2))));
checks{end+1}='global late-special quoting/missing/trailing-whitespace/LF policy and exact stopped prefix';

report=struct('passed',true,'scope','helper-only synthetic; no network or combined capacity qualification', ...
    'checks',{checks},'rows',numel(rows),'matlab',version,'byte_equivalence',true, ...
    'os_write_fault_injection','UNRUN','full_population','UNRUN');
path=fullfile(outputFolder,'REPORT.json');f=fopen(path,'wt');assert(f>=0);
assert(fprintf(f,'%s\n',jsonencode(report))>0);assert(fclose(f)==0);
end
function stopAfterWrite(path,headerBytes,guard)
guard();
if isfile(path)
    info=dir(path);
    if info.bytes>headerBytes,error('typedtest:AfterBatchStop','Intentional stop after first completed body batch.');end
end
end
function t=wrongType(t,first,last) %#ok<INUSD>
t.Id=double(t.Id);
end
function stopGuard()
error('typedtest:Stop','Intentional cooperative checkpoint stop.');
end
function t=remap(t,first,last)
assert(height(t)==last-first+1);t.Id=t.Id+uint64(20);
end
function t=failTransform(t,first,last) %#ok<INUSD>
error('typedtest:Injected','Intentional transform failure.');
end
function atomicFailure(b,row,before,id)
mustFail(@()b.append(row),id);assert(b.Count==height(before));exactTable(b.tableRows(1,b.Count),before);
end
function exactTable(a,b)
assert(isequaln(a,b),'typedtest:Table','Legacy table schema/classes/values differ.');
assert(isequal(a.Properties.VariableNames,b.Properties.VariableNames));
for k=1:width(a)
    name=a.Properties.VariableNames{k};x=a.(name);y=b.(name);assert(strcmp(class(x),class(y))&&isequal(size(x),size(y)));
    if isa(x,'double')||isa(x,'single')
        assert(isequal(typecast(x(:),'uint8'),typecast(y(:),'uint8')),'typedtest:Bits','Float bits differ.');
    end
end
end
function mustFail(action,id)
caught=false;
try,action();catch e
    if ~isempty(id)&&~strcmp(e.identifier,id),rethrow(e);end
    caught=true;
end
assert(caught,'typedtest:Negative','Expected rejection did not occur.');
end
function bytes=readBytes(path)
d=dir(path);f=fopen(path,'rb');assert(f>=0);
try
    [bytes,n]=fread(f,d.bytes,'*uint8');assert(n==d.bytes);
    [message,number]=ferror(f);assert(number==0,message);
catch e
    fclose(f);rethrow(e);
end
assert(fclose(f)==0,'typedtest:Close','Baseline comparison file close failed.');
end
