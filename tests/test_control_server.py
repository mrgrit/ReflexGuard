"""Authorization, session, cryptographic and persistence boundaries of the dashboard."""
import json
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, update, delete
from reflexguard.control_server.app import create_app, COOKIE, LOGIN_COOKIE
from reflexguard.control_server.config import ControlSettings
from reflexguard.control_server.database import users, chairs, audit, heads, sessions, password_hash
from reflexguard.control_server.schemas import RemoteRequest, DecisionInput
from reflexguard.control_server.signing import RemoteGuard, sign_command
from reflexguard.control.arbiter import Command

ORIGIN="https://localhost:8444"

@pytest.fixture
def control(tmp_path):
    secret=lambda:secrets.token_urlsafe(32)
    settings=ControlSettings(database=tmp_path/"control.db",devices=[
        {"chair_id":"seat-a","token":secret(),"hmac_key":secret()},
        {"chair_id":"seat-b","token":secret(),"hmac_key":secret()}],audit_key=secret())
    from reflexguard.control.settings_store import CalibrationStore
    from pathlib import Path
    (tmp_path/"config").mkdir()
    (tmp_path/"config/control.json").write_bytes((Path(__file__).resolve().parents[1]/"config/control.json").read_bytes())
    app=create_app(settings, calibration_store=CalibrationStore(tmp_path))
    password=secret()
    hashed=password_hash(password)
    with app.state.db.tx() as conn:
        for name,role in [("admin","admin"),("operator","operator"),("guardian","guardian"),("outsider","guardian")]:
            result=conn.execute(insert(users).values(username=name,password_hash=hashed,role=role))
            if name in ("guardian","outsider"):
                conn.execute(update(chairs).where(chairs.c.id==("seat-a" if name=="guardian" else "seat-b")).values(guardian_id=result.inserted_primary_key[0]))
    with TestClient(app,base_url=ORIGIN,raise_server_exceptions=False) as client:
        yield client,app.state.db,settings,password
    app.state.db.engine.dispose()

def login(client,password,name="admin"):
    page=client.get("/login")
    assert page.status_code==200
    csrf=client.cookies.get(LOGIN_COOKIE)
    response=client.post("/login",json={"username":name,"password":password},headers={"Origin":ORIGIN,"X-CSRF-Token":csrf})
    if response.status_code==200:
        client.headers.update({"Origin":ORIGIN,"X-CSRF-Token":response.json()["csrf"]})
    return response

def hello(client,settings,chair="seat-a"):
    device=next(d for d in settings.devices if d.chair_id==chair)
    headers={"Authorization":"Bearer "+device.token.get_secret_value()}
    boot=secrets.token_urlsafe(32)
    assert client.post(f"/device/{chair}/hello",json={"boot_id":boot},headers=headers).status_code==200
    return boot,headers

def decision(boot,sequence=1):
    return DecisionInput(boot_id=boot,sequence=sequence,t_ms=32,left_looming=.5,right_looming=.1,escape=.6,
        top_neurons=[{"id":"mock-left","type":"mock","rate_hz":2.0}],model_version="mock-rules-v1",
        reason="hazard_stop",forward=0.0,turn=0.0,remote_stopped=False).model_dump()

def test_login_cookie_and_csrf(control):
    client,db,settings,password=control
    response=login(client,password)
    cookie=response.headers["set-cookie"]
    assert all(value in cookie for value in ["HttpOnly","Secure","SameSite=strict","Path=/"])
    assert client.get("/").status_code==200
    assert client.post("/logout",json={},headers={"X-CSRF-Token":"bad"}).status_code==403
    assert client.post("/logout",json={},headers={"Origin":"https://evil.invalid"}).status_code==403
    assert client.post("/logout",json={}).status_code==200
    assert client.get("/").status_code==401

def test_login_lock_and_unknown_user(control):
    client,db,settings,password=control
    for _ in range(5):
        assert login(client,secrets.token_urlsafe(32)).status_code==401
    assert login(client,password).status_code==401
    assert login(client,password,"does-not-exist").status_code==401
    with db.tx() as conn:
        conn.execute(update(users).where(users.c.username=="admin").values(locked_until=time.time()-1))
    assert login(client,password).status_code==200

