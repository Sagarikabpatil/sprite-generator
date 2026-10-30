"""Copy AssetAI SQLite data into a new, empty MySQL database.

This command never overwrites or drops an existing target database. If a run
fails after creating `assetai`, inspect and back up that database manually.
Only after confirming it contains no data worth retaining should an operator
rename or remove it using a separate, reviewed MySQL administration procedure.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from app.database import (
    DatabaseConfig,
    DatabaseConfigurationError,
    DatabaseConnection,
    connect_database,
)
from app.mysql_schema import MYSQL_SCHEMA

TARGET_DATABASE = "assetai"
TABLES = ("users", "auth_sessions", "generation_records", "user_assets")
TABLE_COLUMNS: Mapping[str, tuple[str, ...]] = {
    "users": (
        "id",
        "email",
        "password_hash",
        "password_salt",
        "display_name",
        "created_at",
    ),
    "auth_sessions": ("id", "user_id", "token", "expires_at", "created_at"),
    "generation_records": (
        "id",
        "user_id",
        "prompt",
        "action",
        "status",
        "character_path",
        "processed_path",
        "sprite_sheet_path",
        "video_path",
        "metadata",
        "created_at",
    ),
    "user_assets": (
        "id",
        "user_id",
        "asset_type",
        "name",
        "file_url",
        "prompt",
        "action",
        "created_at",
    ),
}
CHILD_TABLES = ("auth_sessions", "generation_records", "user_assets")
ID_MAX = (1 << 64) - 1
INSERT_BATCH_SIZE = 250


class MigrationError(RuntimeError):
    """Migration was refused or validation failed."""


@dataclass(frozen=True)
class SourceSnapshot:
    row_counts: Mapping[str, int]
    ids: Mapping[str, tuple[int, ...]]


def normalize_datetime(value: object, *, field: str) -> datetime | None:
    """Convert SQLite timestamp text to a naive UTC MySQL DATETIME value."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise MigrationError(f"Invalid source timestamp in {field}.") from exc
    else:
        raise MigrationError(f"Unsupported source timestamp type in {field}.")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def validate_existing_target(exists: bool) -> None:
    if exists:
        raise MigrationError(
            "Target database 'assetai' already exists. No data was changed. "
            "Use the documented manual recovery procedure only after reviewing "
            "and backing up the existing target."
        )


def _validate_text_lengths(table: str, row: sqlite3.Row) -> None:
    limits = {
        "users": {
            "email": 320,
            "password_hash": 255,
            "password_salt": 255,
        },
        "auth_sessions": {"token": 255},
        "generation_records": {"action": 255, "status": 64},
        "user_assets": {"asset_type": 64, "name": 255, "action": 255},
    }[table]
    for column, limit in limits.items():
        value = row[column]
        if value is not None and len(value) > limit:
            raise MigrationError(
                f"Source value exceeds the MySQL schema limit for {table}.{column}."
            )
    if table == "auth_sessions":
        try:
            row["token"].encode("ascii")
        except UnicodeEncodeError as exc:
            raise MigrationError("A source session token is not ASCII.") from exc
    if table == "user_assets":
        try:
            row["asset_type"].encode("ascii")
        except UnicodeEncodeError as exc:
            raise MigrationError("A source asset type is not ASCII.") from exc


