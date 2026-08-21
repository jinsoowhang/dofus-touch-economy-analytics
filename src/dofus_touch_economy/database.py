from pathlib import Path
from typing import Any

from sqlalchemy import URL, create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def create_engine_for_url(database_url: str | URL) -> Engine:
    url = make_url(database_url)
    database_path = url.database
    is_file_backed = database_path not in (None, "", ":memory:")
    if is_file_backed:
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    engine_options: dict[str, Any] = {
        "connect_args": {"check_same_thread": False},
    }
    if database_path == ":memory:":
        engine_options["poolclass"] = StaticPool

    engine = create_engine(
        url,
        **engine_options,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            if is_file_backed:
                cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
