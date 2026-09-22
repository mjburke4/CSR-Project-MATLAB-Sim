function output = edgeRecordTable(records,prototype)
%EDGERECORDTABLE Give T14 observation fields stable scalar column types.
% struct2table can infer an N-by-width char matrix for equal-width text.
% These records require one string per row, including fixed-width hex text.
% The explicit prototype also preserves empty numeric and uint64 columns.
if ~isstruct(prototype) || ~isscalar(prototype)
    error('csr:validation:EdgeRecordSchema','A scalar record prototype is required.');
end
names = fieldnames(prototype)'; types = cell(size(names));
for k=1:numel(names)
    value = prototype.(names{k});
    if ischar(value) || (isstring(value) && isscalar(value))
        types{k} = 'string';
    elseif (isnumeric(value) || islogical(value)) && isscalar(value)
        types{k} = class(value);
    else
        error('csr:validation:EdgeRecordSchema','Prototype fields must be scalar values or text.');
    end
end
fromTable = istable(records);
if fromTable
    count = height(records); recordNames = records.Properties.VariableNames;
elseif isstruct(records)
    count = numel(records); recordNames = fieldnames(records)';
else
    error('csr:validation:EdgeRecordSchema','Records must be a table or structure array.');
end
if ~isequal(recordNames,names)
    error('csr:validation:EdgeRecordSchema','Record fields differ from the prescribed schema.');
end
output = table('Size',[count numel(names)],'VariableTypes',types,'VariableNames',names);
for k=1:numel(names)
    key = names{k}; values = output.(key);
    if fromTable, column = records.(key); end
    for row=1:count
        if fromTable
            if iscell(column), value = column{row}; else, value = column(row,:); end
        else
            value = records(row).(key);
        end
        if strcmp(types{k},'string')
            if ~((ischar(value) && (isrow(value) || isempty(value))) || ...
                    (isstring(value) && isscalar(value)))
                error('csr:validation:EdgeRecordType','Text fields must contain one value per row.');
            end
            values(row,1) = string(value);
        else
            if ~isa(value,types{k}) || ~isscalar(value)
                error('csr:validation:EdgeRecordType','Numeric fields must retain the prescribed scalar type.');
            end
            values(row,1) = value;
        end
    end
    output.(key) = values;
end
end