@pytest.mark.parametrize("path",["/","/api/chairs","/exports/seat-a","/logs/seat-a/verify"])
def test_unauthenticated_reads_denied(control,path):
    assert control[0].get(path).status_code==401

def test_guardian_scope_and_remote_roles(control):
    client,db,settings,password=control
    hello(client,settings)
    login(client,password,"guardian")
    assert [row["id"] for row in client.get("/api/chairs").json()]==["seat-a"]
    assert client.get("/exports/seat-b").status_code==404
    assert client.get("/logs/seat-b/verify").status_code==404
    assert client.post("/remote",json={"chair_id":"seat-b","action":"stop"}).status_code==404
    assert client.post("/remote",json={"chair_id":"seat-a","action":"speed_limit","speed_limit":.2}).status_code==403
    assert client.post("/remote",json={"chair_id":"seat-a","action":"stop"}).status_code==200
    assert client.post("/chairs/seat-a/silence",json={"neuron_ids":[]}).status_code==403
    assert client.post("/admin/users",json={"username":"new","password":password,"role":"admin"}).status_code==403

def test_signed_stop_delivery_ack_and_audit(control):
    client,db,settings,password=control
    boot,headers=hello(client,settings)
    login(client,password,"guardian")
    r=client.post("/remote",json={"chair_id":"seat-a","action":"stop"})
    assert r.status_code==200
    result=client.post("/device/seat-a/poll",json={"boot_id":boot},headers=headers).json()
    from reflexguard.control_server.schemas import SignedRemote
    guard=RemoteGuard("seat-a",settings.devices[0].hmac_key.get_secret_value(),boot)
    guard.accept(SignedRemote.model_validate(result["command"]))
    assert guard.apply(Command(forward=.5,turn=.5))==Command(forward=0.0,turn=0.0)
    ack=client.post("/device/seat-a/poll",json={"boot_id":boot,"acknowledged":guard.acknowledged},headers=headers)
    assert ack.json()["command"] is None
    assert client.get("/logs/seat-a/verify").json()=={"valid":True,"records":3}

@pytest.mark.parametrize("change",["signature","timestamp","chair","boot","body","replay","restart"])
def test_remote_forgery_and_replay(change):
    key=secrets.token_urlsafe(32)
    boot=secrets.token_urlsafe(32)
    env=sign_command(RemoteRequest(chair_id="seat-a",action="stop"),boot,key,10000)
    from reflexguard.control_server.schemas import SignedRemote
    guard=RemoteGuard("seat-a",key,boot)
    raw=env.model_dump()
    now=10000
    if change=="signature":raw["signature"]="0"*64
    if change=="timestamp":now=12001
    if change=="chair":guard.chair_id="seat-b"
    if change in ("boot","restart"):guard.boot_id=secrets.token_urlsafe(32)
    if change=="body":raw["body"]["issued_ms"]=10001
    if change=="replay":guard.accept(env,now_ms=now)
    with pytest.raises(ValueError):guard.accept(SignedRemote.model_validate(raw),now_ms=now)

def test_speed_bounds_both_wheels_and_stop_latch():
    key=secrets.token_urlsafe(32);boot=secrets.token_urlsafe(32)
    guard=RemoteGuard("seat-a",key,boot)
    guard.accept(sign_command(RemoteRequest(chair_id="seat-a",action="speed_limit",speed_limit=.1),boot,key,1000),1000)
    command=guard.apply(Command(forward=.6,turn=1.0))
    assert max(abs(command.forward-command.turn*.32),abs(command.forward+command.turn*.32))<=.100001
    guard.accept(sign_command(RemoteRequest(chair_id="seat-a",action="stop"),boot,key,1000),1000)
    guard.accept(sign_command(RemoteRequest(chair_id="seat-a",action="speed_limit",speed_limit=.6),boot,key,1000),1000)
    assert guard.apply(Command(forward=.6,turn=1.0)).forward==0

def test_device_token_binding_and_sequence(control):
    client,db,settings,password=control
    boot,headers=hello(client,settings)
    assert client.post("/device/seat-b/hello",json={"boot_id":boot},headers=headers).status_code==401
    assert client.post("/device/seat-a/decisions",json=decision(boot)).status_code==401
    assert client.post("/device/seat-a/decisions",json=decision(boot),headers=headers).status_code==200
    assert client.post("/device/seat-a/decisions",json=decision(boot),headers=headers).status_code==409
    hello(client,settings)
    assert client.post("/device/seat-a/poll",json={"boot_id":boot},headers=headers).status_code==409

