"""Three-seed descriptive comparison with explicitly different input identities."""
from pathlib import Path
import csv
import math
import statistics
from analyze_tranche11_return import require, json_object, sha256, safe_path, record_map, all_files
import tranche19_metrics as metrics
import tranche20_native_metrics as native_metrics

PIN='486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b'
ENGINE='6b5cd24ea80713ce16d88575869aedd6f432bdae'

def verify_seed_derivation(parent,derived,seed):
    with Path(parent).open(newline='') as stream: before=list(csv.DictReader(stream))
    with Path(derived).open(newline='') as stream: after=list(csv.DictReader(stream))
    require(len(before)==len(after) and before and all(set(a)==set(b) for a,b in zip(before,after)), 'Native seed input shape changed')
    changes=[[i,k,a[k],b[k]] for i,(a,b) in enumerate(zip(before,after)) for k in a if a[k]!=b[k]]
    require(before[0]['record']=='run' and changes==[[0,'seed','128',str(seed)]], 'Native input changed beyond run.seed')
    return changes

def verify_native(source_root,seed):
    source_root=Path(source_root); root=source_root/'evidence/tranche-20-ns3-reference'; directory=root/f's{seed}'
    manifest=json_object(directory/'manifest.json'); build=json_object(root/'build.json')
    require(manifest.get('schema')=='csr-tranche20-native-reference-v1' and manifest.get('status')=='completed' and
        manifest.get('ns3_source_commit')==PIN and manifest.get('engine_commit')==ENGINE and
        manifest.get('observer_enabled') is False and manifest.get('build_sha256')==sha256(root/'build.json') and
        manifest.get('runner_sha256')==build.get('runner_sha256'),'Native run/build identity mismatch')
    require(build.get('schema')=='csr-tranche20-native-build-v1' and build.get('status')=='verified-reused-pristine' and
        build.get('ns3_source_commit')==PIN and build.get('engine_commit')==ENGINE and build.get('observer_enabled') is False,
        'Native build provenance mismatch')
    for name,key in [('t18-build.json','t18_build_sha256'),('t18-environment-build.json','t18_environment_sha256')]:
        require(sha256(root/name)==build.get(key),'Native reused build binding mismatch')
    bindings=record_map(manifest.get('files'),'native files',sizes=True)
    require(set(bindings)==all_files(directory)-{'manifest.json'}, 'Native file inventory incomplete')
    for name,row in bindings.items():
        p=safe_path(directory,name)
        require(p.stat().st_size==row['bytes'] and sha256(p)==row['sha256'],'Native artifact mismatch: '+name)
    for stage in ('run_ns3','aggregate_ns3'):
        require(manifest.get('stages',{}).get(stage,{}).get('exit_code')==0,'Native stage failed')
    parent=source_root/'scenarios/benchmarks/campus_multihop_6000.csv'; derived=directory/'scenario.csv'
    changes=verify_seed_derivation(parent,derived,seed); recipe=json_object(directory/'seed-recipe.json')
    require(recipe==manifest.get('seed_recipe') and recipe.get('parent_sha256')==sha256(parent) and
        recipe.get('scenario_sha256')==sha256(derived) and recipe.get('field_changes')==changes and
        recipe.get('only_run_seed_changed') is True and recipe.get('seed')==seed,'Native seed recipe binding mismatch')
    case=manifest.get('case',{})
    require(case.get('seed')==seed and case.get('case_id')==f's{seed}' and case.get('duration_s')==6000 and
        case.get('scenario_sha256')==sha256(derived),'Native case identity mismatch')
    result=native_metrics.native_applications(directory)
    require(result==json_object(directory/'native-applications.json'),'Native application reconstruction mismatch')
    require(result['totals']['attempts']==1710000 and {f['source'] for f in result['flows']}=={2,3,4,5,7,8},'Native traffic population mismatch')
    result['input_provenance']={'original_sha256':sha256(parent),'derived_sha256':sha256(derived),'seed':seed,'field_changes':changes}
    return result

def analyze_case(directory,case):
    result=metrics.analyze_case(directory,case)
    result['schema']='csr-tranche20-ownership-metrics-v1'
    result['seed']=case['seed']
    result['limitations'][-1]='One seed in the unchanged default-policy ensemble. Event histories and RNG consumption differ across seeds and engines; no cross-engine packet identity joins.'
    return result


def describe(values):
    return {'mean':statistics.fmean(values),'minimum':min(values),'maximum':max(values)}

def compare_seeds(matlab,native,band_percent=5):
    require(set(matlab)==set(native)=={128,129,130},'Exactly all three seeds required')
    require(math.isfinite(band_percent) and band_percent>=0,'Invalid descriptive band')
    maps={engine:{seed:{r['source']:r for r in data[seed]['flows']} for seed in data} for engine,data in [('matlab',matlab),('ns3',native)]}
    sources={2,3,4,5,7,8}
    require(all(set(m)==sources for engine in maps.values() for m in engine.values()),'Flow populations differ')
    rows=[]; summaries=[]
    for source in [None,*sorted(sources)]:
        for metric in ('admitted','delivered'):
            ms=[];ns=[];rs=[];ds=[]
            for seed in (128,129,130):
                m=(matlab[seed]['totals'] if source is None else maps['matlab'][seed][source])[metric]
                n=(native[seed]['totals'] if source is None else maps['ns3'][seed][source])[metric]
                require(isinstance(m,(int,float)) and isinstance(n,(int,float)) and math.isfinite(m) and math.isfinite(n) and m>=0 and n>=0,'Invalid counts')
                residual=100*(m-n)/n if n else None
                rows.append({'seed':seed,'source':source,'metric':metric,'matlab':m,'ns3':n,'delta':m-n,
                    'residual_percent':residual,'within_descriptive_band':abs(residual)<=band_percent if residual is not None else None})
                ms.append(m);ns.append(n);ds.append(m-n);rs.append(residual)
            summaries.append({'source':source,'metric':metric,'matlab':describe(ms),'ns3':describe(ns),
                'delta':describe(ds),'per_seed_residual_percent':describe(rs) if all(x is not None for x in rs) else None,
                'pooled_ratio_of_sums_percent':100*(sum(ms)-sum(ns))/sum(ns) if sum(ns) else None,
                'signed_residual_consistency':'positive_all' if all(x>0 for x in ds) else 'negative_all' if all(x<0 for x in ds) else 'zero_all' if all(x==0 for x in ds) else 'mixed_or_zero',
                'all_seeds_within_descriptive_band':all(x is not None and abs(x)<=band_percent for x in rs)})
    return {'schema':'csr-tranche20-multi-seed-comparison-v1','seeds':[128,129,130],'band_percent':band_percent,
        'band_is_acceptance_gate':False,'statistical_equivalence_established':False,'rows':rows,'summaries':summaries,
        'scope':'All three seeds and all six flows; mean per-seed percentage and pooled ratio of sums are distinct. Three seeds do not establish statistical equivalence.'}
