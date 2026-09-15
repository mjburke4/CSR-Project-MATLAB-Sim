import pathlib, subprocess, time, json, shutil, hashlib, os
root=pathlib.Path(__file__).resolve().parent
source=root/'ns';engine=root/'engine';module=engine/'contrib/csr';module.mkdir(parents=True,exist_ok=True)
prior=json.loads((root.parent/'csr11/evidence/tranche-10-native-build/engine-logs/module-copy.json').read_text())
files=[]
for row in prior['files']:
 rel=row['path'];src=source/rel;dst=module/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 h=hashlib.sha256(src.read_bytes()).hexdigest();assert h==row['source_sha256'];assert src.read_bytes()==dst.read_bytes();files.append(dict(path=rel,sha256=h,bytes=src.stat().st_size))
(root/'module-copy.json').write_text(json.dumps(dict(files=files,all_24_match_historical=True),indent=2)+'\n')
env=os.environ.copy();env['PYTHONPATH']=str(root/'tools')+os.pathsep+env.get('PYTHONPATH','');env['PATH']=str(root/'tools/bin')+os.pathsep+env['PATH']
cmake=str(root/'tools/bin/cmake');ninja=str(root/'tools/bin/ninja')
modules=['csr','spectrum','buildings','propagation','mobility','antenna','network','stats','core']
commands=[('configure',[cmake,'-S',str(engine),'-B',str(engine/'cmake-cache'),'-G','Ninja','-DCMAKE_MAKE_PROGRAM='+ninja,'-DCMAKE_BUILD_TYPE=Debug','-DCMAKE_CXX_STANDARD=23','-DCMAKE_CXX_COMPILER=/usr/bin/g++','-DNS3_ASSERT=ON','-DNS3_LOG=ON','-DNS3_WARNINGS_AS_ERRORS=OFF','-DNS3_EXAMPLES=OFF','-DNS3_TESTS=OFF','-DNS3_PYTHON_BINDINGS=OFF','-DNS3_ENABLED_MODULES='+';'.join(modules)]),('build',[cmake,'--build',str(engine/'cmake-cache'),'--parallel','4','--target']+modules)]
for name,cmd in commands:
 start=time.monotonic()
 proc=subprocess.run(cmd,capture_output=True,text=True,env=env)
 (root/(name+'.log')).write_text(proc.stdout+proc.stderr)
 record=dict(command=cmd,exit_code=proc.returncode,elapsed_seconds=time.monotonic()-start,output_captured_after_process_closed=True)
 (root/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n');print(name,record['exit_code'],record['elapsed_seconds'],flush=True)
 if proc.returncode: raise SystemExit(proc.returncode)
