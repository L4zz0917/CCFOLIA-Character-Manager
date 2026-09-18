import sqlite3

from app.paths import DATABASE_PATH


MIGRATIONS = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS characters (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            player_name TEXT NOT NULL DEFAULT '',
            memo TEXT NOT NULL DEFAULT '',
            initiative REAL NOT NULL DEFAULT 0,
            external_url TEXT NOT NULL DEFAULT '',
            color TEXT NOT NULL DEFAULT '#888888',

            secret INTEGER NOT NULL DEFAULT 0,
            invisible INTEGER NOT NULL DEFAULT 0,
            hide_status INTEGER NOT NULL DEFAULT 0,

            cocofolia_source_id TEXT,
            cocofolia_export_id TEXT NOT NULL UNIQUE,

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            deleted_at TEXT,
            quick_memo TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS character_images (
            id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            label TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS statuses (
            id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL,
            label TEXT NOT NULL,
            current_value REAL,
            max_value REAL,
            sort_order INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS params (
            id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL,
            label TEXT NOT NULL,
            value TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS derived_values (
            id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL,
            label TEXT NOT NULL,
            formula TEXT NOT NULL DEFAULT '',
            last_value TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL,
            label TEXT NOT NULL,
            value TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            category TEXT NOT NULL DEFAULT '',

            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS memos (
            id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            body TEXT NOT NULL DEFAULT '',
            is_private INTEGER NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS chat_palettes (
            id TEXT PRIMARY KEY,
            character_id TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            mode TEXT NOT NULL DEFAULT 'normal',
            content TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS tags (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS character_tags (
            character_id TEXT NOT NULL,
            tag_id TEXT NOT NULL,

            PRIMARY KEY(character_id, tag_id),

            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE,

            FOREIGN KEY(tag_id)
                REFERENCES tags(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS groups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            parent_group_id TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,

            FOREIGN KEY(parent_group_id)
                REFERENCES groups(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS character_groups (
            character_id TEXT NOT NULL,
            group_id TEXT NOT NULL,

            PRIMARY KEY(character_id, group_id),

            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE,

            FOREIGN KEY(group_id)
                REFERENCES groups(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS cocofolia_raw_json (
            character_id TEXT PRIMARY KEY,
            raw_json TEXT NOT NULL DEFAULT '',

            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS cocofolia_character_raw (
            character_id TEXT PRIMARY KEY,
            source_character_id TEXT NOT NULL DEFAULT '',
            raw_json TEXT NOT NULL DEFAULT '',
            source_token TEXT NOT NULL DEFAULT '',
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_characters_name
        ON characters(name);

        CREATE INDEX IF NOT EXISTS idx_groups_parent
        ON groups(parent_group_id);

        CREATE INDEX IF NOT EXISTS idx_character_images_character
        ON character_images(character_id, sort_order);

        CREATE INDEX IF NOT EXISTS idx_character_groups_group
        ON character_groups(group_id);
        """,
    ),
    (
        2,
        "\n        -- IMAGES_MODULE_SCHEMA_V1\n        CREATE TABLE IF NOT EXISTS image_assets (\n            id TEXT PRIMARY KEY,\n            display_name TEXT NOT NULL DEFAULT '',\n            local_path TEXT NOT NULL DEFAULT '',\n            original_filename TEXT NOT NULL DEFAULT '',\n\n            ccfolia_file_id TEXT UNIQUE,\n            ccfolia_url TEXT NOT NULL DEFAULT '',\n            content_type TEXT NOT NULL DEFAULT '',\n            file_size INTEGER NOT NULL DEFAULT 0,\n\n            source TEXT NOT NULL DEFAULT 'local',\n\n            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,\n            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP\n        );\n\n        CREATE TABLE IF NOT EXISTS image_tags (\n            id TEXT PRIMARY KEY,\n            name TEXT NOT NULL COLLATE NOCASE UNIQUE\n        );\n\n        CREATE TABLE IF NOT EXISTS image_asset_tags (\n            image_id TEXT NOT NULL,\n            tag_id TEXT NOT NULL,\n\n            PRIMARY KEY(image_id, tag_id),\n\n            FOREIGN KEY(image_id)\n                REFERENCES image_assets(id)\n                ON DELETE CASCADE,\n\n            FOREIGN KEY(tag_id)\n                REFERENCES image_tags(id)\n                ON DELETE CASCADE\n        );\n\n        CREATE TABLE IF NOT EXISTS image_groups (\n            id TEXT PRIMARY KEY,\n            name TEXT NOT NULL,\n            parent_group_id TEXT,\n            sort_order INTEGER NOT NULL DEFAULT 0,\n\n            FOREIGN KEY(parent_group_id)\n                REFERENCES image_groups(id)\n                ON DELETE CASCADE\n        );\n\n        CREATE TABLE IF NOT EXISTS image_asset_groups (\n            image_id TEXT NOT NULL,\n            group_id TEXT NOT NULL,\n\n            PRIMARY KEY(image_id, group_id),\n\n            FOREIGN KEY(image_id)\n                REFERENCES image_assets(id)\n                ON DELETE CASCADE,\n\n            FOREIGN KEY(group_id)\n                REFERENCES image_groups(id)\n                ON DELETE CASCADE\n        );\n\n        CREATE INDEX IF NOT EXISTS idx_image_assets_display_name\n        ON image_assets(display_name);\n\n        CREATE INDEX IF NOT EXISTS idx_image_assets_ccfolia_file_id\n        ON image_assets(ccfolia_file_id);\n\n        CREATE INDEX IF NOT EXISTS idx_image_groups_parent\n        ON image_groups(parent_group_id);\n\n        CREATE INDEX IF NOT EXISTS idx_image_asset_tags_tag\n        ON image_asset_tags(tag_id, image_id);\n\n        CREATE INDEX IF NOT EXISTS idx_image_asset_groups_group\n        ON image_asset_groups(group_id, image_id);\n",
    ),
    (
        3,
        '''
        -- BGM_MODULE_SCHEMA_V1
        CREATE TABLE IF NOT EXISTS bgm_assets (
            id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL DEFAULT '',
            local_path TEXT NOT NULL DEFAULT '',
            original_filename TEXT NOT NULL DEFAULT '',

            content_type TEXT NOT NULL DEFAULT '',
            file_size INTEGER NOT NULL DEFAULT 0,
            content_sha256 TEXT NOT NULL DEFAULT '',
            duration_ms INTEGER NOT NULL DEFAULT 0,

            default_volume REAL NOT NULL DEFAULT 0.5,
            default_loop INTEGER NOT NULL DEFAULT 1,

            media_kind TEXT NOT NULL DEFAULT 'bgm',
            source TEXT NOT NULL DEFAULT 'local',

            ccfolia_media_id TEXT UNIQUE,
            ccfolia_url TEXT NOT NULL DEFAULT '',
            ccfolia_dir TEXT NOT NULL DEFAULT '',
            ccfolia_order REAL NOT NULL DEFAULT 0,
            ccfolia_uploaded INTEGER NOT NULL DEFAULT 0,
            ccfolia_archived INTEGER NOT NULL DEFAULT 0,
            ccfolia_updated_at INTEGER,
            ccfolia_raw_json TEXT NOT NULL DEFAULT '',

            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS bgm_tags (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE
        );

        CREATE TABLE IF NOT EXISTS bgm_asset_tags (
            bgm_id TEXT NOT NULL,
            tag_id TEXT NOT NULL,
            PRIMARY KEY(bgm_id, tag_id),
            FOREIGN KEY(bgm_id) REFERENCES bgm_assets(id) ON DELETE CASCADE,
            FOREIGN KEY(tag_id) REFERENCES bgm_tags(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS bgm_groups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            parent_group_id TEXT,
            sort_order INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(parent_group_id) REFERENCES bgm_groups(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS bgm_asset_groups (
            bgm_id TEXT NOT NULL,
            group_id TEXT NOT NULL,
            PRIMARY KEY(bgm_id, group_id),
            FOREIGN KEY(bgm_id) REFERENCES bgm_assets(id) ON DELETE CASCADE,
            FOREIGN KEY(group_id) REFERENCES bgm_groups(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_bgm_assets_display_name
        ON bgm_assets(display_name);
        CREATE INDEX IF NOT EXISTS idx_bgm_assets_media_kind
        ON bgm_assets(media_kind);
        CREATE INDEX IF NOT EXISTS idx_bgm_assets_ccfolia_media_id
        ON bgm_assets(ccfolia_media_id);
        CREATE INDEX IF NOT EXISTS idx_bgm_assets_ccfolia_dir
        ON bgm_assets(ccfolia_dir);
        CREATE INDEX IF NOT EXISTS idx_bgm_assets_content_sha256
        ON bgm_assets(content_sha256);
        CREATE INDEX IF NOT EXISTS idx_bgm_groups_parent
        ON bgm_groups(parent_group_id);
        CREATE INDEX IF NOT EXISTS idx_bgm_asset_tags_tag
        ON bgm_asset_tags(tag_id, bgm_id);
        CREATE INDEX IF NOT EXISTS idx_bgm_asset_groups_group
        ON bgm_asset_groups(group_id, bgm_id);
        ''',
    ),
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")

    return conn


def initialize_database() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        applied = {
            row["version"]
            for row in conn.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
        }

        for version, sql in MIGRATIONS:
            if version in applied:
                continue

            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(version) VALUES (?)",
                (version,),
            )

        # CHARACTER_SCHEMA_COMPAT_V2
        # Existing databases created before Character schema parity need these
        # fields even when migration 1 is already marked as applied.
        _character_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(characters)").fetchall()
        }
        if "quick_memo" not in _character_columns:
            conn.execute(
                "ALTER TABLE characters "
                "ADD COLUMN quick_memo TEXT NOT NULL DEFAULT ''"
            )

        _skill_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(skills)").fetchall()
        }
        if "category" not in _skill_columns:
            conn.execute(
                "ALTER TABLE skills "
                "ADD COLUMN category TEXT NOT NULL DEFAULT ''"
            )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cocofolia_character_raw (
                character_id TEXT PRIMARY KEY,
                source_character_id TEXT NOT NULL DEFAULT '',
                raw_json TEXT NOT NULL DEFAULT '',
                source_token TEXT NOT NULL DEFAULT '',
                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(character_id)
                    REFERENCES characters(id)
                    ON DELETE CASCADE
            )
            """
        )

        defaults = {
            "autosave_enabled": "1",
            "autosave_delay_ms": "750",
            "default_token_size": "4",
        }

        for key, value in defaults.items():
            conn.execute(
                """
                INSERT OR IGNORE INTO settings(key, value)
                VALUES (?, ?)
                """,
                (key, value),
            )

    # Phase 22+: fresh installations also receive the rule-aware schema.
    from app.services.rule_data_service import ensure_phase22a_schema
    ensure_phase22a_schema()
