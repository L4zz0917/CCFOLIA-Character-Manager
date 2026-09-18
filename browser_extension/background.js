const BASE = "http://127.0.0.1:17431";
const fileCache = new Map();
const CHUNK_SIZE = 256 * 1024;

async function apiJson(path, options = {}) {
  const headers =
    new Headers(
      options.headers || {},
    );

  if (
    !headers.has(
      "X-CCM-Client"
    )
  ) {
    headers.set(
      "X-CCM-Client",
      "browser-extension",
    );
  }

  const response = await fetch(
    `${BASE}${path}`,
    {
      ...options,
      cache: "no-store",
      headers,
    },
  );

  let payload = null;

  try {
    payload =
      await response.json();
  } catch (error) {
  }

  if (!response.ok) {
    throw new Error(
      payload?.error
      || `Bridge HTTP ${response.status}`,
    );
  }

  return payload || {};
}

function bytesToBase64(bytes) {
  let binary = "";
  const step = 0x8000;

  for (let i = 0; i < bytes.length; i += step) {
    const part = bytes.subarray(
      i,
      Math.min(i + step, bytes.length),
    );

    binary += String.fromCharCode(...part);
  }

  return btoa(binary);
}

async function canReceive(sender) {
  const tab = sender?.tab;

  if (!tab || !tab.active) {
    return false;
  }

  try {
    const lastWindow =
      await chrome.windows.getLastFocused();

    return Boolean(
      lastWindow
      && tab.windowId === lastWindow.id
    );
  } catch (error) {
    return Boolean(tab.active);
  }
}

async function handleMessage(message, sender) {
  switch (message?.type) {
    case "ccmApi": {
      const path = String(
        message.path || ""
      );

      if (!path.startsWith("/api/")) {
        throw new Error(
          "Invalid CCM API path"
        );
      }

      const method = String(
        message.method || "GET"
      ).toUpperCase();

      const options = {
        method,
        headers: {
          "X-CCM-Client":
            "browser-extension",
        },
      };

      if (
        method !== "GET"
        && method !== "HEAD"
      ) {
        options.headers["Content-Type"] =
          "application/json";
        options.body = JSON.stringify(
          message.body || {},
        );
      }

      const data = await apiJson(
        path,
        options,
      );

      return {
        ok: true,
        data,
      };
    }

    case "canReceive": {
      return {
        ok: true,
        canReceive: await canReceive(sender),
      };
    }

    case "claimPending": {
      let pending;

      try {
        pending = await apiJson("/pending");
      } catch (error) {
        return {
          ok: true,
          pending: false,
          offline: true,
        };
      }

      if (!pending.pending) {
        return {
          ok: true,
          pending: false,
        };
      }

      try {
        await apiJson(
          `/claim/${encodeURIComponent(pending.id)}`,
          {
            method: "POST",
          },
        );
      } catch (error) {
        return {
          ok: true,
          pending: false,
        };
      }

      return {
        ok: true,
        pending: true,
        id: pending.id,
        filename:
          pending.filename
          || "ccm_characters.zip",
        size: pending.size || 0,
      };
    }

    case "prepareFile": {
      const id = String(message.id || "");

      if (!id) {
        throw new Error("Missing request id");
      }

      const response = await fetch(
        `${BASE}/file/${encodeURIComponent(id)}`,
        {
          cache: "no-store",
          headers: {
            "X-CCM-Client":
              "browser-extension",
          },
        },
      );

      if (!response.ok) {
        throw new Error(`Bridge HTTP ${response.status}`);
      }

      const bytes = new Uint8Array(
        await response.arrayBuffer(),
      );

      fileCache.set(id, bytes);

      return {
        ok: true,
        size: bytes.length,
        chunkSize: CHUNK_SIZE,
      };
    }

    case "getFileChunk": {
      const id = String(message.id || "");
      const offset = Number(message.offset || 0);
      const bytes = fileCache.get(id);

      if (!bytes) {
        throw new Error("File cache is missing");
      }

      const end = Math.min(
        offset + CHUNK_SIZE,
        bytes.length,
      );

      return {
        ok: true,
        offset,
        end,
        data: bytesToBase64(
          bytes.subarray(offset, end),
        ),
      };
    }

    case "releaseFile": {
      const id = String(message.id || "");
      fileCache.delete(id);

      return {
        ok: true,
      };
    }

    case "ack": {
      const id = String(message.id || "");
      fileCache.delete(id);

      await apiJson(
        `/ack/${encodeURIComponent(id)}`,
        {
          method: "POST",
        },
      );

      return {
        ok: true,
      };
    }

    case "release": {
      const id = String(message.id || "");
      fileCache.delete(id);

      try {
        await apiJson(
          `/release/${encodeURIComponent(id)}`,
          {
            method: "POST",
          },
        );
      } catch (error) {
      }

      return {
        ok: true,
      };
    }

    default:
      return {
        ok: false,
        error: "unknown_message",
      };
  }
}

chrome.runtime.onMessage.addListener(
  (message, sender, sendResponse) => {
    handleMessage(message, sender)
      .then(sendResponse)
      .catch((error) => {
        sendResponse({
          ok: false,
          error: String(
            error?.message || error,
          ),
        });
      });

    return true;
  },
);
