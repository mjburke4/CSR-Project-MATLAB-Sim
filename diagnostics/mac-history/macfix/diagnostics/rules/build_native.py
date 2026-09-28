#!/usr/bin/env python3
"""Create a disposable RNG-only seam in production MAC; preserve algorithm body."""
import argparse, hashlib, json, pathlib, shutil, subprocess
P=pathlib.Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--source',type=pathlib.Path,required=True);p.add_argument('--engine-build',type=pathlib.Path,required=True);a=p.parse_args()
source=a.source.resolve();build=a.engine_build.resolve();overlay=P/'overlay'/'ns3';overlay.mkdir(parents=True,exist_ok=True)
for f in (source/'model').glob('*.h'): shutil.copy2(f,overlay/f.name)
f=overlay/'csr-mac-core.h';original=f.read_text();text=original
text=text.replace('#include <algorithm>','#include <algorithm>\nint CsrRuleDraw(int low, int high);',1)
anchor='if (m_slotSelectionProfile ==\n        SlotSelectionProfile::HIST_2014_NEXT_TSLOT_MODULO_PROBE)'
pos=text.index(anchor,text.index('  PickTxSlot (CsrNodeId dest)'))
before=text[:pos];branch=text[pos:]
old='int chosenSlot = rng->GetInteger (0, slotRange);';new='int chosenSlot = CsrRuleDraw (0, slotRange);'
assert branch.count(old)==1
text=before+branch.replace(old,new,1);f.write_text(text)
assert text.replace(new,old,1).replace('\nint CsrRuleDraw(int low, int high);','',1)==original
cmd=['g++','-std=c++23','-O0','-g','-DNS3_ASSERT_ENABLE','-DNS3_BUILD_PROFILE_DEBUG','-DNS3_LOG_ENABLE','-DSTACKTRACE_LIBRARY_IS_LINKED=1','-D__LINUX__','-I'+str(P/'overlay'),'-I'+str(build/'include'),str(P/'native_vectors.cc'),'-L'+str(build/'lib'),'-Wl,-rpath,'+str(build/'lib'),'-Wl,--no-as-needed','-lns3-dev-csr-debug','-Wl,--as-needed']+['-lns3-dev-'+n+'-debug' for n in ['spectrum','buildings','propagation','mobility','antenna','network','stats','core']]+['-lstdc++exp','-o',str(P/'native-vectors')]
r=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);(P/'compile.log').write_text(r.stdout)
receipt={'command':cmd,'exit_code':r.returncode,'production_mac_sha256':hashlib.sha256(original.encode()).hexdigest(),'overlay_mac_sha256':hashlib.sha256(text.encode()).hexdigest(),'seam':'Only historical initial integer draw replaced; checked inverse patch exactly reproduces production MAC header','original_source':str(source),'engine_build':str(build)}
(P/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if r.returncode: print(r.stdout);raise SystemExit(r.returncode)
print('Production native slot vector runner built')
