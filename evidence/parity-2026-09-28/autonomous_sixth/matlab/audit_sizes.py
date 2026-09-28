from pathlib import Path
import csv,json,hashlib,collections
root=Path(__file__).resolve().parents[1]
fixture=root.parents[0]/'autonomous_fifth/kit/autocase/ref/native/tx_signatures.csv'
rows=list(csv.DictReader(fixture.open()))
counts=collections.Counter(); mismatches=[];routing=[]
for r in rows:
 k=int(r['kind']); counts[(k,r['routing_section_origin'])]+=1
 if k==6:
  raw=bytes.fromhex(r['routing_section_hex']);base=16+len(raw); actual=int(r['wire_bytes'])
  routing.append(dict(tx_id=r['tx_id'],time_ns=r['time_ns'],origin=r['routing_section_origin'],native_wire=actual,matlab_untagged_wire=base,semantic_hex=r['routing_section_hex']))
  if actual!=base:mismatches.append(routing[-1])
cases=[]
for name in ['G_population','H_admission_route']:
 d=json.loads((root/'data'/name/'first_divergence.json').read_text());status=json.loads((root/'data'/name/'random_summary.json').read_text())
 cases.append(dict(name=name,divergence=d,summary={k:v for k,v in status.items() if k not in ['first_divergence','first_context_mismatch','counts']}))
out=dict(schema='csr-sixth-control-size-audit-v1',fixture_sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
 native_routing_children=len(routing),ordinary_formula_mismatches=mismatches,
 kind_origin_counts=[dict(kind=k[0],origin=k[1],count=v) for k,v in sorted(counts.items())],cases=cases,
 matlab_execution_performed_here=False,scope='Read-only supplied owner evidence, native fixture, and source-size arithmetic')
(root/'matlab/size_audit.json').write_text(json.dumps(out,indent=2)+'\n')
with (root/'matlab/routing_sizes.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(routing[0]));w.writeheader();w.writerows(routing)
print('Native routing children',len(routing),'ordinary size mismatches',len(mismatches));print(collections.Counter(x['origin'] for x in mismatches))
for name in ['G_population','H_admission_route']:
 s=json.loads((root/'data'/name/'random_summary.json').read_text());print(name,{k:v for k,v in s.items() if k not in ['first_divergence','first_context_mismatch','counts']})
