from __future__ import annotations

import sys
from pathlib import Path


def _runtime_root() -> Path:
    """
    Writable application root.

    Source run:
        project directory

    PyInstaller build:
        directory containing CCFOLIACharacterManager.exe
    """
    if getattr(
        sys,
        "frozen",
        False,
    ):
        return Path(
            sys.executable
        ).resolve().parent

    return (
        Path(__file__)
        .resolve()
        .parent
        .parent
    )


def _resource_root() -> Path:
    """
    Read-only bundled-resource root.

    In PyInstaller this points at _MEIPASS / _internal.
    """
    if getattr(
        sys,
        "frozen",
        False,
    ):
        return Path(
            getattr(
                sys,
                "_MEIPASS",
                Path(sys.executable).resolve().parent,
            )
        )

    return (
        Path(__file__)
        .resolve()
        .parent
        .parent
    )


PROJECT_ROOT = _runtime_root()
RESOURCE_ROOT = _resource_root()

APP_DATA_DIR = PROJECT_ROOT / "app_data"
DATABASE_PATH = APP_DATA_DIR / "database.sqlite3"
IMAGES_DIR = APP_DATA_DIR / "images"
# IMAGES_MODULE_PATH_V1
IMAGE_ASSETS_DIR = APP_DATA_DIR / "image_assets"
# BGM_MODULE_PATH_V1
BGM_ASSETS_DIR = APP_DATA_DIR / "bgm_assets"
COCOFOLIA_DIR = APP_DATA_DIR / "cocofolia"

EXPORTS_DIR = PROJECT_ROOT / "exports"
BACKUPS_DIR = PROJECT_ROOT / "backups"

STYLE_PATH = (
    RESOURCE_ROOT
    / "app"
    / "ui"
    / "styles.qss"
)

BROWSER_EXTENSION_DIR = (
    PROJECT_ROOT
    / "browser_extension"
)


def ensure_app_directories() -> None:
    for directory in (
        APP_DATA_DIR,
        IMAGES_DIR,
        IMAGE_ASSETS_DIR,
        BGM_ASSETS_DIR,
        COCOFOLIA_DIR,
        EXPORTS_DIR,
        BACKUPS_DIR,
    ):
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )
