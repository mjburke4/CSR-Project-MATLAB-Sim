function write_json(file,value)
fid=fopen(file,'wb');assert(fid>=0,'auto6000:Open','Cannot open %s',file);
c=onCleanup(@()fclose(fid)); %#ok<NASGU>
assert(fprintf(fid,'%s\n',jsonencode(value))>0,'auto6000:Write','Cannot write %s',file);
end