@pytest.mark.parametrize("mutation",["payload","previous","recompute","delete_tail"])
def test_audit_tampering(control,mutation):
    client,db,settings,password=control
    boot,headers=hello(client,settings)
    client.post("/device/seat-a/decisions",json=decision(boot),headers=headers)
    login(client,password)
    assert client.get("/logs/seat-a/verify").json()["valid"]
    with db.tx() as conn:
        row=conn.execute(select(audit).order_by(audit.c.id.desc())).mappings().first()
        if mutation=="delete_tail":conn.execute(delete(audit).where(audit.c.id==row["id"]))
        elif mutation=="previous":conn.execute(update(audit).where(audit.c.id==row["id"]).values(previous="f"*64))
        else:
            from reflexguard.control_server.database import digest
            values={"payload":"{}"}
            if mutation=="recompute":values["digest"]=digest(row["previous"]+"{}")
            conn.execute(update(audit).where(audit.c.id==row["id"]).values(**values))
    assert not client.get("/logs/seat-a/verify").json()["valid"]

def test_sql_special_characters_and_template_escape(control):
    client,db,settings,password=control
    name="<script>alert('x')</script> ' OR 1=1 --"
    login(client,password)
    response=client.post("/admin/users",json={"username":name,"password":password,"role":"operator"})
    assert response.status_code==200
    assert login(client,password,name).status_code==200
    page=client.get("/").text
    assert "<script>alert" not in page and "&lt;script&gt;" in page
    assert login(client,password,"' OR 1=1 --").status_code==401

def test_admin_session_revocation_and_assignment(control):
    client,db,settings,password=control
    login(client,password,"guardian")
    old=client.cookies.get(COOKIE)
    login(client,password)
    with db.tx() as conn:
        guardian=conn.execute(select(users.c.id).where(users.c.username=="guardian")).scalar_one()
    assert client.patch(f"/admin/users/{guardian}",json={"role":"guardian","active":False}).status_code==200
    with db.tx() as conn:
        assert conn.execute(select(sessions).where(sessions.c.user_id==guardian)).first() is None
    assert client.patch("/admin/chairs/seat-b",json={"guardian_id":guardian}).status_code==422

@pytest.mark.parametrize("body",[
    {"chair_id":"seat-a","action":"drive"},
    {"chair_id":"seat-a","action":"stop","speed_limit":.5},
    {"chair_id":"seat-a","action":"speed_limit","speed_limit":.7},
    {"chair_id":"seat-a","action":"speed_limit"}])
def test_remote_invalid_actions(control,body):
    client,db,settings,password=control
    login(client,password)
    assert client.post("/remote",json=body).status_code==422

def test_transport_and_body_boundary(control):
    client=control[0]
    assert client.get("http://localhost:8444/login").status_code==400
    assert client.get("/login",headers={"Host":"evil.invalid"}).status_code==400
    assert client.post("/login",content="x"*32769).status_code==413
    assert client.post("/login",json={"username":"a","password":"short"}).json()=={"detail":"Invalid request"}

def test_lan_origin_login_keeps_host_and_csrf_boundaries(control, tmp_path):
    _, _, settings, password = control
    origin = "https://192.0.2.10:8444"
    settings = ControlSettings.model_validate({**settings.model_dump(), "origin": origin})
    from reflexguard.control.settings_store import CalibrationStore
    app = create_app(settings, calibration_store=CalibrationStore(tmp_path))
    try:
        with TestClient(app, base_url=origin) as client:
            assert client.get("/login").status_code == 200
            csrf = client.cookies.get(LOGIN_COOKIE)
            body = {"username": "admin", "password": password}
            assert client.post("/login", json=body, headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}).status_code == 403
            assert client.get("/login", headers={"Host": "evil.invalid"}).status_code == 400
            response = client.post("/login", json=body, headers={"Origin": origin, "X-CSRF-Token": csrf})
            assert response.status_code == 200
            assert client.get("/").status_code == 200
            assert client.get("/settings/control").status_code == 200
            assert client.get("/activity/seat-a").status_code == 200
            snapshot = client.get("/api/settings/control").json()
            save = {"expected_revision": snapshot["revision"], "calibration": snapshot["calibration"]}
            headers = {"Origin": origin, "X-CSRF-Token": response.json()["csrf"]}
            assert client.post("/api/settings/control", json=save, headers=headers).status_code == 200
            assert client.post("/logout", json={}, headers={"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrf"]}).status_code == 403
            assert client.post("/logout", json={}, headers={"Origin": origin, "X-CSRF-Token": response.json()["csrf"]}).status_code == 200
    finally:
        app.state.db.engine.dispose()

