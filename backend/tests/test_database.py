import sqlite3
import sys
from types import ModuleType, SimpleNamespace
from pathlib import Path

import pytest

from app.database import (
    DatabaseConfig,
    DatabaseConfigurationError,
    DatabaseConnection,
    adapt_qmark_placeholders,
    connect_database,
)
from app.mysql_schema import MYSQL_SCHEMA


def test_database_configuration_defaults_to_sqlite(tmp_path):
    config = DatabaseConfig.from_env({}, default_sqlite_path=tmp_path / "app.sqlite")

    assert config.engine == "sqlite"
    assert config.sqlite_path == tmp_path / "app.sqlite"


def test_database_configuration_accepts_explicit_sqlite_path(tmp_path):
    config = DatabaseConfig.from_env(
        {"ASSETAI_DB_ENGINE": "sqlite", "ASSETAI_DB_PATH": str(tmp_path / "custom.sqlite")},
        default_sqlite_path=tmp_path / "default.sqlite",
    )

    assert config.engine == "sqlite"
    assert config.sqlite_path == tmp_path / "custom.sqlite"


def test_database_configuration_requires_explicit_and_complete_mysql_settings():
    with pytest.raises(DatabaseConfigurationError, match="not set"):
        DatabaseConfig.from_env(
            {"ASSETAI_MYSQL_HOST": "localhost"},
            default_sqlite_path=Path("app.sqlite"),
        )

    with pytest.raises(DatabaseConfigurationError, match="required configuration"):
        DatabaseConfig.from_env(
            {"ASSETAI_DB_ENGINE": "mysql", "ASSETAI_MYSQL_HOST": "localhost"},
            default_sqlite_path=Path("app.sqlite"),
        )


def test_database_configuration_selects_mysql_only_when_explicit():
    config = DatabaseConfig.from_env(
        {
            "ASSETAI_DB_ENGINE": "mysql",
            "ASSETAI_MYSQL_HOST": "127.0.0.1",
            "ASSETAI_MYSQL_PORT": "3307",
            "ASSETAI_MYSQL_USER": "assetai",
            "ASSETAI_MYSQL_PASSWORD": "test-password",
            "ASSETAI_MYSQL_DATABASE": "assetai_test",
        },
        default_sqlite_path=Path("app.sqlite"),
    )

    assert config.engine == "mysql"
    assert config.mysql_host == "127.0.0.1"
    assert config.mysql_port == 3307
    assert config.mysql_user == "assetai"
    assert config.mysql_database == "assetai_test"
    assert "test-password" not in repr(config)


def test_database_configuration_rejects_unknown_engine():
    with pytest.raises(DatabaseConfigurationError, match="must be either"):
        DatabaseConfig.from_env(
            {"ASSETAI_DB_ENGINE": "postgres"},
            default_sqlite_path=Path("app.sqlite"),
        )


def test_qmark_adaptation_preserves_quoted_text_and_comments():
    sql = "SELECT '?' AS literal, value FROM records WHERE id = ? -- ? ignored\nAND note = '??'"

    assert adapt_qmark_placeholders(sql, 1) == (
        "SELECT '?' AS literal, value FROM records WHERE id = %s -- ? ignored\nAND note = '??'"
    )
    with pytest.raises(ValueError, match="received 2 parameters"):
        adapt_qmark_placeholders("SELECT * FROM records WHERE id = ?", 2)


def test_sqlite_connection_commits_and_rolls_back_and_closes(tmp_path):
    database_path = tmp_path / "transaction.sqlite"
    config = DatabaseConfig(engine="sqlite", sqlite_path=database_path)

    with connect_database(config) as connection:
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample (value) VALUES (?)", ("committed",))

    with pytest.raises(RuntimeError, match="force rollback"):
        with connect_database(config) as connection:
            connection.execute("INSERT INTO sample (value) VALUES (?)", ("rolled back",))
            raise RuntimeError("force rollback")

    check = sqlite3.connect(database_path)
    try:
        assert check.execute("SELECT value FROM sample").fetchall() == [("committed",)]
    finally:
        check.close()


def test_connection_context_closes_sqlite_connection_after_commit(tmp_path):
    raw_connection = sqlite3.connect(tmp_path / "closed.sqlite")
    connection = DatabaseConnection(raw_connection, "sqlite")

    with connection:
        connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")

    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        raw_connection.execute("SELECT 1")


