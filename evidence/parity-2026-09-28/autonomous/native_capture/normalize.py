#!/usr/bin/env python3
"""Normalize only prefix-verified passive native observations."""
from pathlib import Path
import collections,csv,gzip,hashlib,itertools,json
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
RUN=HERE/'run'
REFERENCE=HERE/'fixture/native_s132_prefix_0_330.csv.gz'
STOP=330_000_000_000

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def write(path,fields,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def tx_signatures(obs):
    """Actual wire serialization, after MAC control/header updates."""
    txs=[];children={};hexes={}
    for line in (RUN/'mac-input.log').open():
        parts=line.rstrip('\n').split('|');kind=parts.pop(0)
        if kind=='TX':
            txs.append(dict(zip('event_order time_ns node rate power preamble next_slot consumed_slot segments'.split(),parts)))
        elif kind=='TXFRAME':
            row=dict(zip('time_ns node child_index source destination sequence kind wirebytes frame_id'.split(),parts))
            key=tuple(row[k] for k in ('time_ns','node','child_index'))
            assert key not in children
            children[key]=row
        elif kind=='TXHEX':
            row=dict(zip('time_ns node child_index frame_id packet_hex'.split(),parts))
            key=tuple(row[k] for k in ('time_ns','node','child_index'))
            assert key not in hexes
            hexes[key]=row
    assert children.keys()==hexes.keys(),('incomplete actual TX bytes',len(children),len(hexes))
    native={}
    hop_apps={};discovery_meta={}
    for r in obs:
        if r['event']=='discovery_plaintext':
            key=(r['node'],r['frame_id']);assert key not in discovery_meta
            discovery_meta[key]=json.loads(r['detail_json'])
        if r['event'] in ('hop_admit','node5_hop_admit'):
            d=json.loads(r['detail_json']);key=(r['node'],r['peer'],d['sequence'])
            assert key not in hop_apps,('reused HOPsequence',key)
            hop_apps[key]=(r['app_source'],r['app_sequence'])
        if r['event'] not in ('mac_tx','node5_mac_tx'): continue
        key=(r['time_ns'],r['node']);assert key not in native
        native[key]=r
    apps={}
    for r in csv.DictReader((RUN/'ns3-trace.csv').open()):
        if r['event']!='app_admission' or r['success']!='1': continue
        detail=dict(s.split('=',1) for s in r['detail'].split(';') if '=' in s)
        key=(r['src'],r['sequence']);assert key not in apps
        apps[key]=dict(app_attempt_index=detail['attempt_index'],app_flow_index=detail['flow_index'],
                       app_generated_time_ns=str(int(Decimal(r['time_s'])*10**9)),native_app_sequence=r['sequence'])
    rows=[]
    counts=collections.Counter()
    for t in txs:
        key=(t['time_ns'],t['node'])
        assert key in native
        physical_id=native[key]['tx_id'];counts[t['node']]+=1
        assert int(physical_id)==(int(t['node'])<<32)|counts[t['node']]
        n=int(t['segments'])
        total_wire=sum(int(children[key+(str(i),)]['wirebytes']) for i in range(n))
        for i in range(n):
            c=children[key+(str(i),)];x=hexes[key+(str(i),)]
            assert c['frame_id']==x['frame_id']
            b=bytes.fromhex(x['packet_hex']);assert len(b)>=13
            def integer(a,n,signed=False): return int.from_bytes(b[a:a+n],'big',signed=signed)
            assert integer(0,3)==int(c['source']) and integer(3,3)==int(c['destination'])
            assert integer(6,2)==int(c['sequence']) and b[10]==int(c['kind'])
            flags=b[9];offset=13
            ack=dack=0;power=rxpower=security='';destseq=[]
            if flags&8:
                ack=integer(offset,8);dack=integer(offset+8,8);offset+=16
            if flags&32:
                power=integer(offset,2,True)/10;rxpower=integer(offset+2,2,True)/10;offset+=4
            if flags&64: security=integer(offset,2);offset+=2
            if flags&16:
                ndest=b[offset];offset+=1
                for j in range(ndest):
                    destseq.append(str(integer(offset,3))+':'+str(integer(offset+3,2)));offset+=5
            payload=b[offset:]
            nwksrc=nwkdst=nwkdscp=''
            if int(c['kind'])==0:
                assert len(payload)>=7
                nwksrc=int.from_bytes(payload[0:3],'big');nwkdst=int.from_bytes(payload[3:6],'big');nwkdscp=payload[6]
            app={k:'' for k in ['app_attempt_index','app_flow_index','app_generated_time_ns','native_app_sequence']}
            routing={k:'' for k in ['routing_section_hex','routing_sequence','routing_section','routing_total_sections',
                                    'routing_operation','routing_sender','routing_active_nodes','routing_section_origin']}
            snmp={k:'' for k in ['snmp_source','snmp_destination','snmp_destination_type','snmp_command','snmp_value','snmp_nodes']}
            control={k:'' for k in ['discover_subtype','discover_sequence','discover_active_peers',
                'check_subtype','check_sequence','check_target','check_active',
                'control_native_active_nodes','control_node_type','control_speed_key','control_s0_dbm',
                'control_payload_origin']}
            if int(c['kind'])==0:
                appkey=hop_apps[(c['source'],c['destination'],c['sequence'])]
                assert int(appkey[0])==nwksrc
                app=apps[appkey]
            if int(c['kind'])==6:
                # Native Group16: 3-byte packed key/sequence, unencrypted
                # compatibility payload, 2-byte authentication trailer.
                plain=payload[3:-2] if flags&128 else payload
                assert len(plain)>=32
                po=30+(16 if plain[26]==4 else 0)
                chirps=plain[po];po+=1+3*chirps
                routes=plain[po];po+=1
                for ri in range(routes):
                    assert len(plain)>=po+12
                    paths=plain[po+11];po+=12+3*paths
                section=plain[po:]
                origin='actual_arl_section'
                if not section:
                    # Native REQUESTs are a compatibility CsrHelloHeader
                    # operation; MATLAB uses an equivalent ARL REQUEST record.
                    assert plain[26]==3 and chirps==0 and routes==0,('unsupported legacy routing normalization',plain.hex())
                    section=plain[20:26]+bytes([3])
                    origin='normalized_legacy_request'
                assert len(section)>=6,('routing ARLprefixmissing',t,c,plain.hex(),po)
                routing.update(routing_section_hex=section.hex(),routing_sequence=int.from_bytes(plain[20:24],'big'),
                     routing_section=plain[24],routing_total_sections=plain[25],routing_operation=plain[26],
                     routing_sender=int.from_bytes(plain[0:3],'big'),routing_active_nodes=plain[8],routing_section_origin=origin)
            if int(c['kind'])==7:
                assert len(payload)>=13 and len(payload)==13+3*payload[12]
                snmp.update(snmp_source=int.from_bytes(payload[0:3],'big'),snmp_destination=int.from_bytes(payload[3:6],'big'),
                     snmp_destination_type=payload[6],snmp_command=payload[7],snmp_value=int.from_bytes(payload[8:12],'big',signed=True),
                     snmp_nodes=';'.join(str(int.from_bytes(payload[13+3*j:16+3*j],'big')) for j in range(payload[12])))
            if int(c['kind']) in (4,5):
                # GroupEstablish encrypts Discover; bind passive metadata
                # observed at SendProtectedDiscovery to its exact frame tag.
                # Pairwise16 leaves NeighborCheck plaintext and needs no key.
                if int(c['kind'])==4:
                    assert flags&128 and flags&64
                    d=discovery_meta[(c['source'],c['frame_id'])]
                    subtype=int(d['subtype']);assert subtype in (0,1)
                    control.update(discover_subtype={0:'broadcast',1:'chirp'}[subtype],
                        discover_sequence=d['discovery_sequence'],discover_active_peers=d['active_peers'],
                        control_native_active_nodes=d['native_active_nodes'],control_node_type=d['node_type'],
                        control_speed_key=d['speed_key'],control_s0_dbm=d['s0_dbm'],
                        control_payload_origin='passive_pre_encryption_metadata')
                else:
                    assert flags&64 and not flags&128
                    plain=payload[3:-2]
                    origin='pairwise16_plaintext'
                    assert len(plain)>=32 and int.from_bytes(plain[0:3],'big')==int(c['source'])
                    po=30+(16 if plain[26]==4 else 0)
                    chirps=plain[po];po+=1+3*chirps
                    routes=plain[po];po+=1
                    assert routes==0 and po==len(plain),(c,origin,plain.hex(),po)
                    control.update(control_native_active_nodes=plain[8],control_node_type=plain[9],
                        control_speed_key=plain[5],control_s0_dbm=int.from_bytes(plain[6:8],'big',signed=True)/10,
                        control_payload_origin=origin)
                    assert plain[10]==3 and plain[11] in (0,1,2,3,4)
                    control.update(check_subtype={0:'discovery',1:'message',2:'no_path',3:'overheard',4:'verify'}[plain[11]],
                        check_sequence=int.from_bytes(plain[16:20],'big'),check_target=int.from_bytes(plain[12:15],'big'))
                    if plain[11]==0:
                        assert plain[8] in (0,3)
                        control['check_active']=int(plain[8]==3)
            rows.append(dict(time_ns=t['time_ns'],event_order=t['event_order'],tx_id=physical_id,
                source=t['node'],source_tx_ordinal=counts[t['node']],rate_kbps=t['rate'],tx_power_dbm=t['power'],
                preamble=t['preamble'],reservation_slot=t['next_slot'],consumed_slot=t['consumed_slot'],
                child_count=n,total_wire_bytes=total_wire,child_index=i,hop_source=c['source'],
                hop_destination=c['destination'],hop_sequence=c['sequence'],kind=c['kind'],wire_bytes=c['wirebytes'],
                frame_id=c['frame_id'],dscp=b[8],flags=flags,ackable=int(bool(flags&1)),is_ack=int(bool(flags&2)),
                is_dack=int(bool(flags&4)),has_ack_window=int(bool(flags&8)),ack_bitmap=str(ack),dack_bitmap=str(dack),
                ack_bitmap_hex=f'{ack:016x}',dack_bitmap_hex=f'{dack:016x}',
                destination_type=b[11],speed_key=b[12],has_link_control=int(bool(flags&32)),
                child_tx_power_dbm=power,child_rx_power_dbm=rxpower,security_count=security,
                destination_sequences=';'.join(destseq),compatibility_header_bytes=offset,
                compatibility_payload_bytes=len(payload),network_source=nwksrc,network_destination=nwkdst,
                network_dscp=nwkdscp,application_bytes=len(payload)-7 if int(c['kind'])==0 else '',
                payload_hex=payload.hex(),packet_hex=x['packet_hex'],**app,**routing,**snmp,**control))
    return rows,len(txs)

def main():
    with gzip.open(REFERENCE,'rt',newline='') as a,(RUN/'ns3-trace.csv').open(newline='') as b:
        ar,br=csv.DictReader(a),csv.DictReader(b)
        assert ar.fieldnames==br.fieldnames and len(ar.fieldnames)==30
        def bounded(rows):
            return itertools.takewhile(lambda r:float(r['time_s'])<330,rows)
        count=0
        for left,right in itertools.zip_longest(bounded(ar),bounded(br)):
            assert left==right, ('canonical prefix differs',count,left,right)
            count+=1
    assert count>40_000
    with (RUN/'observations.tsv').open(newline='') as f:
        obs=list(csv.DictReader(f,delimiter='\t'))
    assert all(0<=int(r['time_ns'])<STOP for r in obs)
    orders=[int(r['event_order']) for r in obs]
    assert orders==sorted(set(orders))
    fields=['event_order','time_ns','node','purpose','ordinal','value','low','high',
            'mean','variance','tx_id','interval_ordinal','component',
            'interval_start_ns','interval_end_ns','component_start_ns','component_end_ns',
            'bits','probability','rng_consumed','active_nodes','reported_nodes',
            'reservation_counter','reservation_slot','profile','state','cause']
    purpose={'mac_draw':'mac_slot','rx_sync_draw':'sync_threshold','rx_binomial_draw':'phy_binomial'}
    rows=[]
    ordinal=collections.Counter()
    intervals={}
    eventcounts=collections.Counter(r['event'] for r in obs)
    for r in obs:
        d=json.loads(r['detail_json'])
        if r['event']=='rx_error_interval':
            key=(r['node'],r['tx_id'],d['interval_ordinal'])
            assert key not in intervals
            intervals[key]=d
        if r['event'] not in purpose: continue
        item={k:'' for k in fields}
        item.update({k:r[k] for k in ('event_order','time_ns','node','tx_id')})
        item.update({k:d[k] for k in fields if k in d})
        item.update(purpose=purpose[r['event']],ordinal=d['draw_ordinal'],
                    value=d['draw'],state=r['state_before'])
        if item['purpose']=='sync_threshold': item['rng_consumed']='1'
        if item['rng_consumed']=='1':
            key=(item['node'],item['purpose']);ordinal[key]+=1
            assert int(item['ordinal'])==ordinal[key],('draw ordinal gap',item,ordinal[key])
        if item['purpose']=='phy_binomial':
            assert (r['node'],r['tx_id'],d['interval_ordinal']) in intervals
            assert item['component'] in ['header','payload']
            assert item['rng_consumed']=='1' and int(item['bits'])>0 and 0<float(item['probability'])<1
        rows.append(item)
    assert {r['node'] for r in rows}=={'1','2','3','4','5','7','8'}
    fixture=HERE/'fixture';fixture.mkdir(exist_ok=True)
    write(fixture/'random_draws.csv',fields,rows)
    txrows,txcount=tx_signatures(obs)
    write(fixture/'tx_signatures.csv',list(txrows[0]),txrows)
    details=[]
    for r in obs:
        if r['event'] not in ('receiver_state','receiver_boundary','timer_lifecycle','sync_change'):
            continue
        details.append(r)
    write(fixture/'receiver_history.csv',list(obs[0]),details)
    summary={'schema':'csr-autonomous-passive-native-capture-v1',
       'status':'verified_exact_native_prefix','canonical_rows':count,'canonical_fields':ar.fieldnames,
       'stop_ns_exclusive':STOP,'observation_rows':len(obs),'random_rows':len(rows),
       'receiver_history_rows':len(details),'tx_count':txcount,'tx_children':len(txrows),'event_counts':dict(eventcounts),
       'draw_counts':[{'node':node,'purpose':purpose,'rows':n} for (node,purpose),n in sorted(ordinal.items())],
       'source_pin':'486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b',
       'engine_pin':'6b5cd24ea80713ce16d88575869aedd6f432bdae',
       'sha256':{str(p.relative_to(ROOT)):sha(p) for p in [REFERENCE,RUN/'ns3-trace.csv',RUN/'observations.tsv',
                    fixture/'random_draws.csv',fixture/'receiver_history.csv',fixture/'tx_signatures.csv',HERE/'prepare_overlay.py',HERE/'base_prepare_overlay.py']},
       'limitations':['Native EventId IDs have no cross-engine identity; compare cause,deadline and state.',
           'Receiver history is reference-only; coupled MATLAB test must not inject it.',
           'MAC integer values are returned inclusive discrete samples, not raw uniforms.',
           'SYNC values are sampled dB thresholds, not standard-normal samples.',
           'MAC slots/holdoff callback internals remain in canonical trace; extra lifecycle captures device timers.',
           'No network parity or MATLAB execution claim is made by this native gate.']}
    sources=list(HERE.glob('*.py'))+list(HERE.glob('*.h'))+list((RUN/'overlay/ns3').glob('*.h'))
    sources += [HERE/'vendor/capture.cc',HERE/'fixture/scenario_s132.csv',
                HERE/'compile-command.json',HERE/'command.json',HERE/'native-build.json']
    summary['source_and_build_sha256']={str(p.relative_to(ROOT)):sha(p) for p in sources}
    (HERE/'receipt.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ['canonical_fields','sha256','event_counts']},indent=2))

if __name__=='__main__': main()
