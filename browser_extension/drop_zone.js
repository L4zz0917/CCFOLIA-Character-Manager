(() => {
  "use strict";

  const zone = document.getElementById("zone");
  const label = document.getElementById("label");
  const picker = document.getElementById("picker");
  const params = new URLSearchParams(window.location.search);
  const characterId = params.get("character_id") || "";
  const allowed = /\.(png|jpe?g|webp|bmp)$/i;
  const maxBytes = 12 * 1024 * 1024;
  let dragDepth = 0;
  let busy = false;

  function setState(text, className = "") {
    label.textContent = text;
    zone.classList.remove("dragging", "busy", "error");
    if (className) zone.classList.add(className);
  }

  function hasFiles(event) {
    return Array.from(event.dataTransfer?.types || []).includes("Files");
  }

  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error("画像を読み込めません。"));
      reader.onload = () => {
        const value = String(reader.result || "");
        const comma = value.indexOf(",");
        if (comma < 0) {
          reject(new Error("画像データが不正です。"));
          return;
        }
        resolve(value.slice(comma + 1));
      };
      reader.readAsDataURL(file);
    });
  }

  async function sendUpload(payload) {
    const response = await fetch(
      "http://127.0.0.1:17431/api/images/upload",
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json",
          "X-CCM-Client":
            "browser-extension",
        },
        body:
          JSON.stringify(payload),
      },
    );

    let data = null;

    try {
      data =
        await response.json();
    } catch {
      data = null;
    }

    if (
      !response.ok
      || !data?.ok
    ) {
      throw new Error(
        data?.error
        || `HTTP ${response.status}`
      );
    }

    return data;
  }

  async function uploadFiles(files) {
    if (busy) return;

    if (!characterId) {
      setState("キャラクターIDを取得できません。", "error");
      return;
    }

    const images = Array.from(files || []).filter((file) => allowed.test(file.name));

    if (!images.length) {
      setState("画像ファイルをドロップしてください。", "error");
      return;
    }

    busy = true;
    setState("画像を追加中…", "busy");

    try {
      let completed = 0;

      for (const file of images) {
        if (file.size > maxBytes) {
          throw new Error(`${file.name} は12MBを超えています。`);
        }

        const dataBase64 = await fileToBase64(file);

        await sendUpload({
          character_id: characterId,
          filename: file.name,
          data_base64: dataBase64,
        });

        completed += 1;
        setState(`${completed}/${images.length} 追加中…`, "busy");
      }

      setState(`${completed}枚追加しました`);

      window.parent.postMessage(
        {
          source: "ccm-extension-drop-zone",
          type: "uploaded",
          character_id: characterId,
          count: completed,
        },
        "*",
      );

      window.setTimeout(
        () => setState("画像をここへドラッグ＆ドロップ"),
        1200,
      );
    } catch (error) {
      setState(error?.message || "画像追加に失敗しました。", "error");
    } finally {
      busy = false;
      picker.value = "";
    }
  }

  window.addEventListener("dragenter", (event) => {
    if (busy || !hasFiles(event)) return;
    event.preventDefault();
    event.stopPropagation();
    dragDepth += 1;
    setState("ここにドロップ", "dragging");
  }, true);

  window.addEventListener("dragover", (event) => {
    if (busy || !hasFiles(event)) return;
    event.preventDefault();
    event.stopPropagation();
    if (event.dataTransfer) event.dataTransfer.dropEffect = "copy";
    setState("ここにドロップ", "dragging");
  }, true);

  window.addEventListener("dragleave", (event) => {
    if (busy || !hasFiles(event)) return;
    event.preventDefault();
    event.stopPropagation();
    dragDepth = Math.max(0, dragDepth - 1);
    if (dragDepth === 0) setState("画像をここへドラッグ＆ドロップ");
  }, true);

  window.addEventListener("drop", (event) => {
    if (busy || !hasFiles(event)) return;
    event.preventDefault();
    event.stopPropagation();
    dragDepth = 0;
    void uploadFiles(event.dataTransfer?.files);
  }, true);

  picker.addEventListener("change", () => {
    void uploadFiles(picker.files);
  });
})();
