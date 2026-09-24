"""Initialize local demonstration credentials without printing or overwriting secrets."""
import json
import os
from pathlib import Path
import secrets
import shlex
from sqlalchemy import insert, select
from reflexguard.control_server.config import ControlSettings
from reflexguard.control_server.database import Database, users, password_hash

ROOT=Path(__file__).resolve().parents[1]

def main():
    os.umask(0o077)
    environment=ROOT/".env.control"
    bootstrap=ROOT/".env.admin"
    database=ROOT/"control.db"
    if any(path.exists() for path in (environment,bootstrap,database)):
        raise RuntimeError("Existing control environment is never overwritten")
    device_token=secrets.token_urlsafe(32)
    remote_key=secrets.token_urlsafe(32)
    audit_key=secrets.token_urlsafe(32)
    password=secrets.token_urlsafe(24)
    devices=[{"chair_id":"seat-a","token":device_token,"hmac_key":remote_key}]
    values={"REFLEXGUARD_CONTROL_URL":"https://localhost:8444","REFLEXGUARD_CONTROL_PORT":"8444",
        "REFLEXGUARD_CONTROL_DB":str(database),"REFLEXGUARD_CONTROL_DEVICES":json.dumps(devices),
        "REFLEXGUARD_AUDIT_KEY":audit_key,"REFLEXGUARD_CHAIR_ID":"seat-a",
        "REFLEXGUARD_DEVICE_TOKEN":device_token,"REFLEXGUARD_REMOTE_KEY":remote_key}
    settings=ControlSettings(origin=values["REFLEXGUARD_CONTROL_URL"],database=database,devices=devices,audit_key=audit_key)
    with environment.open("x",encoding="utf-8") as handle:
        for name,value in values.items():handle.write(name+"="+shlex.quote(value)+"\n")
    with bootstrap.open("x",encoding="utf-8") as handle:
        handle.write("REFLEXGUARD_ADMIN_USER=admin\nREFLEXGUARD_ADMIN_PASSWORD="+shlex.quote(password)+"\n")
    db=Database(settings)
    with db.tx() as conn:
        if conn.execute(select(users.c.id)).first() is not None:raise RuntimeError("Database must be empty")
        conn.execute(insert(users).values(username="admin",password_hash=password_hash(password),role="admin"))
    db.engine.dispose()
    print("Local control environment initialized. Administrator credentials: .env.admin (0600, Git-ignored).")

if __name__=="__main__":
    main()
