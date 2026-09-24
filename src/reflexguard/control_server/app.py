"""HTTPS dashboard: server-side authorization and authenticated device mailboxes."""
import hmac
import json
import logging
import secrets
import time
from pathlib import Path as FilePath
from typing import Annotated
from fastapi import FastAPI, Request, HTTPException, Path
from fastapi.exceptions import RequestValidationError
from pydantic import TypeAdapter
from sqlalchemy import select, insert, update, delete
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse, Response
from starlette.templating import Jinja2Templates
from reflexguard.common.schemas import Identifier, SilenceRequest
from reflexguard.control_server.config import ControlSettings
from reflexguard.control_server.database import Database, users, sessions, chairs, audit, digest, password_hash
from reflexguard.control_server.schemas import (Login, UserCreate, UserUpdate, Assignment, RemoteRequest,
    SignedRemote, Hello, DevicePoll, DecisionInput, Nonce)
from reflexguard.control_server.signing import sign_command

LOGGER=logging.getLogger(__name__)
ChairPath=Annotated[str, Path(min_length=1,max_length=128,pattern=r"^[A-Za-z0-9_-][A-Za-z0-9_.:-]*$")]
UserPath=Annotated[int, Path(gt=0)]
COOKIE="__Host-rg-session"
LOGIN_COOKIE="__Host-rg-login"

class Boundary:
    def __init__(self, app, origin):
        self.app=app
        self.host=origin.split("://",1)[1]

    async def __call__(self, scope, receive, send):
        if scope["type"]!="http":
            return await self.app(scope,receive,send)
        headers={key.lower():value for key,value in scope["headers"]}
        if scope["scheme"]!="https" or headers.get(b"host",b"").decode()!=self.host:
            return await JSONResponse({"detail":"Request rejected"},status_code=400)(scope,receive,send)
        data=bytearray()
        while True:
            message=await receive()
            if message["type"]=="http.disconnect":
                return
            data.extend(message.get("body",b""))
            if len(data)>32768:
                return await JSONResponse({"detail":"Request rejected"},status_code=413)(scope,receive,send)
            if not message.get("more_body",False):
                break
        delivered=False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered=True
                return {"type":"http.request","body":bytes(data),"more_body":False}
            return await receive()
        async def secure_send(message):
            if message["type"]=="http.response.start":
                message["headers"]+= [(b"cache-control",b"no-store"), (b"x-content-type-options",b"nosniff"),
                    (b"referrer-policy",b"no-referrer"), (b"x-frame-options",b"DENY"),
                    (b"strict-transport-security",b"max-age=31536000"),
                    (b"content-security-policy",b"default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")]
            await send(message)
        await self.app(scope,bounded_receive,secure_send)


