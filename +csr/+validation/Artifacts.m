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
            hasher.update(typecast(bytes,'int8'));
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
            % Include executable MATLAB, BER data and shared inputs. Result
            % directories are excluded so creating evidence cannot change it.
            listing = [dir(fullfile(root,'*.m')); ...
                dir(fullfile(root,'+csr','**','*.m')); ...
                dir(fullfile(root,'tests','**','*.m')); ...
                dir(fullfile(root,'data','**','*')); ...
                dir(fullfile(root,'scenarios','shared','**','*'))];
            candidate = fullfile(root,'evidence','tranche-4-candidate.json');
            if isfile(candidate), listing = [listing; dir(candidate)]; end
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
                    'MATLAB source, BER data, shared inputs or candidate changed during validation.');
            end
        end

        function files = fileInventory(directory)
            source = javaObject('java.io.File',directory);
            directory = char(source.getCanonicalPath());
            listing = dir(fullfile(directory,'**','*'));
            listing = listing(~[listing.isdir]);
            files = repmat(struct('path','','sha256','','bytes',0),numel(listing),1);
            for k = 1:numel(listing)
                path = fullfile(listing(k).folder,listing(k).name);
                files(k).path = strrep(path(numel(directory)+2:end),filesep,'/');
                files(k).sha256 = csr.validation.Artifacts.sha256(path);
                files(k).bytes = listing(k).bytes;
            end
            [~,order] = sort({files.path}); files = files(order);
        end
    end
end
