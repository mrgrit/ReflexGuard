"""Local administrator recovery: hash update, unlock and session revocation in one transaction."""
import os
from pathlib import Path
import secrets
import shlex
from sqlalchemy import select, update, delete
from reflexguard.control_server.config import ControlSettings
from reflexguard.control_server.database import Database, users, sessions, budgets, password_hash, digest
from reflexguard.control_server.schemas import Login

ROOT=Path(__file__).resolve().parents[3]

def reset_account(db, body: Login):
    body=Login.model_validate(body)
    hashed=password_hash(body.password.get_secret_value())
    with db.tx() as conn:
        user=conn.execute(select(users).where(users.c.username==body.username,users.c.role=="admin",users.c.active.is_(True))).mappings().first()
        if user is None:
            raise ValueError("Active administrator not found")
        conn.execute(update(users).where(users.c.id==user["id"]).values(password_hash=hashed,failures=0,locked_until=0))
        conn.execute(delete(sessions).where(sessions.c.user_id==user["id"]))
        # Explicit local recovery also releases the local browser's source-address budget.
        conn.execute(delete(budgets).where(budgets.c.key.in_([digest("127.0.0.1"),digest("::1")])))

def main():
    os.umask(0o077)
    # No plaintext password arguments or output. Chosen passwords may be supplied through environment.
    body=Login(username=os.environ.get("REFLEXGUARD_ADMIN_USER","admin"),
               password=os.environ.get("REFLEXGUARD_ADMIN_PASSWORD") or secrets.token_urlsafe(18))
    destination=ROOT/".env.admin"
    if destination.is_symlink():
        raise ValueError("Credential file must not be a symlink")
    db=Database(ControlSettings.from_env())
    try:
        reset_account(db,body)
        # The ignored bootstrap file is a local recovery record, never a live password source.
        descriptor=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,"w",encoding="utf-8") as handle:
            os.fchmod(handle.fileno(),0o600)
            handle.write("REFLEXGUARD_ADMIN_USER="+shlex.quote(body.username)+"\n")
            handle.write("REFLEXGUARD_ADMIN_PASSWORD="+shlex.quote(body.password.get_secret_value())+"\n")
    finally:
        db.engine.dispose()
    print("Administrator password reset; account unlocked and sessions revoked. Read .env.admin locally.")

if __name__=="__main__":
    main()