def test_mysql_connection_factory_uses_dict_cursors_and_utc_session(monkeypatch):
    class FakeCursor:
        def __init__(self):
            self.sql = None
            self.parameters = None

        def execute(self, sql, parameters):
            self.sql = sql
            self.parameters = parameters

        def fetchone(self):
            return {"id": 9}

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()
            self.commits = 0
            self.rollbacks = 0
            self.closed = False

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            self.commits += 1

        def rollback(self):
            self.rollbacks += 1

        def close(self):
            self.closed = True

    fake_connection = FakeConnection()
    connect_options = {}
    fake_pymysql = ModuleType("pymysql")
    fake_pymysql.MySQLError = type("MySQLError", (Exception,), {})
    fake_pymysql.err = SimpleNamespace(
        IntegrityError=type("IntegrityError", (fake_pymysql.MySQLError,), {})
    )
    fake_pymysql.cursors = SimpleNamespace(DictCursor=object())

    def fake_connect(**kwargs):
        connect_options.update(kwargs)
        return fake_connection

    fake_pymysql.connect = fake_connect
    monkeypatch.setitem(sys.modules, "pymysql", fake_pymysql)
    config = DatabaseConfig(
        engine="mysql",
        sqlite_path=Path("unused.sqlite"),
        mysql_host="127.0.0.1",
        mysql_port=3307,
        mysql_user="assetai",
        mysql_password="test-password",
        mysql_database="assetai",
    )

    with connect_database(config) as connection:
        row = connection.execute(
            "SELECT id FROM users WHERE email = ?", ("person@example.com",)
        ).fetchone()

    assert row == {"id": 9}
    assert fake_connection.cursor_instance.sql == (
        "SELECT id FROM users WHERE email = %s"
    )
    assert fake_connection.cursor_instance.parameters == ("person@example.com",)
    assert connect_options["host"] == "127.0.0.1"
    assert connect_options["port"] == 3307
    assert connect_options["database"] == "assetai"
    assert connect_options["autocommit"] is False
    assert connect_options["init_command"] == "SET time_zone = '+00:00'"
    assert fake_connection.commits == 1
    assert fake_connection.rollbacks == 0
    assert fake_connection.closed


def test_mysql_connection_context_rolls_back_and_closes_on_failure(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.rollbacks = 0
            self.closed = False

        def cursor(self):
            return SimpleNamespace(execute=lambda *_args: None)

        def commit(self):
            raise AssertionError("failed transactions must not commit")

        def rollback(self):
            self.rollbacks += 1

        def close(self):
            self.closed = True

    fake_connection = FakeConnection()
    fake_pymysql = ModuleType("pymysql")
    fake_pymysql.MySQLError = type("MySQLError", (Exception,), {})
    fake_pymysql.err = SimpleNamespace(
        IntegrityError=type("IntegrityError", (fake_pymysql.MySQLError,), {})
    )
    fake_pymysql.cursors = SimpleNamespace(DictCursor=object())
    fake_pymysql.connect = lambda **_kwargs: fake_connection
    monkeypatch.setitem(sys.modules, "pymysql", fake_pymysql)
    config = DatabaseConfig(
        engine="mysql",
        sqlite_path=Path("unused.sqlite"),
        mysql_host="127.0.0.1",
        mysql_user="assetai",
        mysql_password="test-password",
        mysql_database="assetai",
    )

    with pytest.raises(RuntimeError, match="rollback test"):
        with connect_database(config) as connection:
            connection.execute("DELETE FROM auth_sessions WHERE token = ?", ("token",))
            raise RuntimeError("rollback test")

    assert fake_connection.rollbacks == 1
    assert fake_connection.closed


def test_mysql_schema_defines_all_owned_tables_and_constraints():
    schema = "\n".join(MYSQL_SCHEMA).lower()

    for table in ("users", "auth_sessions", "generation_records", "user_assets"):
        assert f"create table if not exists {table}" in schema
    assert schema.count("engine=innodb") == 4
    assert "auto_increment" in schema
    assert "unique (email)" in schema
    assert "unique (token)" in schema
    assert "foreign key (user_id) references users (id)" in schema
    assert "ix_generation_records_user_created" in schema
    assert "ix_user_assets_user_created" in schema
    assert "ix_user_assets_type_name_user" in schema
    assert "password_hash" in schema
    assert "password_salt" in schema
    assert "sprite_sheet_path" in schema
    assert "video_path" in schema
