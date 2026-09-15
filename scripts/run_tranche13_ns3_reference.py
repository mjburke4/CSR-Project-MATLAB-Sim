#!/usr/bin/env python3
"""Execute the bounded T13 continued-demand loss fixture on verified ns-3.

No source model or clean shared library is changed. A copied T12 test overlay
provides the existing raw-draw, controlled-transport and read-only DACK seams.
"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from build_tranche12_overlay import build as build_overlay
from run_tranche4_ns3_reference import MODULES, compile_runner, check_source

PIN = "486d9e01f010fdfd4c6aebb87c6d7e51fc674a5b"
ENGINE = "6b5cd24ea80713ce16d88575869aedd6f432bdae"
PLAN_SHA256 = "06ede1b0b67d28b5690e6912284b3a57518ed1c884b725475ba14a881ea5a142"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def write(path, fields, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader(); writer.writerows(rows)


def execute(command, log, timeout=180):
    start = time.monotonic()
    run = subprocess.run([str(x) for x in command], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, timeout=timeout)
    log.write_bytes(run.stdout)
    if run.returncode:
        raise RuntimeError(f"Command failed ({run.returncode}): see {log}")
    return {"argv": [str(x) for x in command], "exit_code": run.returncode,
            "wall_seconds": time.monotonic()-start, "log_sha256": sha(log)}


def validate_inputs(inputs):
    if sha(inputs / "plan.json") != PLAN_SHA256:
        raise ValueError("Unsupported loss plan identity; review fixture when changing plan")
    plan = json.loads((inputs / "plan.json").read_text())
    cases = read(inputs / "cases.csv")
    expected = [{"case": c,"apps4":"48","apps5":"48","duration_seconds":"64",
                 "loss_policy":c,"loss_start_ns":"8000000000" if c=="out" else "0",
                 "loss_stop_ns":"9500000000" if c=="out" else "0"} for c in plan["cases"]]
    if cases != expected: raise ValueError("Changed case order/horizon/workload/loss policy")
    offers = [{"case": c,"source":str(s),"app_id":str(i),"due_ns":str(max(0,i-20)*1000000000)}
              for c in plan["cases"] for i in range(1,49) for s in (4,5)]
    if read(inputs / "offers.csv") != offers: raise ValueError("Changed continued demand identities/order")
    draws = [{"case":c,"node":str(n),"ordinal":str(i),"min":"0","max":"31",
              "draw":str(1 if n==1 else ((3,7) if n==4 else (9,1))[(i-1)%2])}
             for c in plan["cases"] for n in (1,4,5) for i in range(1,1025)]
    if read(inputs / "draws.csv") != draws: raise ValueError("Changed full raw contention tape")
    return plan


def summarize_case(case, folder, plan):
    events, native = read(folder / "events.csv"), read(folder / "native.csv")
    raw, nodes, transport = read(folder / "raw.csv"), read(folder / "summary.csv"), read(folder / "transport.csv")
    if events and list(events[0]) != plan["events_schema"]: raise ValueError("Event schema drift")
    if transport and list(transport[0]) != plan["transport_schema"]: raise ValueError("Transport schema drift")
    if any(r["event"] not in plan["event_names"] for r in events): raise ValueError("Unknown observed event")
    purposes = {}
    for row in native:
        if row["event"] == "reservation_advertise": purpose = "advertise"
        elif row["event"] == "reservation_prepare" and row["reason"] == "new": purpose = "prepare"
        else: continue
        ns = str(int((Decimal(row["time_s"])*1000000000).to_integral_value()))
        purposes.setdefault((row["node"],ns),[]).append((purpose,row["reservation_slot"]))
    draws=[]
    for row in raw:
        key=(row["node"],row["time_ns"])
        if not purposes.get(key): raise ValueError("Raw reservation request lacks native semantic purpose")
        purpose,resolved=purposes[key].pop(0)
        if resolved != row["resolved"]: raise ValueError("Raw reservation resolution mismatch")
        draws.append({k:row[k] for k in plan["draws_output_schema"] if k!="purpose"}|{"purpose":purpose})
    if any(purposes.values()): raise ValueError("Native reservation trace without raw request")
    terminals,failures=[] , []
    reasons={"ack":("1","ack"),"dack":("1","dack_custody"),"no_ack":("0","retry_exhausted")}
    for row in native:
        if row["event"] != "hop_completion": continue
        if row["reason"] not in reasons: raise ValueError("Unknown native completion reason")
        raw_success="1" if row["reason"]=="ack" else "0"
        if row["success"] != raw_success: raise ValueError("Native completion raw success changed")
        success,reason=reasons[row["reason"]]
        ns=str(int((Decimal(row["time_s"])*1000000000).to_integral_value()))
        terminals.append({"case":case,"order":str(len(terminals)+1),"time_ns":ns,"node":row["node"],
                          "app_source":row["src"],"app_id":row["sequence"],"success":success,"reason":reason})
        if reason=="retry_exhausted":
            detail=dict(part.split("=",1) for part in row["detail"].split(";") if "=" in part)
            failures.append({"case":case,"time_ns":ns,"node":row["node"],"peer":row["peer"],
                             "app_source":row["src"],"app_id":row["sequence"],"hop_seq":detail["hop_sequence"],
                             "resend_count":detail["resend_count"],"reason":reason})
    identity=lambda r:(int(r["app_source"]),int(r["app_id"]))
    select=lambda kind:[r for r in events if r["event"]==kind]
    generated,admitted,delivered=select("generate"),select("admit"),select("deliver")
    wanted={(source,app) for source in (4,5) for app in range(1,49)}
    if len(generated)!=96 or {identity(r) for r in generated}!=wanted: raise ValueError("Generated identity coverage")
    if len(admitted)!=96 or {identity(r) for r in admitted}!=wanted: raise ValueError("Unadmitted demand at fixed stop")
    if len(delivered)!=len({identity(r) for r in delivered}): raise ValueError("Duplicate delivery")
    if not {identity(r) for r in delivered}.issubset(wanted): raise ValueError("Unadmitted delivery")
    failed={identity(r) for r in failures}
    if wanted-{identity(r) for r in delivered}-failed: raise ValueError("Unexplained undelivered identities")
    if case=="ok" and len(delivered)!=96: raise ValueError("Loss-free control incomplete")
    if any(sum(1 for r in admitted if r["node"]==str(n) and int(r["time_ns"])>20000000000)==0 for n in (4,5)):
        raise ValueError("Continued admission after20s not exercised")
    stable=select("checkpoint")+select("final")
    if len(stable)!=18: raise ValueError("Missing fixed stable checkpoint/final rows")
    for r in stable:
        if int(r["hop_pending"])!=int(r["resend_queue"])+int(r["dack_holds"]): raise ValueError("Stable HOP capacity accounting")
        if int(r["nwk_custody"])!=int(r["nsdp4"])+int(r["nsdp5"]): raise ValueError("Stable NWK custody accounting")
    for r in select("final"):
        if any(int(r[k]) for k in ("nwk_custody","nwk_waiting","hop_pending","dack_holds","resend_queue","ack_queue","data_queue")):
            raise ValueError("DATA/custody/capacity residue at64s")
    if len(select("release"))!=len(terminals): raise ValueError("Terminal/release accounting mismatch")
    usage=[{"case":case,"node":r["node"],"supplied":"1024","consumed":r["draws_consumed"],"unused":r["draws_unused"]} for r in nodes]
    for u in usage:
        if int(u["consumed"])+int(u["unused"])!=1024: raise ValueError("Incomplete raw tape accounting")
    drops=[r for r in transport if r["decision"]=="drop"]
    if len(drops)!=len(select("loss")): raise ValueError("Drop-to-loss event coverage")
    groups={(r["group_id"],r["sender"],r["receiver"]) for r in drops}
    if case in ("data","ack") and len(groups)!=2: raise ValueError("Both prescribed first-drop edges not exercised")
    if case=="out" and not drops: raise ValueError("Blackout did not drop any actual transmission")
    if case=="ok" and drops: raise ValueError("Control unexpectedly dropped frames")
    flows=[]
    generation={identity(r):int(r["time_ns"]) for r in generated}
    admission={identity(r):int(r["time_ns"]) for r in admitted}
    for source in (4,5):
        got=[r for r in delivered if int(r["app_source"])==source]
        delays=[int(r["time_ns"])-generation[identity(r)] for r in got]
        service=[int(r["time_ns"])-admission[identity(r)] for r in got]
        flows.append({"source":source,"generated":48,"admitted":48,"delivered":len(got),
                      "mean_generation_to_delivery_ns":sum(delays)/len(delays) if delays else 0,
                      "max_generation_to_delivery_ns":max(delays,default=0),
                      "mean_admission_to_delivery_ns":sum(service)/len(service) if service else 0,
                      "last_delivery_ns":max((int(r["time_ns"]) for r in got),default=0)})
    case_summary={"case":case,"nodes":[{k:(v if k=="case" else int(v)) for k,v in r.items()} for r in nodes],
                  "flows":flows,"generated":96,"admitted":96,"delivered":len(delivered),
                  "terminal_reasons":dict(Counter(r["reason"] for r in terminals)),"retry_exhausted":len(failures),
                  "delivered_and_retry_exhausted_overlap":len(failed&{identity(r) for r in delivered}),
                  "loss_groups":len(groups),"lost_segments":len(drops),
                  "lost_directions":sorted({r["sender"]+"->"+r["receiver"] for r in drops}),
                  "loss_kind_counts":dict(Counter(r["kind"] for r in drops)),
                  "max_dack_holds":max(int(r["dack_holds"]) for r in events),"final_dack_holds":0,
                  "routing_controls_excluded_from_transport":True,"structural_checks_passed":True}
    return events,draws,usage,transport,terminals,failures,case_summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("source","build","work","output"): parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--compiler",default="/usr/bin/g++")
    args=parser.parse_args()
    source,build,work,output=[getattr(args,n).resolve() for n in ("source","build","work","output")]
    root=Path(__file__).resolve().parent.parent; inputs=root/"scenarios"/"loss"
    plan=validate_inputs(inputs); check_source(source,build)
    build_path=root/"evidence"/"tranche-11-native-build.json"; baseline=json.loads(build_path.read_text())
    if (baseline["status"],baseline["source_commit"],baseline["engine_commit"])!=("passed",PIN,ENGINE):
        raise ValueError("Unverified native clean build")
    for record in baseline["libraries"]:
        if sha(build/"lib"/Path(record["path"]).name)!=record["sha256"]: raise ValueError("Clean library changed")
    for path in (work,output):
        if path.exists() and any(path.iterdir()): raise ValueError(f"Use empty destination: {path}")
        path.mkdir(parents=True,exist_ok=True)
    libraries={n:sha(build/"lib"/f"libns3-dev-{n}-debug.so") for n in MODULES}
    models={p.name:sha(p) for p in sorted((source/"model").glob("csr-*")) if p.is_file()}
    overlay=work/"overlay"; overlay_manifest=build_overlay(source,overlay)
    controls=output/"controls"; controls.mkdir(); records=[]
    def compile_one(task):
        label,filename,use_overlay=task; target=work/label
        command=compile_runner(source,build,target,args.compiler)
        command[command.index(str(source/"csr-opnet-scenario-runner.cc"))]=str(root/"scripts"/"ns3"/filename)
        if use_overlay: command.insert(1,"-I"+str(overlay))
        record=execute(command,controls/(label+"-build.log"),timeout=300)
        record["binary_sha256"]=sha(target)
        return record
    tasks=[("ack-clean","tranche9_ack_contract.cc",False),("ack-off","tranche9_ack_contract.cc",True),
           ("receiver-clean","tranche10_receiver_contract.cc",False),("receiver-off","tranche10_receiver_contract.cc",True),
           ("loss","tranche13_loss.cc",True)]
    with ThreadPoolExecutor(max_workers=2) as pool: records.extend(pool.map(compile_one,tasks))
    control_results={}
    for label,count in (("ack",101),("receiver",154)):
        for mode in ("clean","off"):
            records.append(execute([work/(label+"-"+mode),controls/(label+"-"+mode+".csv")],controls/(label+"-"+mode+".log")))
        clean=controls/(label+"-clean.csv"); off=controls/(label+"-off.csv")
        rows=read(clean)
        if len(rows)!=count or any(r["pass"]!="1" for r in rows) or clean.read_bytes()!=off.read_bytes():
            raise ValueError("Disabled test seams changed clean "+label+" contract")
        control_results[label]={"checkpoints":count,"passed":True,"clean_and_disabled_byte_equal":True,"sha256":sha(clean)}
    records.append(execute([work/"loss","--self-test"],controls/"self-test.log"))
    if (controls/"self-test.log").read_text().strip()!="LOSS_SELF_TEST checks=25 failed=0": raise ValueError("Missing negative/self tests")
    execution=execute([work/"loss",inputs/"cases.csv",inputs/"draws.csv",inputs/"offers.csv",output/"raw"],output/"run.log")
    records.append(execution)
    results=[summarize_case(c,output/"raw"/c,plan) for c in plan["cases"]]
    for i,(name,schema) in enumerate((("events.csv",plan["events_schema"]),("draws.csv",plan["draws_output_schema"]),
                                      ("usage.csv",["case","node","supplied","consumed","unused"]),
                                      ("transport.csv",plan["transport_schema"]),("terminal.csv",plan["terminal_schema"]))):
        write(output/name,schema,[r for result in results for r in result[i]])
    shutil.copy2(overlay/"seams.patch",output/"seams.patch"); shutil.copy2(overlay/"overlay.json",output/"overlay.json")
    if models!={p.name:sha(p) for p in sorted((source/"model").glob("csr-*")) if p.is_file()}: raise ValueError("Pinned native model changed")
    if libraries!={n:sha(build/"lib"/f"libns3-dev-{n}-debug.so") for n in MODULES}: raise ValueError("Native libraries changed")
    fixtures=[Path(__file__),root/"scripts"/"run_tranche4_ns3_reference.py",root/"scripts"/"build_tranche12_overlay.py",
              *[root/"scripts"/"ns3"/n for n in ("tranche13_loss.cc","tranche12-relay-hooks.h","tranche9_ack_contract.cc","tranche10_receiver_contract.cc")]]
    summary={"schema":"csr-tranche13-native-reference-v1","status":"completed","source_pin":PIN,"engine_pin":ENGINE,
             "scope":plan["scope"],"cases":[r[6] for r in results],"matlab_execution":False,
             "cross_simulator_parity_established":False,"event_count":sum(len(r[0]) for r in results),
             "draw_count":sum(len(r[1]) for r in results),"terminal_count":sum(len(r[4]) for r in results),
             "wall_seconds":execution["wall_seconds"],"self_tests":25,"disabled_seam_controls":control_results,
             "native_source_unchanged":True,"native_libraries_unchanged":True,"instrumented_native_fixture":True,
             "real_nwk_application_and_relay_path":True,"clean_build_record":"evidence/tranche-11-native-build.json",
             "clean_build_record_sha256":sha(build_path),"engine_build_reused_after_hash_verification":True,
             "terminal_normalization":"Native hop_completion ack success1 -> ack true; dack success0 -> dack_custody true because common success describes NWK custody handoff, not HOP pending-capacity release; no_ack success0 -> retry_exhausted false. Preserve original raw native.csv success/reason/detail. Delivered and retry-exhausted identity sets may overlap after lost feedback.",
             "observed_outage_scope":"Policy covers both directions of both chain links; actual lost directions and kinds are reported per case, not assumed.",
             "input_hashes":{p.name:sha(p) for p in sorted(inputs.iterdir()) if p.is_file()},
             "fixture_hashes":{p.name:sha(p) for p in fixtures},"shared_libraries":libraries,
             "native_source_hashes":models,"commands":records}
    (output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    files={p.relative_to(output).as_posix():sha(p) for p in sorted(output.rglob("*")) if p.is_file()}
    (output/"manifest.json").write_text(json.dumps({"schema":"csr-tranche13-reference-files-v1","files":files},indent=2)+"\n")
    print(f"Native T13 completed:4 cases; {sum(r[6]['delivered'] for r in results)}/384 delivered; 255/255 disabled controls;25/25 self-tests")


if __name__=="__main__": main()
