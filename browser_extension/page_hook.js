(() => {
  const originalConfirm = window.confirm.bind(window);
  let armedUntil = 0;

  window.addEventListener(
    "ccm-arm-native-confirm",
    () => {
      armedUntil = Date.now() + 10000;
    },
  );

  window.confirm = function(message) {
    const text = String(
      message ?? "",
    );

    const isCCFOLIAExternalImportWarning =
      text.includes(
        "外部ツールで作成および編集されたデータです"
      )
      && text.includes(
        "信頼できるデータのみ取り込むようにしてください"
      );

    if (
      Date.now() <= armedUntil
      && isCCFOLIAExternalImportWarning
    ) {
      armedUntil = 0;
      return true;
    }

    return originalConfirm(message);
  };
})();


(() => {
  // IM5_IMAGE_BACKGROUND_ADAPTER
  const PROJECT_ID = "ccfolia-160aa";
  const UPLOAD_URL =
    "https://asia-northeast1-ccfolia-160aa.cloudfunctions.net/uploadFile";
  const REQUEST_SOURCE = "ccfolia-manager-panel";
  const RESPONSE_SOURCE = "ccfolia-manager-main";

  function decodeJwtPayload(token) {
    const parts = String(token || "").split(".");

    if (parts.length < 2) {
      throw new Error("CCFOLIA認証情報の形式を判定できませんでした。");
    }

    let body = parts[1]
      .replace(/-/g, "+")
      .replace(/_/g, "/");

    while (body.length % 4) {
      body += "=";
    }

    const binary = atob(body);
    const bytes = Uint8Array.from(
      binary,
      (char) => char.charCodeAt(0),
    );

    return JSON.parse(
      new TextDecoder().decode(bytes),
    );
  }

  function findAccessToken(value, seen = new Set()) {
    if (value == null) {
      return null;
    }

    if (typeof value === "string") {
      if (
        value.startsWith("eyJ")
        && value.split(".").length >= 3
      ) {
        return value;
      }

      if (
        value.startsWith("{")
        || value.startsWith("[")
      ) {
        try {
          return findAccessToken(
            JSON.parse(value),
            seen,
          );
        } catch (error) {
        }
      }

      return null;
    }

    if (typeof value !== "object") {
      return null;
    }

    if (seen.has(value)) {
      return null;
    }

    seen.add(value);

    for (const key of [
      "accessToken",
      "idToken",
      "token",
    ]) {
      const candidate = value[key];

      if (
        typeof candidate === "string"
        && candidate.startsWith("eyJ")
        && candidate.split(".").length >= 3
      ) {
        return candidate;
      }
    }

    for (const child of Object.values(value)) {
      const token = findAccessToken(
        child,
        seen,
      );

      if (token) {
        return token;
      }
    }

    return null;
  }

  function readStoreAll(db, storeName) {
    return new Promise((resolve, reject) => {
      const tx = db.transaction(
        storeName,
        "readonly",
      );
      const store = tx.objectStore(storeName);

      if (typeof store.getAll === "function") {
        const request = store.getAll();
        request.onsuccess = () => {
          resolve(request.result || []);
        };
        request.onerror = () => {
          reject(request.error);
        };
        return;
      }

      const rows = [];
      const request = store.openCursor();

      request.onsuccess = () => {
        const cursor = request.result;

        if (!cursor) {
          resolve(rows);
          return;
        }

        rows.push(cursor.value);
        cursor.continue();
      };

      request.onerror = () => {
        reject(request.error);
      };
    });
  }

  function openDb(name) {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(name);

      request.onsuccess = () => {
        resolve(request.result);
      };
      request.onerror = () => {
        reject(request.error);
      };
      request.onblocked = () => {
        reject(
          new Error(
            `IndexedDB ${name} がブロックされています。`,
          ),
        );
      };
    });
  }

  async function findFirebaseAccessToken() {
    const dbNames = [
      "firebaseLocalStorageDb",
    ];

    if (typeof indexedDB.databases === "function") {
      try {
        const infos = await indexedDB.databases();

        for (const info of infos) {
          const name = String(info?.name || "");

          if (
            name
            && /firebase/i.test(name)
            && !dbNames.includes(name)
          ) {
            dbNames.push(name);
          }
        }
      } catch (error) {
      }
    }

    for (const dbName of dbNames) {
      let db;

      try {
        db = await openDb(dbName);
      } catch (error) {
        continue;
      }

      try {
        for (const storeName of db.objectStoreNames) {
          let rows;

          try {
            rows = await readStoreAll(
              db,
              storeName,
            );
          } catch (error) {
            continue;
          }

          for (const row of rows) {
            const token = findAccessToken(row);

            if (!token) {
              continue;
            }

            const payload = decodeJwtPayload(token);
            const expiresAt = Number(
              payload.exp || 0,
            );

            if (
              expiresAt
              && expiresAt * 1000
                < Date.now() + 30000
            ) {
              continue;
            }

            return token;
          }
        }
      } finally {
        db.close();
      }
    }

    throw new Error(
      "CCFOLIAのログイン認証情報を取得できませんでした。"
      + " CCFOLIAを再読み込みしてログイン状態を確認してください。",
    );
  }

  function currentRoomId() {
    const match = location.pathname.match(
      /^\/rooms\/([^/?#]+)/,
    );

    if (!match) {
      throw new Error(
        "現在のCCFOLIAルームIDを取得できませんでした。",
      );
    }

    return decodeURIComponent(match[1]);
  }

  // IM7_BACKGROUND_LEGACY_URL_APPLY_FIX
  function validateBackgroundUrl(value) {
    const parsed = new URL(
      String(value || ""),
    );

    if (parsed.protocol !== "https:") {
      throw new Error(
        "CCFOLIA画像URLとして扱えないURLです。",
      );
    }

    const host = parsed.hostname.toLowerCase();
    const path = parsed.pathname.toLowerCase();

    if (host === "storage.ccfolia-cdn.net") {
      if (!path.startsWith("/users/")) {
        throw new Error(
          "CCFOLIA CDNの画像パスとして扱えません。",
        );
      }
      return parsed.href;
    }

    if (host === "firebasestorage.googleapis.com") {
      const legacyPrefix =
        "/v0/b/ccfolia-160aa.appspot.com/o/users%2f";

      if (!path.startsWith(legacyPrefix)) {
        throw new Error(
          "CCFOLIA旧Firebase Storageの画像パスとして扱えません。",
        );
      }
      return parsed.href;
    }

    throw new Error(
      "CCFOLIA画像URLとして扱えないホストです。",
    );
  }

  // IM6_IMAGE_UPLOAD_ADAPTER
  function randomHex(length = 64) {
    const bytes = new Uint8Array(length);
    crypto.getRandomValues(bytes);

    const chars = "0123456789abcdef";
    let result = "";

    for (const value of bytes) {
      result += chars[value % 16];
    }

    return result;
  }

  function base64ToBytes(value) {
    const binary = atob(
      String(value || ""),
    );

    return Uint8Array.from(
      binary,
      (char) => char.charCodeAt(0),
    );
  }

  async function uploadImageToCCFOLIA(data) {
    const token =
      await findFirebaseAccessToken();

    const payload =
      decodeJwtPayload(token);

    const uid = String(
      payload.user_id
      || payload.sub
      || "",
    );

    if (!uid) {
      throw new Error(
        "認証トークンからユーザーIDを取得できませんでした。",
      );
    }

    const filename = String(
      data.filename || "image.png",
    );

    const contentType = String(
      data.contentType
      || "image/png",
    );

    if (!contentType.startsWith("image/")) {
      throw new Error(
        "画像ファイルとして扱えないデータです。",
      );
    }

    const bytes = base64ToBytes(
      data.dataBase64,
    );

    if (!bytes.length) {
      throw new Error(
        "画像データが空です。",
      );
    }

    const file = new File(
      [bytes],
      filename,
      {
        type: contentType,
      },
    );

    const fileId = randomHex(64);
    const filePath =
      `users/${uid}/files/${fileId}`;

    const form = new FormData();
    form.append(
      "file",
      file,
      filename,
    );
    form.append(
      "filePath",
      filePath,
    );

    const uploadResponse = await fetch(
      UPLOAD_URL,
      {
        method: "POST",
        headers: {
          Authorization:
            `Bearer ${token}`,
        },
        body: form,
        mode: "cors",
        credentials: "omit",
      },
    );

    const uploadText =
      await uploadResponse.text();

    let uploadJson = null;

    try {
      uploadJson = JSON.parse(
        uploadText,
      );
    } catch (error) {
    }

    if (!uploadResponse.ok) {
      throw new Error(
        `uploadFile が失敗しました (${uploadResponse.status})`
        + (
          uploadText
            ? `\n${uploadText.slice(0, 500)}`
            : ""
        ),
      );
    }

    const storageName = String(
      uploadJson?.name
      || filePath,
    );

    const finalContentType = String(
      uploadJson?.contentType
      || contentType,
    );

    const fileSize = Number(
      uploadJson?.size
      || bytes.length,
    );

    const fileUrl =
      `https://storage.ccfolia-cdn.net/${storageName}`
      + `?t=${Date.now()}`;

    const documentUrl =
      `https://firestore.googleapis.com/v1/projects/${PROJECT_ID}`
      + `/databases/(default)/documents/users/${encodeURIComponent(uid)}`
      + `/files/${encodeURIComponent(fileId)}`;

    const registerResponse = await fetch(
      documentUrl,
      {
        method: "PATCH",
        headers: {
          Authorization:
            `Bearer ${token}`,
          "Content-Type":
            "application/json",
        },
        body: JSON.stringify({
          fields: {
            archived: {
              booleanValue: false,
            },
            uploaded: {
              booleanValue: true,
            },
            url: {
              stringValue: fileUrl,
            },
            contentType: {
              stringValue:
                finalContentType,
            },
            size: {
              integerValue:
                String(fileSize),
            },
          },
        }),
        mode: "cors",
        credentials: "omit",
      },
    );

    const registerText =
      await registerResponse.text();

    if (!registerResponse.ok) {
      throw new Error(
        `画像登録が失敗しました (${registerResponse.status})`
        + (
          registerText
            ? `\n${registerText.slice(0, 700)}`
            : ""
        ),
      );
    }

    if (data.applyBackground) {
      await applyBackgroundUrl(
        fileUrl,
      );
    }

    return {
      fileId,
      url: fileUrl,
      contentType: finalContentType,
      fileSize,
    };
  }

  // IM7_IMAGE_SALVAGE_ADAPTER
  function firestoreFieldValue(field) {
    if (!field || typeof field !== "object") {
      return null;
    }

    if ("stringValue" in field) {
      return String(field.stringValue || "");
    }

    if ("integerValue" in field) {
      return Number(field.integerValue || 0);
    }

    if ("doubleValue" in field) {
      return Number(field.doubleValue || 0);
    }

    if ("booleanValue" in field) {
      return Boolean(field.booleanValue);
    }

    return null;
  }

  // IM7_BACKGROUND_ONLY_SALVAGE_ADAPTER
  async function listCCFOLIAImageFiles() {
    const token =
      await findFirebaseAccessToken();
    const payload = decodeJwtPayload(token);

    const uid = String(
      payload.user_id
      || payload.sub
      || "",
    );

    if (!uid) {
      throw new Error(
        "認証トークンからユーザーIDを取得できませんでした。",
      );
    }

    const output = [];
    let pageToken = "";
    let pageCount = 0;

    do {
      const params = new URLSearchParams({
        pageSize: "300",
      });

      if (pageToken) {
        params.set(
          "pageToken",
          pageToken,
        );
      }

      const listUrl =
        `https://firestore.googleapis.com/v1/projects/${PROJECT_ID}`
        + `/databases/(default)/documents/users/${encodeURIComponent(uid)}`
        + `/files?${params.toString()}`;

      const response = await fetch(
        listUrl,
        {
          method: "GET",
          headers: {
            Authorization:
              `Bearer ${token}`,
          },
          mode: "cors",
          credentials: "omit",
        },
      );

      const responseText =
        await response.text();

      let responseJson = {};

      try {
        responseJson = JSON.parse(
          responseText || "{}",
        );
      } catch (error) {
      }

      if (!response.ok) {
        throw new Error(
          `CCFOLIA背景一覧の取得に失敗しました (${response.status})`
          + (
            responseText
              ? `\n${responseText.slice(0, 700)}`
              : ""
          ),
        );
      }

      const documents = Array.isArray(
        responseJson.documents,
      )
        ? responseJson.documents
        : [];

      for (const document of documents) {
        const fields =
          document?.fields || {};
        const name = String(
          document?.name || "",
        );
        const fileId = decodeURIComponent(
          name.split("/").pop() || "",
        );
        const url = String(
          firestoreFieldValue(fields.url)
          || "",
        );
        const contentType = String(
          firestoreFieldValue(
            fields.contentType,
          )
          || "",
        );
        const size = Number(
          firestoreFieldValue(fields.size)
          || 0,
        );
        const archived = Boolean(
          firestoreFieldValue(
            fields.archived,
          )
        );
        const uploaded = Boolean(
          firestoreFieldValue(
            fields.uploaded,
          )
        );
        const directory = String(
          firestoreFieldValue(fields.dir)
          || "",
        ).trim().toLowerCase();

        if (
          !fileId
          || !url
          || archived
          || !uploaded
          || directory !== "background"
          || !contentType.startsWith(
            "image/",
          )
        ) {
          continue;
        }

        const displayName = String(
          firestoreFieldValue(fields.name)
          || firestoreFieldValue(
            fields.fileName,
          )
          || firestoreFieldValue(
            fields.filename,
          )
          || "",
        );

        output.push({
          file_id: fileId,
          url,
          content_type: contentType,
          file_size:
            Number.isFinite(size)
              ? Math.max(0, size)
              : 0,
          display_name: displayName,
          dir: directory,
        });
      }

      pageToken = String(
        responseJson.nextPageToken
        || "",
      );
      pageCount += 1;

      if (pageCount > 200) {
        throw new Error(
          "CCFOLIA背景一覧のページ数が上限を超えました。",
        );
      }
    } while (pageToken);

    return output;
  }

  async function applyBackgroundUrl(url) {
    const backgroundUrl =
      validateBackgroundUrl(url);
    const token =
      await findFirebaseAccessToken();
    const roomId = currentRoomId();

    const query = [
      "backgroundUrl",
      "updatedAt",
    ]
      .map(
        (field) =>
          `updateMask.fieldPaths=${encodeURIComponent(field)}`,
      )
      .join("&");

    const roomUrl =
      `https://firestore.googleapis.com/v1/projects/${PROJECT_ID}`
      + `/databases/(default)/documents/rooms/${encodeURIComponent(roomId)}`
      + `?${query}`;

    const response = await fetch(
      roomUrl,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          fields: {
            backgroundUrl: {
              stringValue: backgroundUrl,
            },
            updatedAt: {
              integerValue: String(Date.now()),
            },
          },
        }),
        mode: "cors",
        credentials: "omit",
      },
    );

    const responseText = await response.text();

    if (!response.ok) {
      throw new Error(
        `背景変更が失敗しました (${response.status})`
        + (
          responseText
            ? `\n${responseText.slice(0, 500)}`
            : ""
        ),
      );
    }
  }


  // CHARACTER_SALVAGE_IMPORT_ADAPTER_V1
  function decodeFirestoreCharacterValue(value) {
    if (!value || typeof value !== "object") {
      return null;
    }
    if ("nullValue" in value) return null;
    if ("booleanValue" in value) return Boolean(value.booleanValue);
    if ("integerValue" in value) {
      const number = Number(value.integerValue);
      return Number.isSafeInteger(number)
        ? number
        : String(value.integerValue);
    }
    if ("doubleValue" in value) return Number(value.doubleValue);
    if ("stringValue" in value) return String(value.stringValue);
    if ("timestampValue" in value) return String(value.timestampValue);
    if ("referenceValue" in value) return String(value.referenceValue);
    if ("arrayValue" in value) {
      const values = value.arrayValue?.values || [];
      return values.map(decodeFirestoreCharacterValue);
    }
    if ("mapValue" in value) {
      return decodeFirestoreCharacterFields(
        value.mapValue?.fields || {},
      );
    }
    return null;
  }

  function decodeFirestoreCharacterFields(fields) {
    const result = {};
    for (const [key, value] of Object.entries(fields || {})) {
      result[key] = decodeFirestoreCharacterValue(value);
    }
    return result;
  }

  function firestoreDocumentId(name) {
    const parts = String(name || "").split("/");
    return parts[parts.length - 1] || "";
  }

  // CHARACTER_SALVAGE_ROOM_TAG_ADAPTER_V1
  async function readCurrentRoomName(
    roomId,
    token,
  ) {
    const roomUrl =
      `https://firestore.googleapis.com/v1/projects/${PROJECT_ID}`
      + `/databases/(default)/documents/rooms/${
        encodeURIComponent(roomId)
      }`;

    const response = await fetch(
      roomUrl,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        mode: "cors",
        credentials: "omit",
      },
    );

    if (!response.ok) {
      const text = await response.text();
      let detail = `HTTP ${response.status}`;

      if (text) {
        try {
          const body = JSON.parse(text);
          detail = body?.error?.message || detail;
        } catch (error) {
          // Keep generic HTTP detail.
        }
      }

      throw new Error(
        `CCFOLIAルーム名取得失敗: ${detail}`,
      );
    }

    const body = await response.json();
    const decoded =
      decodeFirestoreCharacterFields(
        body?.fields || {},
      );

    return String(decoded?.name || "").trim();
  }

  async function readCurrentRoomCharacters() {
    const token = await findFirebaseAccessToken();
    const roomId = currentRoomId();
    const roomName =
      await readCurrentRoomName(
        roomId,
        token,
      );
    const url =
      `https://firestore.googleapis.com/v1/projects/${PROJECT_ID}`
      + `/databases/(default)/documents/rooms/${
        encodeURIComponent(roomId)
      }:runQuery`;

    const response = await fetch(
      url,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          structuredQuery: {
            from: [
              {
                collectionId: "characters",
              },
            ],
            limit: 1000,
          },
        }),
        mode: "cors",
        credentials: "omit",
      },
    );

    const text = await response.text();
    let body = [];

    if (text) {
      try {
        body = JSON.parse(text);
      } catch (error) {
        throw new Error(
          "CCFOLIAキャラクター一覧の応答を解析できませんでした。",
        );
      }
    }

    if (!response.ok) {
      const detail =
        body?.error?.message
        || `HTTP ${response.status}`;
      throw new Error(
        `CCFOLIAキャラクター取得失敗: ${detail}`,
      );
    }

    const characters = [];

    for (const item of Array.isArray(body) ? body : []) {
      const document = item?.document;
      if (!document) continue;

      const id = firestoreDocumentId(document.name);
      if (!id) continue;

      characters.push({
        id,
        fields: decodeFirestoreCharacterFields(
          document.fields || {},
        ),
      });
    }

    return {
      room_id: roomId,
      room_name: roomName,
      characters,
      truncated: characters.length >= 1000,
    };
  }


  // BGM_FIRESTORE_MEDIA_HELPERS_V1
  function decodeFirestoreBgmValue(value) {
    if (!value || typeof value !== "object") {
      return null;
    }

    if ("nullValue" in value) {
      return null;
    }
    if ("booleanValue" in value) {
      return Boolean(value.booleanValue);
    }
    if ("integerValue" in value) {
      const number = Number(value.integerValue);
      return Number.isSafeInteger(number)
        ? number
        : String(value.integerValue);
    }
    if ("doubleValue" in value) {
      return Number(value.doubleValue);
    }
    if ("stringValue" in value) {
      return String(value.stringValue);
    }
    if ("timestampValue" in value) {
      return String(value.timestampValue);
    }
    if ("referenceValue" in value) {
      return String(value.referenceValue);
    }
    if ("arrayValue" in value) {
      const values =
        value.arrayValue?.values || [];
      return values.map(
        decodeFirestoreBgmValue,
      );
    }
    if ("mapValue" in value) {
      return decodeFirestoreBgmFields(
        value.mapValue?.fields || {},
      );
    }

    return null;
  }

  function decodeFirestoreBgmFields(fields) {
    const result = {};

    for (
      const [key, value]
      of Object.entries(fields || {})
    ) {
      result[key] =
        decodeFirestoreBgmValue(value);
    }

    return result;
  }

  function bgmProbeDocumentId(name) {
    const parts =
      String(name || "").split("/");
    return parts[parts.length - 1] || "";
  }

  async function bgmProbeFetchJson(
    url,
    token,
    options = {},
  ) {
    const response = await fetch(
      url,
      {
        ...options,
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
          ...(options.headers || {}),
        },
        mode: "cors",
        credentials: "omit",
      },
    );

    const text =
      await response.text();

    let body = null;

    if (text) {
      try {
        body = JSON.parse(text);
      } catch (error) {
        body = null;
      }
    }

    if (!response.ok) {
      const detail =
        body?.error?.message
        || `HTTP ${response.status}`;

      throw new Error(
        `${response.status}: ${detail}`,
      );
    }

    return body;
  }

  // BGM_FIRESTORE_PAGED_QUERY_V1
  async function bgmProbeRunQuery(
    parentPath,
    collectionId,
    token,
    pageSize,
    maxPages = 10,
  ) {
    const url =
      `https://firestore.googleapis.com/v1/projects/${PROJECT_ID}`
      + `/databases/(default)/documents/${parentPath}:runQuery`;

    const documents = [];
    let offset = 0;
    let pages = 0;
    let capped = false;

    for (
      let pageIndex = 0;
      pageIndex < maxPages;
      pageIndex += 1
    ) {
      const rows =
        await bgmProbeFetchJson(
          url,
          token,
          {
            method: "POST",
            body: JSON.stringify({
              structuredQuery: {
                from: [
                  {
                    collectionId,
                  },
                ],
                limit: pageSize,
                ...(offset > 0
                  ? { offset }
                  : {}),
              },
            }),
          },
        );

      const pageDocuments = [];

      for (
        const row
        of Array.isArray(rows) ? rows : []
      ) {
        if (row?.document) {
          pageDocuments.push(
            row.document,
          );
        }
      }

      documents.push(
        ...pageDocuments,
      );

      pages += 1;

      if (
        pageDocuments.length
        < pageSize
      ) {
        break;
      }

      offset +=
        pageDocuments.length;

      if (
        pageIndex
        === maxPages - 1
      ) {
        capped = true;
      }
    }

    return {
      documents,
      pages,
      capped,
      page_size: pageSize,
      max_pages: maxPages,
    };
  }

  function bgmProbeMediaSummary(document) {
    const fields =
      decodeFirestoreBgmFields(
        document?.fields || {},
      );

    const result = {
      id:
        bgmProbeDocumentId(
          document?.name,
        ),
      name:
        String(fields.name || ""),
      dir:
        String(fields.dir || ""),
      url:
        fields.url ?? null,
      contentType:
        fields.contentType ?? null,
      size:
        fields.size ?? null,
      volume:
        fields.volume ?? null,
      loop:
        fields.loop ?? null,
      order:
        fields.order ?? null,
      uploaded:
        fields.uploaded ?? null,
      updatedAt:
        fields.updatedAt ?? null,
      field_keys:
        Object.keys(
          document?.fields || {},
        ).sort(),
    };

    return result;
  }



  // BGM_FIXED_TAB_SLOTS_V1
  async function collectBgmSalvagePayload() {
    const token =
      await findFirebaseAccessToken();

    const payload =
      decodeJwtPayload(token);

    const uid = String(
      payload.user_id
      || payload.sub
      || "",
    );

    if (!uid) {
      throw new Error(
        "認証情報からユーザーIDを取得できませんでした。",
      );
    }

    const queryResult =
      await bgmProbeRunQuery(
        `users/${encodeURIComponent(uid)}`,
        "media",
        token,
        1000,
        10,
      );

    const documents =
      Array.isArray(queryResult)
        ? queryResult
        : (
          Array.isArray(
            queryResult?.documents,
          )
            ? queryResult.documents
            : []
        );

    const items = [];
    const dirIds = [];
    const seenDirs =
      new Set();

    for (
      const document
      of documents
    ) {
      const fields =
        decodeFirestoreBgmFields(
          document?.fields || {},
        );

      const contentType =
        String(
          fields.contentType || "",
        );

      if (
        contentType
        && !contentType
          .startsWith("audio/")
      ) {
        continue;
      }

      const directory =
        String(
          fields.dir || "",
        ).trim();

      const item = {
        id:
          bgmProbeDocumentId(
            document?.name,
          ),
        name:
          String(
            fields.name || "",
          ),
        dir:
          directory,
        url:
          fields.url ?? null,
        contentType:
          fields.contentType
          ?? null,
        size:
          fields.size ?? 0,
        volume:
          fields.volume ?? 0.5,
        loop:
          fields.loop ?? true,
        order:
          fields.order ?? 0,
        uploaded:
          fields.uploaded ?? true,
        archived:
          fields.archived ?? false,
        external:
          fields.external ?? null,
        updatedAt:
          fields.updatedAt ?? null,
      };

      items.push(item);

      if (
        !item.archived
        && item.url
        && directory
        && !seenDirs.has(
          directory,
        )
      ) {
        seenDirs.add(directory);
        dirIds.push(directory);
      }
    }

    return {
      items,
      dir_ids:
        dirIds,
      total:
        items.length,
      active:
        items.filter(
          (item) =>
            !item.archived
            && item.url,
        ).length,
      tab_count:
        dirIds.length,
      audio_bytes_downloaded:
        false,
      auth_token_included:
        false,
    };
  }

  // BGM_BROWSER_APPLY_ADAPTER_V1
  function randomAlphaNum(length = 20) {
    const chars =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
      + "abcdefghijklmnopqrstuvwxyz"
      + "0123456789";
    const bytes = new Uint8Array(length);
    crypto.getRandomValues(bytes);

    let result = "";
    for (const value of bytes) {
      result += chars[value % chars.length];
    }
    return result;
  }

  async function uploadBgmToCCFOLIA(data) {
    const token = await findFirebaseAccessToken();
    const payload = decodeJwtPayload(token);
    const uid = String(payload.user_id || payload.sub || "");

    if (!uid) {
      throw new Error("認証情報からユーザーIDを取得できませんでした。");
    }

    const filename = String(data.filename || "audio.mp3");
    const contentType = String(data.contentType || "audio/mpeg");
    if (!contentType.startsWith("audio/")) {
      throw new Error("音声ファイルとして扱えないデータです。");
    }

    const bytes = base64ToBytes(data.dataBase64);
    if (!bytes.length) {
      throw new Error("音声データが空です。");
    }

    const displayName = String(data.displayName || filename);
    const volume = Math.max(
      0,
      Math.min(1, Number(data.volume ?? 0.5)),
    );
    const loop = Boolean(data.loop);
    const directory = String(data.directory || "bgm01");

    const mediaId = randomAlphaNum(20);
    const filePath = `users/${uid}/media/${mediaId}`;
    const file = new File(
      [bytes],
      filename,
      { type: contentType },
    );

    const form = new FormData();
    form.append("file", file, filename);
    form.append("filePath", filePath);

    const uploadResponse = await fetch(
      UPLOAD_URL,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: form,
        mode: "cors",
        credentials: "omit",
      },
    );

    const uploadText = await uploadResponse.text();
    let uploadJson = null;
    try {
      uploadJson = JSON.parse(uploadText);
    } catch (error) {
    }

    if (!uploadResponse.ok) {
      throw new Error(
        `BGM uploadFile が失敗しました (${uploadResponse.status})`
        + (uploadText ? `\n${uploadText.slice(0, 500)}` : ""),
      );
    }

    const storageName = String(uploadJson?.name || filePath);
    const finalContentType = String(
      uploadJson?.contentType || contentType,
    );
    const fileSize = Number(uploadJson?.size || bytes.length);
    const fileUrl =
      `https://storage.ccfolia-cdn.net/${storageName}`
      + `?t=${Date.now()}`;

    let maxOrder = -1;
    try {
      const queryResult = await bgmProbeRunQuery(
        `users/${encodeURIComponent(uid)}`,
        "media",
        token,
        1000,
        10,
      );
      const documents = Array.isArray(queryResult)
        ? queryResult
        : (
          Array.isArray(queryResult?.documents)
            ? queryResult.documents
            : []
        );

      for (const document of documents) {
        const fields = decodeFirestoreBgmFields(
          document?.fields || {},
        );
        if (String(fields.dir || "") !== directory) {
          continue;
        }
        const order = Number(fields.order);
        if (Number.isFinite(order) && order > maxOrder) {
          maxOrder = order;
        }
      }
    } catch (error) {
      console.warn(
        "[CCFOLIA Manager] BGM order probe failed",
        error,
      );
    }

    const order = maxOrder + 1;
    const now = Date.now();
    const documentUrl =
      `https://firestore.googleapis.com/v1/projects/${PROJECT_ID}`
      + `/databases/(default)/documents/users/${encodeURIComponent(uid)}`
      + `/media/${encodeURIComponent(mediaId)}`;

    const registerResponse = await fetch(
      documentUrl,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          fields: {
            archived: { booleanValue: false },
            uploaded: { booleanValue: true },
            external: { booleanValue: false },
            owner: { stringValue: uid },
            by: { stringValue: uid },
            roomId: { nullValue: null },
            url: { stringValue: fileUrl },
            contentType: { stringValue: finalContentType },
            size: { integerValue: String(fileSize) },
            createdAt: { integerValue: String(now) },
            updatedAt: { integerValue: String(now) },
            name: { stringValue: displayName },
            volume: { doubleValue: volume },
            loop: { booleanValue: loop },
            dir: { stringValue: directory },
            order: { integerValue: String(order) },
          },
        }),
        mode: "cors",
        credentials: "omit",
      },
    );

    const registerText = await registerResponse.text();
    if (!registerResponse.ok) {
      throw new Error(
        `BGMライブラリ登録が失敗しました (${registerResponse.status})`
        + (registerText ? `\n${registerText.slice(0, 700)}` : ""),
      );
    }

    return {
      mediaId,
      url: fileUrl,
      contentType: finalContentType,
      fileSize,
      directory,
      order,
      updatedAt: now,
    };
  }

  async function applyBgmToCurrentRoom(data) {
    const token = await findFirebaseAccessToken();
    const roomId = currentRoomId();
    const name = String(data.name || "");
    const url = String(data.url || "");

    if (!url) {
      throw new Error("BGM URLがありません。");
    }

    const volume = Math.max(
      0,
      Math.min(1, Number(data.volume ?? 0.5)),
    );
    const loop = Boolean(data.loop);
    const fields = [
      "mediaName",
      "mediaUrl",
      "mediaRef",
      "mediaType",
      "mediaVolume",
      "mediaRepeat",
      "updatedAt",
    ];
    const query = fields
      .map(
        (field) =>
          `updateMask.fieldPaths=${encodeURIComponent(field)}`,
      )
      .join("&");

    const roomUrl =
      `https://firestore.googleapis.com/v1/projects/${PROJECT_ID}`
      + `/databases/(default)/documents/rooms/${encodeURIComponent(roomId)}`
      + `?${query}`;

    const response = await fetch(
      roomUrl,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          fields: {
            mediaName: { stringValue: name },
            mediaUrl: { stringValue: url },
            mediaRef: { nullValue: null },
            mediaType: { stringValue: "file" },
            mediaVolume: { doubleValue: volume },
            mediaRepeat: { booleanValue: loop },
            updatedAt: { integerValue: String(Date.now()) },
          },
        }),
        mode: "cors",
        credentials: "omit",
      },
    );

    const text = await response.text();
    if (!response.ok) {
      throw new Error(
        `BGM変更が失敗しました (${response.status})`
        + (text ? `\n${text.slice(0, 700)}` : ""),
      );
    }

    return {
      roomId,
      name,
      url,
      volume,
      loop,
    };
  }


  window.addEventListener(
    "message",
    async (event) => {
      if (event.source !== window) {
        return;
      }

      const data = event.data;

      if (
        !data
        || data.source !== REQUEST_SOURCE
      ) {
        return;
      }

      const requestId = String(
        data.requestId || "",
      );

      if (!requestId) {
        return;
      }

      if (
        data.type
        === "character-salvage-import-request"
      ) {
        try {
          const result =
            await readCurrentRoomCharacters();

          window.postMessage(
            {
              source: RESPONSE_SOURCE,
              type:
                "character-salvage-import-result",
              requestId,
              ok: true,
              result,
            },
            location.origin,
          );
        } catch (error) {
          window.postMessage(
            {
              source: RESPONSE_SOURCE,
              type:
                "character-salvage-import-result",
              requestId,
              ok: false,
              error: String(
                error?.message || error,
              ),
            },
            location.origin,
          );
        }

        return;
      }

      if (
        data.type
        === "bgm-salvage-scan-request"
      ) {
        try {
          const result =
            await collectBgmSalvagePayload();

          window.postMessage(
            {
              source: RESPONSE_SOURCE,
              type:
                "bgm-salvage-scan-result",
              requestId,
              ok: true,
              result,
            },
            location.origin,
          );
        } catch (error) {
          window.postMessage(
            {
              source: RESPONSE_SOURCE,
              type:
                "bgm-salvage-scan-result",
              requestId,
              ok: false,
              error: String(
                error?.message
                || error,
              ),
            },
            location.origin,
          );
        }

        return;
      }

      if (
        data.type
        === "bgm-upload-request"
      ) {
        try {
          const result = await uploadBgmToCCFOLIA(data);
          window.postMessage(
            {
              source: RESPONSE_SOURCE,
              type: "bgm-upload-result",
              requestId,
              ok: true,
              result,
            },
            location.origin,
          );
        } catch (error) {
          window.postMessage(
            {
              source: RESPONSE_SOURCE,
              type: "bgm-upload-result",
              requestId,
              ok: false,
              error: String(error?.message || error),
            },
            location.origin,
          );
        }
        return;
      }

      if (
        data.type
        === "bgm-apply-room-request"
      ) {
        try {
          const result = await applyBgmToCurrentRoom(data);
          window.postMessage(
            {
              source: RESPONSE_SOURCE,
              type: "bgm-apply-room-result",
              requestId,
              ok: true,
              result,
            },
            location.origin,
          );
        } catch (error) {
          window.postMessage(
            {
              source: RESPONSE_SOURCE,
              type: "bgm-apply-room-result",
              requestId,
              ok: false,
              error: String(error?.message || error),
            },
            location.origin,
          );
        }
        return;
      }

      if (
        data.type
        === "image-apply-background-request"
      ) {
        try {
          await applyBackgroundUrl(
            data.url
          );

          window.postMessage(
            {
              source: RESPONSE_SOURCE,
              type:
                "image-apply-background-result",
              requestId,
              ok: true,
            },
            location.origin,
          );
        } catch (error) {
          window.postMessage(
            {
              source: RESPONSE_SOURCE,
              type:
                "image-apply-background-result",
              requestId,
              ok: false,
              error: String(
                error?.message || error,
              ),
            },
            location.origin,
          );
        }

        return;
      }

      if (
        data.type
        === "image-salvage-list-request"
      ) {
        try {
          const images =
            await listCCFOLIAImageFiles();

          window.postMessage(
            {
              source: RESPONSE_SOURCE,
              type:
                "image-salvage-list-result",
              requestId,
              ok: true,
              images,
            },
            location.origin,
          );
        } catch (error) {
          window.postMessage(
            {
              source: RESPONSE_SOURCE,
              type:
                "image-salvage-list-result",
              requestId,
              ok: false,
              error: String(
                error?.message || error,
              ),
            },
            location.origin,
          );
        }

        return;
      }

      if (
        data.type
        === "image-upload-request"
      ) {
        try {
          const result =
            await uploadImageToCCFOLIA(
              data,
            );

          window.postMessage(
            {
              source: RESPONSE_SOURCE,
              type:
                "image-upload-result",
              requestId,
              ok: true,
              result,
            },
            location.origin,
          );
        } catch (error) {
          window.postMessage(
            {
              source: RESPONSE_SOURCE,
              type:
                "image-upload-result",
              requestId,
              ok: false,
              error: String(
                error?.message || error,
              ),
            },
            location.origin,
          );
        }
      }
    },
  );
})();
