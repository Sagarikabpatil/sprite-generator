import sqlite3
from datetime import datetime
from pathlib import Path

import pytest

from app.database import DatabaseConfig, connect_database
from scripts import migrate_sqlite_to_mysql as migration


SOURCE_SCHEMA = (
    """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        password_salt TEXT NOT NULL,
        display_name TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE auth_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE generation_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        prompt TEXT,
        action TEXT,
        status TEXT NOT NULL,
        character_path TEXT,
        processed_path TEXT,
        sprite_sheet_path TEXT,
        video_path TEXT,
        metadata TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE user_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        asset_type TEXT NOT NULL,
        name TEXT NOT NULL,
        file_url TEXT,
        prompt TEXT,
        action TEXT,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
)


def create_source(path: Path, *, with_data: bool = True) -> None:
    connection = sqlite3.connect(path)
    try:
        for statement in SOURCE_SCHEMA:
            connection.execute(statement)
        if with_data:
            connection.execute(
                """
                INSERT INTO users
                    (id, email, password_hash, password_salt, display_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    7,
                    "sprite@example.com",
                    "hash-value",
                    "salt-value",
                    "Sprite",
                    "2026-01-01T10:00:00.654321",
                ),
            )
            connection.execute(
                """
                INSERT INTO auth_sessions
                    (id, user_id, token, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    11,
                    7,
                    "session-token",
                    "2026-02-01T12:30:00+02:00",
                    "2026-01-01T12:00:00+02:00",
                ),
            )
            connection.execute(
                """
                INSERT INTO generation_records
                    (id, user_id, prompt, action, status, character_path,
                     processed_path, sprite_sheet_path, video_path, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    13,
                    7,
                    "pixel character",
                    "walk",
                    "completed",
                    "/assets/1/file",
                    "/assets/2/file",
                    "/assets/3/file",
                    "/assets/4/file",
                    '{"frames": 4}',
                    "2026-01-01 10:00:00",
                ),
            )
            connection.execute(
                """
                INSERT INTO user_assets
                    (id, user_id, asset_type, name, file_url, prompt, action, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    17,
                    7,
                    "processed",
                    "character.png",
                    "/assets/2/file",
                    "pixel character",
                    None,
                    "2026-01-01 10:00:00",
                ),
            )
        connection.commit()
    finally:
        connection.close()


def create_target(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        for statement in SOURCE_SCHEMA:
            connection.execute(statement)
        connection.commit()
    finally:
        connection.close()


def source_snapshot(path: Path):
    with migration.open_validated_source(path) as (_, snapshot):
        return snapshot


def test_source_validation_captures_counts_ids_and_relationships(tmp_path):
    source_path = tmp_path / "source.sqlite"
    create_source(source_path)

    snapshot = source_snapshot(source_path)

    assert snapshot.row_counts == {
        "users": 1,
        "auth_sessions": 1,
        "generation_records": 1,
        "user_assets": 1,
    }
    assert snapshot.ids == {
        "users": (7,),
        "auth_sessions": (11,),
        "generation_records": (13,),
        "user_assets": (17,),
    }


def test_source_connection_is_read_only(tmp_path):
    source_path = tmp_path / "readonly.sqlite"
    create_source(source_path)

    with migration.open_validated_source(source_path) as (source, _):
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            source.execute("DELETE FROM users")


def test_source_validation_rejects_orphaned_user_relationship(tmp_path):
    source_path = tmp_path / "orphan.sqlite"
    create_source(source_path, with_data=False)
    connection = sqlite3.connect(source_path)
    connection.execute(
        """
        INSERT INTO user_assets (user_id, asset_type, name)
        VALUES (?, ?, ?)
        """,
        (999, "processed", "orphan.png"),
    )
    connection.commit()
    connection.close()

    with pytest.raises(migration.MigrationError, match="orphan user references"):
        source_snapshot(source_path)


def test_existing_target_is_refused_without_attempting_creation(monkeypatch):
    class Cursor:
        def __init__(self):
            self.statements = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def execute(self, statement, parameters):
            self.statements.append((statement, parameters))

        def fetchone(self):
            return ("assetai",)

    class Server:
        def __init__(self):
            self.fake_cursor = Cursor()
            self.closed = False

        def cursor(self):
            return self.fake_cursor

        def close(self):
            self.closed = True

    server = Server()
    monkeypatch.setattr(migration, "_mysql_server_connection", lambda _config: server)
    config = DatabaseConfig(
        engine="mysql",
        sqlite_path=Path("unused.sqlite"),
        mysql_host="localhost",
        mysql_user="assetai",
        mysql_password="not-printed",
        mysql_database="assetai",
    )

    with pytest.raises(migration.MigrationError, match="already exists"):
        migration.create_new_target_database(config)

    assert len(server.fake_cursor.statements) == 1
    assert server.closed


def test_populated_target_is_refused(tmp_path):
    target_path = tmp_path / "target.sqlite"
    create_target(target_path)
    config = DatabaseConfig(engine="sqlite", sqlite_path=target_path)

    with connect_database(config) as target:
        target.execute(
            """
            INSERT INTO users (email, password_hash, password_salt)
            VALUES (?, ?, ?)
            """,
            ("present@example.com", "hash", "salt"),
        )
        with pytest.raises(migration.MigrationError, match="contains data"):
            migration.ensure_target_empty(target)


def test_copy_preserves_ids_data_and_normalizes_timestamps(tmp_path):
    source_path = tmp_path / "source.sqlite"
    target_path = tmp_path / "target.sqlite"
    create_source(source_path)
    create_target(target_path)
    snapshot = source_snapshot(source_path)
    config = DatabaseConfig(engine="sqlite", sqlite_path=target_path)

    with migration.open_validated_source(source_path) as (source, _):
        with connect_database(config) as target:
            migration._copy_rows(source, target)
            counts = migration.verify_target(target, snapshot)
            user = target.execute("SELECT * FROM users WHERE id = ?", (7,)).fetchone()
            session = target.execute(
                "SELECT * FROM auth_sessions WHERE id = ?", (11,)
            ).fetchone()
            history = target.execute(
                "SELECT * FROM generation_records WHERE id = ?", (13,)
            ).fetchone()
            asset = target.execute(
                "SELECT * FROM user_assets WHERE id = ?", (17,)
            ).fetchone()

    assert counts == dict(snapshot.row_counts)
    assert user["password_hash"] == "hash-value"
    assert user["password_salt"] == "salt-value"
    assert user["created_at"] == "2026-01-01 10:00:00.654321"
    assert session["token"] == "session-token"
    assert session["expires_at"] == "2026-02-01 10:30:00"
    assert history["sprite_sheet_path"] == "/assets/3/file"
    assert asset["user_id"] == 7
    assert asset["file_url"] == "/assets/2/file"


def test_copy_failure_rolls_back_target_transaction(tmp_path):
    source_path = tmp_path / "source.sqlite"
    target_path = tmp_path / "target.sqlite"
    create_source(source_path)
    create_target(target_path)
    config = DatabaseConfig(engine="sqlite", sqlite_path=target_path)

    with migration.open_validated_source(source_path) as (source, _):
        with pytest.raises(RuntimeError, match="simulated verification failure"):
            with connect_database(config) as target:
                migration._copy_rows(source, target)
                raise RuntimeError("simulated verification failure")

    check = sqlite3.connect(target_path)
    try:
        assert check.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
        assert check.execute("SELECT COUNT(*) FROM user_assets").fetchone()[0] == 0
    finally:
        check.close()


def test_timestamp_normalization_converts_offsets_to_utc():
    assert migration.normalize_datetime(
        "2026-02-01T12:30:00+02:00", field="auth_sessions.expires_at"
    ) == datetime(2026, 2, 1, 10, 30)


def test_mysql_schema_preserves_microsecond_creation_timestamps():
    schema = "\n".join(migration.MYSQL_SCHEMA)

    assert schema.count("created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)") == 4


def test_migration_refuses_wrong_engine_and_database_before_connecting(tmp_path):
    source_path = tmp_path / "source.sqlite"
    create_source(source_path)

    sqlite_config = DatabaseConfig(engine="sqlite", sqlite_path=source_path)
    with pytest.raises(migration.MigrationError, match="explicit MySQL"):
        migration.migrate(source_path, sqlite_config)

    wrong_target = DatabaseConfig(
        engine="mysql",
        sqlite_path=source_path,
        mysql_host="localhost",
        mysql_user="assetai",
        mysql_password="not-printed",
        mysql_database="other",
    )
    with pytest.raises(migration.MigrationError, match="exactly 'assetai'"):
        migration.migrate(source_path, wrong_target)
