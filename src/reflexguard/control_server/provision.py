"""One-time local administrator creation; password is supplied only through environment."""
import os
from sqlalchemy import select, insert
from reflexguard.control_server.config import ControlSettings
from reflexguard.control_server.database import Database, users, password_hash
from reflexguard.control_server.schemas import UserCreate

def main():
    os.umask(0o077)
    body=UserCreate(username=os.environ["REFLEXGUARD_ADMIN_USER"],
                    password=os.environ["REFLEXGUARD_ADMIN_PASSWORD"],role="admin")
    db=Database(ControlSettings.from_env())
    with db.tx() as conn:
        if conn.execute(select(users.c.id)).first() is not None:
            raise RuntimeError("Provisioning requires an empty user table")
        conn.execute(insert(users).values(username=body.username,password_hash=password_hash(body.password.get_secret_value()),role="admin"))
    db.engine.dispose()
    print("Administrator created. Remove bootstrap password from the service environment.")

if __name__=="__main__":
    main()
