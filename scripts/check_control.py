"""Real HTTPS dashboard → signed remote stop → Webots motors → authenticated audit.
All credentials and databases are temporary; only loopback sockets are opened.
"""
import json
import os
from pathlib import Path
import secrets
import socket
import ssl
import subprocess  # nosec B404 - fixed local integration commands, no shell or request input
import sys
import tempfile
import time
import httpx
from sqlalchemy import insert, update
from reflexguard.common.config import ClientSettings
from reflexguard.control_server.config import ControlSettings
from reflexguard.control_server.database import Database, users, chairs, password_hash
from reflexguard.simulation.models import Result, Settings

ROOT=Path(__file__).resolve().parents[1]

def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        return sock.getsockname()[1]

def main():
    profile=os.environ.get("REFLEXGUARD_BRAIN_PROFILE","mock")
    if profile not in ("mock","real"): raise ValueError("Unknown brain profile")
    external_brain=ClientSettings.from_env() if profile=="real" else None
    processes=[]
    with tempfile.TemporaryDirectory(prefix="reflexguard-control-") as temporary:
        directory=Path(temporary)
        try:
            certs=directory/"certs"
            subprocess.run(["/bin/bash",str(ROOT/"scripts/gen_certs.sh"),str(certs)],check=True,capture_output=True,timeout=30)  # nosec B603 - fixed certificate script; temporary directory created here
            brain_port,control_port=free_port(),free_port()
            while control_port==brain_port:control_port=free_port()
            token=secrets.token_urlsafe(32)
            device_token=secrets.token_urlsafe(32)
            remote_key=secrets.token_urlsafe(32)
            password=secrets.token_urlsafe(32)
            env=os.environ.copy()
            env.update({"PYTHONPATH":str(ROOT/"src"),"REFLEXGUARD_BRAIN_URL":f"https://localhost:{brain_port}",
                "REFLEXGUARD_BRAIN_TOKEN":token,"REFLEXGUARD_API_TOKENS":json.dumps([{"token":token,"subject":"seat-a","role":"operator"}]),
                "REFLEXGUARD_MOCK_PORT":str(brain_port),"REFLEXGUARD_CONTROL_PORT":str(control_port),
                "REFLEXGUARD_CONTROL_URL":f"https://localhost:{control_port}","REFLEXGUARD_CONTROL_DB":str(directory/"control.db"),
                "REFLEXGUARD_CONTROL_DEVICES":json.dumps([{"chair_id":"seat-a","token":device_token,"hmac_key":remote_key}]),
                "REFLEXGUARD_AUDIT_KEY":secrets.token_urlsafe(32),"REFLEXGUARD_CHAIR_ID":"seat-a",
                "REFLEXGUARD_DEVICE_TOKEN":device_token,"REFLEXGUARD_REMOTE_KEY":remote_key,
                "REFLEXGUARD_SCENARIO":Settings(world="corridor_static",duration_s=6,drive="forward",batch=True).model_dump_json()})
            for var,file in [("CA","ca.crt"),("SERVER_CERT","server.crt"),("SERVER_KEY","server.key"),("CLIENT_CERT","client.crt"),("CLIENT_KEY","client.key")]:
                env["REFLEXGUARD_TLS_"+var]=str(certs/file)
            env["REFLEXGUARD_CONTROL_TLS_CA"]=str(certs/"ca.crt")
            if external_brain is not None:
                token=external_brain.token.get_secret_value()
                env.update({"REFLEXGUARD_BRAIN_URL":str(external_brain.base_url).rstrip("/"),
                    "REFLEXGUARD_BRAIN_TOKEN":token,"REFLEXGUARD_TLS_CA":str(external_brain.ca_cert),
                    "REFLEXGUARD_TLS_CLIENT_CERT":str(external_brain.client_cert),
                    "REFLEXGUARD_TLS_CLIENT_KEY":str(external_brain.client_key)})
            settings=ControlSettings(origin=env["REFLEXGUARD_CONTROL_URL"],database=directory/"control.db",
                devices=json.loads(env["REFLEXGUARD_CONTROL_DEVICES"]),audit_key=env["REFLEXGUARD_AUDIT_KEY"])
            db=Database(settings)
            with db.tx() as conn:
                uid=conn.execute(insert(users).values(username="guardian",password_hash=password_hash(password),role="guardian")).inserted_primary_key[0]
                conn.execute(update(chairs).where(chairs.c.id=="seat-a").values(guardian_id=uid))
            db.engine.dispose()
            handles=[]
            modules=("control_server",) if external_brain is not None else ("mock_brain","control_server")
            for name in modules:
                handle=(directory/(name+".log")).open("w")
                handles.append(handle)
                processes.append(subprocess.Popen([sys.executable,"-m","reflexguard."+name],cwd=ROOT,env=env,stdout=handle,stderr=subprocess.STDOUT))  # nosec B603 - module names from literal tuple; current venv interpreter
            context=ssl.create_default_context(cafile=str(certs/"ca.crt"))
            brain_context=ssl.create_default_context(cafile=env["REFLEXGUARD_TLS_CA"])
            brain_context.load_cert_chain(env["REFLEXGUARD_TLS_CLIENT_CERT"],env["REFLEXGUARD_TLS_CLIENT_KEY"])
            with httpx.Client(base_url=settings.origin,verify=context,trust_env=False,timeout=2) as browser, httpx.Client(verify=brain_context,trust_env=False,timeout=2) as brain:
                deadline=time.monotonic()+20
                ready=False
                while time.monotonic()<deadline:
                    if any(p.poll() is not None for p in processes):raise RuntimeError("Server exited before readiness")
                    try:
                        ready=browser.get("/login").status_code==200 and brain.get(env["REFLEXGUARD_BRAIN_URL"]+"/v1/health",headers={"Authorization":"Bearer "+token}).status_code==200
                        if ready:break
                    except httpx.HTTPError:
                        pass
                    time.sleep(.1)
                if not ready:raise RuntimeError("Server readiness timeout")
                csrf=browser.cookies.get("__Host-rg-login")
                response=browser.post("/login",json={"username":"guardian","password":password},headers={"Origin":settings.origin,"X-CSRF-Token":csrf})
                response.raise_for_status()
                browser.headers.update({"Origin":settings.origin,"X-CSRF-Token":response.json()["csrf"]})
                if 'class="stop"' not in browser.get("/").text:raise RuntimeError("Dashboard stop button missing")
                subprocess.run([sys.executable,str(ROOT/"scripts/configure_webots.py")],check=True,cwd=ROOT,env=env,capture_output=True,timeout=10)  # nosec B603 - fixed repository configuration script
                log=(directory/"webots.log").open("w")
                handles.append(log)
                sim=subprocess.Popen(["/usr/bin/xvfb-run","-a","/usr/local/webots/webots","--batch","--mode=fast","--no-rendering","--minimize","--stdout","--stderr",str(ROOT/"webots/worlds/corridor_static.wbt")],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)  # nosec B603 - fixed Webots executable, flags and world
                processes.append(sim)
                deadline=time.monotonic()+90
                sent=False
                while sim.poll() is None and time.monotonic()<deadline:
                    status=browser.get("/api/chairs").json()[0]["status"]
                    if not sent and status and status["forward"]>0 and status["t_ms"]>=500:
                        browser.post("/remote",json={"chair_id":"seat-a","action":"stop"}).raise_for_status()
                        sent=True
                    time.sleep(.02)
                if sim.poll() is None:raise RuntimeError("Webots timeout")
                if sim.returncode!=0 or not sent:raise RuntimeError("Webots remote stop was not exercised")
                log.flush()
                raw=(directory/"webots.log").read_text()
                result_lines=[line.partition("REFLEXGUARD_RESULT=")[2] for line in raw.splitlines() if line.startswith("REFLEXGUARD_RESULT=")]
                if len(result_lines)!=1:raise RuntimeError("Missing Webots result")
                result=Result.model_validate_json(result_lines[0])
                exported=browser.get("/exports/seat-a")
                exported.raise_for_status()
                records=[json.loads(json.loads(line)["payload"]) for line in exported.text.splitlines()]
                decisions=[row for row in records if row['event']=='decision']
                expected_prefix='malecns-' if profile=='real' else 'mock-'
                if not decisions or any(not row['model_version'].startswith(expected_prefix) for row in decisions):
                    raise RuntimeError('Unexpected model identity in audit records')
                if result.brain_failures or result.control_failures:
                    raise RuntimeError('Communication failed during remote control test')
                stopped=[row for row in records if row["event"]=="decision" and row["reason"]=="remote_stop"]
                applied=[row for row in records if row["event"]=="remote_applied"]
                verification=browser.get("/logs/seat-a/verify").json()
                if not stopped or not applied or not verification["valid"] or result.final_forward!=0 or result.collision or result.displacement_m<0.1:
                    raise RuntimeError("Remote stop or audit verification failed")
                if any(row["forward"]!=0 or row["turn"]!=0 for row in stopped):raise RuntimeError("Nonzero motor command after stop")
                print(json.dumps({"brain_profile":profile,"dashboard_remote_stop":True,"signed_command_acknowledged":True,"audit":verification,
                    "remote_stop_records":len(stopped),"world":result.model_dump()},ensure_ascii=False))
                # Keep evidence free of cookies, tokens, session IDs and private keys.
                print(raw,file=sys.stderr)
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            for handle in locals().get("handles",[]):handle.close()

if __name__=="__main__":
    main()