def test_operator_silence_and_pending_stop_priority(control):
    client,db,settings,password=control
    boot,headers=hello(client,settings)
    login(client,password,"operator")
    assert client.post("/chairs/seat-a/silence",json={"neuron_ids":["mock-left"]}).status_code==200
    assert client.post("/device/seat-a/poll",json={"boot_id":boot},headers=headers).json()["silence"]=={"neuron_ids":["mock-left"]}
    assert client.post("/chairs/seat-a/silence",json={"neuron_ids":[str(n) for n in range(11)]}).status_code==422
    client.post("/remote",json={"chair_id":"seat-a","action":"stop"})
    assert client.post("/remote",json={"chair_id":"seat-a","action":"speed_limit","speed_limit":.3}).status_code==409

def test_concurrent_audit_append(control):
    client,db,settings,password=control
    def append(i):
        with db.tx() as conn:db.append(conn,"seat-a",{"event":"test","i":i})
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(append,range(20)))
    with db.tx() as conn:assert db.verify(conn,"seat-a")=={"valid":True,"records":20}


def test_expired_remote_fails_closed(control):
    client,db,settings,password=control
    boot,headers=hello(client,settings)
    login(client,password)
    env=sign_command(RemoteRequest(chair_id="seat-a",action="stop"),boot,settings.devices[0].hmac_key.get_secret_value(),int(time.time()*1000)-3000)
    with db.tx() as conn:
        conn.execute(update(chairs).where(chairs.c.id=="seat-a").values(pending=env.model_dump_json()))
    assert client.post("/device/seat-a/poll",json={"boot_id":boot},headers=headers).status_code==409


def test_login_requires_prelogin_csrf(control):
    client,db,settings,password=control
    assert client.post("/login",json={"username":"admin","password":password},headers={"Origin":ORIGIN,"X-CSRF-Token":"invalid"}).status_code==403


def test_log_neuron_type_is_escaped(control):
    client,db,settings,password=control
    boot,headers=hello(client,settings)
    body=decision(boot)
    body["top_neurons"][0]["type"]="<img src=x onerror=alert(1)>"
    assert client.post("/device/seat-a/decisions",json=body,headers=headers).status_code==200
    login(client,password,"guardian")
    page=client.get("/").text
    assert "<img src=x" not in page and "&lt;img src=x" in page


def test_session_expiry_and_offline_command(control):
    client,db,settings,password=control
    login(client,password)
    assert client.post("/remote",json={"chair_id":"seat-a","action":"stop"}).status_code==409
    with db.tx() as conn:conn.execute(update(sessions).values(expires=time.time()-1))
    assert client.get("/api/chairs").status_code==401


def test_admin_recovery_updates_hash_unlocks_and_revokes(control):
    import bcrypt
    from reflexguard.control_server.reset_admin import reset_account
    from reflexguard.control_server.schemas import Login
    client,db,settings,password=control
    login(client,password)
    with db.tx() as conn:
        conn.execute(update(users).where(users.c.username=="admin").values(failures=5,locked_until=time.time()+900))
    replacement=secrets.token_urlsafe(24)
    reset_account(db,Login(username="admin",password=replacement))
    assert client.get("/").status_code==401
    with db.tx() as conn:
        user=conn.execute(select(users).where(users.c.username=="admin")).mappings().one()
        assert user["failures"]==0 and user["locked_until"]==0
        assert bcrypt.checkpw(replacement.encode(),user["password_hash"].encode())
        assert not bcrypt.checkpw(password.encode(),user["password_hash"].encode())
    assert login(client,replacement).status_code==200