def _validate_source(connection: sqlite3.Connection) -> SourceSnapshot:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()
    if integrity is None or integrity[0] != "ok":
        raise MigrationError("SQLite integrity check failed.")

    existing_tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if set(TABLES) - existing_tables:
        raise MigrationError("SQLite source is missing one or more required tables.")

    for table, expected_columns in TABLE_COLUMNS.items():
        actual_columns = tuple(
            row[1] for row in connection.execute(f'PRAGMA table_info("{table}")')
        )
        if actual_columns != expected_columns:
            raise MigrationError(
                f"SQLite source schema for {table} does not match the expected AssetAI schema."
            )

    row_counts: dict[str, int] = {}
    id_values: dict[str, tuple[int, ...]] = {}
    emails: set[str] = set()
    for table in TABLES:
        ids: list[int] = []
        cursor = connection.execute(f'SELECT * FROM "{table}" ORDER BY id')
        while rows := cursor.fetchmany(INSERT_BATCH_SIZE):
            for row in rows:
                record_id = row["id"]
                if not isinstance(record_id, int) or not 1 <= record_id <= ID_MAX:
                    raise MigrationError(f"Invalid primary key found in {table}.")
                ids.append(record_id)
                _validate_text_lengths(table, row)
                for timestamp_column in (
                    ("created_at", "expires_at")
                    if table == "auth_sessions"
                    else ("created_at",)
                ):
                    normalize_datetime(
                        row[timestamp_column], field=f"{table}.{timestamp_column}"
                    )
                if table == "users":
                    normalized_email = row["email"].casefold()
                    if normalized_email in emails:
                        raise MigrationError(
                            "Source emails collide under the target MySQL collation."
                        )
                    emails.add(normalized_email)
        row_counts[table] = len(ids)
        id_values[table] = tuple(ids)

    for child_table in CHILD_TABLES:
        orphan_count = connection.execute(
            f"""
            SELECT COUNT(*)
            FROM "{child_table}" AS child
            LEFT JOIN users AS parent ON parent.id = child.user_id
            WHERE child.user_id IS NOT NULL AND parent.id IS NULL
            """
        ).fetchone()[0]
        if orphan_count:
            raise MigrationError(
                f"SQLite source contains orphan user references in {child_table}."
            )

    return SourceSnapshot(row_counts=row_counts, ids=id_values)


@contextmanager
def open_validated_source(path: Path) -> Iterator[tuple[sqlite3.Connection, SourceSnapshot]]:
    try:
        source_path = Path(path).resolve(strict=True)
        uri = f"{source_path.as_uri()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
    except (OSError, RuntimeError, sqlite3.Error) as exc:
        raise MigrationError("Could not open the SQLite source database read-only.") from exc
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("BEGIN")
        try:
            snapshot = _validate_source(connection)
        except sqlite3.Error as exc:
            raise MigrationError("Could not validate the SQLite source database.") from exc
        yield connection, snapshot
    finally:
        connection.close()


def _read_target_counts(connection: DatabaseConnection) -> dict[str, int]:
    return {
        table: int(
            connection.execute(
                f"SELECT COUNT(*) AS row_count FROM `{table}`"
            ).fetchone()["row_count"]
        )
        for table in TABLES
    }


def ensure_target_empty(connection: DatabaseConnection) -> None:
    counts = _read_target_counts(connection)
    if any(counts.values()):
        raise MigrationError(
            "Target database contains data. Migration refused without changing its rows."
        )