def create_app(settings=None):
    settings=settings or ControlSettings.from_env()
    app=FastAPI(debug=False,docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(Boundary,origin=settings.origin)
    db=Database(settings)
    app.state.db=db
    templates=Jinja2Templates(directory=str(FilePath(__file__).parent/"templates"))
    devices={device.chair_id:device for device in settings.devices}

    @app.exception_handler(RequestValidationError)
    async def invalid(request,exc):
        LOGGER.warning("Control request validation failed: %d errors",len(exc.errors()))
        return JSONResponse({"detail":"Invalid request"},status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def rejected(request,exc):
        return JSONResponse({"detail":"Request rejected"},status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected(request,exc):
        LOGGER.error("Control service failure (%s)",type(exc).__name__)
        return JSONResponse({"detail":"Service unavailable"},status_code=500)

    def origin(request):
        if request.headers.get("origin")!=settings.origin:
            raise HTTPException(403)

    def principal(request,conn,write=False):
        raw=request.cookies.get(COOKIE,"")
        if len(raw)>128:
            raise HTTPException(401)
        row=conn.execute(select(users,sessions.c.csrf).join(sessions,users.c.id==sessions.c.user_id)
                        .where(sessions.c.digest==digest(raw),sessions.c.expires>time.time(),users.c.active.is_(True))).mappings().first()
        if row is None:
            raise HTTPException(401)
        if write:
            origin(request)
            if not hmac.compare_digest(request.headers.get("x-csrf-token",""),row["csrf"]):
                raise HTTPException(403)
        return row

    def chair_for(conn,user,chair_id):
        chair=conn.execute(select(chairs).where(chairs.c.id==chair_id)).mappings().first()
        if chair is None or (user["role"]=="guardian" and chair["guardian_id"]!=user["id"]):
            raise HTTPException(404)
        return chair

    def device_for(request,chair_id):
        device=devices.get(chair_id)
        if device is None or not hmac.compare_digest(request.headers.get("authorization",""),"Bearer "+device.token.get_secret_value()):
            raise HTTPException(401)
        return device

    def current_boot(conn,chair_id,boot_id):
        chair=conn.execute(select(chairs).where(chairs.c.id==chair_id)).mappings().one()
        if chair["boot_id"]!=boot_id:
            raise HTTPException(409)
        return chair

    @app.get("/login")
    def login_page(request: Request):
        csrf=secrets.token_urlsafe(32)
        response=templates.TemplateResponse(request=request,name="login.html",context={"csrf":csrf})
        response.set_cookie(LOGIN_COOKIE,csrf,secure=True,httponly=True,samesite="strict",max_age=300,path="/")
        return response

    @app.post("/login")
    def login(body: Login,request: Request):
        origin(request)
        cookie=request.cookies.get(LOGIN_COOKIE,"")
        if not cookie or not hmac.compare_digest(cookie,request.headers.get("x-csrf-token","")):
            raise HTTPException(403)
        result=db.login(body,request.client.host if request.client else "unknown")
        if result is None:
            raise HTTPException(401)
        token,csrf=result
        response=JSONResponse({"csrf":csrf})
        response.set_cookie(COOKIE,token,secure=True,httponly=True,samesite="strict",max_age=1800,path="/")
        response.delete_cookie(LOGIN_COOKIE,secure=True,httponly=True,samesite="strict",path="/")
        return response

    @app.post("/logout")
    def logout(request: Request):
        with db.tx() as conn:
            principal(request,conn,True)
            conn.execute(delete(sessions).where(sessions.c.digest==digest(request.cookies[COOKIE])))
        response=JSONResponse({"ok":True})
        response.delete_cookie(COOKIE,secure=True,httponly=True,samesite="strict",path="/")
        return response

    @app.get("/")
    def dashboard(request: Request):
        with db.tx() as conn:
            user=principal(request,conn)
            query=select(chairs)
            if user["role"]=="guardian":
                query=query.where(chairs.c.guardian_id==user["id"])
            rows=[dict(row) for row in conn.execute(query.order_by(chairs.c.id)).mappings()]
            for row in rows:
                row["online"]=time.time()-row["last_seen"]<=2
                row["status"]=json.loads(row["status"]) if row["status"] else None
                logs=conn.execute(select(audit).where(audit.c.chair_id==row["id"]).order_by(audit.c.id.desc()).limit(20)).mappings()
                row["logs"]=[json.loads(log["payload"]) for log in logs]
            return templates.TemplateResponse(request=request,name="dashboard.html",context={"user":user,"chairs":rows,"csrf":user["csrf"]})

    @app.get("/assets/{asset}")
    def asset(asset: LiteralAsset):
        # Closed ID mapping only; request text is never appended to a path.
        mapping={"dashboard.js":("dashboard.js","text/javascript"),"style.css":("style.css","text/css")}
        name,kind=mapping[asset]
        return Response((FilePath(__file__).parent/"static"/name).read_text(),media_type=kind)

    @app.get("/api/chairs")
    def status(request: Request):
        with db.tx() as conn:
            user=principal(request,conn)
            query=select(chairs)
            if user["role"]=="guardian":
                query=query.where(chairs.c.guardian_id==user["id"])
            return [{"id":row["id"],"online":time.time()-row["last_seen"]<=2,
                     "status":json.loads(row["status"]) if row["status"] else None}
                    for row in conn.execute(query).mappings()]

    @app.post("/remote")
    def remote(body: RemoteRequest,request: Request):
        with db.tx() as conn:
            user=principal(request,conn,True)
            chair=chair_for(conn,user,body.chair_id)
            if body.action=="speed_limit" and user["role"] not in ("operator","admin"):
                raise HTTPException(403)
            if not chair["boot_id"] or time.time()-chair["last_seen"]>2:
                raise HTTPException(409)
            # A pending stop cannot be overwritten by a speed command.
            if chair["pending"]:
                pending=SignedRemote.model_validate_json(chair["pending"])
                if pending.body.action=="stop" and body.action!="stop":
                    raise HTTPException(409)
            envelope=sign_command(body,chair["boot_id"],devices[body.chair_id].hmac_key.get_secret_value(),int(time.time()*1000))
            conn.execute(update(chairs).where(chairs.c.id==body.chair_id).values(pending=envelope.model_dump_json()))
            db.append(conn,body.chair_id,{"event":"remote_requested","at_ms":int(time.time()*1000),
                "actor":user["username"],"action":body.action,"speed_limit":body.speed_limit,"nonce":envelope.body.nonce})
            return {"accepted":True,"nonce":envelope.body.nonce}

    @app.post("/chairs/{chair_id}/silence")
    def silence(chair_id: ChairPath,body: SilenceRequest,request: Request):
        with db.tx() as conn:
            user=principal(request,conn,True)
            if user["role"] not in ("operator","admin"):
                raise HTTPException(403)
            chair=chair_for(conn,user,chair_id)
            if time.time()-chair["last_seen"]>2:
                raise HTTPException(409)
            conn.execute(update(chairs).where(chairs.c.id==chair_id).values(silence=body.model_dump_json(),silence_until=time.time()+2))
            db.append(conn,chair_id,{"event":"silence_requested","at_ms":int(time.time()*1000),"actor":user["username"],"neuron_ids":body.neuron_ids})
        return {"queued":True}

    @app.get("/logs/{chair_id}/verify")
    def verify(chair_id: ChairPath,request: Request):
        with db.tx() as conn:
            user=principal(request,conn)
            chair_for(conn,user,chair_id)
            return db.verify(conn,chair_id)

    @app.get("/exports/{chair_id}")
    def export(chair_id: ChairPath,request: Request):
        with db.tx() as conn:
            user=principal(request,conn)
            chair_for(conn,user,chair_id)
            # Export ID maps to authorized database records; no filesystem path is supplied.
            rows=conn.execute(select(audit).where(audit.c.chair_id==chair_id).order_by(audit.c.id)).mappings()
            result="\n".join(json.dumps(dict(row),ensure_ascii=True) for row in rows)
            return Response(result,media_type="application/x-ndjson",headers={"Content-Disposition":'attachment; filename="decisions.ndjson"'})

    @app.post("/admin/users")
    def create_user(body: UserCreate,request: Request):
        with db.tx() as conn:
            user=principal(request,conn,True)
            if user["role"]!="admin":
                raise HTTPException(403)
            try:
                result=conn.execute(insert(users).values(username=body.username,password_hash=password_hash(body.password.get_secret_value()),role=body.role))
            except IntegrityError:
                raise HTTPException(409) from None
            return {"id":result.inserted_primary_key[0]}

    @app.patch("/admin/users/{user_id}")
    def update_user(user_id: UserPath,body: UserUpdate,request: Request):
        with db.tx() as conn:
            user=principal(request,conn,True)
            if user["role"]!="admin" or user["id"]==user_id:
                raise HTTPException(403)
            if conn.execute(update(users).where(users.c.id==user_id).values(role=body.role,active=body.active)).rowcount!=1:
                raise HTTPException(404)
            conn.execute(delete(sessions).where(sessions.c.user_id==user_id))
        return {"ok":True}

    @app.patch("/admin/chairs/{chair_id}")
    def assign(chair_id: ChairPath,body: Assignment,request: Request):
        with db.tx() as conn:
            user=principal(request,conn,True)
            if user["role"]!="admin":
                raise HTTPException(403)
            chair_for(conn,user,chair_id)
            guardian=conn.execute(select(users.c.id).where(users.c.id==body.guardian_id,users.c.role=="guardian",users.c.active.is_(True))).first()
            if guardian is None:
                raise HTTPException(422)
            conn.execute(update(chairs).where(chairs.c.id==chair_id).values(guardian_id=body.guardian_id))
        return {"ok":True}

    @app.post("/device/{chair_id}/hello")
    def hello(chair_id: ChairPath,body: Hello,request: Request):
        device_for(request,chair_id)
        with db.tx() as conn:
            conn.execute(update(chairs).where(chairs.c.id==chair_id).values(boot_id=body.boot_id,sequence=0,status=None,
                         pending=None,silence=None,last_seen=time.time()))
            db.append(conn,chair_id,{"event":"device_started","at_ms":int(time.time()*1000)})
        return {"ok":True}

    @app.post("/device/{chair_id}/poll")
    def poll(chair_id: ChairPath,body: DevicePoll,request: Request):
        device_for(request,chair_id)
        with db.tx() as conn:
            chair=current_boot(conn,chair_id,body.boot_id)
            command=SignedRemote.model_validate_json(chair["pending"]) if chair["pending"] else None
            if command and body.acknowledged==command.body.nonce:
                db.append(conn,chair_id,{"event":"remote_applied","at_ms":int(time.time()*1000),"nonce":body.acknowledged,"action":command.body.action})
                conn.execute(update(chairs).where(chairs.c.id==chair_id).values(pending=None))
                command=None
            if command and abs(int(time.time()*1000)-command.body.issued_ms)>2000:
                # An undelivered command is an error; controller latches a stop.
                raise HTTPException(409)
            sil=SilenceRequest.model_validate_json(chair["silence"]) if chair["silence"] and chair["silence_until"]>=time.time() else None
            conn.execute(update(chairs).where(chairs.c.id==chair_id).values(last_seen=time.time(),silence=None))
            return {"command":command,"silence":sil}

    @app.post("/device/{chair_id}/decisions")
    def decision(chair_id: ChairPath,body: DecisionInput,request: Request):
        device_for(request,chair_id)
        with db.tx() as conn:
            chair=current_boot(conn,chair_id,body.boot_id)
            if body.sequence!=chair["sequence"]+1:
                raise HTTPException(409)
            payload={"event":"decision","at_ms":int(time.time()*1000),**body.model_dump(exclude={"boot_id"})}
            db.append(conn,chair_id,payload)
            conn.execute(update(chairs).where(chairs.c.id==chair_id).values(sequence=body.sequence,status=json.dumps(payload),last_seen=time.time()))
        return {"ok":True}
    return app

from typing import Literal
LiteralAsset=Literal["dashboard.js","style.css"]
