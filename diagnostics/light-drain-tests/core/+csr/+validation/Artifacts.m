classdef Artifacts
    %ARTIFACTS Raw-byte provenance for portable MATLAB validation exports.
    methods (Static)
        function value = utcNow()
            value = char(datetime('now','TimeZone','UTC', ...
                'Format','yyyy-MM-dd''T''HH:mm:ss.SSS''Z'''));
        end

        function digest = sha256(path)
            if ~usejava('jvm')
                error('csr:validation:JVMRequired','Hashing requires MATLAB with its standard JVM.');
            end
            fid = fopen(path,'rb');
            if fid < 0, error('csr:validation:Read','Cannot read %s.',path); end
            cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
            bytes = fread(fid,Inf,'*uint8');
            hasher = javaMethod('getInstance','java.security.MessageDigest','SHA-256');
            % MATLAB cannot reliably dispatch an empty array to Java's
            % overloaded update methods. No update hashes the empty stream.
            if ~isempty(bytes), hasher.update(typecast(bytes,'int8')); end
            raw = typecast(hasher.digest(),'uint8');
            digest = lower(reshape(dec2hex(raw,2).',1,[]));
        end

        function writeJson(path,value)
            fid = fopen(path,'w');
            if fid < 0, error('csr:validation:Write','Cannot write %s.',path); end
            cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
            fprintf(fid,'%s\n',jsonencode(value,'PrettyPrint',true));
        end

        function files = sourceSnapshot(root)
            root = csr.validation.Artifacts.canonicalPath(root);
            % Bind simulator and analysis code, BER data, shared inputs and
            % candidate identities. Results are excluded: writing evidence
            % must not invalidate the source snapshot that produced it.
            listing = [dir(fullfile(root,'*.m')); ...
                dir(fullfile(root,'+csr','**','*.m')); ...
                dir(fullfile(root,'tests','**','*.m')); ...
                dir(fullfile(root,'examples','**','*.m')); ...
                dir(fullfile(root,'scripts','**','*.py')); ...
                dir(fullfile(root,'scripts','**','*.cc')); ...
                dir(fullfile(root,'scripts','**','*.h')); ...
                dir(fullfile(root,'data','**','*')); ...
                dir(fullfile(root,'scenarios','**','*')); ...
                dir(fullfile(root,'evidence','tranche-*-candidate.json')); ...
                dir(fullfile(root,'evidence','source-baseline.json'))];
            listing = listing(~[listing.isdir]);
            files = repmat(struct('path','','sha256',''),numel(listing),1);
            for k = 1:numel(listing)
                path = fullfile(listing(k).folder,listing(k).name);
                files(k).path = strrep(path(numel(root)+2:end),filesep,'/');
                files(k).sha256 = csr.validation.Artifacts.sha256(path);
            end
            [~,indices] = unique({files.path});
            files = files(indices);
        end

        function checkSnapshot(root,expected)
            if ~isequal(expected,csr.validation.Artifacts.sourceSnapshot(root))
                error('csr:validation:SourceChanged', ...
                    'Simulator/analysis source, BER data, shared inputs or candidate changed during validation.');
            end
        end

        function path = canonicalPath(path)
            if isstring(path) && isscalar(path), path = char(path); end
            if ~ischar(path) || ~isrow(path) || isempty(path)
                error('csr:validation:Path','Expected a nonempty path.');
            end
            source = javaObject('java.io.File',path);
            if ~source.isAbsolute()
                % JVM user.dir need not follow MATLAB cd. Supply MATLAB's
                % current folder explicitly without changing Java globals.
                source = javaObject('java.io.File',pwd,path);
            end
            path = char(source.getCanonicalPath());
        end

        function files = fileInventory(directory,excludedPaths)
            if nargin < 2, excludedPaths = {}; end
            directory = csr.validation.Artifacts.canonicalPath(directory);
            if ~isfolder(directory)
                error('csr:validation:Directory','Inventory directory does not exist: %s.',directory);
            end
            listing = dir(fullfile(directory,'**','*'));
            listing = listing(~[listing.isdir]);
            files = repmat(struct('path','','sha256','','bytes',0),numel(listing),1);
            for k = 1:numel(listing)
                path = fullfile(listing(k).folder,listing(k).name);
                files(k).path = strrep(path(numel(directory)+2:end),filesep,'/');
                if ismember(files(k).path,excludedPaths), continue; end
                files(k).sha256 = csr.validation.Artifacts.sha256(path);
                files(k).bytes = listing(k).bytes;
            end
            files = files(~ismember({files.path},excludedPaths));
            [~,order] = sort({files.path}); files = files(order);
        end
    end
end
