from __future__ import annotations

import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4


BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 17431

CLAIM_SECONDS = 45
PENDING_SECONDS = 180
RESULT_SECONDS = 300
MAX_QUEUE = 12


class CCFOLIABridgeServer:
    def __init__(self):
        self._lock = threading.RLock()
        self._server = None
        self._thread = None

        self._requests = {}
        self._order = deque()
        self._results = {}

    def start(self):
        with self._lock:
            if self._server is not None:
                return

            bridge = self

            class Handler(BaseHTTPRequestHandler):
                server_version = "CCMBridge/1.2"

                def log_message(self, format, *args):
                    return

                def _json(self, status, payload):
                    body = json.dumps(
                        payload,
                        ensure_ascii=False,
                    ).encode("utf-8")

                    self.send_response(status)
                    self.send_header(
                        "Content-Type",
                        "application/json; charset=utf-8",
                    )
                    self.send_header(
                        "Content-Length",
                        str(len(body)),
                    )
                    self.send_header(
                        "Cache-Control",
                        "no-store",
                    )
                    self.send_header(
                        "X-Content-Type-Options",
                        "nosniff",
                    )
                    self.send_header(
                        "Referrer-Policy",
                        "no-referrer",
                    )
                    self.end_headers()

                    # BRIDGE_CLIENT_DISCONNECT_GUARD_V1
                    try:
                        self.wfile.write(body)
                    except (
                        BrokenPipeError,
                        ConnectionResetError,
                        ConnectionAbortedError,
                    ):
                        return
                    except OSError as exc:
                        if getattr(
                            exc,
                            "winerror",
                            None,
                        ) in {
                            10053,
                            10054,
                            10058,
                        }:
                            return

                        raise


                def _api_allowed(self):
                    # PHASE32_BRIDGE_GUARD
                    if (
                        self.headers.get(
                            "X-CCM-Client",
                            "",
                        )
                        != "browser-extension"
                    ):
                        return False

                    host = (
                        self.headers.get(
                            "Host",
                            "",
                        )
                        .strip()
                        .lower()
                    )

                    allowed_hosts = {
                        f"{BRIDGE_HOST}:{BRIDGE_PORT}",
                        BRIDGE_HOST,
                        f"localhost:{BRIDGE_PORT}",
                        "localhost",
                    }

                    if host not in allowed_hosts:
                        return False

                    origin = (
                        self.headers.get(
                            "Origin",
                            "",
                        )
                        .strip()
                        .lower()
                    )

                    if (
                        origin.startswith("http://")
                        or origin.startswith("https://")
                    ):
                        return False

                    return True


                # BRIDGE_VARIABLE_JSON_LIMIT_V1
                def _read_json_body(
                    self,
                    max_json_bytes=None,
                ):
                    try:
                        length = int(
                            self.headers.get(
                                "Content-Length",
                                "0",
                            )
                            or "0"
                        )
                    except ValueError:
                        length = 0

                    if length <= 0:
                        return {}

                    if max_json_bytes is None:
                        max_json_bytes = (
                            24
                            * 1024
                            * 1024
                        )
                    else:
                        try:
                            max_json_bytes = int(
                                max_json_bytes
                            )
                        except (
                            TypeError,
                            ValueError,
                        ):
                            raise ValueError(
                                "送信上限の指定が不正です。"
                            )

                        max_json_bytes = max(
                            1,
                            min(
                                max_json_bytes,
                                128
                                * 1024
                                * 1024,
                            ),
                        )

                    if length > max_json_bytes:
                        raise ValueError(
                            "送信データが大きすぎます。"
                        )

                    raw = self.rfile.read(
                        length
                    )

                    try:
                        data = json.loads(
                            raw.decode(
                                "utf-8"
                            )
                        )
                    except Exception as exc:
                        raise ValueError(
                            "JSONが不正です。"
                        ) from exc

                    if not isinstance(
                        data,
                        dict,
                    ):
                        raise ValueError(
                            "JSONオブジェクトが必要です。"
                        )

                    return data

                def do_GET(self):
                    path = urlparse(self.path).path

                    if path == "/health":
                        self._json(
                            200,
                            {
                                "ok": True,
                                "service": "ccm-cocofolia-bridge",
                                "version": "1.2",
                            },
                        )
                        return

                    if (
                        path.startswith("/api/character/")
                        and path.endswith("/editor")
                    ):
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        parts = path.strip("/").split("/")

                        if len(parts) != 4:
                            self._json(
                                404,
                                {
                                    "ok": False,
                                    "error": "unknown_endpoint",
                                },
                            )
                            return

                        character_id = parts[2]

                        try:
                            from app.services.browser_panel_service import (
                                get_character_editor_bundle,
                            )
                            editor = get_character_editor_bundle(
                                character_id
                            )
                        except Exception as exc:
                            self._json(
                                404,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "editor": editor,
                            },
                        )
                        return

                    if (
                        path.startswith("/api/character/")
                        and path.endswith("/icon")
                    ):
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        parts = path.strip("/").split("/")

                        if len(parts) != 4:
                            self._json(
                                404,
                                {
                                    "ok": False,
                                    "error": "unknown_endpoint",
                                },
                            )
                            return

                        character_id = parts[2]

                        try:
                            from app.services.browser_panel_service import (
                                get_character_icon_data_url,
                            )

                            data_url = get_character_icon_data_url(
                                character_id
                            )
                        except Exception as exc:
                            self._json(
                                404,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "data_url": data_url,
                            },
                        )
                        return

                    if path.startswith("/api/character/"):
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        character_id = path.split(
                            "/",
                            3,
                        )[-1]

                        try:
                            from app.services.browser_panel_service import (
                                get_character_panel_detail,
                            )

                            detail = get_character_panel_detail(
                                character_id
                            )
                        except Exception as exc:
                            self._json(
                                404,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "character": detail,
                            },
                        )
                        return


                    # BGM_BROWSER_PANEL_API_V1
                    if path == "/api/bgm-manager/assets":
                        if not self._api_allowed():
                            self._json(403, {"ok": False, "error": "forbidden"})
                            return

                        parsed = urlparse(self.path)
                        query = parse_qs(parsed.query)

                        search_text = query.get("search", [""])[0]
                        search_mode = query.get("mode", ["keyword"])[0]
                        group_id = query.get("group", [""])[0]
                        media_kind = query.get("kind", [""])[0]
                        only_untagged = (
                            query.get("tagless", ["0"])[0] == "1"
                        )

                        try:
                            page = int(query.get("page", ["1"])[0])
                            page_size = int(
                                query.get("page_size", ["60"])[0]
                            )

                            from app.services.bgm_browser_service import (
                                list_browser_bgm_assets,
                            )

                            result = list_browser_bgm_assets(
                                search_text=search_text,
                                search_mode=search_mode,
                                group_id=(
                                    None
                                    if group_id in ("", "__ungrouped__")
                                    else group_id
                                ),
                                only_ungrouped=(
                                    group_id == "__ungrouped__"
                                ),
                                only_untagged=only_untagged,
                                media_kind=(media_kind or None),
                                page=page,
                                page_size=page_size,
                            )
                        except Exception as exc:
                            self._json(
                                400,
                                {"ok": False, "error": str(exc)},
                            )
                            return

                        self._json(200, {"ok": True, **result})
                        return

                    if path == "/api/bgm-manager/tags":
                        if not self._api_allowed():
                            self._json(403, {"ok": False, "error": "forbidden"})
                            return

                        try:
                            from app.services.bgm_browser_service import (
                                browser_bgm_tags,
                            )
                            tags = browser_bgm_tags()
                        except Exception as exc:
                            self._json(400, {"ok": False, "error": str(exc)})
                            return

                        self._json(200, {"ok": True, "tags": tags})
                        return

                    if path == "/api/bgm-manager/groups":
                        if not self._api_allowed():
                            self._json(403, {"ok": False, "error": "forbidden"})
                            return

                        try:
                            from app.services.bgm_browser_service import (
                                browser_bgm_groups,
                            )
                            groups = browser_bgm_groups()
                        except Exception as exc:
                            self._json(400, {"ok": False, "error": str(exc)})
                            return

                        self._json(200, {"ok": True, "groups": groups})
                        return

                    if path.startswith("/api/bgm-manager/upload-source/"):
                        if not self._api_allowed():
                            self._json(403, {"ok": False, "error": "forbidden"})
                            return

                        bgm_id = path.rsplit("/", 1)[-1]

                        try:
                            from app.services.bgm_browser_service import (
                                get_browser_bgm_upload_source,
                            )
                            source = get_browser_bgm_upload_source(bgm_id)
                        except Exception as exc:
                            self._json(400, {"ok": False, "error": str(exc)})
                            return

                        self._json(200, {"ok": True, "source": source})
                        return

                    # IM4_IMAGES_BROWSER_API
                    # IMAGES_BROWSER_PAGINATION_BRIDGE
                    if path == "/api/image-manager/assets":
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        parsed = urlparse(self.path)
                        query = parse_qs(parsed.query)

                        search_text = query.get(
                            "search",
                            [""],
                        )[0]
                        search_mode = query.get(
                            "mode",
                            ["keyword"],
                        )[0]
                        group_id = query.get(
                            "group",
                            [""],
                        )[0]
                        only_untagged = (
                            query.get(
                                "tagless",
                                ["0"],
                            )[0]
                            == "1"
                        )

                        try:
                            limit = max(
                                1,
                                min(
                                    int(
                                        query.get(
                                            "limit",
                                            ["120"],
                                        )[0]
                                    ),
                                    240,
                                ),
                            )
                            offset = max(
                                0,
                                int(
                                    query.get(
                                        "offset",
                                        ["0"],
                                    )[0]
                                ),
                            )
                        except (TypeError, ValueError):
                            self._json(
                                400,
                                {
                                    "ok": False,
                                    "error": "invalid pagination",
                                },
                            )
                            return

                        try:
                            from app.services.image_browser_service import (
                                list_browser_image_assets,
                            )

                            kwargs = {
                                "search_text": search_text,
                                "search_mode": search_mode,
                                "only_untagged": only_untagged,
                                "limit": limit,
                                "offset": offset,
                            }

                            if group_id == "__ungrouped__":
                                kwargs["only_ungrouped"] = True
                            else:
                                kwargs["group_id"] = (
                                    group_id
                                    or None
                                )

                            result = list_browser_image_assets(
                                **kwargs,
                            )
                        except Exception as exc:
                            self._json(
                                400,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "assets": result["assets"],
                                "total": result["total"],
                                "limit": result["limit"],
                                "offset": result["offset"],
                            },
                        )
                        return

                    if path == "/api/image-manager/tags":
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        try:
                            from app.services.image_browser_service import (
                                browser_image_tags,
                            )
                            tags = browser_image_tags()
                        except Exception as exc:
                            self._json(
                                400,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "tags": tags,
                            },
                        )
                        return

                    if path == "/api/image-manager/groups":
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        try:
                            from app.services.image_browser_service import (
                                browser_image_groups,
                            )
                            groups = browser_image_groups()
                        except Exception as exc:
                            self._json(
                                400,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "groups": groups,
                            },
                        )
                        return

                    # IM6_IMAGE_UPLOAD_API
                    if (
                        path.startswith(
                            "/api/image-manager/upload-source/"
                        )
                    ):
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        image_id = path.rsplit(
                            "/",
                            1,
                        )[-1]

                        try:
                            from app.services.image_browser_service import (
                                get_browser_image_upload_source,
                            )

                            source = get_browser_image_upload_source(
                                image_id
                            )
                        except Exception as exc:
                            self._json(
                                400,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "source": source,
                            },
                        )
                        return

                    if (
                        path.startswith(
                            "/api/image-manager/apply-info/"
                        )
                    ):
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        image_id = path.rsplit(
                            "/",
                            1,
                        )[-1]

                        try:
                            from app.services.image_browser_service import (
                                get_browser_image_apply_info,
                            )
                            apply_info = get_browser_image_apply_info(
                                image_id
                            )
                        except Exception as exc:
                            self._json(
                                400,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "image": apply_info,
                            },
                        )
                        return

                    if (
                        path.startswith(
                            "/api/image-manager/preview/"
                        )
                    ):
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        image_id = path.rsplit(
                            "/",
                            1,
                        )[-1]
                        parsed = urlparse(self.path)
                        query = parse_qs(parsed.query)
                        size = query.get(
                            "size",
                            ["thumb"],
                        )[0]

                        try:
                            from app.services.image_browser_service import (
                                get_browser_image_preview,
                            )
                            preview = get_browser_image_preview(
                                image_id,
                                size=size,
                            )
                        except Exception as exc:
                            self._json(
                                400,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "preview": preview,
                            },
                        )
                        return

                    if path == "/api/images":
                        if not self._api_allowed():
                            self._json(403, {"ok": False, "error": "forbidden"})
                            return

                        parsed = urlparse(self.path)
                        query = parse_qs(parsed.query)
                        character_id = query.get("character_id", [""])[0]
                        image_id = query.get("image_id", [""])[0]

                        try:
                            if image_id:
                                from app.services.browser_panel_service import (
                                    get_browser_character_image_data_url,
                                )
                                data_url = get_browser_character_image_data_url(
                                    character_id,
                                    image_id,
                                )
                                self._json(200, {"ok": True, "data_url": data_url})
                            else:
                                from app.services.browser_panel_service import (
                                    list_browser_character_images,
                                )
                                images = list_browser_character_images(character_id)
                                self._json(200, {"ok": True, "images": images})
                        except Exception as exc:
                            self._json(400, {"ok": False, "error": str(exc)})
                        return

                    if path == "/api/tags":
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        from app.services.browser_panel_service import (
                            browser_tags,
                        )

                        self._json(
                            200,
                            {
                                "ok": True,
                                "tags": browser_tags(),
                            },
                        )
                        return

                    if path == "/api/groups":
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        from app.services.character_service import (
                            list_groups,
                        )

                        groups = [
                            {
                                "id": str(row["id"]),
                                "name": str(row["name"]),
                                "parent_group_id": (
                                    None
                                    if row["parent_group_id"] is None
                                    else str(row["parent_group_id"])
                                ),
                                "sort_order": int(
                                    row["sort_order"]
                                    or 0
                                ),
                            }
                            for row in list_groups()
                        ]

                        self._json(
                            200,
                            {
                                "ok": True,
                                "groups": groups,
                            },
                        )
                        return

                    if path == "/api/characters":
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        parsed = urlparse(
                            self.path
                        )
                        query = parse_qs(
                            parsed.query
                        )

                        search_text = (
                            query.get(
                                "search",
                                [""],
                            )[0]
                        )
                        search_mode = (
                            query.get(
                                "mode",
                                ["keyword"],
                            )[0]
                        )
                        group_id = (
                            query.get(
                                "group",
                                [""],
                            )[0]
                        )

                        from app.services.character_service import (
                            list_characters,
                        )

                        if group_id == "__ungrouped__":
                            from app.services.character_service import (
                                list_ungrouped_characters,
                            )

                            rows = list_ungrouped_characters(
                                search_text=search_text,
                                search_mode=search_mode,
                            )
                        else:
                            rows = list_characters(
                                search_text=search_text,
                                search_mode=search_mode,
                                group_id=(
                                    group_id
                                    or None
                                ),
                            )

                        characters = []

                        for row in rows:
                            characters.append(
                                {
                                    "id": str(
                                        row["id"]
                                    ),
                                    "name": str(
                                        row["name"]
                                        or ""
                                    ),
                                    "player_name": str(
                                        row["player_name"]
                                        or ""
                                    ),
                                    "color": str(
                                        row["color"]
                                        or "#888888"
                                    ),
                                    "has_icon": bool(
                                        row["main_image"]
                                    ),
                                }
                            )

                        self._json(
                            200,
                            {
                                "ok": True,
                                "characters": characters,
                            },
                        )
                        return

                    if path == "/pending":
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        self._json(
                            200,
                            bridge._pending_info(),
                        )
                        return

                    if path.startswith("/status/"):
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        request_id = path.split("/", 2)[-1]

                        self._json(
                            200,
                            bridge.status_info(
                                request_id
                            ),
                        )
                        return

                    if path.startswith("/file/"):
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        request_id = path.split("/", 2)[-1]
                        file_info = bridge._get_file(
                            request_id
                        )

                        if file_info is None:
                            self._json(
                                404,
                                {
                                    "ok": False,
                                    "error": "not_found",
                                },
                            )
                            return

                        file_path, filename = file_info

                        try:
                            size = file_path.stat().st_size
                            source = file_path.open("rb")
                        except OSError:
                            bridge._fail(
                                request_id,
                                "file_missing",
                            )

                            self._json(
                                404,
                                {
                                    "ok": False,
                                    "error": "file_missing",
                                },
                            )
                            return

                        self.send_response(200)
                        self.send_header(
                            "Content-Type",
                            "application/zip",
                        )
                        self.send_header(
                            "Content-Disposition",
                            f'attachment; filename="{filename}"',
                        )
                        self.send_header(
                            "Content-Length",
                            str(size),
                        )
                        self.send_header(
                            "Cache-Control",
                            "no-store",
                        )
                        self.end_headers()

                        with source:
                            while True:
                                chunk = source.read(
                                    1024 * 1024
                                )

                                if not chunk:
                                    break

                                self.wfile.write(
                                    chunk
                                )

                        return

                    self._json(
                        404,
                        {
                            "ok": False,
                            "error": "unknown_endpoint",
                        },
                    )

                def do_POST(self):
                    path = urlparse(self.path).path

                    # IM7_IMAGE_SALVAGE_API
                    if path == "/api/image-manager/salvage":
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        try:
                            payload = self._read_json_body()
                            images = payload.get(
                                "images",
                                [],
                            )

                            from app.services.image_browser_service import (
                                salvage_browser_images,
                            )

                            result = salvage_browser_images(
                                images
                            )
                        except Exception as exc:
                            self._json(
                                400,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "result": result,
                            },
                        )
                        return

                    # IM6_IMAGE_UPLOAD_API
                    if path == "/api/image-manager/register":
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        try:
                            payload = self._read_json_body()

                            from app.services.image_browser_service import (
                                register_browser_image_ccfolia,
                            )

                            image = register_browser_image_ccfolia(
                                image_id=payload.get(
                                    "image_id",
                                    "",
                                ),
                                file_id=payload.get(
                                    "file_id",
                                    "",
                                ),
                                url=payload.get(
                                    "url",
                                    "",
                                ),
                                content_type=payload.get(
                                    "content_type",
                                    "",
                                ),
                                file_size=payload.get(
                                    "file_size",
                                ),
                            )
                        except Exception as exc:
                            self._json(
                                400,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "image": image,
                            },
                        )
                        return

                    # BGM_BROWSER_IMPORT_API_V1
                    # BGM_SALVAGE_API_V1
                    if path == "/api/bgm-manager/salvage":
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        try:
                            payload = self._read_json_body()

                            from app.services.bgm_browser_service import (
                                salvage_browser_bgm_items,
                            )

                            result = salvage_browser_bgm_items(
                                items=payload.get(
                                    "items",
                                    [],
                                ),
                                tab_labels=payload.get(
                                    "tab_labels",
                                    {},
                                ),
                            )
                        except Exception as exc:
                            self._json(
                                400,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "result": result,
                            },
                        )
                        return

                    if path == "/api/bgm-manager/register":
                        if not self._api_allowed():
                            self._json(403, {"ok": False, "error": "forbidden"})
                            return

                        try:
                            payload = self._read_json_body()
                            from app.services.bgm_browser_service import (
                                register_browser_bgm_ccfolia,
                            )
                            bgm = register_browser_bgm_ccfolia(
                                bgm_id=payload.get("bgm_id", ""),
                                media_id=payload.get("media_id", ""),
                                url=payload.get("url", ""),
                                directory=payload.get("directory", "bgm01"),
                                order=payload.get("order", 0),
                                updated_at=payload.get("updated_at"),
                            )
                        except Exception as exc:
                            self._json(400, {"ok": False, "error": str(exc)})
                            return

                        self._json(200, {"ok": True, "bgm": bgm})
                        return

                    if path == "/api/bgm-manager/update":
                        if not self._api_allowed():
                            self._json(403, {"ok": False, "error": "forbidden"})
                            return

                        try:
                            payload = self._read_json_body()
                            from app.services.bgm_browser_service import (
                                update_browser_bgm,
                            )
                            bgm = update_browser_bgm(
                                bgm_id=payload.get("bgm_id", ""),
                                display_name=payload.get("display_name", ""),
                                default_volume=payload.get("default_volume", 0.5),
                                default_loop=payload.get("default_loop", True),
                                media_kind=payload.get("media_kind", "bgm"),
                                tags=payload.get("tags", []),
                            )
                        except Exception as exc:
                            self._json(400, {"ok": False, "error": str(exc)})
                            return

                        self._json(200, {"ok": True, "bgm": bgm})
                        return

                    if path == "/api/bgm-manager/import":
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        try:
                            payload = self._read_json_body(
                                96
                                * 1024
                                * 1024
                            )

                            from app.services.bgm_browser_service import (
                                import_browser_bgm,
                            )

                            bgm = import_browser_bgm(
                                filename=payload.get(
                                    "filename",
                                    "",
                                ),
                                data_base64=payload.get(
                                    "data_base64",
                                    "",
                                ),
                                media_kind=payload.get(
                                    "media_kind",
                                    "bgm",
                                ),
                            )

                        except Exception as exc:
                            self._json(
                                400,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "bgm": bgm,
                            },
                        )
                        return

                    if path == "/api/image-manager/import":
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        try:
                            payload = self._read_json_body()

                            from app.services.image_browser_service import (
                                import_browser_image,
                            )

                            image = import_browser_image(
                                filename=payload.get(
                                    "filename",
                                    "",
                                ),
                                data_base64=payload.get(
                                    "data_base64",
                                    "",
                                ),
                            )
                        except Exception as exc:
                            self._json(
                                400,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "image": image,
                            },
                        )
                        return

                    # CHARACTER_SALVAGE_IMPORT_API_V1
                    if path == "/api/character-salvage/import":
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        try:
                            payload = self._read_json_body()

                            from app.services.character_salvage_service import (
                                import_room_characters,
                            )

                            # CHARACTER_SALVAGE_ROOM_TAG_BRIDGE_V1
                            result = import_room_characters(
                                room_id=payload.get(
                                    "room_id",
                                    "",
                                ),
                                room_name=payload.get(
                                    "room_name",
                                    "",
                                ),
                                characters=payload.get(
                                    "characters",
                                    [],
                                ),
                            )
                        except Exception as exc:
                            self._json(
                                400,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "result": result,
                            },
                        )
                        return

                    if path == "/api/images/upload":
                        if not self._api_allowed():
                            self._json(403, {"ok": False, "error": "forbidden"})
                            return
                        try:
                            payload = self._read_json_body()
                            from app.services.browser_panel_service import (
                                add_browser_character_image,
                            )
                            image = add_browser_character_image(
                                payload.get("character_id", ""),
                                payload.get("filename", ""),
                                payload.get("data_base64", ""),
                            )
                        except Exception as exc:
                            self._json(400, {"ok": False, "error": str(exc)})
                            return
                        self._json(200, {"ok": True, "image": image})
                        return

                    if path == "/api/images/reorder":
                        if not self._api_allowed():
                            self._json(403, {"ok": False, "error": "forbidden"})
                            return
                        try:
                            payload = self._read_json_body()
                            from app.services.browser_panel_service import (
                                reorder_browser_character_images,
                            )
                            reorder_browser_character_images(
                                payload.get("character_id", ""),
                                payload.get("image_ids", []),
                            )
                        except Exception as exc:
                            self._json(400, {"ok": False, "error": str(exc)})
                            return
                        self._json(200, {"ok": True})
                        return

                    if path == "/api/images/delete":
                        if not self._api_allowed():
                            self._json(403, {"ok": False, "error": "forbidden"})
                            return
                        try:
                            payload = self._read_json_body()
                            from app.services.browser_panel_service import (
                                delete_browser_character_image,
                            )
                            delete_browser_character_image(
                                payload.get("character_id", ""),
                                payload.get("image_id", ""),
                            )
                        except Exception as exc:
                            self._json(400, {"ok": False, "error": str(exc)})
                            return
                        self._json(200, {"ok": True})
                        return

                    if path == "/api/characters/create":
                        if not self._api_allowed():
                            self._json(403, {"ok": False, "error": "forbidden"})
                            return

                        try:
                            payload = self._read_json_body()
                            from app.services.browser_panel_service import (
                                create_browser_character,
                            )

                            character_id = create_browser_character(
                                payload.get("name", ""),
                                payload.get("template_id", "generic"),
                            )
                        except Exception as exc:
                            self._json(400, {"ok": False, "error": str(exc)})
                            return

                        self._json(200, {"ok": True, "character_id": str(character_id)})
                        return

                    if path == "/api/groups/create":
                        if not self._api_allowed():
                            self._json(403, {"ok": False, "error": "forbidden"})
                            return

                        try:
                            payload = self._read_json_body()
                            from app.services.browser_panel_service import (
                                create_browser_group,
                            )
                            group_id = create_browser_group(
                                payload.get("name", ""),
                                payload.get("parent_group_id"),
                            )
                        except Exception as exc:
                            self._json(400, {"ok": False, "error": str(exc)})
                            return

                        self._json(200, {"ok": True, "group_id": str(group_id)})
                        return

                    if path == "/api/groups/rename":
                        if not self._api_allowed():
                            self._json(403, {"ok": False, "error": "forbidden"})
                            return

                        try:
                            payload = self._read_json_body()
                            from app.services.browser_panel_service import (
                                rename_browser_group,
                            )
                            rename_browser_group(
                                payload.get("group_id", ""),
                                payload.get("name", ""),
                            )
                        except Exception as exc:
                            self._json(400, {"ok": False, "error": str(exc)})
                            return

                        self._json(200, {"ok": True})
                        return

                    if path == "/api/groups/delete":
                        if not self._api_allowed():
                            self._json(403, {"ok": False, "error": "forbidden"})
                            return

                        try:
                            payload = self._read_json_body()
                            from app.services.browser_panel_service import (
                                delete_browser_group,
                            )
                            delete_browser_group(
                                payload.get("group_id", "")
                            )
                        except Exception as exc:
                            self._json(400, {"ok": False, "error": str(exc)})
                            return

                        self._json(200, {"ok": True})
                        return

                    if path.startswith("/api/character/"):
                        if not self._api_allowed():
                            self._json(403, {"ok": False, "error": "forbidden"})
                            return

                        parts = path.strip("/").split("/")

                        if len(parts) < 4:
                            self._json(404, {"ok": False, "error": "unknown_endpoint"})
                            return

                        character_id = parts[2]
                        action = parts[3]

                        try:
                            payload = self._read_json_body()

                            if action == "editor":
                                from app.services.browser_panel_service import (
                                    save_character_editor_bundle,
                                )
                                editor = save_character_editor_bundle(
                                    character_id,
                                    payload,
                                )
                                result = {"editor": editor}
                            elif action == "quick-memo":
                                from app.services.browser_panel_service import set_quick_memo
                                set_quick_memo(
                                    character_id,
                                    payload.get("text", ""),
                                )
                                result = {}
                            elif action == "tags":
                                from app.services.browser_panel_service import add_browser_tags
                                added = add_browser_tags(
                                    character_id,
                                    payload.get("tag_names", []),
                                )
                                result = {"added": added}
                            elif action == "group":
                                from app.services.browser_panel_service import add_browser_group
                                added = add_browser_group(
                                    character_id,
                                    payload.get("group_id", ""),
                                )
                                result = {"added": added}
                            elif action == "duplicate":
                                from app.services.browser_panel_service import duplicate_browser_character
                                new_id = duplicate_browser_character(
                                    character_id
                                )
                                result = {"character_id": str(new_id)}
                            elif action == "trash":
                                from app.services.browser_panel_service import trash_browser_character
                                trash_browser_character(
                                    character_id
                                )
                                result = {}
                            else:
                                self._json(404, {"ok": False, "error": "unknown_endpoint"})
                                return
                        except Exception as exc:
                            self._json(400, {"ok": False, "error": str(exc)})
                            return

                        self._json(200, {"ok": True, **result})
                        return

                    if path == "/api/send":
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        try:
                            payload = self._read_json_body()
                            character_ids = payload.get(
                                "character_ids",
                                [],
                            )

                            if not isinstance(
                                character_ids,
                                list,
                            ):
                                raise ValueError(
                                    "character_ids は配列で指定してください。"
                                )

                            from app.services.cocofolia_send_service import (
                                queue_characters_for_cocofolia,
                            )

                            result = queue_characters_for_cocofolia(
                                character_ids
                            )
                        except Exception as exc:
                            self._json(
                                400,
                                {
                                    "ok": False,
                                    "error": str(exc),
                                },
                            )
                            return

                        self._json(
                            200,
                            {
                                "ok": True,
                                "request_id": result[
                                    "request_id"
                                ],
                                "characters": result[
                                    "characters"
                                ],
                            },
                        )
                        return

                    if path.startswith("/claim/"):
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        request_id = path.split("/", 2)[-1]
                        ok = bridge._claim(
                            request_id
                        )

                        self._json(
                            200 if ok else 409,
                            {
                                "ok": ok,
                            },
                        )
                        return

                    if path.startswith("/ack/"):
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        request_id = path.split("/", 2)[-1]
                        ok = bridge._ack(
                            request_id
                        )

                        self._json(
                            200 if ok else 404,
                            {
                                "ok": ok,
                            },
                        )
                        return

                    if path.startswith("/release/"):
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        request_id = path.split("/", 2)[-1]
                        ok = bridge._release(
                            request_id
                        )

                        self._json(
                            200 if ok else 404,
                            {
                                "ok": ok,
                            },
                        )
                        return

                    if path.startswith("/fail/"):
                        if not self._api_allowed():
                            self._json(
                                403,
                                {
                                    "ok": False,
                                    "error": "forbidden",
                                },
                            )
                            return

                        request_id = path.split("/", 2)[-1]
                        ok = bridge._fail(
                            request_id,
                            "extension_error",
                        )

                        self._json(
                            200 if ok else 404,
                            {
                                "ok": ok,
                            },
                        )
                        return

                    self._json(
                        404,
                        {
                            "ok": False,
                            "error": "unknown_endpoint",
                        },
                    )

            try:
                server = ThreadingHTTPServer(
                    (
                        BRIDGE_HOST,
                        BRIDGE_PORT,
                    ),
                    Handler,
                )
            except OSError as exc:
                raise RuntimeError(
                    "ココフォリア連携用のローカル通信を開始できません。"
                    f" ポート {BRIDGE_PORT} が使用中の可能性があります。"
                ) from exc

            server.daemon_threads = True

            thread = threading.Thread(
                target=server.serve_forever,
                name="CCM-CCFOLIA-Bridge",
                daemon=True,
            )

            self._server = server
            self._thread = thread
            thread.start()

    def stop(self):
        with self._lock:
            server = self._server
            thread = self._thread

            self._server = None
            self._thread = None

        if server is not None:
            server.shutdown()
            server.server_close()

        if (
            thread is not None
            and thread.is_alive()
        ):
            thread.join(
                timeout=1.5
            )

    def stage_file(
        self,
        file_path,
        filename=None,
    ):
        self.start()

        path = Path(
            file_path
        ).resolve()

        if not path.is_file():
            raise ValueError(
                "送信用ZIPが見つかりません。"
            )

        with self._lock:
            self._cleanup_locked()

            active_count = sum(
                1
                for request in self._requests.values()
                if request["status"]
                in {
                    "pending",
                    "claimed",
                }
            )

            if active_count >= MAX_QUEUE:
                raise RuntimeError(
                    "ココフォリア送信待ちが多すぎます。"
                    " 数秒待ってからもう一度送信してください。"
                )

            request_id = uuid4().hex

            self._requests[
                request_id
            ] = {
                "id": request_id,
                "path": path,
                "filename": (
                    filename
                    or path.name
                ),
                "created_at": time.time(),
                "claimed_until": 0.0,
                "status": "pending",
            }

            self._order.append(
                request_id
            )

        return request_id

    def status_info(
        self,
        request_id,
    ):
        with self._lock:
            self._cleanup_locked()

            request = self._requests.get(
                request_id
            )

            if request is not None:
                return {
                    "ok": True,
                    "status": request[
                        "status"
                    ],
                }

            result = self._results.get(
                request_id
            )

            if result is not None:
                return {
                    "ok": True,
                    **result,
                }

            return {
                "ok": False,
                "status": "unknown",
            }

    def _cleanup_file(
        self,
        request,
    ):
        path = request.get(
            "path"
        )

        if not isinstance(
            path,
            Path,
        ):
            return

        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass

    def _remember_result(
        self,
        request_id,
        status,
        error=None,
    ):
        self._results[
            request_id
        ] = {
            "status": status,
            "error": error,
            "finished_at": time.time(),
        }

    def _cleanup_locked(self):
        now = time.time()

        for request_id in list(
            self._order
        ):
            request = self._requests.get(
                request_id
            )

            if request is None:
                try:
                    self._order.remove(
                        request_id
                    )
                except ValueError:
                    pass
                continue

            if (
                request["status"]
                == "claimed"
                and request[
                    "claimed_until"
                ]
                <= now
            ):
                request[
                    "status"
                ] = "pending"
                request[
                    "claimed_until"
                ] = 0.0

            if (
                now
                - request[
                    "created_at"
                ]
                > PENDING_SECONDS
            ):
                self._cleanup_file(
                    request
                )

                self._remember_result(
                    request_id,
                    "expired",
                    "受信するアクティブなココフォリアルームが見つかりませんでした。",
                )

                self._requests.pop(
                    request_id,
                    None,
                )

                try:
                    self._order.remove(
                        request_id
                    )
                except ValueError:
                    pass

        for request_id, result in list(
            self._results.items()
        ):
            if (
                now
                - result[
                    "finished_at"
                ]
                > RESULT_SECONDS
            ):
                self._results.pop(
                    request_id,
                    None,
                )

    def _pending_info(self):
        with self._lock:
            self._cleanup_locked()

            for request_id in list(
                self._order
            ):
                request = self._requests.get(
                    request_id
                )

                if (
                    request is None
                    or request[
                        "status"
                    ]
                    != "pending"
                ):
                    continue

                path = request[
                    "path"
                ]

                try:
                    size = path.stat().st_size
                except OSError:
                    self._fail_locked(
                        request_id,
                        "file_missing",
                    )
                    continue

                return {
                    "pending": True,
                    "id": request_id,
                    "filename": request[
                        "filename"
                    ],
                    "size": size,
                }

            return {
                "pending": False,
            }

    def _claim(
        self,
        request_id,
    ):
        with self._lock:
            self._cleanup_locked()

            request = self._requests.get(
                request_id
            )

            if (
                request is None
                or request[
                    "status"
                ]
                != "pending"
            ):
                return False

            request[
                "status"
            ] = "claimed"
            request[
                "claimed_until"
            ] = (
                time.time()
                + CLAIM_SECONDS
            )

            return True

    def _get_file(
        self,
        request_id,
    ):
        with self._lock:
            self._cleanup_locked()

            request = self._requests.get(
                request_id
            )

            if (
                request is None
                or request[
                    "status"
                ]
                not in {
                    "pending",
                    "claimed",
                }
            ):
                return None

            path = request[
                "path"
            ]

            if not path.is_file():
                self._fail_locked(
                    request_id,
                    "file_missing",
                )
                return None

            return (
                path,
                request[
                    "filename"
                ],
            )

    def _finish_locked(
        self,
        request_id,
        status,
        error=None,
    ):
        request = self._requests.pop(
            request_id,
            None,
        )

        if request is None:
            return False

        try:
            self._order.remove(
                request_id
            )
        except ValueError:
            pass

        self._cleanup_file(
            request
        )

        self._remember_result(
            request_id,
            status,
            error,
        )

        return True

    def _ack(
        self,
        request_id,
    ):
        with self._lock:
            return self._finish_locked(
                request_id,
                "delivered",
            )

    def _release(
        self,
        request_id,
    ):
        with self._lock:
            self._cleanup_locked()

            request = self._requests.get(
                request_id
            )

            if request is None:
                return False

            request[
                "status"
            ] = "pending"
            request[
                "claimed_until"
            ] = 0.0

            return True

    def _fail_locked(
        self,
        request_id,
        error,
    ):
        return self._finish_locked(
            request_id,
            "failed",
            error,
        )

    def _fail(
        self,
        request_id,
        error,
    ):
        with self._lock:
            return self._fail_locked(
                request_id,
                error,
            )


_BRIDGE = CCFOLIABridgeServer()


def get_bridge_server():
    return _BRIDGE
