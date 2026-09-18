from __future__ import annotations

# DUAL_EXE_BUILD_SUPPORT_V1

import argparse
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "main.py"

APP_NAME = "CCFOLIAManager"
DISPLAY_NAME = "CCFOLIA Manager"
AUTHOR = "L4zz"

BUILD_ROOT = ROOT / "release_build"
PYI_WORK = BUILD_ROOT / "pyinstaller_work"
PYI_DIST = BUILD_ROOT / "pyinstaller_dist"
OUTPUT_ROOT = ROOT / "releases"

TEXT_RESOURCE_SUFFIXES = {
    ".qss",
    ".css",
    ".html",
    ".json",
    ".txt",
    ".md",
    ".svg",
    ".xml",
    ".toml",
    ".yaml",
    ".yml",
}

EXTENSION_EXCLUDE_PARTS = (
    ".pre_",
    ".broken_",
    ".bak",
    ".backup",
    ".old",
)

PUBLIC_FORBIDDEN_TOP_LEVEL = {
    "app_data",
    "backups",
    "exports",
    ".git",
    ".venv",
    "__pycache__",
}


def require_project_root() -> None:
    required = [
        MAIN,
        ROOT / "app",
        ROOT / "browser_extension" / "manifest.json",
    ]

    missing = [
        str(path)
        for path in required
        if not path.exists()
    ]

    if missing:
        raise SystemExit(
            "D:\\CCFOLIA_Manager の現在のプロジェクトで実行してください。\n"
            "不足:\n  - "
            + "\n  - ".join(missing)
        )


def manager_is_running() -> bool:
    try:
        with socket.create_connection(
            ("127.0.0.1", 17431),
            timeout=0.25,
        ):
            return True
    except OSError:
        return False


def require_manager_stopped() -> None:
    if manager_is_running():
        raise SystemExit(
            "CCFOLIA Manager が起動中です。\n"
            "DBとデータを安全に固めるため、終了してから実行してください。"
        )


def require_pyinstaller() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import PyInstaller; print(PyInstaller.__version__)",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise SystemExit(
            "PyInstaller が現在のvenvにありません。\n\n"
            "先に次を実行してください:\n"
            "  python -m pip install pyinstaller"
        )


def safe_rmtree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def tree_manifest(root: Path) -> list[dict]:
    rows: list[dict] = []

    for path in sorted(
        (
            item
            for item in root.rglob("*")
            if item.is_file()
        ),
        key=lambda p: p.as_posix().lower(),
    ):
        rows.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )

    return rows


def write_manifest(
    package_root: Path,
    *,
    profile: str,
    version: str | None = None,
) -> None:
    manifest_path = (
        package_root
        / "BUILD_MANIFEST.json"
    )

    manifest = {
        "app": DISPLAY_NAME,
        "profile": profile,
        "version": version,
        "generated_at": datetime.now().astimezone().isoformat(),
        "python": sys.version,
        "files": tree_manifest(package_root),
    }

    # Avoid manifest hashing itself.
    manifest["files"] = [
        row
        for row in manifest["files"]
        if row["path"] != "BUILD_MANIFEST.json"
    ]

    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def non_python_app_resources() -> list[tuple[Path, str]]:
    resources: list[tuple[Path, str]] = []
    app_root = ROOT / "app"

    for path in app_root.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() in {
            ".py",
            ".pyc",
            ".pyo",
        }:
            continue

        if "__pycache__" in path.parts:
            continue

        relative_parent = (
            path.relative_to(ROOT).parent
        )

        resources.append(
            (
                path,
                str(relative_parent),
            )
        )

    # Optional root-level resources.
    for directory_name in (
        "resources",
        "assets",
    ):
        directory = ROOT / directory_name

        if not directory.is_dir():
            continue

        for path in directory.rglob("*"):
            if not path.is_file():
                continue

            resources.append(
                (
                    path,
                    str(
                        path.relative_to(ROOT).parent
                    ),
                )
            )

    return resources


def discover_icon() -> Path | None:
    candidates = [
        ROOT / "app.ico",
        ROOT / "icon.ico",
        ROOT / "assets" / "app.ico",
        ROOT / "assets" / "icon.ico",
        ROOT / "resources" / "app.ico",
        ROOT / "resources" / "icon.ico",
    ]

    for path in candidates:
        if path.is_file():
            return path

    return None


def build_executable() -> Path:
    require_project_root()
    require_manager_stopped()
    require_pyinstaller()

    BUILD_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )
    PYI_WORK.mkdir(
        parents=True,
        exist_ok=True,
    )
    PYI_DIST.mkdir(
        parents=True,
        exist_ok=True,
    )

    dist_target = (
        PYI_DIST / APP_NAME
    )

    safe_rmtree(
        dist_target
    )

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        APP_NAME,
        "--distpath",
        str(PYI_DIST),
        "--workpath",
        str(PYI_WORK),
        "--specpath",
        str(BUILD_ROOT),
        "--paths",
        str(ROOT),
    ]

    for source, destination in (
        non_python_app_resources()
    ):
        command.extend(
            [
                "--add-data",
                f"{source}{os.pathsep}{destination}",
            ]
        )

    icon = discover_icon()

    if icon is not None:
        command.extend(
            [
                "--icon",
                str(icon),
            ]
        )

    command.append(
        str(MAIN)
    )

    print("PyInstaller build:")
    print(
        "  "
        + " ".join(
            f'"{part}"'
            if " " in part
            else part
            for part in command
        )
    )
    print()

    result = subprocess.run(
        command,
        cwd=ROOT,
    )

    if result.returncode != 0:
        raise SystemExit(
            "PyInstaller build に失敗しました。"
        )

    exe = (
        dist_target
        / f"{APP_NAME}.exe"
    )

    if not exe.is_file():
        raise SystemExit(
            "EXEが生成されませんでした:\n"
            f"  {exe}"
        )

    return dist_target


def should_copy_extension_file(
    path: Path,
) -> bool:
    relative = path.relative_to(
        ROOT / "browser_extension"
    )

    if "__pycache__" in relative.parts:
        return False

    name = path.name.lower()

    if any(
        marker in name
        for marker in EXTENSION_EXCLUDE_PARTS
    ):
        return False

    if name.endswith(
        (
            ".log",
            ".tmp",
        )
    ):
        return False

    return True


def copy_extension(
    destination_root: Path,
) -> None:
    source_root = (
        ROOT / "browser_extension"
    )
    target_root = (
        destination_root
        / "browser_extension"
    )

    safe_rmtree(
        target_root
    )

    for source in source_root.rglob("*"):
        if not source.is_file():
            continue

        if not should_copy_extension_file(
            source
        ):
            continue

        relative = source.relative_to(
            source_root
        )
        target = (
            target_root / relative
        )
        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        shutil.copy2(
            source,
            target,
        )


def sqlite_snapshot(
    source: Path,
    destination: Path,
) -> None:
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    src = sqlite3.connect(
        source
    )
    dst = sqlite3.connect(
        destination
    )

    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def copy_personal_app_data(
    destination_root: Path,
) -> None:
    source_root = (
        ROOT / "app_data"
    )
    target_root = (
        destination_root
        / "app_data"
    )

    if not source_root.is_dir():
        return

    safe_rmtree(
        target_root
    )

    database_source = (
        source_root
        / "database.sqlite3"
    )

    def ignore(
        directory: str,
        names: list[str],
    ):
        ignored: set[str] = set()

        for name in names:
            lower = name.lower()

            if (
                lower.endswith(
                    (
                        "-wal",
                        "-shm",
                        ".tmp",
                    )
                )
                or name == "__pycache__"
            ):
                ignored.add(name)

        if (
            Path(directory).resolve()
            == source_root.resolve()
            and "database.sqlite3" in names
        ):
            ignored.add(
                "database.sqlite3"
            )

        return ignored

    shutil.copytree(
        source_root,
        target_root,
        ignore=ignore,
    )

    if database_source.is_file():
        sqlite_snapshot(
            database_source,
            target_root
            / "database.sqlite3",
        )


def copy_optional_personal_exports(
    destination_root: Path,
) -> None:
    source = ROOT / "exports"

    if not source.is_dir():
        return

    target = (
        destination_root
        / "exports"
    )

    safe_rmtree(target)

    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(
            "*.tmp",
            "__pycache__",
        ),
    )


