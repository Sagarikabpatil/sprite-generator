"""Small synchronous database adapter for SQLite and explicitly configured MySQL."""

from __future__ import annotations

import os
import ssl
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


class DatabaseError(RuntimeError):
    """Database operation failed."""


class DatabaseIntegrityError(DatabaseError):
    """Database constraint violation."""


class DatabaseConfigurationError(ValueError):
    """Database configuration is missing, ambiguous, or unsupported."""


@dataclass(frozen=True)
class DatabaseConfig:
    engine: str
    sqlite_path: Path
    mysql_host: str = ""
    mysql_port: int = 3306
    mysql_user: str = ""
    mysql_password: str = field(default="", repr=False)
    mysql_database: str = ""
    mysql_ssl_ca: Path | None = None

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        default_sqlite_path: Path,
        require_explicit_engine: bool = False,
    ) -> "DatabaseConfig":
        values = os.environ if env is None else env
        engine_value = (values.get("ASSETAI_DB_ENGINE") or "").strip() or None
        if require_explicit_engine and engine_value is None:
            raise DatabaseConfigurationError(
                "Production deployments must set ASSETAI_DB_ENGINE explicitly "
                "to either 'sqlite' or 'mysql'."
            )
        mysql_keys = (
            "ASSETAI_MYSQL_HOST",
            "ASSETAI_MYSQL_PORT",
            "ASSETAI_MYSQL_USER",
            "ASSETAI_MYSQL_PASSWORD",
            "ASSETAI_MYSQL_DATABASE",
        )
        has_mysql_settings = any(values.get(key) for key in mysql_keys)
        if not engine_value and has_mysql_settings:
            raise DatabaseConfigurationError(
                "MySQL settings are present but ASSETAI_DB_ENGINE is not set. "
                "Set ASSETAI_DB_ENGINE=mysql explicitly or remove the MySQL settings."
            )

        engine = (engine_value or "sqlite").strip().lower()
        if engine == "sqlite":
            return cls(
                engine="sqlite",
                sqlite_path=Path(values.get("ASSETAI_DB_PATH", default_sqlite_path)),
            )
        if engine != "mysql":
            raise DatabaseConfigurationError(
                "ASSETAI_DB_ENGINE must be either 'sqlite' or 'mysql'."
            )

        required_keys = (
            "ASSETAI_MYSQL_HOST",
            "ASSETAI_MYSQL_USER",
            "ASSETAI_MYSQL_PASSWORD",
            "ASSETAI_MYSQL_DATABASE",
        )
        missing = [key for key in required_keys if not values.get(key)]
        if missing:
            raise DatabaseConfigurationError(
                "MySQL is explicitly selected, but required configuration is missing: "
                + ", ".join(missing)
            )
        try:
            port = int(values.get("ASSETAI_MYSQL_PORT", "3306"))
        except ValueError as exc:
            raise DatabaseConfigurationError(
                "ASSETAI_MYSQL_PORT must be an integer."
            ) from exc
        if not 1 <= port <= 65535:
            raise DatabaseConfigurationError(
                "ASSETAI_MYSQL_PORT must be between 1 and 65535."
            )

        mysql_ssl_ca_value = (values.get("ASSETAI_MYSQL_SSL_CA") or "").strip()
        mysql_ssl_ca = Path(mysql_ssl_ca_value) if mysql_ssl_ca_value else None
        if mysql_ssl_ca is not None:
            _create_mysql_ssl_context(mysql_ssl_ca)

        return cls(
            engine="mysql",
            sqlite_path=Path(values.get("ASSETAI_DB_PATH", default_sqlite_path)),
            mysql_host=values["ASSETAI_MYSQL_HOST"],
            mysql_port=port,
            mysql_user=values["ASSETAI_MYSQL_USER"],
            mysql_password=values["ASSETAI_MYSQL_PASSWORD"],
            mysql_database=values["ASSETAI_MYSQL_DATABASE"],
            mysql_ssl_ca=mysql_ssl_ca,
        )