def test_admin_recovery_cannot_promote_guardian(control):
    from reflexguard.control_server.reset_admin import reset_account
    from reflexguard.control_server.schemas import Login
    client,db,settings,password=control
    with pytest.raises(ValueError):reset_account(db,Login(username="guardian",password=password))
    assert login(client,password,"guardian").status_code==200


def test_admin_recovery_rejects_short_password(control):
    from pydantic import ValidationError
    from reflexguard.control_server.schemas import Login
    with pytest.raises(ValidationError):Login(username="admin",password=secrets.token_hex(1))


@pytest.mark.parametrize("role", ["operator", "admin"])
def test_calibration_save_reset_and_stale_edit(control, role):
    client, _, _, password = control
    login(client, password, role)
    page = client.get("/settings/control")
    assert page.status_code == 200 and "다음 시작에 적용" in page.text
    initial = client.get("/api/settings/control").json()
    changed = dict(initial["calibration"], stop_on=0.4)
    body = {"expected_revision": initial["revision"], "calibration": changed}
    result = client.post("/api/settings/control", json=body)
    assert result.status_code == 200 and result.json()["calibration"]["stop_on"] == .4
    assert client.post("/api/settings/control", json=body).status_code == 409
    reset = client.post("/api/settings/control/reset", json={"expected_revision": result.json()["revision"]})
    assert reset.status_code == 200 and reset.json()["calibration"] == initial["calibration"]
    assert reset.json()["actor"] == role


def test_calibration_permissions_and_csrf(control):
    client, _, _, password = control
    assert client.get("/settings/control").status_code == 401
    assert client.get("/api/settings/control").status_code == 401
    login(client, password, "admin")
    snapshot = client.get("/api/settings/control").json()
    body = {"expected_revision": snapshot["revision"], "calibration": snapshot["calibration"]}
    assert client.post("/api/settings/control", json=body, headers={"X-CSRF-Token": "invalid"}).status_code == 403
    assert client.post("/api/settings/control/reset", json={"expected_revision": snapshot["revision"]}, headers={"Origin": "https://evil.invalid"}).status_code == 403
    login(client, password, "guardian")
    assert client.get("/settings/control").status_code == 403
    assert client.get("/api/settings/control").status_code == 403
    assert client.post("/api/settings/control", json=body).status_code == 403
    assert client.post("/api/settings/control/reset", json={"expected_revision": snapshot["revision"]}).status_code == 403
    assert '/settings/control' not in client.get("/").text


@pytest.mark.parametrize("update", [{"stop_on": 1.1}, {"stop_on": .1}, {"turn_off": .9},
    {"stop_on": True}, {"stop_on": "0.4"}, {"unknown": 1}, {"deceleration": 0}, {"release_ms": 1.5}])
def test_calibration_invalid_save_preserves_state(control, update):
    client, _, _, password = control
    login(client, password)
    initial = client.get("/api/settings/control").json()
    body = {"expected_revision": initial["revision"], "calibration": dict(initial["calibration"], **update)}
    assert client.post("/api/settings/control", json=body).status_code == 422
    assert client.get("/api/settings/control").json() == initial


def test_calibration_partial_and_path_inputs_rejected(control):
    client, _, _, password = control
    login(client, password)
    initial = client.get("/api/settings/control").json()
    body = {"expected_revision": initial["revision"], "calibration": {"stop_on": .4}}
    assert client.post("/api/settings/control", json=body).status_code == 422
    body["calibration"] = initial["calibration"]
    body["path"] = "../../etc/passwd"
    assert client.post("/api/settings/control", json=body).status_code == 422
    assert client.get("/assets/calibration.js").status_code == 200


@pytest.mark.parametrize("speed", [6.1, 0, -1, float("nan"), True])
def test_remote_guard_rejects_invalid_local_speed(speed):
    with pytest.raises(ValueError):
        RemoteGuard("seat-a", secrets.token_urlsafe(32), secrets.token_urlsafe(32), max_speed=speed)


