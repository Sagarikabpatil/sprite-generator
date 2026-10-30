"""MySQL DDL for the current AssetAI persistence model."""

MYSQL_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS users (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        email VARCHAR(320) NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        password_salt VARCHAR(255) NOT NULL,
        display_name TEXT NULL,
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        PRIMARY KEY (id),
        CONSTRAINT uq_users_email UNIQUE (email)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS auth_sessions (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        user_id BIGINT UNSIGNED NOT NULL,
        token VARCHAR(255) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        expires_at DATETIME(6) NOT NULL,
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        PRIMARY KEY (id),
        CONSTRAINT uq_auth_sessions_token UNIQUE (token),
        CONSTRAINT fk_auth_sessions_user
            FOREIGN KEY (user_id) REFERENCES users (id),
        INDEX ix_auth_sessions_user_expiry (user_id, expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS generation_records (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        user_id BIGINT UNSIGNED NULL,
        prompt LONGTEXT NULL,
        action VARCHAR(255) NULL,
        status VARCHAR(64) NOT NULL,
        character_path TEXT NULL,
        processed_path TEXT NULL,
        sprite_sheet_path TEXT NULL,
        video_path TEXT NULL,
        metadata LONGTEXT NULL,
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        PRIMARY KEY (id),
        CONSTRAINT fk_generation_records_user
            FOREIGN KEY (user_id) REFERENCES users (id),
        INDEX ix_generation_records_user_created (user_id, created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS user_assets (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        user_id BIGINT UNSIGNED NULL,
        asset_type VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
        name VARCHAR(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
        file_url TEXT NULL,
        prompt LONGTEXT NULL,
        action VARCHAR(255) NULL,
        created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        PRIMARY KEY (id),
        CONSTRAINT fk_user_assets_user
            FOREIGN KEY (user_id) REFERENCES users (id),
        INDEX ix_user_assets_user_created (user_id, created_at),
        INDEX ix_user_assets_type_name_user (asset_type, name, user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
)
