#!/usr/bin/env python3
"""Build finite shared-input vectors; expected answers come from native production execution."""
import csv, pathlib
P=pathlib.Path(__file__).resolve().parent
rows=[]
sets={
 'empty':[], 'expired_only':[-1,-2], 'outside_range':[32,63,255,256],
 'zero':[0], 'upper_endpoint':[31], 'last_modulo_slot':[30],
 'wrap_chain':[30,0,1,2], 'upper_chain':[28,29,30,31],
 'duplicate_midpoint':[15,15], 'hole_zero':[x for x in range(32) if x!=0],
 'hole_one':[x for x in range(32) if x!=1],
 'hole_thirty':[x for x in range(32) if x!=30],
 'history9':[9], 'history3_27':[3,27], 'history14_16_23':[14,16,23],
 'history5_28':[5,28], 'history7_13':[7,13]}
for name,counters in sets.items():
 for draw in range(32):
  rows.append(dict(case_id=f'{name}_d{draw:02}',kind='select',local=3,reported=99,reduction=0,initial_draw=draw,counters=';'.join(map(str,counters)),expected_class='slot'))
for name,counters in [('occupied_modulo_ring',list(range(31))),('occupied_all',list(range(32)))]:
 for draw in [0,30,31]:
  rows.append(dict(case_id=f'{name}_d{draw:02}',kind='select',local=3,reported=99,reduction=0,initial_draw=draw,counters=';'.join(map(str,counters)),expected_class='slot' if name=='occupied_modulo_ring' and draw==31 else 'probe_exhausted'))
for local in [0,1,4,5,8,9,12,13,255]:
 base=31 if local<=4 else 63 if local<=8 else 127 if local<=12 else 255
 for reported in [0,300]:
  for reduction in [-2,0,1,2,base-2,base-1,base,base+1]:
   rows.append(dict(case_id=f'range_l{local}_n{reported}_r{reduction}',kind='range',local=local,reported=reported,reduction=reduction,initial_draw='',counters='',expected_class='range'))
with (P/'vectors.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(f'{len(rows)} cases: 550 selections, 144 active-node/range cases')