def _copy_rows(
    source: sqlite3.Connection,
    target: DatabaseConnection,
) -> None:
    for table in TABLES:
        columns = TABLE_COLUMNS[table]
        column_sql = ", ".join(f"`{column}`" for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        insert_sql = f"INSERT INTO `{table}` ({column_sql}) VALUES ({placeholders})"
        cursor = source.execute(f'SELECT * FROM "{table}" ORDER BY id')
        while rows := cursor.fetchmany(INSERT_BATCH_SIZE):
            for row in rows:
                values: list[object] = []
                for column in columns:
                    value = row[column]
                    if column == "created_at" or (
                        table == "auth_sessions" and column == "expires_at"
                    ):
                        value = normalize_datetime(value, field=f"{table}.{column}")
                    values.append(value)
                target.execute(insert_sql, values)


def _target_ids(connection: DatabaseConnection) -> dict[str, tuple[int, ...]]:
    return {
        table: tuple(
            int(row["id"])
            for row in connection.execute(
                f"SELECT id FROM `{table}` ORDER BY id"
            ).fetchall()
        )
        for table in TABLES
    }


def verify_target(
    connection: DatabaseConnection, expected: SourceSnapshot
) -> dict[str, int]:
    row_counts = _read_target_counts(connection)
    if row_counts != dict(expected.row_counts):
        raise MigrationError("Source and target row counts do not match.")
    if _target_ids(connection) != dict(expected.ids):
        raise MigrationError("Source and target primary keys do not match.")

    for child_table in CHILD_TABLES:
        orphan_count = connection.execute(
            f"""
            SELECT COUNT(*) AS orphan_count
            FROM `{child_table}` AS child
            LEFT JOIN users AS parent ON parent.id = child.user_id
            WHERE child.user_id IS NOT NULL AND parent.id IS NULL
            """
        ).fetchone()["orphan_count"]
        if orphan_count:
            raise MigrationError(
                f"Target contains orphan user references in {child_table}."
            )
    return row_counts


def _mysql_server_connection(config: DatabaseConfig) -> Any:
    try:
        import pymysql
    except ImportError as exc:
        raise MigrationError(
            "PyMySQL is not installed. Install the declared backend dependency before migration."
        ) from exc
    try:
        return pymysql.connect(
            host=config.mysql_host,
            port=config.mysql_port,
            user=config.mysql_user,
            password=config.mysql_password,
            charset="utf8mb4",
            autocommit=True,
        )
    except pymysql.MySQLError as exc:
        raise MigrationError(
            "Could not connect to MySQL using the supplied configuration."
        ) from exc


def create_new_target_database(config: DatabaseConfig) -> None:
    if config.mysql_database != TARGET_DATABASE:
        raise MigrationError(
            f"Migration target must be exactly '{TARGET_DATABASE}'."
        )
    server = _mysql_server_connection(config)
    try:
        with server.cursor() as cursor:
            cursor.execute(
                "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
                "WHERE SCHEMA_NAME = %s",
                (TARGET_DATABASE,),
            )
            validate_existing_target(cursor.fetchone() is not None)
            cursor.execute(
                f"CREATE DATABASE `{TARGET_DATABASE}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    except MigrationError:
        raise
    except Exception as exc:
        raise MigrationError(
            "Could not create the new MySQL target database. No existing database was dropped."
        ) from exc
    finally:
        server.close()


def migrate(source_path: Path, config: DatabaseConfig) -> dict[str, int]:
    if config.engine != "mysql":
        raise MigrationError("Migration requires explicit MySQL configuration.")
    if config.mysql_database != TARGET_DATABASE:
        raise MigrationError(
            f"Migration target must be exactly '{TARGET_DATABASE}'."
        )

    with open_validated_source(source_path) as (source, snapshot):
        create_new_target_database(config)
        target_config = replace(config, mysql_database=TARGET_DATABASE)
        try:
            with connect_database(target_config) as target:
                for statement in MYSQL_SCHEMA:
                    target.execute(statement)
                ensure_target_empty(target)
                _copy_rows(source, target)
                return verify_target(target, snapshot)
        except Exception as exc:
            if isinstance(exc, MigrationError):
                raise
            raise MigrationError(
                "Migration failed. The SQLite source was not modified; "
                "the newly created MySQL database was not automatically removed. "
                "Inspect and back it up before any manual recovery."
            ) from exc


def _load_mysql_config() -> DatabaseConfig:
    values = dict(os.environ)
    values["ASSETAI_DB_ENGINE"] = "mysql"
    if not values.get("ASSETAI_MYSQL_PASSWORD"):
        values["ASSETAI_MYSQL_PASSWORD"] = getpass(
            "MySQL password (input hidden): "
        )
    try:
        return DatabaseConfig.from_env(values, default_sqlite_path=Path("app.db"))
    except DatabaseConfigurationError as exc:
        raise MigrationError(str(exc)) from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy the AssetAI SQLite database into a brand-new MySQL database "
            "named 'assetai'. This command never overwrites an existing database."
        ),
        epilog=(
            "Recovery: the script never drops targets. If a failed attempt left "
            "'assetai', take a backup and inspect it manually. Only after confirming "
            "it has no useful data should an administrator rename/remove it using a "
            "separate reviewed MySQL procedure before retrying."
        ),
    )
    default_source = Path(__file__).resolve().parents[1] / "app.db"
    parser.add_argument(
        "--source",
        type=Path,
        default=default_source,
        help="SQLite source path (default: backend/app.db).",
    )
    args = parser.parse_args(argv)
    try:
        config = _load_mysql_config()
        counts = migrate(args.source, config)
    except MigrationError as exc:
        print(f"Migration refused or failed: {exc}", file=sys.stderr)
        return 1

    print("Migration completed and verified.")
    for table in TABLES:
        print(f"{table}: {counts[table]} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
