"""Regression test for a real bug found in Phase H: killing lara-database and hitting an
authenticated endpoint surfaced a raw 500 with a full stack trace, not the blueprint's
intended 503 (blueprint section 3, Session 3 Failure Modes: "Database unreachable ...
Requests that need identity fail closed"). Two exception types had to be handled, not one -
see gateway/app/main.py's database_unavailable_handler docstring for why a DNS-resolution
failure raises a bare socket.gaierror that SQLAlchemy never wraps in DBAPIError."""

import socket

from sqlalchemy.exc import DBAPIError

from app.main import app


def test_database_unavailable_handler_registered_for_dbapi_error():
    assert DBAPIError in app.exception_handlers


def test_database_unavailable_handler_registered_for_os_error():
    """The actual bug: a connection-establishment DNS failure is a raw OSError, never wrapped
    in DBAPIError - a handler registered only for DBAPIError misses it, which is exactly what
    happened the first time this was tested against a real stopped lara-database container."""
    assert OSError in app.exception_handlers
    assert socket.gaierror in (OSError,) or issubclass(socket.gaierror, OSError)
