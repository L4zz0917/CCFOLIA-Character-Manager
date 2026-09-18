from __future__ import annotations

import time
from uuid import uuid4

from app.paths import EXPORTS_DIR
from app.services.bridge_service import (
    get_bridge_server,
)
from app.services.cocofolia_service import (
    export_characters_to_zip,
)


BRIDGE_EXPORT_DIR = (
    EXPORTS_DIR
    / "_bridge"
)


def _cleanup_old_bridge_files():
    BRIDGE_EXPORT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    cutoff = (
        time.time()
        - 24 * 60 * 60
    )

    for path in BRIDGE_EXPORT_DIR.glob(
        "*.zip"
    ):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError:
            pass


def queue_characters_for_cocofolia(
    character_ids,
):
    ids = [
        str(value)
        for value in character_ids
        if str(value).strip()
    ]

    if not ids:
        raise ValueError(
            "送信するキャラクターが選択されていません。"
        )

    _cleanup_old_bridge_files()

    stamp = time.strftime(
        "%Y%m%d_%H%M%S"
    )

    unique = uuid4().hex[:8]

    destination = (
        BRIDGE_EXPORT_DIR
        / f"ccm_send_{stamp}_{unique}.zip"
    )

    result = export_characters_to_zip(
        ids,
        destination,
    )

    bridge = get_bridge_server()

    request_id = bridge.stage_file(
        result["path"],
        filename="ccm_characters.zip",
    )

    return {
        "request_id": request_id,
        "path": result["path"],
        "characters": result[
            "characters"
        ],
        "bridge_port": 17431,
    }


def cocofolia_send_status(
    request_id,
):
    bridge = get_bridge_server()
    return bridge.status_info(
        request_id
    )
