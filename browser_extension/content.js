let busy = false;

function extensionMessage(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(
      message,
      (response) => {
        const runtimeError =
          chrome.runtime.lastError;

        if (runtimeError) {
          reject(
            new Error(runtimeError.message),
          );
          return;
        }

        if (!response) {
          reject(
            new Error("No response from extension"),
          );
          return;
        }

        if (!response.ok) {
          reject(
            new Error(
              response.error
              || "Bridge request failed",
            ),
          );
          return;
        }

        resolve(response);
      },
    );
  });
}

function sleep(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function base64ToBytes(base64) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);

  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }

  return bytes;
}

function showToast(message, kind = "ok") {
  const old = document.getElementById(
    "ccm-cocofolia-bridge-toast",
  );

  if (old) {
    old.remove();
  }

  const toast = document.createElement("div");
  toast.id = "ccm-cocofolia-bridge-toast";
  toast.textContent = message;

  Object.assign(
    toast.style,
    {
      position: "fixed",
      top: "18px",
      left: "50%",
      transform: "translateX(-50%)",
      zIndex: "2147483647",
      padding: "10px 14px",
      borderRadius: "6px",
      background:
        kind === "error"
          ? "rgba(110, 32, 40, 0.96)"
          : "rgba(40, 37, 73, 0.96)",
      color: "#ffffff",
      fontFamily: "sans-serif",
      fontSize: "13px",
      boxShadow: "0 4px 18px rgba(0,0,0,.35)",
      pointerEvents: "none",
    },
  );

  document.documentElement.appendChild(toast);

  window.setTimeout(
    () => {
      toast.remove();
    },
    kind === "error" ? 6000 : 3500,
  );
}

function candidateDropTargets() {
  const targets = [];

  const center = document.elementFromPoint(
    Math.floor(window.innerWidth / 2),
    Math.floor(window.innerHeight / 2),
  );

  if (center) {
    targets.push(center);
  }

  const main = document.querySelector("main");

  if (main) {
    targets.push(main);
  }

  if (document.body) {
    targets.push(document.body);
  }

  if (document.documentElement) {
    targets.push(document.documentElement);
  }

  return [...new Set(targets)];
}

function makeDragEvent(type, dataTransfer) {
  return new DragEvent(
    type,
    {
      bubbles: true,
      cancelable: true,
      composed: true,
      dataTransfer,
      clientX: Math.floor(window.innerWidth / 2),
      clientY: Math.floor(window.innerHeight / 2),
    },
  );
}


let autoConfirmUntil = 0;

function armImportAutoConfirm() {
  autoConfirmUntil = Date.now() + 10000;

  window.dispatchEvent(
    new CustomEvent(
      "ccm-arm-native-confirm"
    )
  );
}

function looksLikeExternalImportDialog(dialog) {
  const text = (
    dialog?.innerText || ""
  )
    .replace(/\s+/g, " ")
    .trim();

  if (!text) {
    return false;
  }

  const hasExternal = text.includes("外部");

  const hasImportMeaning = [
    "データ",
    "読み込",
    "インポート",
    "ファイル",
  ].some(
    (word) => text.includes(word)
  );

  return (
    hasExternal
    && hasImportMeaning
  );
}

function findConfirmButton(dialog) {
  const candidates = [
    ...dialog.querySelectorAll(
      'button, [role="button"]'
    ),
  ];

  const preferred = [
    "はい",
    "読み込む",
    "インポート",
    "続行",
    "OK",
    "ＯＫ",
  ];

  for (const label of preferred) {
    const button = candidates.find(
      (candidate) => (
        candidate.innerText
        || candidate.textContent
        || ""
      )
        .replace(/\s+/g, " ")
        .trim() === label
    );

    if (button) {
      return button;
    }
  }

  return null;
}

