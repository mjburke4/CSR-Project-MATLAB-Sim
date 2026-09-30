function writeJson(path,value)
fid=fopen(path,'w'); assert(fid>=0,'autocase:JsonOpen','Cannot write %s.',path);
closeFile=onCleanup(@()fclose(fid)); %#ok<NASGU>
fprintf(fid,'%s\n',jsonencode(value,'PrettyPrint',true));
end