def copy_public_docs(
    destination_root: Path,
) -> None:
    for filename in (
        "README.md",
        "TERMS_OF_USE.md",
        "SECURITY.md",
        "CHANGELOG.md",
        "USAGE.md",
        "LICENSE",
        "LICENSE.txt",
        "NOTICE",
        "NOTICE.txt",
    ):
        source = ROOT / filename

        if source.is_file():
            shutil.copy2(
                source,
                destination_root
                / filename,
            )


def write_install_guide(
    destination_root: Path,
    *,
    profile: str,
) -> None:
    if profile == "public":
        body = """CCFOLIA Manager

1. CCFOLIAManager.exe を起動します。
2. Chromium系ブラウザで拡張機能管理画面を開きます。
3. デベロッパーモードを有効にします。
4. 「パッケージ化されていない拡張機能を読み込む」から
   browser_extension フォルダを指定します。
5. CCFOLIAのルームを再読み込みします。

初回起動時に app_data / backups / exports が自動作成されます。

注意:
- CCFOLIAの非公開内部仕様に依存する機能は、
  CCFOLIA側の更新で動かなくなる可能性があります。
- Firebase認証トークンをファイルやSQLiteへ保存する仕様ではありません。
"""
    else:
        body = """CCFOLIA Manager - Personal Snapshot

このフォルダにはビルド時点の個人用 app_data が含まれます。
第三者へ配布しないでください。

browser_extension は同梱されています。
CCFOLIAManager.exe を起動し、必要に応じてブラウザ拡張を
このフォルダの browser_extension から再読み込みしてください。
"""

    (
        destination_root
        / "INSTALL.txt"
    ).write_text(
        body,
        encoding="utf-8",
    )


def validate_public_package(
    package_root: Path,
) -> None:
    for forbidden in PUBLIC_FORBIDDEN_TOP_LEVEL:
        if (
            package_root
            / forbidden
        ).exists():
            raise RuntimeError(
                "配布版に含めてはいけない"
                f"ディレクトリがあります: {forbidden}"
            )

    extension_root = (
        package_root
        / "browser_extension"
    )

    if not (
        extension_root
        / "manifest.json"
    ).is_file():
        raise RuntimeError(
            "配布版のbrowser_extensionに"
            "manifest.jsonがありません。"
        )

    bad_extension_files = []

    for path in extension_root.rglob("*"):
        if not path.is_file():
            continue

        lower = path.name.lower()

        if any(
            marker in lower
            for marker in EXTENSION_EXCLUDE_PARTS
        ):
            bad_extension_files.append(
                path.relative_to(
                    package_root
                ).as_posix()
            )

    if bad_extension_files:
        raise RuntimeError(
            "配布版に古い拡張機能バックアップが"
            "混入しています:\n  - "
            + "\n  - ".join(
                bad_extension_files
            )
        )


def make_zip(
    source_directory: Path,
    zip_path: Path,
) -> None:
    zip_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if zip_path.exists():
        zip_path.unlink()

    print(
        f"ZIP作成: {zip_path.name}"
    )

    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        for path in sorted(
            source_directory.rglob("*"),
            key=lambda p: p.as_posix().lower(),
        ):
            if not path.is_file():
                continue

            archive.write(
                path,
                (
                    Path(
                        source_directory.name
                    )
                    / path.relative_to(
                        source_directory
                    )
                ).as_posix(),
            )


def stage_base(
    *,
    folder_name: str,
) -> Path:
    built = build_executable()

    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    staging = (
        OUTPUT_ROOT
        / folder_name
    )

    safe_rmtree(
        staging
    )

    shutil.copytree(
        built,
        staging,
    )

    copy_extension(
        staging
    )

    return staging


def build_personal(
    *,
    include_exports: bool,
    make_zip_file: bool,
) -> Path:
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    folder_name = (
        f"CCFOLIAManager_PERSONAL_{timestamp}"
    )

    staging = stage_base(
        folder_name=folder_name
    )

    copy_personal_app_data(
        staging
    )

    if include_exports:
        copy_optional_personal_exports(
            staging
        )

    write_install_guide(
        staging,
        profile="personal",
    )

    write_manifest(
        staging,
        profile="personal",
    )

    if make_zip_file:
        make_zip(
            staging,
            OUTPUT_ROOT
            / f"{folder_name}.zip",
        )

    return staging