def adapt_qmark_placeholders(sql: str, parameter_count: int) -> str:
    """Convert DB-API qmark placeholders without touching quoted SQL text."""
    output: list[str] = []
    placeholders = 0
    index = 0
    quote: str | None = None
    line_comment = False
    block_comment = False

    while index < len(sql):
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < len(sql) else ""

        if line_comment:
            output.append(char)
            if char == "\n":
                line_comment = False
            index += 1
            continue
        if block_comment:
            output.append(char)
            if char == "*" and next_char == "/":
                output.append(next_char)
                block_comment = False
                index += 2
            else:
                index += 1
            continue
        if quote:
            output.append(char)
            if char == "\\" and index + 1 < len(sql):
                output.append(next_char)
                index += 2
                continue
            if char == quote:
                if next_char == quote:
                    output.append(next_char)
                    index += 2
                    continue
                quote = None
            index += 1
            continue

        if char in {"'", '"', "`"}:
            quote = char
            output.append(char)
        elif char == "-" and next_char == "-":
            line_comment = True
            output.extend((char, next_char))
            index += 2
            continue
        elif char == "/" and next_char == "*":
            block_comment = True
            output.extend((char, next_char))
            index += 2
            continue
        elif char == "#":
            line_comment = True
            output.append(char)
        elif char == "?":
            output.append("%s")
            placeholders += 1
        else:
            output.append(char)
        index += 1

    if placeholders != parameter_count:
        raise ValueError(
            f"SQL has {placeholders} placeholders but received {parameter_count} parameters."
        )
    return "".join(output)


class DatabaseConnection:
    """Connection facade retaining the app's execute/fetch/lastrowid usage."""

    def __init__(self, connection: Any, engine: str) -> None:
        self._connection = connection
        self.engine = engine

    def execute(
        self, sql: str, parameters: Sequence[object] = ()
    ) -> Any:
        try:
            if self.engine == "sqlite":
                return self._connection.execute(sql, tuple(parameters))
            adapted_sql = adapt_qmark_placeholders(sql, len(parameters))
            cursor = self._connection.cursor()
            cursor.execute(adapted_sql, tuple(parameters))
            return cursor
        except Exception as exc:
            mapped_error = _map_database_error(exc, self.engine)
            if mapped_error is None:
                raise
            raise mapped_error from exc

    def __enter__(self) -> "DatabaseConnection":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        try:
            if exc_type is None:
                try:
                    self._connection.commit()
                except Exception:
                    self._connection.rollback()
                    raise
            else:
                self._connection.rollback()
        except Exception as transaction_error:
            mapped_error = _map_database_error(transaction_error, self.engine)
            if mapped_error is None:
                raise
            raise mapped_error from transaction_error
        finally:
            self._connection.close()
        return False


def _map_database_error(error: Exception, engine: str) -> DatabaseError | None:
    if engine == "sqlite" and isinstance(error, sqlite3.Error):
        if isinstance(error, sqlite3.IntegrityError):
            return DatabaseIntegrityError(str(error))
        return DatabaseError(str(error))

    if engine == "mysql":
        try:
            import pymysql
        except ImportError:
            return None
        if isinstance(error, pymysql.MySQLError):
            if isinstance(error, pymysql.err.IntegrityError):
                return DatabaseIntegrityError(str(error))
            return DatabaseError(str(error))
    return None


def connect_database(
    config: DatabaseConfig, *, sqlite_path: Path | None = None
) -> DatabaseConnection:
    """Open a configured connection; MySQL driver import remains lazy."""
    if config.engine == "sqlite":
        path = sqlite_path or config.sqlite_path
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        return DatabaseConnection(connection, "sqlite")

    if config.engine == "mysql":
        try:
            import pymysql
        except ImportError as exc:
            raise DatabaseConfigurationError(
                "PyMySQL is required when ASSETAI_DB_ENGINE=mysql."
            ) from exc
        connect_options = {
            "host": config.mysql_host,
            "port": config.mysql_port,
            "user": config.mysql_user,
            "password": config.mysql_password,
            "database": config.mysql_database,
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor,
            "autocommit": False,
            "init_command": "SET time_zone = '+00:00'",
        }
        if config.mysql_ssl_ca is not None:
            connect_options["ssl"] = _create_mysql_ssl_context(config.mysql_ssl_ca)
        try:
            connection = pymysql.connect(**connect_options)
        except pymysql.MySQLError as exc:
            raise DatabaseError("Could not connect to the configured MySQL database.") from exc
        return DatabaseConnection(connection, "mysql")

    raise DatabaseConfigurationError(f"Unsupported database engine: {config.engine}")


def _create_mysql_ssl_context(ca_file: Path) -> ssl.SSLContext:
    try:
        return ssl.create_default_context(cafile=str(ca_file))
    except (OSError, ssl.SSLError, ValueError) as exc:
        raise DatabaseConfigurationError(
            f"ASSETAI_MYSQL_SSL_CA must point to a valid CA certificate file: {ca_file}"
        ) from exc