def test_demo_speed_still_obeys_signed_limits_and_stop():
    key, boot = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    guard = RemoteGuard("seat-a", key, boot, max_speed=1.0)
    assert guard.apply(Command(forward=1.0, turn=0.0)).forward == 1.0
    assert guard.apply(Command(forward=1.2, turn=0.0)).forward == 1.0
    guard.accept(sign_command(RemoteRequest(chair_id="seat-a", action="speed_limit", speed_limit=.3), boot, key, 1000), 1000)
    assert guard.apply(Command(forward=1.0, turn=0.0)).forward == .3
    guard.accept(sign_command(RemoteRequest(chair_id="seat-a", action="stop"), boot, key, 1000), 1000)
    assert guard.apply(Command(forward=1.0, turn=0.0)).forward == 0


@pytest.mark.parametrize('path',['/activity/seat-a','/api/chairs/seat-a/activity'])
def test_neural_activity_authorization(control,path):
    client,_,settings,password=control
    assert client.get(path).status_code==401
    login(client,password,'outsider')
    assert client.get(path).status_code==404
    login(client,password,'guardian')
    assert client.get(path).status_code==200
    assert client.get('/assets/activity.js').status_code==200


def test_neural_activity_real_identity_stale_boot_and_audit(control):
    from pathlib import Path
    client,db,settings,password=control
    graph=json.loads((Path(__file__).resolve().parents[1]/'src/reflexguard/control_server/static/malecns-circuit.json').read_text())
    boot,headers=hello(client,settings)
    login(client,password,'guardian')
    path='/api/chairs/seat-a/activity'
    assert client.get(path).json()['state']=='waiting'
    body=decision(boot)
    body.update(model_version=graph['model_version'],weights_sha256=graph['weights_sha256'],
        neuron_activity=[{'id':n['id'],'type':n['cell_type'],'rate_hz':float(i)} for i,n in enumerate(graph['nodes'])])
    assert len(json.dumps(body).encode())<32768
    assert client.post('/device/seat-a/decisions',json=body,headers=headers).status_code==200
    result=client.get(path).json()
    assert result['state']=='malecns' and len(result['frame']['neuron_activity'])==187
    assert result['frame']['neuron_activity'][10]['rate_hz']==10
    assert client.post('/device/seat-a/decisions',json=body,headers=headers).status_code==409
    assert len(client.get(path).json()['history'])==1
    with db.tx() as conn:
        latest=conn.execute(select(audit.c.payload).where(audit.c.chair_id=='seat-a').order_by(audit.c.id.desc())).first()[0]
        assert 'neuron_activity' not in json.loads(latest)
    body.update(sequence=2,weights_sha256='0'*64)
    assert client.post('/device/seat-a/decisions',json=body,headers=headers).status_code==200
    assert client.get(path).json()['state']=='unverified'
    assert client.get(path).json()['frame']['neuron_activity']==[]
    hello(client,settings)
    assert client.get(path).json()['state']=='waiting'


def test_activity_cache_bounds_and_mock_never_lights_real_nodes():
    from reflexguard.control_server.activity import ActivityMonitor
    monitor=ActivityMonitor(['seat-a'])
    boot=secrets.token_urlsafe(32)
    for i in range(80): monitor.record('seat-a',DecisionInput.model_validate(decision(boot,i+1)))
    assert len(monitor.snapshot('seat-a')['history'])==60
    assert monitor.snapshot('seat-a')['state']=='mock'
    assert monitor.snapshot('seat-a')['frame']['neuron_activity']==[]
    monitor.frames['seat-a']['received_at']-=3
    assert monitor.snapshot('seat-a')['state']=='stale'
    monitor.clear('seat-a')
    assert monitor.snapshot('seat-a')['history']==[]


def test_visual_graph_matches_committed_model_manifest():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    graph=json.loads((root/'src/reflexguard/control_server/static/malecns-circuit.json').read_text())
    manifest=json.loads((root/'brain_server/assets.lock').read_text())
    assert graph['weights_sha256']==manifest['weights_sha256']
    assert graph['nodes']==manifest['neurons']
    assert len(graph['nodes'])==187 and len(graph['edges'])==185
    assert sum(e['synapses'] for e in graph['edges'])==4862
    ids={n['id'] for n in graph['nodes']}
    assert all(e['source'] in ids and e['target'] in ids for e in graph['edges'])