def validate_version(
    version: str,
) -> str:
    value = str(version or "").strip()

    parts = value.split(".")

    if (
        len(parts) != 3
        or not all(
            part.isdigit()
            for part in parts
        )
    ):
        raise SystemExit(
            "--version は X.Y.Z 形式で"
            "指定してください。例: 1.1.0"
        )

    return value


def build_public(
    *,
    version: str,
) -> tuple[Path, Path]:
    version = validate_version(
        version
    )

    folder_name = (
        f"CCFOLIAManager_v{version}_Windows_x64_by_{AUTHOR}"
    )

    staging = stage_base(
        folder_name=folder_name
    )

    copy_public_docs(
        staging
    )

    write_install_guide(
        staging,
        profile="public",
    )

    validate_public_package(
        staging
    )

    write_manifest(
        staging,
        profile="public",
        version=version,
    )

    # Check again after manifest creation.
    validate_public_package(
        staging
    )

    zip_path = (
        OUTPUT_ROOT
        / f"{folder_name}.zip"
    )

    make_zip(
        staging,
        zip_path,
    )

    return staging, zip_path

# PERSONAL_BUILD_OUTPUT_DIR_V2
def stage_base_to_directory(
    destination: str | Path,
) -> Path:
    built = build_executable()

    target = Path(destination).expanduser()

    if not target.is_absolute():
        target = (ROOT / target).resolve()
    else:
        target = target.resolve()

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_rmtree(target)

    shutil.copytree(
        built,
        target,
    )

    copy_extension(target)

    return target


def build_personal(
    *,
    include_exports: bool,
    make_zip_file: bool,
    output_directory: str | None = None,
) -> Path:
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    if output_directory:
        staging = stage_base_to_directory(
            output_directory,
        )
    else:
        folder_name = (
            f"CCFOLIAManager_PERSONAL_{timestamp}"
        )

        staging = stage_base(
            folder_name=folder_name
        )

    copy_personal_app_data(
        staging
    )

    if include_exports:
        copy_optional_personal_exports(
            staging
        )

    write_install_guide(
        staging,
        profile="personal",
    )

    write_manifest(
        staging,
        profile="personal",
    )

    if make_zip_file:
        make_zip(
            staging,
            staging.with_suffix(".zip"),
        )

    return staging

# PUBLIC_DOCS_BUNDLE_V1
# Ensure current public documentation is included in the distribution
# before regenerating the manifest and ZIP.

_build_public_without_public_docs_v1 = build_public


def build_public(*args, **kwargs):
    import inspect as _docs_inspect
    import json as _docs_json
    import shutil as _docs_shutil
    from pathlib import Path as _DocsPath

    result = _build_public_without_public_docs_v1(
        *args,
        **kwargs,
    )

    if isinstance(result, tuple):
        staging_value = result[0]
    else:
        staging_value = result

    staging = _DocsPath(staging_value)

    public_docs = (
        "README.md",
        "USAGE.md",
        "CHANGELOG.md",
        "SECURITY.md",
        "TERMS_OF_USE.md",
    )

    missing = [
        name
        for name in public_docs
        if not (ROOT / name).is_file()
    ]

    if missing:
        raise RuntimeError(
            "公開用ドキュメントが不足しています: "
            + ", ".join(missing)
        )

    for name in public_docs:
        _docs_shutil.copy2(
            ROOT / name,
            staging / name,
        )

    manifest_path = staging / "BUILD_MANIFEST.json"

    previous_manifest = {}
    if manifest_path.is_file():
        try:
            previous_manifest = _docs_json.loads(
                manifest_path.read_text(
                    encoding="utf-8-sig"
                )
            )
        except Exception:
            previous_manifest = {}

        manifest_path.unlink()

    manifest_signature = _docs_inspect.signature(
        write_manifest
    )

    manifest_kwargs = {}

    if "profile" in manifest_signature.parameters:
        manifest_kwargs["profile"] = "public"

    if "version" in manifest_signature.parameters:
        version = kwargs.get("version")

        if version is None:
            version = previous_manifest.get(
                "version"
            )

        if version is not None:
            manifest_kwargs["version"] = version

    write_manifest(
        staging,
        **manifest_kwargs,
    )

    zip_path = staging.with_suffix(".zip")

    if zip_path.exists():
        zip_path.unlink()

    make_zip(
        staging,
        zip_path,
    )

    return result
