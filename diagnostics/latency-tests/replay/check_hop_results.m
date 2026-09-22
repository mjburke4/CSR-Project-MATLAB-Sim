function checks=check_hop_results(rows,cases)
% Check terminal ownership separately from the effect of prescribed feedback.
assert(isequal(sort(unique(rows.case_id)),sort(cases.case_id)),'Missing or extra HOP cases');
checks=table();
for k=1:height(cases)
    r=rows(rows.case_id==cases.case_id(k),:);
    initial=r(r.event=="admit",:); before=r(r.event=="feedback_before",:);
    after=r(r.event=="feedback_after",:); final=r(r.event=="final",:);
    assert(height(initial)==1 && height(before)==1 && height(after)==1 && height(final)==1, ...
        'Missing or duplicate HOP checkpoints');
    expired=cases.feedback_effect(k)=="expired";
    assert(expired || cases.feedback_effect(k)=="ack",'Unknown expected feedback effect');
    check('initial_pending',initial.hop_pending,1);
    check('before_pending',before.hop_pending,double(~expired));
    check('before_outstanding',before.neighbor_outstanding,double(~expired));
    check('before_released',before.released,double(expired));
    check('after_pending',after.hop_pending,0);
    check('after_outstanding',after.neighbor_outstanding,0);
    check('after_released',after.released,1);
    check('feedback_release_delta',after.released-before.released,double(~expired));
    check('final_pending',final.hop_pending,0);
    check('final_data_queue',final.data_queue,0);
    check('final_outstanding',final.neighbor_outstanding,0);
    check('final_released',final.released,1);
    check('final_delivered',final.delivered,double(cases.upstream_first_s(k)>=0)+double(cases.upstream_second_s(k)>=0));
end
    function check(field,actual,expected)
        checks=[checks;table(cases.case_id(k),string(field),actual,expected, ...
            isfinite(actual)&&actual==expected, ...
            'VariableNames',{'case_id','field','actual','expected','pass'})]; %#ok<AGROW>
    end
end
