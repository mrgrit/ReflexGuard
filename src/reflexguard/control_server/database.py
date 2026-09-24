"""SQLAlchemy-bound persistence; immediate transactions serialize audit append and nonce delivery."""
import hashlib
import secrets
import time
from contextlib import contextmanager
import bcrypt
from sqlalchemy import (MetaData, Table, Column, Integer, String, Boolean, Text, Float,
                        create_engine, event, select, insert, update, delete, URL)
from reflexguard.control_server.signing import canonical, mac

metadata=MetaData()
users=Table("users", metadata,
    Column("id", Integer, primary_key=True), Column("username", String(80), unique=True, nullable=False),
    Column("password_hash", String, nullable=False), Column("role", String, nullable=False),
    Column("active", Boolean, nullable=False, default=True), Column("failures", Integer, default=0, nullable=False),
    Column("locked_until", Float, default=0, nullable=False))
sessions=Table("sessions", metadata,
    Column("digest", String, primary_key=True), Column("user_id", Integer, nullable=False),
    Column("csrf", String, nullable=False), Column("expires", Float, nullable=False))
chairs=Table("chairs", metadata,
    Column("id", String, primary_key=True), Column("guardian_id", Integer), Column("boot_id", String),
    Column("sequence", Integer, default=0, nullable=False), Column("last_seen", Float, default=0, nullable=False),
    Column("status", Text), Column("pending", Text), Column("silence", Text), Column("silence_until", Float))
audit=Table("audit", metadata,
    Column("id", Integer, primary_key=True), Column("chair_id", String, nullable=False),
    Column("payload", Text, nullable=False), Column("previous", String, nullable=False),
    Column("digest", String, nullable=False), Column("auth", String, nullable=False))
heads=Table("audit_heads", metadata, Column("chair_id", String, primary_key=True),
    Column("count", Integer, nullable=False), Column("digest", String, nullable=False), Column("auth", String, nullable=False))
budgets=Table("login_budgets", metadata, Column("key", String, primary_key=True),
    Column("attempts", Integer, nullable=False), Column("until", Float, nullable=False))

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def password_hash(secret):
    return bcrypt.hashpw(secret.encode(), bcrypt.gensalt(rounds=12)).decode()

class Database:
    def __init__(self, settings):
        self.settings=settings
        self.engine=create_engine(URL.create("sqlite", database=str(settings.database)),
                                  connect_args={"check_same_thread":False, "timeout":10})
        @event.listens_for(self.engine, "connect")
        def connect(dbapi, record):
            dbapi.isolation_level=None
        @event.listens_for(self.engine, "begin")
        def begin(connection):
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        metadata.create_all(self.engine)
        with self.tx() as conn:
            for device in settings.devices:
                if conn.execute(select(chairs.c.id).where(chairs.c.id==device.chair_id)).first() is None:
                    conn.execute(insert(chairs).values(id=device.chair_id))
        self.dummy=password_hash(secrets.token_urlsafe(32))

    @contextmanager
    def tx(self):
        with self.engine.begin() as conn:
            yield conn

    def append(self, conn, chair_id, payload):
        previous=conn.execute(select(heads).where(heads.c.chair_id==chair_id)).mappings().first()
        count=previous["count"]+1 if previous else 1
        prev=previous["digest"] if previous else "0"*64
        raw=canonical(payload).decode()
        value=digest(prev+raw)
        key=self.settings.audit_key.get_secret_value()
        conn.execute(insert(audit).values(chair_id=chair_id, payload=raw, previous=prev, digest=value,
                                         auth=mac(key, {"chair_id":chair_id,"count":count,"digest":value})))
        head={"count":count,"digest":value,"auth":mac(key,{"chair_id":chair_id,"count":count,"digest":value})}
        if previous:
            conn.execute(update(heads).where(heads.c.chair_id==chair_id).values(**head))
        else:
            conn.execute(insert(heads).values(chair_id=chair_id,**head))

    def verify(self, conn, chair_id):
        import hmac
        rows=conn.execute(select(audit).where(audit.c.chair_id==chair_id).order_by(audit.c.id)).mappings().all()
        prev="0"*64
        key=self.settings.audit_key.get_secret_value()
        for count,row in enumerate(rows,1):
            value=digest(prev+row["payload"])
            auth=mac(key,{"chair_id":chair_id,"count":count,"digest":value})
            if row["previous"]!=prev or row["digest"]!=value or not hmac.compare_digest(row["auth"],auth):
                return {"valid":False,"records":len(rows)}
            prev=value
        head=conn.execute(select(heads).where(heads.c.chair_id==chair_id)).mappings().first()
        valid=(not rows and head is None) or (head is not None and head["count"]==len(rows) and head["digest"]==prev
            and hmac.compare_digest(head["auth"],mac(key,{"chair_id":chair_id,"count":len(rows),"digest":prev})))
        return {"valid":bool(valid),"records":len(rows)}

    def login(self, body, address):
        now=time.time()
        with self.tx() as conn:
            conn.execute(delete(budgets).where(budgets.c.until<now))
            budget_key=digest(address)
            budget=conn.execute(select(budgets).where(budgets.c.key==budget_key)).mappings().first()
            if budget and budget["attempts"]>=30:
                return None
            if budget:
                conn.execute(update(budgets).where(budgets.c.key==budget_key).values(attempts=budget["attempts"]+1))
            else:
                conn.execute(insert(budgets).values(key=budget_key,attempts=1,until=now+900))
            user=conn.execute(select(users).where(users.c.username==body.username)).mappings().first()
            valid=bcrypt.checkpw(body.password.get_secret_value().encode(), (user["password_hash"] if user else self.dummy).encode())
            if not user or not user["active"] or user["locked_until"]>now:
                return None
            if not valid:
                failures=user["failures"]+1 if user["locked_until"]==0 else 1
                conn.execute(update(users).where(users.c.id==user["id"]).values(
                    failures=failures, locked_until=now+900 if failures>=5 else 0))
                return None
            conn.execute(update(users).where(users.c.id==user["id"]).values(failures=0,locked_until=0))
            conn.execute(delete(sessions).where((sessions.c.user_id==user["id"]) | (sessions.c.expires<now)))
            token=secrets.token_urlsafe(32)
            csrf=secrets.token_urlsafe(32)
            conn.execute(insert(sessions).values(digest=digest(token),user_id=user["id"],csrf=csrf,expires=now+1800))
            return token,csrf