function tryAutoConfirmImportDialog() {
  if (Date.now() > autoConfirmUntil) {
    return false;
  }

  const dialogs = [
    ...document.querySelectorAll(
      '[role="dialog"], [aria-modal="true"]'
    ),
  ];

  for (const dialog of dialogs) {
    if (
      !looksLikeExternalImportDialog(
        dialog
      )
    ) {
      continue;
    }

    const button = findConfirmButton(
      dialog
    );

    if (!button) {
      continue;
    }

    autoConfirmUntil = 0;

    window.setTimeout(
      () => {
        button.click();
      },
      60,
    );

    return true;
  }

  return false;
}

const ccmImportObserver =
  new MutationObserver(() => {
    tryAutoConfirmImportDialog();
  });

ccmImportObserver.observe(
  document.documentElement,
  {
    childList: true,
    subtree: true,
  },
);

function dispatchZipDrop(file) {
  armImportAutoConfirm();
  const dataTransfer = new DataTransfer();
  dataTransfer.items.add(file);

  const targets = candidateDropTargets();
  let target = null;

  for (const candidate of targets) {
    candidate.dispatchEvent(
      makeDragEvent(
        "dragenter",
        dataTransfer,
      ),
    );

    const over = makeDragEvent(
      "dragover",
      dataTransfer,
    );

    candidate.dispatchEvent(over);

    if (over.defaultPrevented) {
      target = candidate;
      break;
    }
  }

  if (!target) {
    target = targets[0] || document.body;
  }

  if (!target) {
    throw new Error(
      "ココフォリアのドロップ先を取得できませんでした。",
    );
  }

  target.dispatchEvent(
    makeDragEvent(
      "dragenter",
      dataTransfer,
    ),
  );

  target.dispatchEvent(
    makeDragEvent(
      "dragover",
      dataTransfer,
    ),
  );

  target.dispatchEvent(
    makeDragEvent(
      "drop",
      dataTransfer,
    ),
  );
}

async function downloadPendingFile(pending) {
  const prepared = await extensionMessage({
    type: "prepareFile",
    id: pending.id,
  });

  const output = new Uint8Array(
    prepared.size,
  );

  const chunkSize = prepared.chunkSize;

  for (
    let offset = 0;
    offset < prepared.size;
    offset += chunkSize
  ) {
    const chunk = await extensionMessage({
      type: "getFileChunk",
      id: pending.id,
      offset,
    });

    const bytes = base64ToBytes(
      chunk.data,
    );

    output.set(
      bytes,
      chunk.offset,
    );
  }

  await extensionMessage({
    type: "releaseFile",
    id: pending.id,
  });

  return new File(
    [output],
    pending.filename || "ccm_characters.zip",
    {
      type: "application/zip",
    },
  );
}

function roomIsReady() {
  return (
    location.hostname === "ccfolia.com"
    && location.pathname.startsWith("/rooms/")
    && Boolean(document.body)
  );
}

async function pollBridge() {
  if (busy || !roomIsReady()) {
    return;
  }

  let receiver;

  try {
    receiver = await extensionMessage({
      type: "canReceive",
    });
  } catch (error) {
    return;
  }

  if (!receiver.canReceive) {
    return;
  }

  let pending;

  try {
    pending = await extensionMessage({
      type: "claimPending",
    });
  } catch (error) {
    return;
  }

  if (!pending.pending) {
    return;
  }

  busy = true;

  try {
    showToast(
      "CCM: キャラクターZIPを受信しています…",
    );

    const file = await downloadPendingFile(
      pending,
    );

    dispatchZipDrop(file);

    await sleep(1200);

    await extensionMessage({
      type: "ack",
      id: pending.id,
    });

    showToast(
      "CCM: ココフォリアへZIPを投入しました。",
    );
  } catch (error) {
    try {
      await extensionMessage({
        type: "release",
        id: pending.id,
      });
    } catch (releaseError) {
    }

    showToast(
      `CCM連携エラー: ${
        error?.message || error
      }`,
      "error",
    );
  } finally {
    busy = false;
  }
}

window.setInterval(
  pollBridge,
  700,
);

window.setTimeout(
  pollBridge,
  400,
);
