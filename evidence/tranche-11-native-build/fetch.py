import pathlib, subprocess, time, json, concurrent.futures
root=pathlib.Path(__file__).resolve().parent
specs=[('engine','https://github.com/nsnam/ns-3-dev-git.git','6b5cd24ea80713ce16d88575869aedd6f432bdae'),('ns','https://github.com/mjburke4/CSR-Project-NS3-part2.git','486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b')]
def fetch(spec):
 name,url,commit=spec; work=root/name; records=[]
 cmds=[['git','init',str(work)],['git','-C',str(work),'remote','add','origin',url],['git','-C',str(work),'fetch','--depth=1','origin',commit],['git','-C',str(work),'checkout','--detach','FETCH_HEAD']]
 with (root/(name+'-fetch.log')).open('w') as log:
  for cmd in cmds:
   start=time.monotonic();proc=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT);records.append(dict(command=cmd,exit_code=proc.returncode,elapsed_seconds=time.monotonic()-start));log.flush()
   if proc.returncode: break
 (root/(name+'-fetch.json')).write_text(json.dumps(records,indent=2)+'\n');return name,records[-1]['exit_code']
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for result in pool.map(fetch,specs):print(result,flush=True)
