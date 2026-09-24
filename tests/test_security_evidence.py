"""Behavioral evidence for the documented security controls."""
import hashlib
import secrets
import bcrypt
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from reflexguard.control_server.database import password_hash, sessions
from reflexguard.control_server.schemas import Login
from test_control_server import control, login  # reuse the same isolated database fixture


def test_password_hashes_use_independent_salts():
    secret=secrets.token_urlsafe(24)
    first=password_hash(secret)
    second=password_hash(secret)
    assert first!=second
    assert bcrypt.checkpw(secret.encode(),first.encode())
    assert bcrypt.checkpw(secret.encode(),second.encode())
    assert int(first.split("$")[2])>=12


@pytest.mark.parametrize("password,valid",[("a"*11,False),("a"*12,True),("a"*72,True),("a"*73,False),("가"*4,True),("가"*3,False)])
def test_password_byte_boundaries(password,valid):
    if valid:
        assert Login(username="test",password=password).password.get_secret_value()==password
    else:
        with pytest.raises(ValidationError):Login(username="test",password=password)


def test_session_cookie_is_opaque_and_database_contains_only_digest(control):
    client,db,settings,password=control
    assert login(client,password).status_code==200
    token=client.cookies.get("__Host-rg-session")
    with db.tx() as conn:
        row=conn.execute(select(sessions)).mappings().one()
    assert len(token)>=32
    assert row["digest"]!=token
    assert row["digest"]==hashlib.sha256(token.encode()).hexdigest()
    assert token not in row.values()


def test_service_debug_and_api_documentation_are_disabled(control,api):
    client,db,settings,password=control
    for service in (client,api):
        assert service.app.debug is False
        for path in ("/docs","/redoc","/openapi.json"):
            assert service.get(path).status_code==404
