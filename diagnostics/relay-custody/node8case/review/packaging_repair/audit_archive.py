"""Compare a corrected node8 kit to its issued predecessor; standard library only.
Usage: python audit_archive.py ORIGINAL.zip CORRECTED.zip OUTPUT.json
"""
import hashlib,json,sys,zipfile
from pathlib import Path
old_path,new_path,out_path=map(Path,sys.argv[1:])
sha=lambda b:hashlib.sha256(b).hexdigest()
with zipfile.ZipFile(old_path) as old,zipfile.ZipFile(new_path) as new:
    assert old.testzip() is None and new.testzip() is None
    old_names=[n for n in old.namelist() if not n.endswith('/')]
    new_names=[n for n in new.namelist() if not n.endswith('/')]
    assert len(new_names)==len(set(new_names))
    assert all(n.startswith('node8case/') and '..' not in n.split('/') for n in new_names)
    removed=sorted(set(old_names)-set(new_names)); assert not removed,removed
    changed=sorted(n for n in old_names if old.read(n)!=new.read(n))
    assert set(changed)<= {'node8case/README.md','node8case/FILES.json'},changed
    added=sorted(set(new_names)-set(old_names))
    assert 'node8case/TestQueuedRetryPolicy.m' in added
    assert all(n=='node8case/TestQueuedRetryPolicy.m' or n.startswith('node8case/review/') for n in added),added
    matlab_added=[n for n in added if n.endswith('.m')]
    assert matlab_added==['node8case/TestQueuedRetryPolicy.m'],matlab_added
    expected_test_sha='603eef79184d92c5b217039b234c98815c1b68409321da8c18441a4e7c74ccee'
    assert sha(new.read('node8case/TestQueuedRetryPolicy.m'))==expected_test_sha
    manifest=json.loads(new.read('node8case/FILES.json'))
    declared=[r['path'] for r in manifest['files']]
    assert len(declared)==len(set(declared))
    assert set('node8case/'+p for p in declared)==set(new_names)-{'node8case/FILES.json'}
    assert any(r['path']=='TestQueuedRetryPolicy.m' and r['sha256']==expected_test_sha for r in manifest['files'])
    for row in manifest['files']:
        data=new.read('node8case/'+row['path'])
        assert sha(data)==row['sha256'] and len(data)==row['bytes'],row['path']
    assert manifest['target_percent']==20 and manifest['seed']==132 and manifest['stop_seconds_exclusive']==1200
    assert manifest['entrypoint']=='run_node8_tests'
    assert manifest['model_behavior_changed'] is False and manifest['common_input_checks_unchanged'] is True
    result={'schema':'csr-node8-repaired-archive-independent-review-v1','status':'pass',
      'original_archive':{'name':old_path.name,'sha256':sha(old_path.read_bytes()),'files':len(old_names)},
      'corrected_archive':{'name':new_path.name,'sha256':sha(new_path.read_bytes()),'bytes':new_path.stat().st_size,'files':len(new_names)},
      'removed_original_files':removed,'changed_original_files':changed,'all_other_original_entries_byte_identical':True,
      'added_files':added,'only_runtime_addition':matlab_added,'restored_test_sha256':expected_test_sha,
      'manifest_complete_and_all_hashes_verified':True,'manifest_includes_restored_test':True,
      'manifest_sha256':sha(new.read('node8case/FILES.json')),'matlab_execution_performed':False}
    out_path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['status','corrected_archive','changed_original_files','only_runtime_addition','manifest_complete_and_all_hashes_verified']}))
