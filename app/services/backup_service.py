from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from app.db.database import get_connection
from app.paths import IMAGES_DIR, PROJECT_ROOT


BACKUP_FORMAT = "ccfolia-character-manager-backup"
BACKUP_VERSION = 1
MANIFEST_NAME = "manifest.json"
DATABASE_NAME = "database.sqlite3"
ASSETS_PREFIX = "app_data"


def _backups_dir() -> Path:
    path = PROJECT_ROOT / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_backup_path(prefix: str = "backup") -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _backups_dir() / f"{prefix}_{stamp}.zip"


def _database_path() -> Path:
    with get_connection() as conn:
        for row in conn.execute("PRAGMA database_list").fetchall():
            if row[1] == "main" and row[2]:
                return Path(row[2]).resolve()

    raise RuntimeError(
        "データベースファイルの場所を特定できません。"
    )


def _app_data_dir() -> Path:
    return IMAGES_DIR.parent.resolve()


def _is_database_file(
    path: Path,
    database_path: Path,
) -> bool:
    resolved = path.resolve()

    if resolved == database_path:
        return True

    return str(resolved) in {
        str(database_path) + "-wal",
        str(database_path) + "-shm",
        str(database_path) + "-journal",
    }


def _write_database_snapshot(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as source:
        snapshot = sqlite3.connect(destination)

        try:
            source.backup(snapshot)
            snapshot.commit()
        finally:
            snapshot.close()


def create_backup(destination_path=None, *, prefix="backup"):
    destination = Path(
        destination_path or default_backup_path(prefix)
    )

    if destination.suffix.lower() != ".zip":
        destination = destination.with_suffix(".zip")

    destination.parent.mkdir(parents=True, exist_ok=True)

    database_path = _database_path()
    app_data_dir = _app_data_dir()

    manifest = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "database": DATABASE_NAME,
        "assets_prefix": ASSETS_PREFIX,
    }

    with tempfile.TemporaryDirectory(prefix="ccm_backup_") as temp_dir:
        snapshot_path = Path(temp_dir) / DATABASE_NAME
        _write_database_snapshot(snapshot_path)

        with zipfile.ZipFile(
            destination,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            archive.writestr(
                MANIFEST_NAME,
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                ).encode("utf-8"),
            )
            archive.write(
                snapshot_path,
                DATABASE_NAME,
            )

            if app_data_dir.exists():
                for path in app_data_dir.rglob("*"):
                    if not path.is_file():
                        continue

                    if _is_database_file(path, database_path):
                        continue

                    relative = path.relative_to(app_data_dir)

                    archive.write(
                        path,
                        (
                            Path(ASSETS_PREFIX)
                            / relative
                        ).as_posix(),
                    )

    return {
        "path": str(destination),
        "created_at": manifest["created_at"],
    }


def _validate_backup(archive: zipfile.ZipFile):
    names = set(archive.namelist())

    if MANIFEST_NAME not in names:
        raise ValueError(
            "このZIPはアプリのバックアップではありません。"
        )

    try:
        manifest = json.loads(
            archive.read(MANIFEST_NAME).decode("utf-8-sig")
        )
    except Exception as exc:
        raise ValueError(
            "バックアップ情報を読み取れません。"
        ) from exc

    if (
        not isinstance(manifest, dict)
        or manifest.get("format") != BACKUP_FORMAT
    ):
        raise ValueError(
            "対応していないバックアップ形式です。"
        )

    if manifest.get("version") != BACKUP_VERSION:
        raise ValueError(
            "対応していないバックアップバージョンです。"
        )

    if DATABASE_NAME not in names:
        raise ValueError(
            "バックアップ内にデータベースがありません。"
        )

    return manifest


def inspect_backup(backup_path):
    source = Path(backup_path)

    if not source.is_file():
        raise ValueError(
            "バックアップZIPが見つかりません。"
        )

    with zipfile.ZipFile(source, "r") as archive:
        manifest = _validate_backup(archive)

        asset_count = sum(
            1
            for name in archive.namelist()
            if name.startswith(ASSETS_PREFIX + "/")
            and not name.endswith("/")
        )

    return {
        "created_at": manifest.get("created_at", ""),
        "asset_count": asset_count,
    }


def _safe_extract_file(
    archive: zipfile.ZipFile,
    member_name: str,
    destination_root: Path,
) -> Path:
    member = Path(member_name)

    if member.is_absolute() or ".." in member.parts:
        raise ValueError(
            "バックアップ内に不正なパスがあります。"
        )

    destination = (destination_root / member).resolve()
    root = destination_root.resolve()

    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "バックアップ内に不正なパスがあります。"
        ) from exc

    destination.parent.mkdir(parents=True, exist_ok=True)

    with archive.open(member_name, "r") as src:
        with destination.open("wb") as dst:
            shutil.copyfileobj(src, dst)

    return destination


def _clear_current_assets(
    app_data_dir: Path,
    database_path: Path,
) -> None:
    if not app_data_dir.exists():
        return

    for child in list(app_data_dir.iterdir()):
        if _is_database_file(child, database_path):
            continue

        if child.is_dir():
            shutil.rmtree(child)
        elif child.is_file():
            child.unlink()


def _restore_assets(
    extracted_assets: Path,
    app_data_dir: Path,
) -> None:
    if not extracted_assets.exists():
        return

    for source in extracted_assets.rglob("*"):
        relative = source.relative_to(extracted_assets)
        target = app_data_dir / relative

        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _restore_database(snapshot_path: Path) -> None:
    source = sqlite3.connect(snapshot_path)

    try:
        with get_connection() as destination:
            source.backup(destination)
            destination.commit()
    finally:
        source.close()


def restore_backup(backup_path):
    source_path = Path(backup_path)

    if not source_path.is_file():
        raise ValueError(
            "バックアップZIPが見つかりません。"
        )

    # 復元直前の現在状態を必ず退避してから上書きする。
    safety_path = default_backup_path("pre_restore")
    create_backup(
        safety_path,
        prefix="pre_restore",
    )

    database_path = _database_path()
    app_data_dir = _app_data_dir()
    app_data_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ccm_restore_") as temp_dir:
        temp_root = Path(temp_dir)

        with zipfile.ZipFile(source_path, "r") as archive:
            manifest = _validate_backup(archive)

            snapshot_path = _safe_extract_file(
                archive,
                DATABASE_NAME,
                temp_root,
            )

            for member_name in archive.namelist():
                if not member_name.startswith(
                    ASSETS_PREFIX + "/"
                ):
                    continue

                if member_name.endswith("/"):
                    continue

                _safe_extract_file(
                    archive,
                    member_name,
                    temp_root,
                )

        _restore_database(snapshot_path)
        _clear_current_assets(
            app_data_dir,
            database_path,
        )
        _restore_assets(
            temp_root / ASSETS_PREFIX,
            app_data_dir,
        )

    return {
        "restored_from": str(source_path),
        "safety_backup": str(safety_path),
        "created_at": manifest.get("created_at", ""),
    }
