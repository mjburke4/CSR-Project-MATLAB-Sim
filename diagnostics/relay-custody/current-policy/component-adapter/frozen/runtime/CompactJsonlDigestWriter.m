classdef CompactJsonlDigestWriter < handle
 % Passive exact-byte digest retention. Never claims reconstructible records.
 properties (SetAccess=private)
  Bytes=0
  Records=0
  Closed=false
  Faulted=false
 end
 properties (Access=private)
  Limits
  Payload
  File=[]
  Hasher=[]
  PendingBytes=0
  Digest=''
  RetainedBytes=0
  CloseAttempted=false
 end
 methods
  function obj=CompactJsonlDigestWriter(path,pool,payload,footer,temporary,limits)
   assert(nargin==6&&footer==0&&temporary==0,'compact:Plan','No footer or temporary file allocation.');
   BoundedJsonlWriter.validateLimits(limits);
   for name={'MaxRecords','MaxRawBytes'}
    assert(isfield(limits,name{1}),'compact:Plan','Explicit cumulative work bound required.');
    v=limits.(name{1});assert(isnumeric(v)&&isreal(v)&&isscalar(v)&&isfinite(v)&&v>=0&&v==fix(v)&&v<=flintmax,'compact:Plan','Invalid cumulative bound.');
   end
   assert(isa(pool,'DiagnosticByteBudget')&&isnumeric(payload)&&isscalar(payload)&&isfinite(payload)&&payload==fix(payload)&&payload>=2048,'compact:Plan','Shared pool and at least2048 receipt bytes required.');
   path=pool.assertPath(path);assert(~isfile(path)&&~isfolder(path),'diag2490:Exists','Preserve prior evidence.');
   pool.reserve(path,payload,0,0);obj.Limits=limits;obj.Payload=payload;
   obj.File=System.IO.FileStream(path,System.IO.FileMode.CreateNew,System.IO.FileAccess.Write,System.IO.FileShare.Read);
   obj.Hasher=System.Security.Cryptography.SHA256.Create();
  end
  function n=write(obj,value)
   obj.requireWritable();
   try
    bytes=BoundedJsonlWriter.encodeBounded(value,obj.Limits);
    n=obj.writeBytes(bytes);
   catch e
    obj.Faulted=true;rethrow(e);
   end
  end
  function n=writeBytes(obj,bytes)
   obj.requireWritable();
   try
    assert(isa(bytes,'uint8')&&(isvector(bytes)||isempty(bytes)),'diag2490:Bytes','Explicit byte vector required.');
    n=numel(bytes);assert(n<=obj.Limits.MaxEncodedBytes,'compact:ChunkCap','Byte chunks bounded by reviewed record size.');
    assert(n<=obj.Limits.MaxRawBytes-obj.Bytes,'compact:RawCap','Raw work bound before digest update.');
    b=reshape(bytes,1,[]);ends=find(b==10);added=numel(ends);
    assert(added<=obj.Limits.MaxRecords-obj.Records,'compact:RecordCap','Record count bound before digest update.');
    pending=obj.PendingBytes;
    if isempty(ends)
     pending=pending+n;assert(pending<=obj.Limits.MaxEncodedBytes,'diag2490:RecordBytes','Partial record size bound.');
    else
     lengths=diff([0 ends]);lengths(1)=lengths(1)+pending;
     assert(all(lengths<=obj.Limits.MaxEncodedBytes),'diag2490:RecordBytes','Complete record size bound.');
     pending=n-ends(end);assert(pending<=obj.Limits.MaxEncodedBytes,'diag2490:RecordBytes','Partial record size bound.');
    end
    if n>0,obj.Hasher.TransformBlock(b,0,n,b,0);end
    obj.Bytes=obj.Bytes+n;obj.Records=obj.Records+added;obj.PendingBytes=pending;
   catch e
    obj.Faulted=true;rethrow(e);
   end
  end
  function value=summary(obj)
   value=struct('Schema','csr-jsonl-digest-retention-v1','Retention','sha256-count-only', ...
    'RawBytes',obj.Bytes,'Records',obj.Records,'RawSHA256',obj.Digest,'PendingBytes',obj.PendingBytes, ...
    'Closed',obj.Closed,'Faulted',obj.Faulted,'CompleteRecords',obj.Closed&&~obj.Faulted&&obj.PendingBytes==0, ...
    'RawRecordsRetained',false,'SimulationCompleteAsserted',false);
  end
  function close(obj)
   if obj.Closed,return;end
   assert(~obj.CloseAttempted,'compact:CloseFailed','Prior close failed; preserve incomplete evidence.');
   obj.CloseAttempted=true;cleanup=onCleanup(@()obj.release());
   if obj.PendingBytes~=0,obj.Faulted=true;end
   obj.Hasher.TransformFinalBlock(uint8([]),0,0);
   obj.Digest=lower(reshape(dec2hex(uint8(obj.Hasher.Hash),2)',1,[]));
   value=obj.summary();value.Closed=true;value.CompleteRecords=~obj.Faulted&&obj.PendingBytes==0;
   receiptLimits=struct('MaxNodes',131,'MaxTextUnits',1024,'MaxDepth',4,'MaxEncodedBytes',2048);
   bytes=BoundedJsonlWriter.encodeBounded(value,receiptLimits);
   assert(numel(bytes)<=obj.Payload,'compact:ReceiptCap','Receipt reservation exceeded before write.');
   obj.File.Write(bytes,0,numel(bytes));obj.File.Flush(true);
   obj.RetainedBytes=numel(bytes);obj.Closed=true;
  end
  function delete(obj)
   if ~obj.Closed&&~obj.CloseAttempted
    obj.Faulted=true;
    try,obj.close();catch,obj.release();end
   else,obj.release();end
  end
 end
 methods (Access=private)
  function requireWritable(obj)
   assert(~obj.Closed&&~obj.CloseAttempted,'lossless:Closed','Writer is closed.');
   assert(~obj.Faulted,'compact:Faulted','Prior write failed; no further records accepted.');
  end
  function release(obj)
   if ~isempty(obj.File),obj.File.Dispose();obj.File=[];end
   if ~isempty(obj.Hasher),obj.Hasher.Dispose();obj.Hasher=[];end
  end
 end
end
