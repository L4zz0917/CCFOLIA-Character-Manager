(() => {
  if (window.__ccmPanelInstalled) {
    return;
  }

  window.__ccmPanelInstalled = true;

  const ROOT_ID = "ccm-browser-panel-root";
  const STORAGE_KEY = "ccmFloatingButtonPosition";

  function sendExtensionMessage(message) {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        message,
        (response) => {
          const runtimeError = chrome.runtime.lastError;

          if (runtimeError) {
            reject(
              new Error(runtimeError.message),
            );
            return;
          }

          if (!response?.ok) {
            reject(
              new Error(
                response?.error
                || "CCM request failed",
              ),
            );
            return;
          }

          resolve(response);
        },
      );
    });
  }

  async function apiGet(path) {
    const response = await sendExtensionMessage({
      type: "ccmApi",
      method: "GET",
      path,
    });

    return response.data;
  }

  async function apiPost(path, body = {}) {
    const response = await sendExtensionMessage({
      type: "ccmApi",
      method: "POST",
      path,
      body,
    });

    return response.data;
  }

  function storageGet(key) {
    return new Promise((resolve) => {
      chrome.storage.local.get(
        [key],
        (value) => {
          resolve(value?.[key]);
        },
      );
    });
  }

  function storageSet(value) {
    return new Promise((resolve) => {
      chrome.storage.local.set(
        value,
        resolve,
      );
    });
  }

  function clamp(value, minimum, maximum) {
    return Math.min(
      maximum,
      Math.max(minimum, value),
    );
  }

  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = String(value ?? "");
    return div.innerHTML;
  }

  function buildGroupOptions(groups) {
    const byId = new Map(
      groups.map((group) => [
        String(group.id),
        group,
      ]),
    );
    const cache = new Map();

    function pathFor(id, seen = new Set()) {
      id = String(id);

      if (cache.has(id)) {
        return cache.get(id);
      }

      const group = byId.get(id);

      if (!group) {
        return id;
      }

      if (seen.has(id)) {
        return String(group.name || id);
      }

      const nextSeen = new Set(seen);
      nextSeen.add(id);

      let result = String(group.name || "");

      if (group.parent_group_id) {
        result = `${pathFor(
          group.parent_group_id,
          nextSeen,
        )} / ${result}`;
      }

      cache.set(id, result);
      return result;
    }

    return groups
      .map((group) => ({
        id: String(group.id),
        label: pathFor(group.id),
      }))
      .sort((a, b) => (
        a.label.localeCompare(
          b.label,
          "ja",
        )
      ));
  }

  function install() {
    if (
      !location.hostname.endsWith("ccfolia.com")
      || !location.pathname.startsWith("/rooms/")
      || document.getElementById(ROOT_ID)
    ) {
      return;
    }

    const host = document.createElement("div");
    host.id = ROOT_ID;
    host.style.position = "fixed";
    host.style.inset = "0";
    host.style.pointerEvents = "none";
    host.style.zIndex = "2147483646";

    const shadow = host.attachShadow({
      mode: "open",
    });

    shadow.innerHTML = `
      <style>
        :host {
          all: initial;
        }

        * {
          box-sizing: border-box;
        }

        #ccmButton {
          position: fixed;
          left: 18px;
          top: calc(100vh - 62px);
          width: 44px;
          height: 44px;
          border: 1px solid rgba(134, 122, 220, .74);
          border-radius: 14px;
          background:
            linear-gradient(
              145deg,
              rgba(55, 50, 91, .98),
              rgba(30, 29, 43, .98)
            );
          color: #f8f7ff;
          font: 700 11px/1 "Segoe UI", "Yu Gothic UI", sans-serif;
          letter-spacing: .4px;
          box-shadow:
            0 8px 26px rgba(0, 0, 0, .38);
          cursor: grab;
          user-select: none;
          pointer-events: auto;
          display: grid;
          place-items: center;
          transition:
            border-color .15s ease,
            transform .15s ease,
            box-shadow .15s ease;
        }

        #ccmButton:hover {
          border-color: #9b90ef;
          box-shadow:
            0 10px 30px rgba(0, 0, 0, .46);
        }

        #ccmButton:active {
          cursor: grabbing;
          transform: scale(.96);
        }

        #ccmButton.online::after,
        #ccmButton.offline::after {
          content: "";
          position: absolute;
          right: 4px;
          bottom: 4px;
          width: 7px;
          height: 7px;
          border-radius: 50%;
          border: 1px solid rgba(0,0,0,.6);
        }

        #ccmButton.online::after {
          background: #58d68d;
        }

        #ccmButton.offline::after {
          background: #e36d75;
        }


        /* IM3_TOOLKIT_SHELL */
        #toolkitMenu {
          position: fixed;
          display: none;
          width: 168px;
          padding: 7px;
          border: 1px solid #343342;
          border-radius: 11px;
          background: rgba(18, 18, 22, .985);
          box-shadow:
            0 14px 42px rgba(0, 0, 0, .48);
          pointer-events: auto;
          font-family:
            "Segoe UI",
            "Yu Gothic UI",
            "Meiryo",
            sans-serif;
          z-index: 2;
        }

        #toolkitMenu.open {
          display: grid;
          gap: 6px;
        }

        .toolkitModuleButton {
          appearance: none;
          width: 100%;
          padding: 10px 11px;
          border: 1px solid #393844;
          border-radius: 8px;
          background: #24232a;
          color: #e9e8ee;
          cursor: pointer;
          text-align: left;
          font:
            600 12px/1.2
            "Segoe UI",
            "Yu Gothic UI",
            sans-serif;
        }

        .toolkitModuleButton:hover {
          border-color: #756db8;
          background: #2c2a35;
        }

        /* IM4_IMAGES_PANEL */
        .imageManagerToolbar {
          display: grid;
          gap: 8px;
          padding: 10px;
          border-bottom: 1px solid #2d2c35;
          background: #18171d;
        }

        .imageManagerSearchRow {
          display: grid;
          grid-template-columns: auto minmax(0, 1fr) auto;
          gap: 7px;
          align-items: center;
        }

        .imageManagerSearch {
          width: 100%;
          min-width: 0;
          height: 32px;
          padding: 0 10px;
          border: 1px solid #3c3a47;
          border-radius: 7px;
          outline: none;
          background: #222128;
          color: #f0eff5;
          font: 12px/1.2 "Segoe UI", "Yu Gothic UI", sans-serif;
        }

        .imageManagerSearch:focus {
          border-color: #766ec0;
        }

        .imageManagerFilterRow {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 7px;
          align-items: center;
        }

        .imageManagerFilterRow select {
          min-width: 0;
          width: 100%;
          height: 31px;
          border: 1px solid #3b3945;
          border-radius: 7px;
          background: #24232a;
          color: #e6e4ed;
          padding: 0 8px;
          font-size: 12px;
        }

        .imageTaglessButton,
        .imagePreviewToggleButton {
          height: 31px;
          padding: 0 10px;
          border: 1px solid #3b3945;
          border-radius: 7px;
          background: #24232a;
          color: #c9c6d2;
          cursor: pointer;
          font-size: 11px;
          white-space: nowrap;
        }

        .imageTaglessButton.active,
        .imagePreviewToggleButton.active {
          border-color: #8176d3;
          background: #38334e;
          color: #ffffff;
        }

        /* IM6_PREVIEW_HEADER_LAYOUT */
        .imagePreviewHeaderButton {
          appearance: none;
          height: 29px;
          padding: 0 7px;
          border: 1px solid #393844;
          border-radius: 7px;
          background: #24232a;
          color: #c9c6d2;
          cursor: pointer;
          font: 600 9px/1 "Segoe UI", "Yu Gothic UI", sans-serif;
          white-space: nowrap;
        }

        .imagePreviewHeaderButton:hover {
          border-color: #625b83;
          background: #302e38;
        }

        .imagePreviewHeaderButton.active {
          border-color: #8176d3;
          background: #38334e;
          color: #ffffff;
        }

        .imageTagChipRow {
          display: none;
          gap: 6px;
          overflow-x: auto;
          padding-bottom: 2px;
          scrollbar-width: thin;
        }

        .imageTagChipRow.open {
          display: flex;
        }

        .imageTagChip {
          flex: 0 0 auto;
          max-width: 150px;
          padding: 5px 8px;
          border: 1px solid #3c3a47;
          border-radius: 999px;
          background: #24232a;
          color: #bcb9c7;
          cursor: pointer;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-size: 10px;
        }

        .imageTagChip.active {
          border-color: #887ee0;
          background: #3c3657;
          color: #ffffff;
        }

        /* IMAGES_BROWSER_CARD_SIZE_V1 */
        .imageAssetGrid {
          flex: 1;
          min-height: 0;
          overflow: auto;
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          grid-auto-rows: max-content;
          align-content: start;
          gap: 10px;
          padding: 10px;
          background: #141319;
          scrollbar-width: thin;
        }

        .imageAssetCard {
          min-width: 0;
          align-self: start;
          border: 1px solid #302f38;
          border-radius: 8px;
          overflow: hidden;
          background: #1d1c22;
          color: #e9e7ef;
        }

        /* IM5_IMAGE_BACKGROUND_APPLY */
        /* IM6_IMAGE_AUTO_UPLOAD */
        .imageAssetCard {
          cursor: pointer;
        }

        .imageAssetCard.ccfoliaReady {
          cursor: pointer;
          transition:
            border-color 120ms ease,
            transform 120ms ease,
            opacity 120ms ease;
        }

        .imageAssetCard.ccfoliaReady:hover {
          border-color: #756db8;
          transform: translateY(-1px);
        }

        .imageAssetCard.applying {
          pointer-events: none;
          opacity: .58;
        }

        .imageAssetCard.applied {
          border-color: #8d82e0;
        }

        /* IMAGES_BROWSER_WIDE_THUMB_V1 */
        .imageAssetThumbWrap {
          position: relative;
          width: 100%;
          height: 108px;
          overflow: hidden;
          display: grid;
          place-items: center;
          background:
            linear-gradient(
              135deg,
              #222129,
              #17161b
            );
        }

        .imageAssetThumb {
          width: 100%;
          height: 100%;
          object-fit: cover;
          display: block;
        }

        .imageAssetPlaceholder {
          color: #6f6c78;
          font-size: 10px;
          letter-spacing: .4px;
        }

        .imageAssetBadge {
          position: absolute;
          right: 5px;
          top: 5px;
          padding: 3px 5px;
          border: 1px solid rgba(145, 135, 222, .55);
          border-radius: 5px;
          background: rgba(35, 31, 53, .9);
          color: #d9d4ff;
          font-size: 8px;
          line-height: 1;
        }

        .imageAssetName {
          padding: 8px 9px 9px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-size: 11px;
          line-height: 1.35;
          color: #dddbe5;
        }

        .imageManagerEmpty {
          grid-column: 1 / -1;
          padding: 36px 10px;
          color: #777481;
          text-align: center;
          font-size: 12px;
        }

        .imageManagerFooter {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          padding: 8px 10px;
          border-top: 1px solid #2d2c35;
          background: #19181e;
          color: #8f8c98;
          font-size: 10px;
        }

        /* IMAGES_BROWSER_PAGINATION_PANEL */
        .imageManagerPager {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 5px;
          min-width: 120px;
        }

        .imageManagerPageButton {
          width: 28px;
          height: 24px;
          padding: 0;
          border: 1px solid #3a3844;
          border-radius: 6px;
          background: #24232a;
          color: #d8d5df;
          cursor: pointer;
          font-size: 14px;
          line-height: 1;
        }

        .imageManagerPageButton:hover:not(:disabled) {
          border-color: #6e66a9;
          background: #302d3a;
        }

        .imageManagerPageButton:disabled {
          opacity: .32;
          cursor: default;
        }

        .imageManagerPageInfo {
          min-width: 66px;
          text-align: center;
          white-space: nowrap;
          color: #aaa6b3;
        }

        .imageManagerStatus.ok {
          color: #7ed6a5;
        }

        .imageManagerStatus.error {
          color: #e3848b;
        }

        #imageHoverPreview {
          position: fixed;
          display: none;
          max-width: min(560px, calc(100vw - 32px));
          max-height: min(430px, calc(100vh - 32px));
          padding: 7px;
          border: 1px solid #44414f;
          border-radius: 10px;
          background: rgba(16, 15, 20, .985);
          box-shadow: 0 16px 48px rgba(0, 0, 0, .52);
          pointer-events: none;
          z-index: 20;
        }

        #imageHoverPreview.open {
          display: block;
        }

        #imageHoverPreview img {
          display: block;
          max-width: min(540px, calc(100vw - 50px));
          max-height: min(390px, calc(100vh - 74px));
          object-fit: contain;
          border-radius: 6px;
          background: #0d0d10;
        }

        #imageHoverPreviewName {
          max-width: 540px;
          padding: 7px 3px 1px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          color: #e6e4ec;
          font-size: 11px;
        }

        /* MEDIA_PANEL_DRAGDROP_V1 */
        .mediaDropOverlay {
          position: absolute;
          inset: 0;
          z-index: 2147483000;
          display: none;
          place-items: center;
          padding: 22px;
          border: 2px dashed #8a7ac8;
          border-radius: 12px;
          background: rgba(37, 31, 57, .92);
          color: #f5f2ff;
          text-align: center;
          font-size: 15px;
          font-weight: 750;
          letter-spacing: .02em;
          pointer-events: none;
          box-sizing: border-box;
        }

        .mediaDropOverlay .mediaDropSub {
          display: block;
          margin-top: 7px;
          color: #c1bbd4;
          font-size: 11px;
          font-weight: 500;
        }

        #imagesPanel.mediaDropActive
        .mediaDropOverlay,
        #bgmPanel.mediaDropActive
        .mediaDropOverlay {
          display: grid;
        }

        /* BGM_BROWSER_PANEL_V1 */
        .bgmManagerToolbar {
          display: grid;
          gap: 7px;
          padding: 9px;
          border-bottom: 1px solid #2d2c35;
          background: #18171d;
        }

        .bgmSearchRow {
          display: grid;
          grid-template-columns: auto auto minmax(0,1fr);
          gap: 6px;
        }

        .bgmFilterRow {
          display: grid;
          grid-template-columns: minmax(0,1fr) minmax(0,1fr) auto;
          gap: 6px;
        }

        .bgmSearchRow input,
        .bgmFilterRow select {
          min-width: 0;
          height: 31px;
          border: 1px solid #3b3945;
          border-radius: 7px;
          background: #24232a;
          color: #e6e4ed;
          padding: 0 8px;
          font-size: 11px;
        }

        .bgmModeButton,
        .bgmTaglessButton {
          height: 31px;
          padding: 0 8px;
          border: 1px solid #3b3945;
          border-radius: 7px;
          background: #24232a;
          color: #c9c6d2;
          cursor: pointer;
          font-size: 10px;
        }

        .bgmModeButton.active,
        .bgmTaglessButton.active {
          border-color: #8176d3;
          background: #38334e;
          color: #fff;
        }

        .bgmTagChipRow {
          display: flex;
          gap: 5px;
          overflow-x: auto;
          scrollbar-width: thin;
        }

        .bgmTagChip {
          flex: 0 0 auto;
          max-width: 130px;
          padding: 4px 7px;
          border: 1px solid #3c3a47;
          border-radius: 999px;
          background: #24232a;
          color: #bcb9c7;
          cursor: pointer;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-size: 9px;
        }

        .bgmTagChip.active {
          border-color: #887ee0;
          background: #3c3657;
          color: #fff;
        }

        .bgmAssetList {
          flex: 1;
          min-height: 0;
          overflow: auto;
          display: grid;
          align-content: start;
          gap: 6px;
          padding: 9px;
          background: #141319;
          scrollbar-width: thin;
        }

        .bgmAssetCard {
          display: grid;
          grid-template-columns: 42px minmax(0,1fr);
          gap: 8px;
          align-items: center;
          min-width: 0;
          padding: 7px;
          border: 1px solid #302f38;
          border-radius: 8px;
          background: #1d1c22;
          color: #e9e7ef;
        }

        .bgmAssetCard.playing {
          border-color: #8176d3;
          background: #242033;
        }

        .bgmAssetCard.applying {
          opacity: .62;
        }

        .bgmPlayButton {
          width: 38px;
          height: 38px;
          border: 1px solid #4a4659;
          border-radius: 50%;
          background: #292633;
          color: #f3efff;
          cursor: pointer;
          font-size: 14px;
        }

        .bgmPlayButton:hover:not(:disabled) {
          border-color: #8f83d8;
          background: #3b3552;
        }

        .bgmPlayButton:disabled {
          opacity: .35;
          cursor: default;
        }

        .bgmAssetName {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          font-size: 11px;
          font-weight: 700;
        }

        .bgmAssetMeta {
          margin-top: 3px;
          color: #aaa6b4;
          font-size: 9px;
        }

        .bgmAssetFlags {
          display: flex;
          flex-wrap: wrap;
          gap: 4px;
          margin-top: 5px;
        }

        .bgmAssetFlags span {
          padding: 2px 5px;
          border: 1px solid #3a3843;
          border-radius: 999px;
          color: #aba7b5;
          font-size: 8px;
        }

        .bgmManagerFooter {
          display: flex;
          align-items: center;
          gap: 6px;
          min-height: 32px;
          padding: 5px 9px;
          border-top: 1px solid #2d2c35;
          background: #17161c;
          color: #aaa7b4;
          font-size: 10px;
        }

        .bgmManagerFooter button {
          height: 24px;
          border: 1px solid #3a3844;
          border-radius: 6px;
          background: #24232a;
          color: #d3d0da;
          cursor: pointer;
        }

        .bgmManagerFooter button:disabled {
          opacity: .35;
          cursor: default;
        }

        .bgmManagerFooter .spacer {
          flex: 1;
        }

        .bgmManagerEmpty {
          padding: 30px 12px;
          color: #85818e;
          text-align: center;
          font-size: 11px;
        }

        .modulePlaceholderBody {
          flex: 1;
          display: grid;
          place-items: center;
          padding: 24px;
          color: #aaa7b4;
          text-align: center;
        }

        .modulePlaceholderBody strong {
          display: block;
          margin-bottom: 8px;
          color: #f0eef6;
          font-size: 15px;
        }

        #panel,
        #imagesPanel,
        #bgmPanel {
          position: fixed;
          width: min(390px, calc(100vw - 26px));
          height: min(72vh, 720px);
          min-height: 420px;
          border: 1px solid #343342;
          border-radius: 13px;
          background: rgba(18, 18, 22, .985);
          color: #e9e8ee;
          box-shadow:
            0 18px 58px rgba(0, 0, 0, .52);
          overflow: hidden;
          display: none;
          pointer-events: auto;
          font-family:
            "Segoe UI",
            "Yu Gothic UI",
            "Meiryo",
            sans-serif;
          font-size: 13px;
        }

        #panel.open,
        #imagesPanel.open,
        #bgmPanel.open {
          display: flex;
          flex-direction: column;
        }

        .header {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 11px;
          border-bottom: 1px solid #2d2c34;
          background: #15151a;
        }

        .title {
          font-weight: 750;
          letter-spacing: .5px;
          flex: 1;
        }

        .status {
          font-size: 11px;
          color: #92909c;
        }

        .iconButton,
        .actionButton,
        .modeButton,
        .sendOne {
          appearance: none;
          border: 1px solid #393844;
          background: #24232a;
          color: #e9e8ee;
          border-radius: 7px;
          cursor: pointer;
          font: inherit;
        }

        .iconButton {
          width: 29px;
          height: 29px;
          padding: 0;
        }

        .toolbar {
          display: grid;
          grid-template-columns: auto 1fr;
          gap: 7px;
          padding: 9px 10px 6px;
        }

        .modeGroup {
          display: flex;
        }

        .modeButton {
          padding: 6px 8px;
          border-radius: 0;
          font-size: 11px;
        }

        .modeButton:first-child {
          border-radius: 7px 0 0 7px;
        }

        .modeButton:last-child {
          border-radius: 0 7px 7px 0;
          border-left: none;
        }

        .modeButton.active {
          background: #4e476e;
          color: #fff;
        }

        .tagSearchRow {
          position: relative;
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto;
          gap: 5px;
          min-width: 0;
        }

        .tagSearchRow #search {
          min-width: 0;
        }

        .tagSearchField {
          display: flex;
          align-items: center;
          gap: 4px;
          min-width: 0;
          overflow-x: auto;
          overflow-y: hidden;
          border: 1px solid #373642;
          border-radius: 7px;
          background: #1c1b21;
          padding: 2px 5px;
          scrollbar-width: none;
        }

        .tagSearchField::-webkit-scrollbar {
          display: none;
        }

        .tagSearchField:focus-within {
          border-color: #706399;
        }

        .tagSearchTokens {
          display: none;
          align-items: center;
          gap: 4px;
          flex: 0 0 auto;
        }

        .tagSearchToken {
          appearance: none;
          display: inline-flex;
          align-items: center;
          gap: 5px;
          flex: 0 0 auto;
          max-width: 150px;
          border: 1px solid #625783;
          border-radius: 999px;
          background: #3d3555;
          color: #f4f0ff;
          padding: 4px 7px;
          font: inherit;
          font-size: 10px;
          line-height: 1;
          cursor: pointer;
        }

        .tagSearchToken > span:first-child {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .tagSearchToken:hover {
          border-color: #8779b7;
          background: #4a4067;
        }

        .tagSearchTokenRemove {
          flex: 0 0 auto;
          opacity: .75;
          font-size: 11px;
        }

        .tagSearchField #search {
          flex: 1 0 92px;
          width: auto;
          min-width: 92px;
          border: 0;
          border-radius: 0;
          background: transparent;
          padding: 5px 2px;
          outline: none;
          box-shadow: none;
        }

        .tagDropdownButton {
          display: none;
          width: 32px;
          min-width: 32px;
          border: 1px solid #373642;
          border-radius: 7px;
          background: #24232a;
          color: #d9d6e0;
          font: inherit;
          cursor: pointer;
        }

        .tagDropdownButton:hover,
        .tagDropdownButton.active {
          border-color: #706399;
          background: #302d3a;
          color: #fff;
        }

        .tagSuggestMenu {
          position: absolute;
          top: calc(100% + 4px);
          left: 0;
          right: 0;
          z-index: 2147483647;
          display: none;
          max-height: 250px;
          overflow-y: auto;
          padding: 5px;
          border: 1px solid #3a3745;
          border-radius: 8px;
          background: #19181f;
          box-shadow: 0 10px 28px rgba(0, 0, 0, .42);
        }

        .tagSuggestMenu.open {
          display: block;
        }

        .tagSuggestItem {
          appearance: none;
          display: block;
          width: 100%;
          border: 0;
          border-radius: 6px;
          background: transparent;
          color: #dedbe5;
          padding: 7px 8px;
          text-align: left;
          font: inherit;
          font-size: 11px;
          cursor: pointer;
        }

        .tagSuggestItem:hover,
        .tagSuggestItem.active {
          background: #39334c;
          color: #fff;
        }

        .tagSuggestEmpty {
          padding: 8px;
          color: #85818e;
          font-size: 10px;
          text-align: center;
        }

        #search {
          width: 100%;
          border: 1px solid #373642;
          background: #1d1c22;
          color: #efedf4;
          border-radius: 7px;
          padding: 7px 9px;
          outline: none;
          font: inherit;
        }

        #search:focus,
        #groupSelect:focus {
          border-color: #7368b1;
        }

        .groupRow {
          padding: 0 10px 8px;
        }

        #groupSelect {
          width: 100%;
          border: 1px solid #373642;
          background: #1d1c22;
          color: #e9e8ee;
          border-radius: 7px;
          padding: 7px 8px;
          outline: none;
          font: inherit;
        }

        #list {
          flex: 1;
          overflow: auto;
          padding: 3px 7px 7px;
        }

        .row {
          display: grid;
          grid-template-columns: 24px 40px 1fr auto;
          gap: 7px;
          align-items: center;
          min-height: 43px;
          padding: 5px 6px;
          border: 1px solid transparent;
          border-radius: 8px;
        }

        .row:hover {
          background: #1d1c23;
          border-color: #2c2a35;
        }

        .check {
          width: 16px;
          height: 16px;
          accent-color: #7568b4;
        }

        .charIcon {
          width: 34px;
          height: 34px;
          border: 1px solid #3a3946;
          border-radius: 8px;
          overflow: hidden;
          background: linear-gradient(
            145deg,
            #22212a,
            #17171d
          );
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          user-select: none;
        }

        .charIcon img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          object-position: center 13%;
          display: block;
        }

        .charFallback {
          color: #c7c3d5;
          font-size: 13px;
          font-weight: 750;
          line-height: 1;
        }

        .charText {
          min-width: 0;
        }

        .charName {
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          font-weight: 650;
          color: #f1eff5;
        }

        .player {
          margin-top: 2px;
          color: #85828e;
          font-size: 11px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .sendOne {
          padding: 5px 8px;
          font-size: 11px;
        }

        .empty,
        .error {
          padding: 24px 12px;
          text-align: center;
          color: #8d8995;
        }

        .error {
          color: #d9858b;
        }

        .bulkBar {
          display: none;
          align-items: center;
          gap: 6px;
          padding: 7px 10px;
          border-top: 1px solid #292831;
          background: #18181e;
        }

        .bulkBar.active {
          display: flex;
        }

        .bulkBar .bulkSpacer {
          flex: 1;
        }

        .bulkButton {
          appearance: none;
          border: 1px solid #383640;
          border-radius: 6px;
          background: #24232a;
          color: #d8d5df;
          padding: 5px 7px;
          font: inherit;
          font-size: 10px;
          cursor: pointer;
        }

        .bulkButton:hover {
          background: #302e38;
          border-color: #4a4657;
        }

        .bulkButton.danger {
          color: #efa0a5;
        }

        .bulkButton:disabled {
          cursor: default;
          opacity: .42;
        }

        .tagCardArea {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          padding: 7px 10px;
          border-top: 1px solid #292831;
          background: #17171d;
        }

        .tagCardArea.hidden {
          display: none;
        }

        .tagCard {
          appearance: none;
          border: 1px solid #3a3743;
          border-radius: 999px;
          background: #25242b;
          color: #d8d5df;
          padding: 5px 9px;
          font: inherit;
          font-size: 10px;
          line-height: 1;
          cursor: pointer;
        }

        .tagCard:hover {
          border-color: #625a78;
          background: #302d38;
        }

        .tagCard.active {
          border-color: #8172b6;
          background: #42395d;
          color: #fff;
        }

        .tagCard.removable {
          display: inline-flex;
          align-items: center;
          gap: 5px;
        }

        .tagCardRemove {
          opacity: .75;
          font-size: 11px;
        }

        .tagPickerWrap {
          display: flex;
          flex-direction: column;
          gap: 9px;
        }

        .tagPickerCards {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          max-height: 220px;
          overflow-y: auto;
          padding: 2px;
        }

        .tagPickerInput {
          width: 100%;
          border: 1px solid #3c3945;
          border-radius: 7px;
          background: #17171c;
          color: #ece9f1;
          padding: 8px 9px;
          font: inherit;
          outline: none;
        }

        .tagPickerInput:focus {
          border-color: #706399;
        }

        .editorTagCards {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-bottom: 8px;
        }

        .footer {
          display: flex;
          align-items: center;
          gap: 7px;
          padding: 9px 10px;
          border-top: 1px solid #2d2c34;
          background: #15151a;
        }

        #selectedCount {
          flex: 1;
          color: #85828e;
          font-size: 11px;
        }

        .actionButton {
          padding: 7px 10px;
        }

        .actionButton.primary {
          background: #625799;
          border-color: #7569aa;
          color: #fff;
          font-weight: 650;
        }

        .actionButton:disabled,
        .sendOne:disabled {
          cursor: default;
          opacity: .45;
        }

        #loading {
          height: 2px;
          background: transparent;
        }

        #loading.active {
          background:
            linear-gradient(
              90deg,
              transparent,
              #796db2,
              transparent
            );
          background-size: 45% 100%;
          animation: loadingMove 1s linear infinite;
        }


        .footerActions {
          display: flex;
          gap: 7px;
        }

        .smallAction {
          appearance: none;
          border: 1px solid #393844;
          background: #24232a;
          color: #e9e8ee;
          border-radius: 7px;
          padding: 7px 9px;
          cursor: pointer;
          font: inherit;
          font-size: 11px;
        }

        .smallAction:hover,
        .contextMenu button:hover {
          background: #302e3a;
        }

        .row {
          cursor: default;
        }

        .charText {
          cursor: pointer;
        }

        .charText:hover .charName {
          text-decoration: underline;
          text-underline-offset: 2px;
        }

        .memoPane {
          position: absolute;
          inset: 0;
          z-index: 20;
          display: none;
          flex-direction: column;
          background: #121216;
        }

        .memoPane.open {
          display: flex;
        }

        .memoHeader {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 11px;
          border-bottom: 1px solid #2d2c34;
          background: #15151a;
        }

        .memoCharacterPreview,
        .editorCharacterPreview {
          flex: 0 0 auto;
          overflow: hidden;
          display: flex;
          align-items: center;
          justify-content: center;
          border: 1px solid #3a3946;
          background:
            linear-gradient(
              145deg,
              #22212a,
              #17171d
            );
          box-shadow: inset 0 1px 0 rgba(255,255,255,.03);
        }

        .memoCharacterPreview {
          width: 36px;
          height: 36px;
          border-radius: 9px;
        }

        .editorCharacterPreview {
          width: 46px;
          height: 46px;
          border-radius: 10px;
        }

        .memoCharacterPreview img,
        .editorCharacterPreview img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          object-position: center 13%;
          display: block;
        }

        .memoCharacterFallback,
        .editorCharacterFallback {
          font-weight: 750;
          line-height: 1;
          user-select: none;
        }

        .memoCharacterFallback {
          font-size: 14px;
          color: #cbc8d8;
        }

        .editorCharacterFallback {
          font-size: 18px;
          color: #cbc8d8;
        }

        .memoHeaderText,
        .editorHeaderText {
          min-width: 0;
          display: flex;
          flex-direction: column;
        }

        .memoHeaderText {
          flex: 1;
          gap: 2px;
        }

        .memoName {
          min-width: 0;
          font-weight: 750;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .memoStatus {
          color: #94929d;
          font-size: 11px;
        }

        #quickMemo {
          flex: 1;
          width: 100%;
          resize: none;
          border: none;
          outline: none;
          background: #17171c;
          color: #eeeef3;
          padding: 14px;
          font: 13px/1.65 "Segoe UI", "Yu Gothic UI", sans-serif;
        }

        .contextMenu {
          position: fixed;
          z-index: 40;
          pointer-events: auto;
          min-width: 178px;
          padding: 5px;
          border: 1px solid #3b3948;
          border-radius: 9px;
          background: #18181e;
          box-shadow: 0 12px 34px rgba(0,0,0,.45);
          display: none;
        }

        .contextMenu.open {
          display: block;
        }

        .contextMenu button {
          display: block;
          width: 100%;
          border: 0;
          background: transparent;
          color: #ecebf2;
          text-align: left;
          border-radius: 6px;
          padding: 8px 10px;
          cursor: pointer;
          font: inherit;
        }

        .contextMenu .danger {
          color: #ef8d94;
        }

        .groupTools {
          display: grid;
          grid-template-columns: 1fr auto;
          gap: 6px;
        }

        .modalBackdrop {
          position: fixed;
          inset: 0;
          z-index: 50;
          pointer-events: auto;
          display: none;
          align-items: center;
          justify-content: center;
          background: rgba(0, 0, 0, .48);
        }

        .modalBackdrop.open {
          display: flex;
        }

        .modalCard {
          width: min(330px, calc(100vw - 40px));
          border: 1px solid #3a3946;
          border-radius: 12px;
          background: #19191f;
          box-shadow: 0 20px 50px rgba(0,0,0,.5);
          padding: 14px;
        }

        .modalTitle {
          font-weight: 750;
          margin-bottom: 11px;
        }

        .modalField,
        .modalSelect {
          width: 100%;
          border: 1px solid #3a3946;
          border-radius: 7px;
          background: #222129;
          color: #f1f0f5;
          padding: 8px 9px;
          font: inherit;
          outline: none;
          margin-bottom: 10px;
        }

        .modalButtons {
          display: flex;
          justify-content: flex-end;
          gap: 7px;
        }

        .modalButtons button {
          appearance: none;
          border: 1px solid #3d3b48;
          border-radius: 7px;
          background: #25242c;
          color: #eeeef2;
          padding: 7px 12px;
          cursor: pointer;
          font: inherit;
        }

        .modalButtons .primary {
          background: #514a78;
          border-color: #655c97;
        }

        .editorBackdrop {
          position: fixed;
          inset: 0;
          z-index: 60;
          display: none;
          align-items: center;
          justify-content: center;
          padding: 18px;
          background: rgba(0, 0, 0, .58);
          pointer-events: auto;
          font-family: "Segoe UI", "Yu Gothic UI", "Meiryo", sans-serif;
          color: #ecebf2;
        }

        .editorBackdrop.open {
          display: flex;
        }

        #editorClose {
          position: absolute;
          top: 10px;
          right: 10px;
          z-index: 8;
          width: 36px;
          height: 36px;
          padding: 0;
          border: 1px solid #4a4655;
          border-radius: 8px;
          background: #27262d;
          color: #e6e3eb;
          font-size: 20px;
          line-height: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
        }

        #editorClose:hover {
          background: #35323d;
          border-color: #716781;
          color: #ffffff;
        }

        .editorWindow {
          position: relative;
          width: min(1040px, calc(100vw - 36px));
          height: min(820px, calc(100vh - 36px));
          min-width: min(700px, calc(100vw - 36px));
          min-height: min(520px, calc(100vh - 36px));
          display: flex;
          flex-direction: column;
          overflow: hidden;
          border: 1px solid #3d3a4a;
          border-radius: 13px;
          background: #141419;
          box-shadow: 0 24px 80px rgba(0,0,0,.62);
        }

        .editorHeader {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 11px 58px 11px 13px;
          border-bottom: 1px solid #302f39;
          background: #18181e;
        }

        .editorTitle {
          flex: 1;
          min-width: 0;
          font-weight: 750;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .editorSaveState {
          color: #97949f;
          font-size: 11px;
        }

        .editorTabs {
          display: flex;
          gap: 2px;
          padding: 7px 8px 0;
          overflow-x: auto;
          border-bottom: 1px solid #302f39;
          background: #16161b;
        }

        .editorTab {
          flex: 1 0 auto;
          min-width: 92px;
          appearance: none;
          border: 1px solid transparent;
          border-bottom: none;
          border-radius: 7px 7px 0 0;
          background: transparent;
          color: #a5a2ae;
          padding: 8px 9px;
          cursor: pointer;
          font: 12px "Segoe UI", "Yu Gothic UI", sans-serif;
        }

        .editorTab.active {
          background: #24222d;
          border-color: #403d4e;
          color: #f3f1f7;
        }

        .editorBody {
          flex: 1;
          min-height: 0;
          overflow: auto;
          padding: 14px;
          background: #121217;
        }

        .editorFooter {
          display: flex;
          justify-content: flex-end;
          gap: 8px;
          padding: 10px 12px;
          border-top: 1px solid #302f39;
          background: #18181e;
        }

        .editorButton,
        .editorDanger,
        .editorAdd {
          appearance: none;
          border: 1px solid #403e4b;
          border-radius: 7px;
          background: #26252d;
          color: #eeedf2;
          padding: 7px 11px;
          cursor: pointer;
          font: 12px "Segoe UI", "Yu Gothic UI", sans-serif;
        }

        .editorButton.primary {
          background: #5d548d;
          border-color: #7568aa;
          color: #fff;
          font-weight: 650;
        }

        .editorDanger {
          color: #ef969c;
          padding: 6px 9px;
        }

        .editorAdd {
          margin-top: 9px;
        }

        .editorImageSection {
          margin-bottom: 15px;
          padding: 11px;
          border: 1px solid #302e39;
          border-radius: 10px;
          background: #17171d;
        }

        .editorImageHead {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 9px;
        }

        .editorImageTitle {
          flex: 1;
          font-size: 12px;
          font-weight: 750;
          color: #e5e3ea;
        }

        .editorImageDrop {
          position: relative;
          min-height: 98px;
          border: 1px dashed #464251;
          border-radius: 9px;
          padding: 9px;
          transition: border-color .12s ease, background .12s ease;
        }

        .editorImageDrop.dragging {
          border-color: #8073bc;
          background: rgba(111, 96, 173, .10);
        }

        .editorExtensionDropFrame {
          display: block;
          width: 100%;
          height: 70px;
          margin: 0 0 9px;
          border: 0;
          border-radius: 8px;
          background: transparent;
          pointer-events: auto;
        }

        .editorImageEmpty {
          padding: 25px 10px;
          text-align: center;
          color: #85828f;
          font-size: 11px;
        }

        .editorImageStrip {
          display: flex;
          gap: 9px;
          overflow-x: auto;
          padding-bottom: 3px;
        }

        .editorImageCard {
          flex: 0 0 112px;
          min-width: 112px;
          border: 1px solid #34323d;
          border-radius: 9px;
          overflow: hidden;
          background: #1c1b22;
        }

        .editorImageThumb {
          position: relative;
          width: 100%;
          height: 94px;
          background: #111116;
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
        }

        .editorImageThumb img {
          width: 100%;
          height: 100%;
          object-fit: cover;
          object-position: center 13%;
          display: block;
        }

        .editorImageBadge {
          position: absolute;
          top: 5px;
          left: 5px;
          padding: 3px 5px;
          border-radius: 5px;
          background: rgba(91, 79, 142, .92);
          color: #fff;
          font-size: 9px;
          font-weight: 750;
        }

        .editorImageLabel {
          padding: 6px 7px 2px;
          color: #aaa7b1;
          font-size: 10px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .editorImageActions {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 3px;
          padding: 5px;
        }

        .editorImageActions button {
          appearance: none;
          min-width: 0;
          border: 1px solid #393744;
          border-radius: 5px;
          background: #26252c;
          color: #d9d7df;
          padding: 4px 2px;
          cursor: pointer;
          font-size: 9px;
        }

        .editorImageActions button:hover {
          background: #312f3a;
        }

        .editorImageActions button:disabled {
          cursor: default;
          opacity: .34;
        }

        .editorImageActions .danger {
          color: #ef969c;
        }

        .editorImageNote {
          margin-top: 7px;
          color: #85818e;
          font-size: 10px;
          line-height: 1.5;
        }

        .editorDropOverlay {
          position: fixed;
          z-index: 2147483647;
          display: none;
          align-items: center;
          justify-content: center;
          border: 2px dashed #8a7ac8;
          border-radius: 13px;
          background: rgba(40, 34, 61, .88);
          color: #f2efff;
          font: 700 15px "Segoe UI", "Yu Gothic UI", sans-serif;
          letter-spacing: .02em;
          pointer-events: auto;
          box-shadow:
            inset 0 0 0 1px rgba(255,255,255,.04),
            0 12px 40px rgba(0,0,0,.42);
        }

        .editorDropOverlay.open {
          display: flex;
        }

        .editorGrid {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 12px 14px;
          max-width: 920px;
        }

        .editorField {
          display: flex;
          flex-direction: column;
          gap: 5px;
        }

        .editorField.full {
          grid-column: 1 / -1;
        }

        .editorLabel {
          color: #aaa7b2;
          font-size: 11px;
        }

        .editorInput,
        .editorSelect,
        .editorTextarea {
          width: 100%;
          border: 1px solid #3a3845;
          border-radius: 7px;
          background: #1e1d24;
          color: #f0eef4;
          outline: none;
          padding: 7px 8px;
          font: 13px "Segoe UI", "Yu Gothic UI", sans-serif;
        }

        .editorInput:focus,
        .editorSelect:focus,
        .editorTextarea:focus {
          border-color: #7468ad;
        }

        .editorInput:disabled {
          color: #8f8b98;
          background: #19191e;
        }

        .editorTextarea {
          min-height: 120px;
          resize: vertical;
          line-height: 1.55;
        }

        .editorChecks {
          display: flex;
          flex-wrap: wrap;
          gap: 13px;
          padding: 4px 0;
        }

        .editorCheck {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          color: #dddbe3;
          font-size: 12px;
        }

        .editorCheck input {
          accent-color: #776ab1;
        }

        .editorHint {
          color: #8f8b97;
          font-size: 11px;
          line-height: 1.55;
          margin: 3px 0 10px;
        }

        .editorTableHeader,
        .editorTableRow {
          display: grid;
          gap: 7px;
          align-items: center;
          min-width: 620px;
        }

        .editorTableHeader {
          color: #93909b;
          font-size: 11px;
          padding: 0 2px 5px;
        }

        .editorTableRow {
          padding: 5px 0;
          border-top: 1px solid #24232a;
        }

        .statusGrid {
          grid-template-columns: 1.3fr 1fr 1fr 86px;
        }

        .paramGrid {
          grid-template-columns: 1.4fr 1.4fr 86px;
        }

        .skillGrid {
          grid-template-columns: 1.15fr 1.7fr 1fr 86px;
        }

        .autoBadge {
          display: inline-block;
          color: #b9afe6;
          font-size: 10px;
          margin-left: 5px;
        }

        .editorCard {
          border: 1px solid #302e39;
          border-radius: 9px;
          background: #18181e;
          padding: 10px;
          margin-bottom: 10px;
        }

        .editorCardHead {
          display: grid;
          grid-template-columns: minmax(0, 1fr) auto auto;
          gap: 8px;
          align-items: center;
          margin-bottom: 8px;
        }

        .paletteHead {
          grid-template-columns: minmax(0, 1fr) 110px auto;
        }

        .groupCheckList {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 7px 12px;
          margin-top: 8px;
        }

        @media (max-width: 760px) {
          .editorWindow {
            min-width: 0;
            width: calc(100vw - 18px);
            height: calc(100vh - 18px);
          }

          .editorGrid,
          .groupCheckList {
            grid-template-columns: 1fr;
          }
        }

        @keyframes loadingMove {
          from { background-position: -80% 0; }
          to { background-position: 180% 0; }
        }
      </style>

      <button id="ccmButton" type="button" title="CCFOLIA Manager">CM</button>

      <div id="toolkitMenu" aria-label="CCFOLIA Manager">
        <button id="toolkitCharacter" class="toolkitModuleButton" type="button">キャラクター</button>
        <button id="toolkitImages" class="toolkitModuleButton" type="button">画像</button>
        <button id="toolkitBgm" class="toolkitModuleButton" type="button">BGM</button>
      </div>

      <section id="panel" aria-label="CCFOLIA Character Manager">
        <div class="header">
          <div class="title">CHARACTER MANAGER</div>
          <div id="status" class="status">接続確認中</div>
          <button id="refresh" class="iconButton" type="button" title="更新">↻</button>
          <button id="close" class="iconButton" type="button" title="閉じる">×</button>
        </div>

        <div id="loading"></div>

        <div class="toolbar">
          <div class="modeGroup">
            <button id="keywordMode" class="modeButton active" type="button">キーワード</button>
            <button id="tagMode" class="modeButton" type="button">タグ</button>
          </div>
          <div id="tagSearchRow" class="tagSearchRow">
            <div id="tagSearchField" class="tagSearchField">
              <button id="taglessSearchButton" class="tagSearchToken" type="button">タグ無し</button>
              <div id="tagSearchTokens" class="tagSearchTokens"></div>
              <input id="search" type="search" placeholder="キャラクターを検索" autocomplete="off">
            </div>
            <button id="tagDropdownButton" class="tagDropdownButton" type="button" title="タグ一覧">▼</button>
            <div id="tagSuggestMenu" class="tagSuggestMenu"></div>
          </div>
        </div>

        <div class="groupRow">
          <div class="groupTools">
            <select id="groupSelect">
              <option value="">すべて</option>
              <option value="__ungrouped__">未分類</option>
            </select>
            <button id="groupTools" class="smallAction" type="button" title="グループ操作">＋</button>
          </div>
        </div>

        <div id="list"></div>

        <div id="bulkBar" class="bulkBar">
          <button id="selectVisible" class="bulkButton" type="button">全選択</button>
          <button id="clearSelected" class="bulkButton" type="button">解除</button>
          <span class="bulkSpacer"></span>
          <button id="bulkTags" class="bulkButton" type="button">タグ追加</button>
          <button id="bulkGroup" class="bulkButton" type="button">グループ追加</button>
          <button id="bulkTrash" class="bulkButton danger" type="button">ゴミ箱</button>
        </div>

        <div class="footer">
          <span id="selectedCount">0件選択</span>
          <div class="footerActions">
            <!-- CHARACTER_SALVAGE_IMPORT_PANEL_V1 -->
            <button id="characterSalvageImport" class="smallAction" type="button" title="現在のCCFOLIAルームにあるキャラクターをManagerへ取り込む">CCFOLIAから取り込む</button>
            <button id="createCharacter" class="smallAction" type="button">＋ 作成</button>
            <button id="sendSelected" class="actionButton primary" type="button" disabled>
              選択を送る
            </button>
          </div>
        </div>

        <div id="memoPane" class="memoPane">
          <div class="memoHeader">
            <button id="memoBack" class="iconButton" type="button" title="戻る">←</button>
            <div id="memoPreview" class="memoCharacterPreview">
              <div id="memoPreviewFallback" class="memoCharacterFallback">？</div>
            </div>
            <div class="memoHeaderText">
              <div id="memoName" class="memoName"></div>
              <div id="memoStatus" class="memoStatus"></div>
            </div>
          </div>
          <textarea id="quickMemo" placeholder="セッション中のメモをここへ。入力は自動保存されます。"></textarea>
        </div>
      </section>


      <section id="imagesPanel" aria-label="CCFOLIA Image Manager">
        <div id="imagesDropOverlay" class="mediaDropOverlay">
          <div>
            画像をここにドロップ
            <span class="mediaDropSub">複数ファイル対応</span>
          </div>
        </div>
        <div class="header">
          <div class="title">IMAGE MANAGER</div>
          <div id="imagesStatus" class="status imageManagerStatus">未読込</div>
          <button id="imagesImport" class="iconButton" type="button" title="画像を追加">＋</button>
          <button id="imagesPreviewToggle" class="imagePreviewHeaderButton" type="button" aria-pressed="false" title="ホバー拡大プレビューを切替">プレビュー</button>
          <!-- IM7_BACKGROUND_ONLY_SALVAGE_PANEL -->
          <button id="imagesSalvage" class="iconButton" type="button" title="CCFOLIAの背景を取り込む">⇩</button>
          <button id="imagesRefresh" class="iconButton" type="button" title="更新">↻</button>
          <button id="imagesClose" class="iconButton" type="button" title="閉じる">×</button>
        </div>

        <div class="imageManagerToolbar">
          <div class="imageManagerSearchRow">
            <div class="modeGroup">
              <button id="imagesKeywordMode" class="modeButton active" type="button">キーワード</button>
              <button id="imagesTagMode" class="modeButton" type="button">タグ</button>
            </div>
            <input id="imagesSearch" class="imageManagerSearch" type="search" placeholder="画像を検索" autocomplete="off">
            <button id="imagesClearSearch" class="smallAction" type="button" title="検索解除">×</button>
          </div>

          <div class="imageManagerFilterRow">
            <select id="imagesGroupSelect">
              <option value="">すべて</option>
              <option value="__ungrouped__">未分類</option>
            </select>
            <button id="imagesTagless" class="imageTaglessButton" type="button">タグ無し</button>
          </div>

          <div id="imagesTagChips" class="imageTagChipRow"></div>
        </div>

        <div id="imageAssetGrid" class="imageAssetGrid">
          <div class="imageManagerEmpty">画像を読み込んでいます...</div>
        </div>

        <div class="imageManagerFooter">
          <span id="imagesCount">0件</span>
          <div class="imageManagerPager" aria-label="画像ページ">
            <button id="imagesPrevPage" class="imageManagerPageButton" type="button" title="前の48件" disabled>‹</button>
            <span id="imagesPageInfo" class="imageManagerPageInfo">0 / 0</span>
            <button id="imagesNextPage" class="imageManagerPageButton" type="button" title="次の48件" disabled>›</button>
          </div>
          <span id="imagesPreviewHint">プレビューモードOFF</span>
        </div>
      </section>

      <input id="imagesImportInput" type="file" accept="image/png,image/jpeg,image/webp,image/gif,image/bmp,image/avif,.png,.jpg,.jpeg,.jfif,.webp,.gif,.bmp,.avif" multiple hidden>

      <div id="imageHoverPreview">
        <img id="imageHoverPreviewImg" alt="">
        <div id="imageHoverPreviewName"></div>
      </div>

      <section id="bgmPanel" aria-label="CCFOLIA BGM Manager">
        <div id="bgmDropOverlay" class="mediaDropOverlay">
          <div>
            BGMをここにドロップ
            <span class="mediaDropSub">MP3 / WAV / OGG / M4A / AAC / FLAC / OPUS / WEBM</span>
          </div>
        </div>

        <div class="header">
          <div class="title">BGM MANAGER</div>
          <div id="bgmProbeStatus" class="status">未読込</div>
          <button id="bgmImportButton" class="iconButton" type="button" title="BGMを追加">＋</button>
          <!-- BGM_SALVAGE_V1 -->
          <button id="bgmSalvageButton" class="smallAction" type="button" title="CCFOLIAのBGMをManagerへサルベージ">救出</button>
          <button id="bgmRefresh" class="iconButton" type="button" title="更新">↻</button>
          <button id="bgmClose" class="iconButton" type="button" title="閉じる">×</button>
        </div>

        <div class="bgmManagerToolbar">
          <div class="bgmSearchRow">
            <button id="bgmKeywordMode" class="bgmModeButton active" type="button">キーワード</button>
            <button id="bgmTagMode" class="bgmModeButton" type="button">タグ</button>
            <input id="bgmSearch" type="search" placeholder="BGMを検索">
          </div>

          <div class="bgmFilterRow">
            <select id="bgmGroupSelect">
              <option value="">すべて</option>
              <option value="__ungrouped__">未分類</option>
            </select>
            <select id="bgmKindSelect">
              <option value="bgm" selected>BGM</option>
              <option value="">すべて</option>
              <option value="se">SE</option>
              <option value="other">その他</option>
            </select>
            <button id="bgmTagless" class="bgmTaglessButton" type="button">タグ無し</button>
          </div>

          <div id="bgmTagChips" class="bgmTagChipRow"></div>
        </div>

        <div id="bgmAssetList" class="bgmAssetList">
          <div class="bgmManagerEmpty">BGMを読み込んでいます...</div>
        </div>

        <div class="bgmManagerFooter">
          <span id="bgmCount">0件</span>
          <span class="spacer"></span>
          <button id="bgmPrev" type="button">‹</button>
          <span id="bgmPageLabel">1 / 1</span>
          <button id="bgmNext" type="button">›</button>
        </div>

        <input id="bgmImportInput" type="file" accept="audio/*,.mp3,.wav,.ogg,.oga,.m4a,.aac,.flac,.opus,.webm" multiple hidden>
      </section>

      <div id="contextMenu" class="contextMenu"></div>

      <div id="modalBackdrop" class="modalBackdrop">
        <div class="modalCard">
          <div id="modalTitle" class="modalTitle"></div>
          <div id="modalBody"></div>
          <div class="modalButtons">
            <button id="modalCancel" type="button">キャンセル</button>
            <button id="modalOk" class="primary" type="button">OK</button>
          </div>
        </div>
      </div>

      <div id="editorDropOverlay" class="editorDropOverlay">
        ここに画像をドロップ
      </div>

      <div id="editorBackdrop" class="editorBackdrop">
        <section class="editorWindow" aria-label="キャラクター編集">
          <div class="editorHeader">
            <div id="editorPreview" class="editorCharacterPreview">
              <div id="editorPreviewFallback" class="editorCharacterFallback">？</div>
            </div>
            <div class="editorHeaderText">
              <div id="editorTitle" class="editorTitle">キャラクター編集</div>
              <div id="editorSaveState" class="editorSaveState"></div>
            </div>
            <button id="editorClose" class="iconButton" type="button" title="閉じる">×</button>
          </div>
          <div id="editorTabs" class="editorTabs"></div>
          <div id="editorBody" class="editorBody"></div>
          <div class="editorFooter">
            <button id="editorCancel" class="editorButton" type="button">閉じる</button>
            <button id="editorSave" class="editorButton primary" type="button">保存</button>
          </div>
        </section>
      </div>
    `;

    document.documentElement.appendChild(host);

    const button = shadow.getElementById("ccmButton");
    const toolkitMenu = shadow.getElementById("toolkitMenu");
    const toolkitCharacter = shadow.getElementById("toolkitCharacter");
    const toolkitImages = shadow.getElementById("toolkitImages");
    const toolkitBgm = shadow.getElementById("toolkitBgm");
    const panel = shadow.getElementById("panel");
    const imagesPanel = shadow.getElementById("imagesPanel");
    const bgmPanel = shadow.getElementById("bgmPanel");
    const imagesDropOverlay =
      shadow.getElementById("imagesDropOverlay");
    const bgmDropOverlay =
      shadow.getElementById("bgmDropOverlay");
    const imagesClose = shadow.getElementById("imagesClose");
    const imagesRefresh = shadow.getElementById("imagesRefresh");
    const imagesStatus = shadow.getElementById("imagesStatus");
    const imagesImport = shadow.getElementById("imagesImport");
    const imagesImportInput = shadow.getElementById("imagesImportInput");
    const imagesKeywordMode = shadow.getElementById("imagesKeywordMode");
    const imagesTagMode = shadow.getElementById("imagesTagMode");
    const imagesSearch = shadow.getElementById("imagesSearch");
    const imagesClearSearch = shadow.getElementById("imagesClearSearch");
    const imagesGroupSelect = shadow.getElementById("imagesGroupSelect");
    const imagesTagless = shadow.getElementById("imagesTagless");
    const imagesPreviewToggle = shadow.getElementById("imagesPreviewToggle");
    const imagesSalvage = shadow.getElementById("imagesSalvage");
    const imagesTagChips = shadow.getElementById("imagesTagChips");
    const imageAssetGrid = shadow.getElementById("imageAssetGrid");
    const imagesCount = shadow.getElementById("imagesCount");
    const imagesPrevPage = shadow.getElementById("imagesPrevPage");
    const imagesPageInfo = shadow.getElementById("imagesPageInfo");
    const imagesNextPage = shadow.getElementById("imagesNextPage");
    const imagesPreviewHint = shadow.getElementById("imagesPreviewHint");
    const imageHoverPreview = shadow.getElementById("imageHoverPreview");
    const imageHoverPreviewImg = shadow.getElementById("imageHoverPreviewImg");
    const imageHoverPreviewName = shadow.getElementById("imageHoverPreviewName");
    const bgmClose = shadow.getElementById("bgmClose");
    const bgmImportButton = shadow.getElementById("bgmImportButton");
    const bgmImportInput = shadow.getElementById("bgmImportInput");
    const bgmRefresh = shadow.getElementById("bgmRefresh");
    const bgmKeywordMode = shadow.getElementById("bgmKeywordMode");
    const bgmTagMode = shadow.getElementById("bgmTagMode");
    const bgmSearch = shadow.getElementById("bgmSearch");
    const bgmGroupSelect = shadow.getElementById("bgmGroupSelect");
    const bgmKindSelect = shadow.getElementById("bgmKindSelect");
    const bgmTagless = shadow.getElementById("bgmTagless");
    const bgmTagChips = shadow.getElementById("bgmTagChips");
    const bgmAssetList = shadow.getElementById("bgmAssetList");
    const bgmCount = shadow.getElementById("bgmCount");
    const bgmPrev = shadow.getElementById("bgmPrev");
    const bgmNext = shadow.getElementById("bgmNext");
    const bgmPageLabel = shadow.getElementById("bgmPageLabel");
    const bgmSalvageButton =
      shadow.getElementById("bgmSalvageButton");
    const bgmProbeStatus =
      shadow.getElementById("bgmProbeStatus");
    const status = shadow.getElementById("status");
    const refreshButton = shadow.getElementById("refresh");
    const closeButton = shadow.getElementById("close");
    const keywordMode = shadow.getElementById("keywordMode");
    const tagMode = shadow.getElementById("tagMode");
    const search = shadow.getElementById("search");
    const tagSearchRow = shadow.getElementById("tagSearchRow");
    const tagSearchField = shadow.getElementById("tagSearchField");
    const tagSearchTokens = shadow.getElementById("tagSearchTokens");
    const taglessSearchButton = shadow.getElementById("taglessSearchButton");
    const tagDropdownButton = shadow.getElementById("tagDropdownButton");
    const tagSuggestMenu = shadow.getElementById("tagSuggestMenu");
    const groupSelect = shadow.getElementById("groupSelect");
    const list = shadow.getElementById("list");
    const sendSelected = shadow.getElementById("sendSelected");
    const selectedCount = shadow.getElementById("selectedCount");
    const bulkBar = shadow.getElementById("bulkBar");
    const selectVisible = shadow.getElementById("selectVisible");
    const clearSelected = shadow.getElementById("clearSelected");
    const bulkTags = shadow.getElementById("bulkTags");
    const bulkGroup = shadow.getElementById("bulkGroup");
    const bulkTrash = shadow.getElementById("bulkTrash");
    const loading = shadow.getElementById("loading");
    const createCharacter = shadow.getElementById("createCharacter");
    const characterSalvageImport =
      shadow.getElementById("characterSalvageImport");
    const groupToolsButton = shadow.getElementById("groupTools");
    const memoPane = shadow.getElementById("memoPane");
    const memoBack = shadow.getElementById("memoBack");
    const memoPreview = shadow.getElementById("memoPreview");
    const memoPreviewFallback = shadow.getElementById("memoPreviewFallback");
    const memoName = shadow.getElementById("memoName");
    const memoStatus = shadow.getElementById("memoStatus");
    const quickMemo = shadow.getElementById("quickMemo");
    const contextMenu = shadow.getElementById("contextMenu");
    const modalBackdrop = shadow.getElementById("modalBackdrop");
    const modalTitle = shadow.getElementById("modalTitle");
    const modalBody = shadow.getElementById("modalBody");
    const modalCancel = shadow.getElementById("modalCancel");
    const modalOk = shadow.getElementById("modalOk");
    const editorDropOverlay = shadow.getElementById("editorDropOverlay");
    const editorBackdrop = shadow.getElementById("editorBackdrop");
    const editorPreview = shadow.getElementById("editorPreview");
    const editorPreviewFallback = shadow.getElementById("editorPreviewFallback");
    const editorTitle = shadow.getElementById("editorTitle");
    const editorSaveState = shadow.getElementById("editorSaveState");
    const editorClose = shadow.getElementById("editorClose");
    const editorTabs = shadow.getElementById("editorTabs");
    const editorBody = shadow.getElementById("editorBody");
    const editorCancel = shadow.getElementById("editorCancel");
    const editorSave = shadow.getElementById("editorSave");

    let searchMode = "keyword";
    let panelInitialized = false;
    let characters = [];
    let groups = [];
    let tags = [];
    let selectedTagFilters = [];
    let taglessOnly = false;
    let loadingCount = 0;
    let searchTimer = null;
    const selected = new Set();
    let memoCharacterId = null;
    let memoSaveTimer = null;
    let modalResolver = null;
    let contextCharacter = null;
    let editorData = null;
    let editorCharacterId = null;
    let editorTab = "basic";
    let editorDirty = false;
    const iconCache = new Map();
    const imageDataCache = new Map();

    let imagePanelInitialized = false;
    let bgmPanelInitialized = false;
    let bgmSearchMode = "keyword";
    let browserBgmAssets = [];
    let browserBgmGroups = [];
    let browserBgmTags = [];
    let bgmTaglessOnly = false;
    let bgmSearchTimer = null;
    let bgmPage = 1;
    let bgmPages = 1;
    let bgmTotal = 0;
    let bgmApplyBusy = false;
    let bgmCurrentId = "";

    let imageSearchMode = "keyword";
    let browserImageAssets = [];
    const browserImagePageSize = 48;
    let browserImageTotal = 0;
    let browserImageOffset = 0;
    let browserImageGroups = [];
    let browserImageTags = [];
    let selectedImageTagFilters = [];
    let imageTaglessOnly = false;
    let imageSearchTimer = null;
    let imageHoverTimer = null;
    let imageHoverAssetId = null;
    let imageThumbObserver = null;
    let imagePreviewEnabled = false;
    let imageBackgroundBusy = false;
    let imageSalvageBusy = false;
    const imageThumbCache = new Map();
    const imageLargePreviewCache = new Map();

    function setLoading(active) {
      loadingCount += active ? 1 : -1;
      loadingCount = Math.max(0, loadingCount);
      loading.classList.toggle(
        "active",
        loadingCount > 0,
      );
    }

    function setOnline(online) {
      status.textContent = online
        ? "ローカル接続"
        : "本体オフライン";
      button.classList.toggle(
        "online",
        online,
      );
      button.classList.toggle(
        "offline",
        !online,
      );
    }

    function updateSelectedUi() {
      for (const id of [...selected]) {
        if (!characters.some(
          (character) => character.id === id
        )) {
          selected.delete(id);
        }
      }

      selectedCount.textContent =
        `${selected.size}件選択`;
      sendSelected.disabled =
        selected.size === 0;

      bulkBar.classList.toggle(
        "active",
        selected.size > 0,
      );

      const selectedDisabled =
        selected.size === 0;

      clearSelected.disabled =
        selectedDisabled;
      bulkTags.disabled =
        selectedDisabled;
      bulkGroup.disabled =
        selectedDisabled;
      bulkTrash.disabled =
        selectedDisabled;

      const visibleIds =
        characters.map(
          (character) =>
            character.id
        );

      const allVisibleSelected =
        visibleIds.length > 0
        && visibleIds.every(
          (id) =>
            selected.has(id)
        );

      selectVisible.textContent =
        allVisibleSelected
          ? "表示中を解除"
          : "全選択";
      selectVisible.disabled =
        visibleIds.length === 0;
    }

    function characterFallbackText(character) {
      const raw = String(
        character?.name || ""
      ).trim();

      return raw
        ? raw.slice(0, 1)
        : "？";
    }

    async function resolveCharacterIcon(characterId) {
      const key = String(
        characterId || ""
      );

      if (!key) {
        return null;
      }

      if (iconCache.has(key)) {
        return await iconCache.get(key);
      }

      const promise = apiGet(
        `/api/character/${encodeURIComponent(key)}/icon`,
      )
        .then(
          (data) => data.data_url || null,
        )
        .catch(
          () => null,
        );

      iconCache.set(
        key,
        promise,
      );

      const result = await promise;
      iconCache.set(
        key,
        result,
      );
      return result;
    }

    async function applyCharacterIcon(
      character,
      iconElement,
    ) {
      if (
        !character?.has_icon
        || !iconElement
      ) {
        return;
      }

      const dataUrl =
        await resolveCharacterIcon(
          character.id,
        );

      if (
        !dataUrl
        || !iconElement.isConnected
      ) {
        return;
      }

      const image = document.createElement("img");
      image.alt = "";
      image.draggable = false;
      image.src = dataUrl;

      iconElement.textContent = "";
      iconElement.appendChild(image);
    }

    function setPreviewFallback(
      box,
      fallback,
      character,
      size,
    ) {
      if (!box || !fallback) {
        return;
      }

      box.textContent = "";
      fallback.textContent =
        characterFallbackText(character);

      fallback.style.color =
        character?.color || "#cbc8d8";

      if (size === "large") {
        fallback.className =
          "editorCharacterFallback";
      } else {
        fallback.className =
          "memoCharacterFallback";
      }

      box.appendChild(fallback);
    }

    async function updateCharacterPreview(
      box,
      fallback,
      character,
      size = "small",
    ) {
      setPreviewFallback(
        box,
        fallback,
        character,
        size,
      );

      if (!character) {
        return;
      }

      const previewCharacter = {
        id: character.id,
        name: character.name,
        color: character.color,
        has_icon: Boolean(
          character.has_icon
          || (character.image_count || 0) > 0
        ),
      };

      await applyCharacterIcon(
        previewCharacter,
        box,
      );
    }

    function refreshEditorPreview() {
      if (
        !editorData
        || !editorData.character
        || !editorCharacterId
      ) {
        setPreviewFallback(
          editorPreview,
          editorPreviewFallback,
          {
            name: "",
            color: "#cbc8d8",
          },
          "large",
        )
        return;
      }

      void updateCharacterPreview(
        editorPreview,
        editorPreviewFallback,
        {
          id: editorCharacterId,
          name: editorData.character.name,
          color: editorData.character.color,
          image_count:
            editorData.character.image_count,
        },
        "large",
      );
    }

    function closeContextMenu() {
      contextMenu.classList.remove("open");
      contextMenu.textContent = "";
      contextCharacter = null;
    }

    function closeModal(result = null) {
      modalBackdrop.classList.remove("open");
      const resolver = modalResolver;
      modalResolver = null;
      if (resolver) {
        resolver(result);
      }
    }

    function showModal({
      title,
      fields = [],
      okText = "OK",
    }) {
      modalTitle.textContent = title;
      modalBody.textContent = "";
      modalOk.textContent = okText;

      const controls = [];

      for (const field of fields) {
        let control;

        if (field.type === "select") {
          control = document.createElement("select");
          control.className = "modalSelect";
          for (const optionData of field.options || []) {
            const option = document.createElement("option");
            option.value = String(optionData.value ?? "");
            option.textContent = String(optionData.label ?? option.value);
            control.appendChild(option);
          }
          if (field.value != null) {
            control.value = String(field.value);
          }
        } else {
          control = document.createElement("input");
          control.type = "text";
          control.className = "modalField";
          control.placeholder = field.placeholder || "";
          control.value = field.value || "";
        }

        control.dataset.name = field.name;
        modalBody.appendChild(control);
        controls.push(control);
      }

      modalBackdrop.classList.add("open");
      setTimeout(() => controls[0]?.focus(), 0);

      return new Promise((resolve) => {
        modalResolver = resolve;

        const submit = () => {
          const values = {};
          for (const control of controls) {
            values[control.dataset.name] = control.value;
          }
          closeModal(values);
        };

        modalOk.onclick = submit;
        modalCancel.onclick = () => closeModal(null);

        for (const control of controls) {
          control.onkeydown = (event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              submit();
            }
          };
        }
      });
    }

    function closeTagSuggestMenu() {
      tagSuggestMenu.classList.remove("open");
      tagDropdownButton.classList.remove("active");
    }

    function selectedTagKey(value) {
      return String(value || "")
        .trim()
        .toLocaleLowerCase("ja");
    }

    function canonicalTagName(value) {
      const key = selectedTagKey(value);

      if (!key) {
        return "";
      }

      const found =
        tags.find(
          (tag) =>
            selectedTagKey(tag.name)
            === key
        );

      return found
        ? String(found.name || "")
        : "";
    }

    function tagSearchText() {
      return taglessOnly
        ? "__CCM_TAGLESS__"
        : selectedTagFilters.join(", ");
    }

    function renderSelectedTagFilters() {
      tagSearchTokens.textContent = "";

      const tagMode =
        searchMode === "tag";

      tagSearchTokens.style.display =
        tagMode
          ? "flex"
          : "none";

      taglessSearchButton.style.display =
        tagMode
          ? "inline-flex"
          : "none";

      taglessSearchButton.classList.toggle(
        "active",
        taglessOnly,
      );

      for (const tagName of selectedTagFilters) {
        const chip =
          document.createElement("button");

        chip.type = "button";
        chip.className =
          "tagSearchToken";
        chip.title =
          `「${tagName}」を検索条件から外す`;

        const label =
          document.createElement("span");
        label.textContent =
          tagName;

        const remove =
          document.createElement("span");
        remove.className =
          "tagSearchTokenRemove";
        remove.textContent =
          "×";

        chip.append(
          label,
          remove,
        );

        chip.addEventListener(
          "click",
          () => {
            const key =
              selectedTagKey(tagName);

            selectedTagFilters =
              selectedTagFilters.filter(
                (value) =>
                  selectedTagKey(value)
                  !== key
              );

            renderSelectedTagFilters();
            renderTagSearchCards(false);
            void loadCharacters();
          },
        );

        tagSearchTokens.appendChild(
          chip
        );
      }
    }

    function addTagSearchFilter(tagName) {
      taglessOnly = false;

      const canonical =
        canonicalTagName(tagName);

      if (!canonical) {
        return false;
      }

      const key =
        selectedTagKey(canonical);

      if (
        selectedTagFilters.some(
          (value) =>
            selectedTagKey(value)
            === key
        )
      ) {
        search.value = "";
        closeTagSuggestMenu();
        return false;
      }

      selectedTagFilters.push(
        canonical
      );

      search.value = "";
      closeTagSuggestMenu();
      renderSelectedTagFilters();
      void loadCharacters();

      queueMicrotask(
        () => search.focus()
      );

      return true;
    }

    function sortedTagCandidates(
      query,
      showAll = false,
    ) {
      const normalized =
        selectedTagKey(query);

      const selectedKeys =
        new Set(
          selectedTagFilters.map(
            selectedTagKey
          )
        );

      const rows =
        tags
          .map(
            (tag) => ({
              ...tag,
              normalized:
                selectedTagKey(
                  tag.name
                ),
            })
          )
          .filter(
            (tag) =>
              !selectedKeys.has(
                tag.normalized
              )
          )
          .filter(
            (tag) => (
              showAll
              || !normalized
              || tag.normalized.includes(
                normalized
              )
            )
          );

      rows.sort(
        (a, b) => {
          if (normalized) {
            const aStarts =
              a.normalized.startsWith(
                normalized
              );
            const bStarts =
              b.normalized.startsWith(
                normalized
              );

            if (aStarts !== bStarts) {
              return aStarts
                ? -1
                : 1;
            }
          }

          return String(
            a.name || ""
          ).localeCompare(
            String(
              b.name || ""
            ),
            "ja",
          );
        },
      );

      return showAll
        ? rows
        : rows.slice(0, 8);
    }

    function renderTagSearchCards(
      showAll = false,
    ) {
      tagSuggestMenu.textContent = "";
      renderSelectedTagFilters();

      if (searchMode !== "tag") {
        tagDropdownButton.style.display =
          "none";
        search.placeholder =
          "キャラクターを検索";
        closeTagSuggestMenu();
        return;
      }

      tagDropdownButton.style.display =
        "block";
      search.placeholder =
        selectedTagFilters.length
          ? "タグを追加..."
          : "タグ名を入力...";

      const query =
        search.value.trim();

      if (!showAll && !query) {
        closeTagSuggestMenu();
        return;
      }

      const candidates =
        sortedTagCandidates(
          query,
          showAll,
        );

      if (!candidates.length) {
        const empty =
          document.createElement(
            "div"
          );
        empty.className =
          "tagSuggestEmpty";

        empty.textContent =
          tags.length
            ? (
                selectedTagFilters.length
                  ? "追加できるタグがありません"
                  : "一致するタグがありません"
              )
            : "登録タグなし";

        tagSuggestMenu.appendChild(
          empty
        );
      } else {
        for (const tag of candidates) {
          const button =
            document.createElement(
              "button"
            );

          button.type =
            "button";
          button.className =
            "tagSuggestItem";
          button.textContent =
            tag.name;

          button.addEventListener(
            "click",
            () => {
              addTagSearchFilter(
                tag.name
              );
            },
          );

          tagSuggestMenu.appendChild(
            button
          );
        }
      }

      tagSuggestMenu.classList.add(
        "open"
      );

      tagDropdownButton.classList.toggle(
        "active",
        showAll,
      );
    }

    function commitTagSearchInput() {
      if (
        searchMode !== "tag"
      ) {
        return false;
      }

      const query =
        search.value.trim();

      if (!query) {
        return false;
      }

      const exact =
        canonicalTagName(query);

      if (exact) {
        return addTagSearchFilter(
          exact
        );
      }

      const candidates =
        sortedTagCandidates(
          query,
          false,
        );

      if (candidates.length) {
        return addTagSearchFilter(
          candidates[0].name
        );
      }

      return false;
    }

    async function loadTags() {
      const data =
        await apiGet(
          "/api/tags"
        );

      tags =
        Array.isArray(data.tags)
          ? data.tags
          : [];

      const validKeys =
        new Set(
          tags.map(
            (tag) =>
              selectedTagKey(
                tag.name
              )
          )
        );

      selectedTagFilters =
        selectedTagFilters.filter(
          (value) =>
            validKeys.has(
              selectedTagKey(value)
            )
        );

      renderTagSearchCards();
    }

    function showTagPicker({
      title,
      initial = [],
      okText = "追加",
    }) {
      modalTitle.textContent = title;
      modalBody.textContent = "";
      modalOk.textContent = okText;

      const selectedTags =
        new Set(
          (initial || [])
            .map((value) => String(value).trim())
            .filter(Boolean)
        );

      const wrap = document.createElement("div");
      wrap.className = "tagPickerWrap";

      const cards = document.createElement("div");
      cards.className = "tagPickerCards";

      const input = document.createElement("input");
      input.type = "text";
      input.className = "tagPickerInput";
      input.placeholder = "新しいタグ（複数はカンマ区切り）";

      function redraw() {
        cards.textContent = "";

        for (const tag of tags) {
          const button = document.createElement("button");
          button.type = "button";
          button.className =
            "tagCard"
            + (
              selectedTags.has(tag.name)
                ? " active"
                : ""
            );
          button.textContent = tag.name;

          button.addEventListener("click", () => {
            if (selectedTags.has(tag.name)) {
              selectedTags.delete(tag.name);
            } else {
              selectedTags.add(tag.name);
            }
            redraw();
          });

          cards.appendChild(button);
        }
      }

      redraw();
      wrap.append(cards, input);
      modalBody.appendChild(wrap);
      modalBackdrop.classList.add("open");

      setTimeout(() => input.focus(), 0);

      return new Promise((resolve) => {
        modalResolver = resolve;

        const submit = () => {
          const added =
            String(input.value || "")
              .replaceAll("、", ",")
              .split(",")
              .map((value) => value.trim())
              .filter(Boolean);

          for (const value of added) {
            selectedTags.add(value);
          }

          closeModal([...selectedTags]);
        };

        modalOk.onclick = submit;
        modalCancel.onclick = () => closeModal(null);

        input.onkeydown = (event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            submit();
          }
        };
      });
    }

    async function openQuickMemo(character) {
      memoCharacterId = character.id;
      memoName.textContent = character.name || "(名称なし)";
      memoStatus.textContent = "読込中…";
      quickMemo.value = "";
      memoPane.classList.add("open");
      void updateCharacterPreview(
        memoPreview,
        memoPreviewFallback,
        character,
        "small",
      );

      try {
        const data = await apiGet(
          `/api/character/${encodeURIComponent(character.id)}`,
        );
        quickMemo.value = data.character?.quick_memo || "";
        memoStatus.textContent = "自動保存";
        void updateCharacterPreview(
          memoPreview,
          memoPreviewFallback,
          {
            id: character.id,
            name:
              data.character?.name
              || character.name,
            color:
              data.character?.color
              || character.color,
            has_icon:
              character.has_icon,
            image_count:
              data.character?.image_count,
          },
          "small",
        );
        quickMemo.focus();
      } catch (error) {
        memoStatus.textContent = "読込失敗";
      }
    }

    function closeQuickMemo() {
      clearTimeout(memoSaveTimer);
      memoCharacterId = null;
      memoPane.classList.remove("open");
      setPreviewFallback(
        memoPreview,
        memoPreviewFallback,
        {
          name: "",
          color: "#cbc8d8",
        },
        "small",
      );
    }

    async function saveQuickMemoNow() {
      if (!memoCharacterId) {
        return;
      }

      const targetId = memoCharacterId;
      const value = quickMemo.value;
      memoStatus.textContent = "保存中…";

      try {
        await apiPost(
          `/api/character/${encodeURIComponent(targetId)}/quick-memo`,
          { text: value },
        );
        if (memoCharacterId === targetId) {
          memoStatus.textContent = "保存済み";
        }
      } catch (error) {
        if (memoCharacterId === targetId) {
          memoStatus.textContent = "保存失敗";
        }
      }
    }

    async function createNewCharacter() {
      const values = await showModal({
        title: "キャラクター作成",
        okText: "作成",
        fields: [
          {
            name: "name",
            placeholder: "キャラクター名",
          },
          {
            name: "template_id",
            type: "select",
            value: "generic",
            options: [
              { value: "generic", label: "汎用" },
              { value: "coc6", label: "CoC6" },
            ],
          },
        ],
      });

      if (!values || !values.name.trim()) {
        return;
      }

      try {
        await apiPost("/api/characters/create", {
          name: values.name.trim(),
          template_id: values.template_id,
        });
        await loadCharacters();
      } catch (error) {
        window.alert(`作成できません: ${error?.message || error}`);
      }
    }

    async function addTagsFor(character) {
      const selectedTags =
        await showTagPicker({
          title:
            `${character.name || "キャラクター"}：タグ追加`,
          okText: "追加",
        });

      if (!selectedTags || !selectedTags.length) {
        return;
      }

      await apiPost(
        `/api/character/${encodeURIComponent(character.id)}/tags`,
        { tag_names: selectedTags },
      );

      await loadTags();
      await loadCharacters();
    }

    async function addGroupFor(character) {
      const options = buildGroupOptions(groups);

      if (!options.length) {
        window.alert("グループがまだありません。");
        return;
      }

      const values = await showModal({
        title: `${character.name || "キャラクター"}：グループ追加`,
        okText: "追加",
        fields: [
          {
            name: "group_id",
            type: "select",
            options: options.map((item) => ({
              value: item.id,
              label: item.label,
            })),
          },
        ],
      });

      if (!values?.group_id) return;

      await apiPost(
        `/api/character/${encodeURIComponent(character.id)}/group`,
        { group_id: values.group_id },
      );
      await loadCharacters();
    }

    async function duplicateCharacterFromMenu(character) {
      await apiPost(
        `/api/character/${encodeURIComponent(character.id)}/duplicate`,
        {},
      );
      await loadCharacters();
    }

    async function trashCharacterFromMenu(character) {
      const accepted = window.confirm(
        `「${character.name || "キャラクター"}」をゴミ箱へ移動しますか？`,
      );

      if (!accepted) return;

      await apiPost(
        `/api/character/${encodeURIComponent(character.id)}/trash`,
        {},
      );
      selected.delete(character.id);
      await loadCharacters();
    }

    function openContextMenu(character, x, y) {
      closeContextMenu();
      contextCharacter = character;

      const actions = [
        ["編集", () => openCharacterEditor(character)],
        ["メモを開く", () => openQuickMemo(character)],
        ["グループ追加", () => addGroupFor(character)],
        ["タグ追加", () => addTagsFor(character)],
        ["複製", () => duplicateCharacterFromMenu(character)],
        ["ゴミ箱へ移動", () => trashCharacterFromMenu(character), "danger"],
      ];

      for (const [label, handler, className] of actions) {
        const item = document.createElement("button");
        item.type = "button";
        item.textContent = label;
        if (className) item.className = className;
        item.addEventListener("click", async () => {
          closeContextMenu();
          try {
            await handler();
          } catch (error) {
            window.alert(`CCMエラー: ${error?.message || error}`);
          }
        });
        contextMenu.appendChild(item);
      }

      contextMenu.classList.add("open");
      const width = 190;
      const height = 245;
      contextMenu.style.left = `${clamp(x, 6, window.innerWidth - width - 6)}px`;
      contextMenu.style.top = `${clamp(y, 6, window.innerHeight - height - 6)}px`;
    }

    const EDITOR_TABS = [
      ["basic", "基本情報"],
      ["statuses", "ステータス"],
      ["params", "パラメータ"],
      ["skills", "技能"],
      ["memos", "メモ"],
      ["palettes", "チャットパレット"],
      ["classify", "分類"],
    ];

    function editorInput(value = "", options = {}) {
      const input = document.createElement("input");
      input.className = "editorInput";
      input.type = options.type || "text";
      input.value = String(value ?? "");
      if (options.placeholder) input.placeholder = options.placeholder;
      if (options.disabled) input.disabled = true;
      if (options.onInput) {
        input.addEventListener("input", () => {
          options.onInput(input.value);
          markEditorDirty();
        });
      }
      return input;
    }

    function editorTextarea(value = "", onInput = null) {
      const textarea = document.createElement("textarea");
      textarea.className = "editorTextarea";
      textarea.value = String(value ?? "");
      if (onInput) {
        textarea.addEventListener("input", () => {
          onInput(textarea.value);
          markEditorDirty();
        });
      }
      return textarea;
    }

    function editorField(label, control, full = false) {
      const wrapper = document.createElement("label");
      wrapper.className = `editorField${full ? " full" : ""}`;
      const caption = document.createElement("span");
      caption.className = "editorLabel";
      caption.textContent = label;
      wrapper.append(caption, control);
      return wrapper;
    }

    function editorCheckbox(label, checked, onChange) {
      const wrapper = document.createElement("label");
      wrapper.className = "editorCheck";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = Boolean(checked);
      input.addEventListener("change", () => {
        onChange(input.checked);
        markEditorDirty();
      });
      const text = document.createElement("span");
      text.textContent = label;
      wrapper.append(input, text);
      return wrapper;
    }

    function markEditorDirty() {
      editorDirty = true;
      editorSaveState.textContent = "未保存";
    }

    function setEditorSaved() {
      editorDirty = false;
      editorSaveState.textContent = "保存済み";
    }

    function renderEditorTabs() {
      editorTabs.textContent = "";
      for (const [key, label] of EDITOR_TABS) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `editorTab${editorTab === key ? " active" : ""}`;
        button.textContent = label;
        button.addEventListener("click", () => {
          editorTab = key;
          renderEditor();
        });
        editorTabs.appendChild(button);
      }
    }

    function addHint(text) {
      const hint = document.createElement("div");
      hint.className = "editorHint";
      hint.textContent = text;
      editorBody.appendChild(hint);
      return hint;
    }

    function clearCharacterImageCaches(characterId) {
      const id = String(characterId || "");
      iconCache.delete(id);
      for (const key of [...imageDataCache.keys()]) {
        if (key.startsWith(`${id}:`)) {
          imageDataCache.delete(key);
        }
      }
    }

    function fileToBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => reject(new Error("画像を読み込めません。"));
        reader.onload = () => {
          const result = String(reader.result || "");
          const comma = result.indexOf(",");
          if (comma < 0) {
            reject(new Error("画像データが不正です。"));
            return;
          }
          resolve(result.slice(comma + 1));
        };
        reader.readAsDataURL(file);
      });
    }

    async function fetchEditorImageData(imageId) {
      const key = `${editorCharacterId}:${imageId}`;
      if (imageDataCache.has(key)) {
        return await imageDataCache.get(key);
      }
      const promise = apiGet(
        `/api/images?character_id=${encodeURIComponent(editorCharacterId)}&image_id=${encodeURIComponent(imageId)}`,
      ).then((data) => data.data_url || null).catch(() => null);
      imageDataCache.set(key, promise);
      const result = await promise;
      imageDataCache.set(key, result);
      return result;
    }

    async function loadEditorImages() {
      if (!editorCharacterId) return;
      const data = await apiGet(
        `/api/images?character_id=${encodeURIComponent(editorCharacterId)}`,
      );
      editorData.images = Array.isArray(data.images) ? data.images : [];
      if (editorData.character) {
        editorData.character.image_count = editorData.images.length;
      }
    }

    async function refreshAfterImageChange() {
      if (!editorCharacterId) return;
      clearCharacterImageCaches(editorCharacterId);
      await loadEditorImages();
      refreshEditorPreview();
      if (editorTab === "basic") renderEditor();
      await loadCharacters();
    }

    function editorIsOpen() {
      return Boolean(
        editorBackdrop
        && editorBackdrop.classList.contains("open")
        && editorCharacterId
      );
    }

    function positionEditorDropOverlay() {
      if (
        !editorIsOpen()
        || !editorDropOverlay
      ) {
        return;
      }

      const target =
        shadow.querySelector(
          ".editorImageDrop"
        )
        || shadow.querySelector(
          ".editorWindow"
        );

      if (!target) {
        return;
      }

      const rect =
        target.getBoundingClientRect();

      editorDropOverlay.style.left =
        `${rect.left}px`;
      editorDropOverlay.style.top =
        `${rect.top}px`;
      editorDropOverlay.style.width =
        `${rect.width}px`;
      editorDropOverlay.style.height =
        `${rect.height}px`;
    }

    function showEditorDropOverlay() {
      if (
        !editorIsOpen()
        || !editorDropOverlay
      ) {
        return;
      }

      positionEditorDropOverlay();

      editorDropOverlay.classList.add(
        "open"
      );
    }

    function hideEditorDropOverlay() {
      editorDropOverlay?.classList.remove(
        "open"
      );
    }

    function currentEditorImageDrop() {
      if (
        !editorBackdrop
        || !editorBackdrop.classList.contains("open")
      ) {
        return null;
      }

      return shadow.querySelector(
        ".editorImageDrop"
      );
    }

    function pointInsideElement(element, x, y) {
      if (!element) {
        return false;
      }

      const rect =
        element.getBoundingClientRect();

      return (
        x >= rect.left
        && x <= rect.right
        && y >= rect.top
        && y <= rect.bottom
      );
    }

    function eventHasFiles(event) {
      const types = [
        ...(event.dataTransfer?.types || []),
      ];

      return types.includes("Files");
    }

    async function uploadEditorFiles(files) {
      if (!editorCharacterId || !files?.length) return;
      const allowed = /\.(png|jpe?g|webp|bmp)$/i;
      const usable = [...files].filter((file) => allowed.test(file.name));
      if (!usable.length) {
        window.alert("PNG / JPG / JPEG / WEBP / BMP の画像を選択してください。");
        return;
      }
      editorSaveState.textContent = "画像追加中…";
      try {
        for (const file of usable) {
          if (file.size > 12 * 1024 * 1024) {
            throw new Error(`${file.name} は12MBを超えています。`);
          }
          const dataBase64 = await fileToBase64(file);
          await apiPost("/api/images/upload", {
            character_id: editorCharacterId,
            filename: file.name,
            data_base64: dataBase64,
          });
        }
        editorSaveState.textContent = "画像反映済み";
        await refreshAfterImageChange();
      } catch (error) {
        editorSaveState.textContent = "画像追加失敗";
        window.alert(`画像を追加できません: ${error?.message || error}`);
      }
    }

    async function reorderEditorImages(images) {
      await apiPost("/api/images/reorder", {
        character_id: editorCharacterId,
        image_ids: images.map((image) => image.id),
      });
      await refreshAfterImageChange();
    }

    async function setEditorMainImage(index) {
      const images = [...(editorData.images || [])];
      if (index <= 0 || index >= images.length) return;
      const [target] = images.splice(index, 1);
      images.unshift(target);
      await reorderEditorImages(images);
    }

    async function moveEditorImage(index, delta) {
      const images = [...(editorData.images || [])];
      const next = index + delta;
      if (next < 0 || next >= images.length) return;
      [images[index], images[next]] = [images[next], images[index]];
      await reorderEditorImages(images);
    }

    async function deleteEditorImage(image) {
      if (!window.confirm("この画像をキャラクターから削除しますか？")) return;
      await apiPost("/api/images/delete", {
        character_id: editorCharacterId,
        image_id: image.id,
      });
      await refreshAfterImageChange();
    }

    function renderImageManager() {
      const section = document.createElement("section");
      section.className = "editorImageSection";

      const head = document.createElement("div");
      head.className = "editorImageHead";
      const title = document.createElement("div");
      title.className = "editorImageTitle";
      title.textContent = "キャラクター画像";

      const input = document.createElement("input");
      input.type = "file";
      input.multiple = true;
      input.accept = ".png,.jpg,.jpeg,.webp,.bmp";
      input.style.display = "none";

      const addButton = document.createElement("button");
      addButton.type = "button";
      addButton.className = "editorButton";
      addButton.textContent = "＋ 画像追加";
      addButton.addEventListener("click", () => input.click());
      input.addEventListener("change", async () => {
        const files = [...(input.files || [])];
        input.value = "";
        await uploadEditorFiles(files);
      });
      head.append(title, addButton, input);

      const drop = document.createElement("div");
      drop.className = "editorImageDrop";
      const dropFrame = document.createElement("iframe");
      dropFrame.className = "editorExtensionDropFrame";
      dropFrame.title = "CCM画像ドロップ";
      dropFrame.src = chrome.runtime.getURL(
        `drop_zone.html?character_id=${encodeURIComponent(editorCharacterId)}`,
      );
      drop.appendChild(dropFrame);
      const images = Array.isArray(editorData.images) ? editorData.images : [];

      if (!images.length) {
        const empty = document.createElement("div");
        empty.className = "editorImageEmpty";
        empty.textContent = "登録画像はありません";
        drop.appendChild(empty);
      } else {
        const strip = document.createElement("div");
        strip.className = "editorImageStrip";
        images.forEach((image, index) => {
          const card = document.createElement("div");
          card.className = "editorImageCard";
          const thumb = document.createElement("div");
          thumb.className = "editorImageThumb";
          const fallback = document.createElement("div");
          fallback.className = "editorCharacterFallback";
          fallback.textContent = characterFallbackText(editorData.character);
          thumb.appendChild(fallback);

          if (index === 0) {
            const badge = document.createElement("span");
            badge.className = "editorImageBadge";
            badge.textContent = "MAIN";
            thumb.appendChild(badge);
          }

          void fetchEditorImageData(image.id).then((dataUrl) => {
            if (!dataUrl || !thumb.isConnected) return;
            const imageElement = document.createElement("img");
            imageElement.alt = "";
            imageElement.draggable = false;
            imageElement.src = dataUrl;
            thumb.textContent = "";
            thumb.appendChild(imageElement);
            if (index === 0) {
              const badge = document.createElement("span");
              badge.className = "editorImageBadge";
              badge.textContent = "MAIN";
              thumb.appendChild(badge);
            }
          });

          const label = document.createElement("div");
          label.className = "editorImageLabel";
          label.textContent = image.label || `画像 ${index + 1}`;
          label.title = label.textContent;

          const actions = document.createElement("div");
          actions.className = "editorImageActions";
          const mainButton = document.createElement("button");
          mainButton.type = "button";
          mainButton.textContent = "主";
          mainButton.title = "主画像にする";
          mainButton.disabled = index === 0;
          const leftButton = document.createElement("button");
          leftButton.type = "button";
          leftButton.textContent = "←";
          leftButton.title = "左へ移動";
          leftButton.disabled = index === 0;
          const rightButton = document.createElement("button");
          rightButton.type = "button";
          rightButton.textContent = "→";
          rightButton.title = "右へ移動";
          rightButton.disabled = index === images.length - 1;
          const deleteButton = document.createElement("button");
          deleteButton.type = "button";
          deleteButton.textContent = "×";
          deleteButton.title = "削除";
          deleteButton.className = "danger";
          mainButton.addEventListener("click", () => setEditorMainImage(index));
          leftButton.addEventListener("click", () => moveEditorImage(index, -1));
          rightButton.addEventListener("click", () => moveEditorImage(index, 1));
          deleteButton.addEventListener("click", () => deleteEditorImage(image));
          actions.append(mainButton, leftButton, rightButton, deleteButton);
          card.append(thumb, label, actions);
          strip.appendChild(card);
        });
        drop.appendChild(strip);
      }


      const note = document.createElement("div");
      note.className = "editorImageNote";
      note.textContent = "先頭画像が主画像です。画像の追加・並び替え・削除は即時反映されます。";
      section.append(head, drop, note);
      editorBody.appendChild(section);
    }

    function renderBasicEditor() {
      const c = editorData.character;
      renderImageManager();
      const grid = document.createElement("div");
      grid.className = "editorGrid";

      grid.appendChild(editorField(
        "キャラクター名",
        editorInput(c.name, { onInput: (v) => { c.name = v; editorTitle.textContent = v || "キャラクター編集"; refreshEditorPreview(); } }),
      ));
      grid.appendChild(editorField(
        "プレイヤー名",
        editorInput(c.player_name, { onInput: (v) => { c.player_name = v; } }),
      ));
      grid.appendChild(editorField(
        "イニシアティブ",
        editorInput(c.initiative, { onInput: (v) => { c.initiative = v; } }),
      ));
      grid.appendChild(editorField(
        "カラー",
        editorInput(c.color, { onInput: (v) => { c.color = v; refreshEditorPreview(); } }),
      ));
      grid.appendChild(editorField(
        "外部URL",
        editorInput(c.external_url, { onInput: (v) => { c.external_url = v; } }),
        true,
      ));

      const checks = document.createElement("div");
      checks.className = "editorChecks editorField full";
      checks.append(
        editorCheckbox("シークレット", c.secret, (v) => { c.secret = v; }),
        editorCheckbox("盤面で非表示", c.invisible, (v) => { c.invisible = v; }),
        editorCheckbox("ステータスを隠す", c.hide_status, (v) => { c.hide_status = v; }),
      );
      grid.appendChild(checks);

      editorBody.appendChild(grid);
      addHint(
        `テンプレート: ${c.template_id || "generic"} / 登録画像: ${c.image_count ?? 0}枚`,
      );
    }

    function rowDeleteButton(handler) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "editorDanger";
      button.textContent = "削除";
      button.addEventListener("click", () => {
        handler();
        markEditorDirty();
        renderEditor();
      });
      return button;
    }

    function renderStatusesEditor() {
      addHint("式を持つ自動計算項目は、本体側のルールを保持したまま保存されます。最大値が自動計算の場合はブラウザから直接変更できません。");
      const head = document.createElement("div");
      head.className = "editorTableHeader statusGrid";
      head.innerHTML = "<span>名前</span><span>現在値</span><span>最大値</span><span></span>";
      editorBody.appendChild(head);

      editorData.statuses.forEach((row, index) => {
        const line = document.createElement("div");
        line.className = "editorTableRow statusGrid";
        const label = editorInput(row.label, { onInput: (v) => { row.label = v; } });
        const current = editorInput(row.current, { onInput: (v) => { row.current = v; } });
        const maximum = editorInput(row.max, {
          disabled: Boolean(row.max_formula),
          onInput: (v) => { row.max = v; },
        });
        if (row.initial_formula) current.title = `初期式: ${row.initial_formula}`;
        if (row.max_formula) maximum.title = `自動計算: ${row.max_formula}`;
        line.append(label, current, maximum, rowDeleteButton(() => editorData.statuses.splice(index, 1)));
        editorBody.appendChild(line);
      });

      const add = document.createElement("button");
      add.type = "button";
      add.className = "editorAdd";
      add.textContent = "＋ ステータス追加";
      add.addEventListener("click", () => {
        editorData.statuses.push({ label: "", current: "", max: "", initial_formula: "", max_formula: "" });
        markEditorDirty();
        renderEditor();
      });
      editorBody.appendChild(add);
    }

    function renderParamsEditor() {
      addHint("ルール式を持つパラメータの値は自動計算されるため、ブラウザでは読み取り専用です。");
      const head = document.createElement("div");
      head.className = "editorTableHeader paramGrid";
      head.innerHTML = "<span>名前</span><span>値</span><span></span>";
      editorBody.appendChild(head);

      editorData.params.forEach((row, index) => {
        const line = document.createElement("div");
        line.className = "editorTableRow paramGrid";
        const label = editorInput(row.label, { onInput: (v) => { row.label = v; } });
        const value = editorInput(row.value, {
          disabled: Boolean(row.formula),
          onInput: (v) => { row.value = v; },
        });
        if (row.formula) value.title = `自動計算: ${row.formula}`;
        line.append(label, value, rowDeleteButton(() => editorData.params.splice(index, 1)));
        editorBody.appendChild(line);
      });

      const add = document.createElement("button");
      add.type = "button";
      add.className = "editorAdd";
      add.textContent = "＋ パラメータ追加";
      add.addEventListener("click", () => {
        editorData.params.push({ label: "", value: "", formula: "" });
        markEditorDirty();
        renderEditor();
      });
      editorBody.appendChild(add);
    }

    function renderSkillsEditor() {
      const head = document.createElement("div");
      head.className = "editorTableHeader skillGrid";
      head.innerHTML = "<span>分類</span><span>技能名</span><span>値</span><span></span>";
      editorBody.appendChild(head);

      editorData.skills.forEach((row, index) => {
        const line = document.createElement("div");
        line.className = "editorTableRow skillGrid";
        line.append(
          editorInput(row.category, { onInput: (v) => { row.category = v; } }),
          editorInput(row.label, { onInput: (v) => { row.label = v; } }),
          editorInput(row.value, { onInput: (v) => { row.value = v; } }),
          rowDeleteButton(() => editorData.skills.splice(index, 1)),
        );
        editorBody.appendChild(line);
      });

      const add = document.createElement("button");
      add.type = "button";
      add.className = "editorAdd";
      add.textContent = "＋ 技能追加";
      add.addEventListener("click", () => {
        editorData.skills.push({ category: "", label: "", value: "" });
        markEditorDirty();
        renderEditor();
      });
      editorBody.appendChild(add);
    }

    function renderMemosEditor() {
      editorData.memos.forEach((row, index) => {
        const card = document.createElement("div");
        card.className = "editorCard";
        const head = document.createElement("div");
        head.className = "editorCardHead";
        head.append(
          editorInput(row.title, { placeholder: "メモ名", onInput: (v) => { row.title = v; } }),
          editorCheckbox("ココフォリアへ出力", !row.private, (v) => { row.private = !v; }),
          rowDeleteButton(() => editorData.memos.splice(index, 1)),
        );
        card.append(head, editorTextarea(row.body, (v) => { row.body = v; }));
        editorBody.appendChild(card);
      });

      const add = document.createElement("button");
      add.type = "button";
      add.className = "editorAdd";
      add.textContent = "＋ メモ追加";
      add.addEventListener("click", () => {
        editorData.memos.push({ title: "新しいメモ", body: "", private: false });
        markEditorDirty();
        renderEditor();
      });
      editorBody.appendChild(add);
    }

    function renderPalettesEditor() {
      editorData.palettes.forEach((row, index) => {
        const card = document.createElement("div");
        card.className = "editorCard";
        const head = document.createElement("div");
        head.className = "editorCardHead paletteHead";
        const name = editorInput(row.name, { placeholder: "パレット名", onInput: (v) => { row.name = v; } });
        const mode = document.createElement("select");
        mode.className = "editorSelect";
        for (const [value, label] of [["normal", "通常"], ["kp", "KP"]]) {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = label;
          option.selected = row.mode === value;
          mode.appendChild(option);
        }
        mode.addEventListener("change", () => {
          row.mode = mode.value;
          markEditorDirty();
        });
        head.append(name, mode, rowDeleteButton(() => editorData.palettes.splice(index, 1)));
        card.append(head, editorTextarea(row.content, (v) => { row.content = v; }));
        editorBody.appendChild(card);
      });

      const add = document.createElement("button");
      add.type = "button";
      add.className = "editorAdd";
      add.textContent = "＋ パレット追加";
      add.addEventListener("click", () => {
        editorData.palettes.push({ name: "新しいパレット", mode: "normal", content: "" });
        markEditorDirty();
        renderEditor();
      });
      editorBody.appendChild(add);
    }

    function renderClassificationEditor() {
      const label = document.createElement("div");
      label.className = "editorLabel";
      label.textContent = "タグ";
      editorBody.appendChild(label);

      const cards = document.createElement("div");
      cards.className = "editorTagCards";

      const currentTags =
        Array.isArray(editorData.tags)
          ? editorData.tags
          : [];

      for (const tagName of currentTags) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "tagCard removable";
        button.title = "クリックで外す";

        const name = document.createElement("span");
        name.textContent = tagName;

        const remove = document.createElement("span");
        remove.className = "tagCardRemove";
        remove.textContent = "×";

        button.append(name, remove);

        button.addEventListener("click", () => {
          editorData.tags =
            currentTags.filter(
              (value) => value !== tagName
            );
          markEditorDirty();
          renderEditor();
        });

        cards.appendChild(button);
      }

      const add = document.createElement("button");
      add.type = "button";
      add.className = "editorAdd";
      add.textContent = "＋ タグ追加";

      add.addEventListener("click", async () => {
        const values =
          await showTagPicker({
            title: "タグを選択",
            initial: editorData.tags || [],
            okText: "反映",
          });

        if (!values) {
          return;
        }

        editorData.tags = values;
        markEditorDirty();
        renderEditor();
      });

      editorBody.append(cards, add);

      const title = document.createElement("div");
      title.className = "editorLabel";
      title.style.marginTop = "14px";
      title.textContent = "所属グループ";
      editorBody.appendChild(title);

      const list = document.createElement("div");
      list.className = "groupCheckList";
      const selectedGroups = new Set(editorData.group_ids || []);
      for (const group of buildGroupOptions(editorData.groups || [])) {
        const check = editorCheckbox(group.label, selectedGroups.has(group.id), (checked) => {
          const current = new Set(editorData.group_ids || []);
          if (checked) current.add(group.id);
          else current.delete(group.id);
          editorData.group_ids = [...current];
        });
        list.appendChild(check);
      }
      editorBody.appendChild(list);
    }

    function renderEditor() {
      if (!editorData) return;
      refreshEditorPreview();
      renderEditorTabs();
      editorBody.textContent = "";
      if (editorTab === "basic") renderBasicEditor();
      else if (editorTab === "statuses") renderStatusesEditor();
      else if (editorTab === "params") renderParamsEditor();
      else if (editorTab === "skills") renderSkillsEditor();
      else if (editorTab === "memos") renderMemosEditor();
      else if (editorTab === "palettes") renderPalettesEditor();
      else renderClassificationEditor();
    }

    async function openCharacterEditor(character) {
      setLoading(true);
      try {
        const data = await apiGet(
          `/api/character/${encodeURIComponent(character.id)}/editor`,
        );
        editorCharacterId = character.id;
        editorData = data.editor;

        await loadEditorImages();
        editorTab = "basic";
        editorDirty = false;
        editorTitle.textContent = editorData.character?.name || "キャラクター編集";
        editorSaveState.textContent = "";
        renderEditor();
        editorBackdrop.classList.add("open");
      } finally {
        setLoading(false);
      }
    }

    function closeCharacterEditor(force = false) {
      if (!editorBackdrop.classList.contains("open")) return true;
      if (!force && editorDirty) {
        const accepted = window.confirm("未保存の変更があります。保存せず閉じますか？");
        if (!accepted) return false;
      }
      editorBackdrop.classList.remove("open");
      hideEditorDropOverlay();
      editorDragDepth = 0;
      editorData = null;
      editorCharacterId = null;
      editorDirty = false;
      editorBody.textContent = "";
      setPreviewFallback(
        editorPreview,
        editorPreviewFallback,
        {
          name: "",
          color: "#cbc8d8",
        },
        "large",
      );
      return true;
    }

    async function saveCharacterEditor() {
      if (!editorCharacterId || !editorData) return;
      editorSave.disabled = true;
      editorSaveState.textContent = "保存中…";
      try {
        const data = await apiPost(
          `/api/character/${encodeURIComponent(editorCharacterId)}/editor`,
          {
            character: editorData.character,
            statuses: editorData.statuses,
            params: editorData.params,
            skills: editorData.skills,
            memos: editorData.memos,
            palettes: editorData.palettes,
            tags: editorData.tags,
            group_ids: editorData.group_ids,
          },
        );
        editorData = data.editor;
        editorTitle.textContent = editorData.character?.name || "キャラクター編集";
        setEditorSaved();
        renderEditor();
        await loadCharacters();
      } catch (error) {
        editorSaveState.textContent = "保存エラー";
        window.alert(`保存できません: ${error?.message || error}`);
      } finally {
        editorSave.disabled = false;
      }
    }

    async function manageGroups() {
      const current = groupSelect.value;
      const actualGroup = current && current !== "__ungrouped__";

      const values = await showModal({
        title: "グループ操作",
        okText: "実行",
        fields: [
          {
            name: "action",
            type: "select",
            options: [
              { value: "create", label: "新規グループ作成" },
              ...(actualGroup ? [
                { value: "child", label: "選択グループの子を作成" },
                { value: "rename", label: "選択グループ名を変更" },
                { value: "delete", label: "選択グループを削除" },
              ] : []),
            ],
          },
          {
            name: "name",
            placeholder: "グループ名（削除時は空欄でOK）",
          },
        ],
      });

      if (!values) return;

      if (values.action === "create" || values.action === "child") {
        if (!values.name.trim()) return;
        await apiPost("/api/groups/create", {
          name: values.name.trim(),
          parent_group_id: values.action === "child" ? current : null,
        });
      } else if (values.action === "rename") {
        if (!values.name.trim()) return;
        await apiPost("/api/groups/rename", {
          group_id: current,
          name: values.name.trim(),
        });
      } else if (values.action === "delete") {
        if (!window.confirm("選択中のグループを削除しますか？キャラクター自体は削除されません。")) {
          return;
        }
        await apiPost("/api/groups/delete", {
          group_id: current,
        });
        groupSelect.value = "";
      }

      await refreshAll();
    }

    function renderCharacters() {
      list.textContent = "";

      if (!characters.length) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent =
          "該当するキャラクターはいません。";
        list.appendChild(empty);
        updateSelectedUi();
        return;
      }

      for (const character of characters) {
        const row = document.createElement("div");
        row.className = "row";
        row.dataset.id = character.id;

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.className = "check";
        checkbox.checked = selected.has(
          character.id
        );

        const icon = document.createElement("div");
        icon.className = "charIcon";

        const fallback = document.createElement("div");
        fallback.className = "charFallback";
        fallback.textContent =
          characterFallbackText(character);

        if (character.color) {
          fallback.style.color = character.color;
        }

        icon.appendChild(fallback);
        void applyCharacterIcon(
          character,
          icon,
        );

        const text = document.createElement("div");
        text.className = "charText";

        const name = document.createElement("div");
        name.className = "charName";
        name.textContent =
          character.name || "(名称なし)";
        if (character.color) {
          name.style.color = character.color;
        }

        const player = document.createElement("div");
        player.className = "player";
        player.textContent =
          character.player_name
          ? `Player: ${character.player_name}`
          : "";

        text.appendChild(name);
        text.appendChild(player);

        const send = document.createElement("button");
        send.type = "button";
        send.className = "sendOne";
        send.textContent = "送る";

        checkbox.addEventListener(
          "change",
          () => {
            if (checkbox.checked) {
              selected.add(character.id);
            } else {
              selected.delete(character.id);
            }
            updateSelectedUi();
          },
        );

        const openCharacterQuickMemo =
          () => {
            openQuickMemo(character);
          };

        icon.addEventListener(
          "click",
          openCharacterQuickMemo,
        );

        text.addEventListener(
          "click",
          openCharacterQuickMemo,
        );

        row.addEventListener(
          "contextmenu",
          (event) => {
            event.preventDefault();
            openContextMenu(
              character,
              event.clientX,
              event.clientY,
            );
          },
        );

        send.addEventListener(
          "click",
          async () => {
            send.disabled = true;
            try {
              await apiPost(
                "/api/send",
                {
                  character_ids: [
                    character.id,
                  ],
                },
              );
            } catch (error) {
              window.alert(
                `CCM送信エラー: ${
                  error?.message || error
                }`,
              );
            } finally {
              send.disabled = false;
            }
          },
        );

        row.appendChild(checkbox);
        row.appendChild(icon);
        row.appendChild(text);
        row.appendChild(send);
        list.appendChild(row);
      }

      updateSelectedUi();
    }

    async function loadGroups() {
      const data = await apiGet(
        "/api/groups",
      );

      groups = Array.isArray(data.groups)
        ? data.groups
        : [];

      const selectedValue =
        groupSelect.value;

      while (
        groupSelect.options.length > 2
      ) {
        groupSelect.remove(2);
      }

      for (
        const item
        of buildGroupOptions(groups)
      ) {
        const option =
          document.createElement("option");
        option.value = item.id;
        option.textContent = item.label;
        groupSelect.appendChild(option);
      }

      if (
        [...groupSelect.options]
          .some(
            (option) =>
              option.value === selectedValue
          )
      ) {
        groupSelect.value =
          selectedValue;
      }
    }

    async function loadCharacters() {
      setLoading(true);

      try {
        const params =
          new URLSearchParams();

        const searchText =
          searchMode === "tag"
            ? tagSearchText()
            : search.value.trim();

        if (searchText) {
          params.set(
            "search",
            searchText,
          );
        }

        params.set(
          "mode",
          searchMode,
        );

        if (groupSelect.value) {
          params.set(
            "group",
            groupSelect.value,
          );
        }

        const data = await apiGet(
          `/api/characters?${params.toString()}`,
        );

        characters = Array.isArray(
          data.characters
        )
          ? data.characters
          : [];

        setOnline(true);
        renderCharacters();
      } catch (error) {
        characters = [];
        selected.clear();
        renderCharacters();
        setOnline(false);

        list.textContent = "";
        const message =
          document.createElement("div");
        message.className = "error";
        message.textContent =
          "CCFOLIA Character Manager本体を起動してください。";
        list.appendChild(message);
      } finally {
        setLoading(false);
      }
    }

    async function refreshAll() {
      setLoading(true);

      try {
        await loadGroups();
        await loadTags();
        await loadCharacters();
        setOnline(true);
      } catch (error) {
        setOnline(false);
        await loadCharacters();
      } finally {
        setLoading(false);
      }
    }

    function selectedCharacterIds() {
      return [...selected];
    }

    async function runBulkCharacterPosts(
      ids,
      endpointBuilder,
      payloadBuilder,
    ) {
      const failures = [];

      for (const id of ids) {
        try {
          await apiPost(
            endpointBuilder(id),
            payloadBuilder(id),
          );
        } catch (error) {
          failures.push(
            {
              id,
              error:
                error?.message
                || String(error),
            },
          );
        }
      }

      return failures;
    }

    async function bulkAddTags() {
      const ids = selectedCharacterIds();

      if (!ids.length) {
        return;
      }

      const selectedTags =
        await showTagPicker({
          title: `${ids.length}件にタグ追加`,
          okText: "追加",
        });

      if (!selectedTags || !selectedTags.length) {
        return;
      }

      setLoading(true);

      try {
        const failures =
          await runBulkCharacterPosts(
            ids,
            (id) =>
              `/api/character/${encodeURIComponent(id)}/tags`,
            () => ({
              tag_names: selectedTags,
            }),
          );

        await loadTags();
        await loadCharacters();

        if (failures.length) {
          window.alert(
            `${ids.length - failures.length}件に追加しました。`
            + ` ${failures.length}件は失敗しました。`,
          );
        }
      } finally {
        setLoading(false);
      }
    }

    async function bulkAddGroup() {
      const ids =
        selectedCharacterIds();

      if (!ids.length) {
        return;
      }

      const options =
        buildGroupOptions(groups);

      if (!options.length) {
        window.alert(
          "グループがまだありません。"
        );
        return;
      }

      const values =
        await showModal(
          {
            title:
              `${ids.length}件にグループ追加`,
            okText: "追加",
            fields: [
              {
                name: "group_id",
                type: "select",
                options:
                  options.map(
                    (item) => ({
                      value:
                        item.id,
                      label:
                        item.label,
                    }),
                  ),
              },
            ],
          },
        );

      if (!values?.group_id) {
        return;
      }

      setLoading(true);

      try {
        const failures =
          await runBulkCharacterPosts(
            ids,
            (id) =>
              `/api/character/${encodeURIComponent(id)}/group`,
            () => ({
              group_id:
                values.group_id,
            }),
          );

        await loadCharacters();

        if (failures.length) {
          window.alert(
            `${ids.length - failures.length}件に追加しました。`
            + ` ${failures.length}件は失敗しました。`,
          );
        }
      } finally {
        setLoading(false);
      }
    }

    async function bulkMoveToTrash() {
      const ids =
        selectedCharacterIds();

      if (!ids.length) {
        return;
      }

      const accepted =
        window.confirm(
          `選択中の${ids.length}件をゴミ箱へ移動しますか？`,
        );

      if (!accepted) {
        return;
      }

      setLoading(true);

      try {
        const failures =
          await runBulkCharacterPosts(
            ids,
            (id) =>
              `/api/character/${encodeURIComponent(id)}/trash`,
            () => ({}),
          );

        const failedIds =
          new Set(
            failures.map(
              (item) =>
                item.id
            ),
          );

        for (const id of ids) {
          if (!failedIds.has(id)) {
            selected.delete(id);
          }
        }

        await loadCharacters();

        if (failures.length) {
          window.alert(
            `${ids.length - failures.length}件をゴミ箱へ移動しました。`
            + ` ${failures.length}件は失敗しました。`,
          );
        }
      } finally {
        setLoading(false);
        updateSelectedUi();
      }
    }

    async function sendSelectedCharacters() {
      const ids = [...selected];

      if (!ids.length) {
        return;
      }

      sendSelected.disabled = true;

      try {
        await apiPost(
          "/api/send",
          {
            character_ids: ids,
          },
        );
      } catch (error) {
        window.alert(
          `CCM送信エラー: ${
            error?.message || error
          }`,
        );
      } finally {
        updateSelectedUi();
      }
    }


    // CHARACTER_SALVAGE_IMPORT_PANEL_V1
    function requestRoomCharactersForImport() {
      return new Promise((resolve, reject) => {
        const requestId =
          `character-import-${Date.now()}-${
            Math.random().toString(16).slice(2)
          }`;

        const cleanup = () => {
          window.removeEventListener(
            "message",
            onMessage,
          );
          window.clearTimeout(timeoutId);
        };

        const onMessage = (event) => {
          if (event.source !== window) {
            return;
          }

          const data = event.data;
          if (
            !data
            || data.source !== "ccfolia-manager-main"
            || data.type !== "character-salvage-import-result"
            || data.requestId !== requestId
          ) {
            return;
          }

          cleanup();

          if (data.ok) {
            resolve(data.result || {});
            return;
          }

          reject(
            new Error(
              data.error
              || "CCFOLIAキャラクターの取得に失敗しました。",
            ),
          );
        };

        const timeoutId = window.setTimeout(
          () => {
            cleanup();
            reject(
              new Error(
                "CCFOLIAキャラクター取得がタイムアウトしました。",
              ),
            );
          },
          30000,
        );

        window.addEventListener(
          "message",
          onMessage,
        );

        window.postMessage(
          {
            source: "ccfolia-manager-panel",
            type: "character-salvage-import-request",
            requestId,
          },
          window.location.origin,
        );
      });
    }

    async function runCharacterSalvageImport() {
      if (!characterSalvageImport) {
        return;
      }

      const accepted = window.confirm(
        "現在のCCFOLIAルームにあるキャラクターを"
        + "CCFOLIA Managerへ取り込みます。\n\n"
        + "すでに取り込み済みのキャラクターは"
        + "CCFOLIA上のIDで判定してスキップします。\n"
        + "続行しますか？",
      );

      if (!accepted) {
        return;
      }

      const originalText =
        characterSalvageImport.textContent;

      characterSalvageImport.disabled = true;
      characterSalvageImport.textContent = "取得中…";
      status.textContent = "CCFOLIAキャラ取得中";

      try {
        const fetched =
          await requestRoomCharactersForImport();

        // CHARACTER_SALVAGE_ROOM_TAG_PANEL_V1
        const roomId =
          String(fetched.room_id || "");
        const roomName =
          String(fetched.room_name || "").trim();
        const roomCharacters =
          Array.isArray(fetched.characters)
            ? fetched.characters
            : [];

        if (!roomCharacters.length) {
          status.textContent = "部屋キャラ 0件";
          window.alert(
            "現在のルームに取り込める"
            + "キャラクターが見つかりませんでした。",
          );
          return;
        }

        characterSalvageImport.textContent = "保存中…";
        status.textContent =
          `${roomCharacters.length}件 保存中`;

        const data = await apiPost(
          "/api/character-salvage/import",
          {
            room_id: roomId,
            room_name: roomName,
            characters: roomCharacters,
          },
        );

        const result = data.result || {};
        const imported = Number(result.imported || 0);
        const skipped = Number(result.skipped || 0);
        const imageImported = Number(result.image_imported || 0);
        const imageFailed = Number(result.image_failed || 0);
        const roomTag =
          String(result.room_tag || "").trim();
        const tagged =
          Number(result.tagged || 0);

        await refreshAll();

        status.textContent =
          `新規${imported} / 既存${skipped}`;

        let message =
          `CCFOLIAからの取り込みが完了しました。\n\n`
          + `新規: ${imported}件\n`
          + `既存スキップ: ${skipped}件\n`
          + `立ち絵保存: ${imageImported}件`;

        if (imageFailed > 0) {
          message +=
            `\n立ち絵保存失敗: ${imageFailed}件`;
        }

        if (roomTag) {
          message +=
            `\nルームタグ: ${roomTag} (${tagged}件)`;
        }

        if (fetched.truncated) {
          message +=
            "\n\n※CCFOLIA取得件数が上限に達しました。"
            + " 1000件を超える部屋は追加対応が必要です。";
        }

        window.alert(message);

      } catch (error) {
        status.textContent = "取り込み失敗";
        window.alert(
          `CCFOLIAからの取り込みに失敗しました: ${
            error?.message || error
          }`,
        );
      } finally {
        characterSalvageImport.disabled = false;
        characterSalvageImport.textContent = originalText;
      }
    }

    // IM4_IMAGES_PANEL
    function setImageStatus(text, kind = "") {
      imagesStatus.textContent = text;
      imagesStatus.classList.remove("ok", "error");

      if (kind) {
        imagesStatus.classList.add(kind);
      }
    }

    function imageTagKey(value) {
      return String(value || "")
        .trim()
        .toLocaleLowerCase("ja");
    }

    function imageTagSearchTerms() {
      const values = [
        ...selectedImageTagFilters,
      ];

      if (imageSearchMode === "tag") {
        const typed =
          imagesSearch.value
            .replace(/、/g, ",")
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean);

        values.push(...typed);
      }

      const seen = new Set();
      const result = [];

      for (const value of values) {
        const key = imageTagKey(value);
        if (!key || seen.has(key)) {
          continue;
        }

        seen.add(key);
        result.push(value);
      }

      return result;
    }

    function renderImageTagChips() {
      imagesTagChips.textContent = "";
      imagesTagChips.classList.toggle(
        "open",
        imageSearchMode === "tag",
      );

      if (imageSearchMode !== "tag") {
        return;
      }

      const selectedKeys = new Set(
        selectedImageTagFilters.map(
          imageTagKey,
        ),
      );

      for (const tag of browserImageTags) {
        const name = String(tag.name || "");
        const button =
          document.createElement("button");

        button.type = "button";
        button.className = "imageTagChip";
        button.textContent = name;
        button.title = name;

        const active =
          selectedKeys.has(
            imageTagKey(name),
          );

        button.classList.toggle(
          "active",
          active,
        );

        button.addEventListener(
          "click",
          () => {
            const key = imageTagKey(name);
            const next =
              selectedImageTagFilters.filter(
                (value) =>
                  imageTagKey(value) !== key,
              );

            if (!active) {
              next.push(name);
            }

            selectedImageTagFilters = next;
            renderImageTagChips();
            void loadBrowserImageAssets();
          },
        );

        imagesTagChips.appendChild(button);
      }
    }

    async function loadBrowserImageGroups() {
      const data = await apiGet(
        "/api/image-manager/groups",
      );

      browserImageGroups =
        Array.isArray(data.groups)
          ? data.groups
          : [];

      const selectedValue =
        imagesGroupSelect.value;

      while (
        imagesGroupSelect.options.length > 2
      ) {
        imagesGroupSelect.remove(2);
      }

      for (
        const item
        of buildGroupOptions(
          browserImageGroups,
        )
      ) {
        const option =
          document.createElement("option");

        option.value = item.id;
        option.textContent = item.label;
        imagesGroupSelect.appendChild(
          option,
        );
      }

      if (
        [...imagesGroupSelect.options]
          .some(
            (option) =>
              option.value === selectedValue,
          )
      ) {
        imagesGroupSelect.value =
          selectedValue;
      }
    }

    async function loadBrowserImageTags() {
      const data = await apiGet(
        "/api/image-manager/tags",
      );

      browserImageTags =
        Array.isArray(data.tags)
          ? data.tags
          : [];

      const validKeys = new Set(
        browserImageTags.map(
          (tag) =>
            imageTagKey(tag.name),
        ),
      );

      selectedImageTagFilters =
        selectedImageTagFilters.filter(
          (value) =>
            validKeys.has(
              imageTagKey(value),
            ),
        );

      renderImageTagChips();
    }

    async function loadImagePreviewSource(
      assetId,
      size,
    ) {
      const cache =
        size === "large"
          ? imageLargePreviewCache
          : imageThumbCache;

      if (cache.has(assetId)) {
        return cache.get(assetId);
      }

      const data = await apiGet(
        `/api/image-manager/preview/${
          encodeURIComponent(assetId)
        }?size=${encodeURIComponent(size)}`,
      );

      const src = String(
        data?.preview?.src || "",
      );

      cache.set(assetId, src);
      return src;
    }

    async function loadImageAssetThumb(
      image,
      assetId,
    ) {
      if (
        image.dataset.loaded === "1"
        || image.dataset.loading === "1"
      ) {
        return;
      }

      image.dataset.loading = "1";

      try {
        const src =
          await loadImagePreviewSource(
            assetId,
            "thumb",
          );

        if (src) {
          image.src = src;
          image.dataset.loaded = "1";
          image.style.display = "block";

          const placeholder =
            image.parentElement?.querySelector(
              ".imageAssetPlaceholder",
            );

          if (placeholder) {
            placeholder.style.display = "none";
          }
        }
      } catch (error) {
      } finally {
        image.dataset.loading = "0";
      }
    }

    function updateImagePreviewUi() {
      imagesPreviewToggle.classList.toggle(
        "active",
        imagePreviewEnabled,
      );
      imagesPreviewToggle.setAttribute(
        "aria-pressed",
        imagePreviewEnabled
          ? "true"
          : "false",
      );
      imagesPreviewHint.textContent =
        imagePreviewEnabled
          ? "プレビューモードON"
          : "プレビューモードOFF";

      if (!imagePreviewEnabled) {
        hideImageHoverPreview();
      }
    }

    // IM6_PREVIEW_TOGGLE
    function hideImageHoverPreview() {
      imageHoverAssetId = null;

      if (imageHoverTimer) {
        clearTimeout(imageHoverTimer);
        imageHoverTimer = null;
      }

      imageHoverPreview.classList.remove(
        "open",
      );
      imageHoverPreviewImg.removeAttribute(
        "src",
      );
      imageHoverPreviewName.textContent = "";
    }

    function positionImageHoverPreview(card) {
      if (
        !imageHoverPreview.classList.contains(
          "open",
        )
      ) {
        return;
      }

      const panelRect =
        imagesPanel.getBoundingClientRect();
      const cardRect =
        card.getBoundingClientRect();
      const previewRect =
        imageHoverPreview.getBoundingClientRect();

      const gap = 12;
      const width =
        previewRect.width || 480;
      const height =
        previewRect.height || 340;

      const roomRight =
        window.innerWidth
        - panelRect.right
        - gap;

      const roomLeft =
        panelRect.left
        - gap;

      let left;

      if (
        roomRight >= width
        || roomRight >= roomLeft
      ) {
        left = panelRect.right + gap;
      } else {
        left =
          panelRect.left - width - gap;
      }

      left = clamp(
        left,
        8,
        window.innerWidth
          - width
          - 8,
      );

      let top =
        cardRect.top
        + (cardRect.height / 2)
        - (height / 2);

      top = clamp(
        top,
        8,
        window.innerHeight
          - height
          - 8,
      );

      imageHoverPreview.style.left =
        `${left}px`;
      imageHoverPreview.style.top =
        `${top}px`;
    }

    function scheduleImageHover(
      asset,
      card,
    ) {
      if (!imagePreviewEnabled) {
        return;
      }

      hideImageHoverPreview();
      imageHoverAssetId = asset.id;

      imageHoverTimer = window.setTimeout(
        async () => {
          if (
            imageHoverAssetId !== asset.id
          ) {
            return;
          }

          try {
            const src =
              await loadImagePreviewSource(
                asset.id,
                "large",
              );

            if (
              !src
              || imageHoverAssetId !== asset.id
            ) {
              return;
            }

            imageHoverPreviewImg.src = src;
            imageHoverPreviewName.textContent =
              asset.display_name
              || asset.original_filename
              || "画像";

            imageHoverPreview.classList.add(
              "open",
            );

            requestAnimationFrame(
              () =>
                positionImageHoverPreview(
                  card,
                ),
            );
          } catch (error) {
          }
        },
        180,
      );
    }

    function imageBackgroundRequestId() {
      if (
        globalThis.crypto
        && typeof globalThis.crypto.randomUUID
          === "function"
      ) {
        return globalThis.crypto.randomUUID();
      }

      return [
        Date.now().toString(36),
        Math.random().toString(36).slice(2),
      ].join("-");
    }

    function applyImageBackgroundThroughPage(url) {
      return new Promise((resolve, reject) => {
        const requestId =
          imageBackgroundRequestId();

        const cleanup = () => {
          window.removeEventListener(
            "message",
            onMessage,
          );
          window.clearTimeout(timeoutId);
        };

        const onMessage = (event) => {
          if (event.source !== window) {
            return;
          }

          const data = event.data;

          if (
            !data
            || data.source
              !== "ccfolia-manager-main"
            || data.type
              !== "image-apply-background-result"
            || data.requestId !== requestId
          ) {
            return;
          }

          cleanup();

          if (data.ok) {
            resolve();
            return;
          }

          reject(
            new Error(
              data.error
              || "背景変更に失敗しました。",
            ),
          );
        };

        const timeoutId = window.setTimeout(
          () => {
            cleanup();
            reject(
              new Error(
                "CCFOLIAへの背景変更がタイムアウトしました。",
              ),
            );
          },
          15000,
        );

        window.addEventListener(
          "message",
          onMessage,
        );

        window.postMessage(
          {
            source: "ccfolia-manager-panel",
            type: "image-apply-background-request",
            requestId,
            url,
          },
          window.location.origin,
        );
      });
    }

    function browserImageFileToBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();

        reader.onerror = () => {
          reject(
            new Error(
              "画像を読み込めません。",
            ),
          );
        };

        reader.onload = () => {
          const value = String(
            reader.result || "",
          );
          const comma = value.indexOf(",");

          if (comma < 0) {
            reject(
              new Error(
                "画像データが不正です。",
              ),
            );
            return;
          }

          resolve(
            value.slice(comma + 1),
          );
        };

        reader.readAsDataURL(file);
      });
    }

    function uploadImageThroughPage({
      filename,
      contentType,
      dataBase64,
      applyBackground = false,
    }) {
      return new Promise((resolve, reject) => {
        const requestId =
          imageBackgroundRequestId();

        const cleanup = () => {
          window.removeEventListener(
            "message",
            onMessage,
          );
          window.clearTimeout(timeoutId);
        };

        const onMessage = (event) => {
          if (event.source !== window) {
            return;
          }

          const data = event.data;

          if (
            !data
            || data.source
              !== "ccfolia-manager-main"
            || data.type
              !== "image-upload-result"
            || data.requestId !== requestId
          ) {
            return;
          }

          cleanup();

          if (data.ok) {
            resolve(data.result || {});
            return;
          }

          reject(
            new Error(
              data.error
              || "画像アップロードに失敗しました。",
            ),
          );
        };

        const timeoutId = window.setTimeout(
          () => {
            cleanup();
            reject(
              new Error(
                "CCFOLIAへの画像アップロードがタイムアウトしました。",
              ),
            );
          },
          45000,
        );

        window.addEventListener(
          "message",
          onMessage,
        );

        window.postMessage(
          {
            source:
              "ccfolia-manager-panel",
            type: "image-upload-request",
            requestId,
            filename,
            contentType,
            dataBase64,
            applyBackground,
          },
          window.location.origin,
        );
      });
    }

    // IM7_IMAGE_SALVAGE_PANEL
    function listCCFOLIAImagesThroughPage() {
      return new Promise((resolve, reject) => {
        const requestId =
          imageBackgroundRequestId();

        const cleanup = () => {
          window.removeEventListener(
            "message",
            onMessage,
          );
          window.clearTimeout(timeoutId);
        };

        const onMessage = (event) => {
          if (event.source !== window) {
            return;
          }

          const data = event.data;

          if (
            !data
            || data.source
              !== "ccfolia-manager-main"
            || data.type
              !== "image-salvage-list-result"
            || data.requestId !== requestId
          ) {
            return;
          }

          cleanup();

          if (data.ok) {
            resolve(
              Array.isArray(data.images)
                ? data.images
                : [],
            );
            return;
          }

          reject(
            new Error(
              data.error
              || "CCFOLIA画像一覧の取得に失敗しました。",
            ),
          );
        };

        const timeoutId = window.setTimeout(
          () => {
            cleanup();
            reject(
              new Error(
                "CCFOLIA画像一覧の取得がタイムアウトしました。",
              ),
            );
          },
          60000,
        );

        window.addEventListener(
          "message",
          onMessage,
        );

        window.postMessage(
          {
            source:
              "ccfolia-manager-panel",
            type:
              "image-salvage-list-request",
            requestId,
          },
          window.location.origin,
        );
      });
    }

    async function salvageCCFOLIAImages() {
      if (imageSalvageBusy) {
        return;
      }

      imageSalvageBusy = true;
      imagesSalvage.disabled = true;
      setImageStatus(
        "CCFOLIA背景を取得中…",
      );
      imagesStatus.title = "";

      try {
        const images =
          await listCCFOLIAImagesThroughPage();

        if (!images.length) {
          setImageStatus(
            "背景の取込対象なし",
            "ok",
          );
          return;
        }

        // Thousands of backgrounds are synchronized in small, restart-safe batches.
        const batchSize = 50;
        const totals = {
          received: 0,
          created: 0,
          linked: 0,
          updated: 0,
          remote_only: 0,
          skipped: 0,
          errors: [],
        };

        for (
          let offset = 0;
          offset < images.length;
          offset += batchSize
        ) {
          const batch = images.slice(
            offset,
            offset + batchSize,
          );
          const endIndex = Math.min(
            images.length,
            offset + batch.length,
          );

          setImageStatus(
            `${endIndex}/${images.length} 背景を同期中…`,
          );

          const response = await apiPost(
            "/api/image-manager/salvage",
            { images: batch },
          );
          const result = response?.result || {};

          for (const key of [
            "received",
            "created",
            "linked",
            "updated",
            "remote_only",
            "skipped",
          ]) {
            totals[key] += Number(result[key] || 0);
          }

          if (Array.isArray(result.errors)) {
            totals.errors.push(...result.errors);
            if (totals.errors.length > 20) {
              totals.errors.length = 20;
            }
          }
        }

        const created = totals.created;
        const linked = totals.linked;
        const updated = totals.updated;
        const remoteOnly = totals.remote_only;
        const skipped = totals.skipped;

        const summary = [
          created ? `新規${created}` : "",
          linked ? `紐付${linked}` : "",
          updated ? `更新${updated}` : "",
          remoteOnly ? `遠隔${remoteOnly}` : "",
          skipped ? `除外${skipped}` : "",
        ].filter(Boolean);

        imageThumbCache.clear();
        imageLargePreviewCache.clear();
        await refreshImagePanel();

        setImageStatus(
          summary.length
            ? summary.join(" / ")
            : "背景同期済み",
          skipped ? "" : "ok",
        );

        if (totals.errors.length) {
          imagesStatus.title = totals.errors
            .slice(0, 8)
            .map(
              (item) =>
                `${item.file_id || "?"}: ${item.error || "error"}`,
            )
            .join("\n");
        }
      } catch (error) {
        const message = String(
          error?.message || error,
        );

        console.error(
          "[CCFOLIA Manager] background salvage failed",
          error,
        );

        setImageStatus(
          "背景取込失敗",
          "error",
        );
        imagesStatus.title = message;
      } finally {
        imageSalvageBusy = false;
        imagesSalvage.disabled = false;
      }
    }

    async function saveImageRegistration(
      imageId,
      result,
    ) {
      return apiPost(
        "/api/image-manager/register",
        {
          image_id: imageId,
          file_id: String(
            result.fileId || "",
          ),
          url: String(
            result.url || "",
          ),
          content_type: String(
            result.contentType || "",
          ),
          file_size: Number(
            result.fileSize || 0,
          ),
        },
      );
    }

    async function uploadLocalImageAsset(
      asset,
      {
        applyBackground = false,
      } = {},
    ) {
      const data = await apiGet(
        `/api/image-manager/upload-source/${
          encodeURIComponent(asset.id)
        }`,
      );

      const source = data.source || {};

      if (!source.data_base64) {
        throw new Error(
          "ローカル画像データを取得できませんでした。",
        );
      }

      const result =
        await uploadImageThroughPage({
          filename:
            source.filename
            || asset.original_filename
            || "image.png",
          contentType:
            source.content_type
            || "image/png",
          dataBase64:
            source.data_base64,
          applyBackground,
        });

      await saveImageRegistration(
        asset.id,
        result,
      );

      asset.ccfolia_registered = true;

      return result;
    }

    async function importBrowserImageFiles(
      files,
    ) {
      const images = Array.from(
        files || [],
      ).filter(
        (file) =>
          !file.type
          || file.type.startsWith("image/"),
      );

      if (!images.length) {
        return;
      }

      const maxBytes =
        12 * 1024 * 1024;

      imagesImport.disabled = true;
      setImageStatus("画像追加中…");
      imagesStatus.title = "";

      try {
        let completed = 0;

        for (const file of images) {
          if (file.size > maxBytes) {
            throw new Error(
              `${file.name} は12MBを超えています。`,
            );
          }

          const dataBase64 =
            await browserImageFileToBase64(
              file,
            );

          const imported = await apiPost(
            "/api/image-manager/import",
            {
              filename: file.name,
              data_base64: dataBase64,
            },
          );

          const imageId = String(
            imported.image?.id || "",
          );

          if (!imageId) {
            throw new Error(
              "Managerへの画像登録に失敗しました。",
            );
          }

          const result =
            await uploadImageThroughPage({
              filename: file.name,
              contentType:
                file.type || "image/png",
              dataBase64,
              applyBackground: false,
            });

          await saveImageRegistration(
            imageId,
            result,
          );

          completed += 1;
          setImageStatus(
            `${completed}/${images.length} 追加中…`,
          );
        }

        setImageStatus(
          `${completed}枚追加`,
          "ok",
        );

        await refreshImagePanel();
      } catch (error) {
        const message = String(
          error?.message || error,
        );

        console.error(
          "[CCFOLIA Manager] image import failed",
          error,
        );

        setImageStatus(
          "画像追加失敗",
          "error",
        );
        imagesStatus.title = message;
      } finally {
        imagesImport.disabled = false;
        imagesImportInput.value = "";
      }
    }


    // MEDIA_PANEL_DRAGDROP_V1
    function mediaPanelHasFiles(event) {
      const types = Array.from(
        event?.dataTransfer?.types || [],
      );

      return types.includes("Files");
    }

    function genericFileToBase64(
      file,
      kindLabel = "ファイル",
    ) {
      return new Promise(
        (resolve, reject) => {
          const reader =
            new FileReader();

          reader.onerror = () => {
            reject(
              new Error(
                `${kindLabel}を読み込めません。`,
              ),
            );
          };

          reader.onload = () => {
            const value = String(
              reader.result || "",
            );
            const comma =
              value.indexOf(",");

            if (comma < 0) {
              reject(
                new Error(
                  `${kindLabel}データが不正です。`,
                ),
              );
              return;
            }

            resolve(
              value.slice(comma + 1),
            );
          };

          reader.readAsDataURL(
            file,
          );
        },
      );
    }

    async function importBrowserBgmFiles(
      files,
    ) {
      const allowed =
        /\.(mp3|wav|ogg|oga|m4a|aac|flac|opus|webm)$/i;

      const audioFiles = Array.from(
        files || [],
      ).filter(
        (file) =>
          (
            file.type
            && file.type.startsWith(
              "audio/",
            )
          )
          || allowed.test(
            file.name || "",
          ),
      );

      if (!audioFiles.length) {
        if (bgmProbeStatus) {
          bgmProbeStatus.textContent =
            "音声ファイルなし";
        }
        return;
      }

      const maxBytes =
        64 * 1024 * 1024;

      let completed = 0;
      let duplicates = 0;

      if (bgmProbeStatus) {
        bgmProbeStatus.textContent =
          `0/${audioFiles.length} 追加中…`;
      }

      try {
        for (
          const file
          of audioFiles
        ) {
          if (
            file.size
            > maxBytes
          ) {
            throw new Error(
              `${file.name} は64MBを超えています。`,
            );
          }

          const dataBase64 =
            await genericFileToBase64(
              file,
              "音声",
            );

          const response =
            await apiPost(
              "/api/bgm-manager/import",
              {
                filename:
                  file.name,
                data_base64:
                  dataBase64,
                media_kind:
                  "bgm",
              },
            );

          if (
            response.bgm
            && response.bgm.created
              === false
          ) {
            duplicates += 1;
          }

          completed += 1;

          if (bgmProbeStatus) {
            bgmProbeStatus.textContent =
              `${completed}/${audioFiles.length} 追加中…`;
          }
        }

        if (bgmProbeStatus) {
          bgmProbeStatus.textContent =
            duplicates
              ? `${completed}件追加・重複${duplicates}`
              : `${completed}件追加`;
        }

        bgmPage = 1;
        await refreshBgmPanel();

      } catch (error) {
        const message =
          String(
            error?.message
            || error,
          );

        if (bgmProbeStatus) {
          bgmProbeStatus.textContent =
            "BGM追加失敗";
          bgmProbeStatus.title =
            message;
        }

        window.alert(
          `BGMを追加できません: ${message}`,
        );
      }
    }

    function installMediaPanelDropTarget(
      panelElement,
      overlayElement,
      handler,
    ) {
      if (
        !panelElement
        || !overlayElement
      ) {
        return;
      }

      let dragDepth = 0;

      const reset = () => {
        dragDepth = 0;
        panelElement.classList.remove(
          "mediaDropActive",
        );
      };

      panelElement.addEventListener(
        "dragenter",
        (event) => {
          if (
            !mediaPanelHasFiles(
              event,
            )
          ) {
            return;
          }

          event.preventDefault();
          event.stopPropagation();

          dragDepth += 1;

          panelElement.classList.add(
            "mediaDropActive",
          );
        },
      );

      panelElement.addEventListener(
        "dragover",
        (event) => {
          if (
            !mediaPanelHasFiles(
              event,
            )
          ) {
            return;
          }

          event.preventDefault();
          event.stopPropagation();

          if (
            event.dataTransfer
          ) {
            event.dataTransfer.dropEffect =
              "copy";
          }

          panelElement.classList.add(
            "mediaDropActive",
          );
        },
      );

      panelElement.addEventListener(
        "dragleave",
        (event) => {
          if (
            !mediaPanelHasFiles(
              event,
            )
          ) {
            return;
          }

          event.preventDefault();
          event.stopPropagation();

          dragDepth = Math.max(
            0,
            dragDepth - 1,
          );

          if (
            dragDepth === 0
          ) {
            panelElement.classList.remove(
              "mediaDropActive",
            );
          }
        },
      );

      panelElement.addEventListener(
        "drop",
        (event) => {
          if (
            !mediaPanelHasFiles(
              event,
            )
          ) {
            return;
          }

          event.preventDefault();
          event.stopPropagation();

          const files =
            event.dataTransfer
              ?.files;

          reset();

          if (
            files
            && files.length
          ) {
            void handler(
              files,
            );
          }
        },
      );

      window.addEventListener(
        "blur",
        reset,
      );
    }

    async function applyBrowserImageAsset(
      asset,
      card,
    ) {
      if (imageBackgroundBusy) {
        return;
      }

      imageBackgroundBusy = true;
      card.classList.add("applying");
      setImageStatus("背景変更中…");
      imagesStatus.title = "";

      try {
        let image = null;

        if (!asset.ccfolia_registered) {
          setImageStatus(
            "CCFOLIAへ登録中…",
          );

          const result =
            await uploadLocalImageAsset(
              asset,
              {
                applyBackground: true,
              },
            );

          image = {
            display_name:
              asset.display_name,
            url: result.url,
          };

          card.classList.add(
            "ccfoliaReady",
          );
        } else {
          const data = await apiGet(
            `/api/image-manager/apply-info/${
              encodeURIComponent(asset.id)
            }`,
          );

          image = data.image || {};
          const url = String(
            image.url || "",
          );

          if (!url) {
            throw new Error(
              "CCFOLIA画像URLがありません。",
            );
          }

          await applyImageBackgroundThroughPage(
            url,
          );
        }

        const name =
          image.display_name
          || asset.display_name
          || asset.original_filename
          || "画像";

        setImageStatus(
          "背景変更済み",
          "ok",
        );
        imagesStatus.title = name;
        card.classList.add("applied");

        window.setTimeout(
          () => {
            card.classList.remove("applied");
          },
          900,
        );
      } catch (error) {
        const message = String(
          error?.message || error,
        );

        console.error(
          "[CCFOLIA Manager] image background apply failed",
          error,
        );

        setImageStatus(
          "背景変更失敗",
          "error",
        );
        imagesStatus.title = message;
      } finally {
        imageBackgroundBusy = false;
        card.classList.remove("applying");
      }
    }

    function renderBrowserImageAssets() {
      if (imageThumbObserver) {
        imageThumbObserver.disconnect();
        imageThumbObserver = null;
      }

      imageAssetGrid.textContent = "";
      imagesCount.textContent =
        `${browserImageTotal}件`;

      const pageStart =
        browserImageAssets.length
          ? browserImageOffset + 1
          : 0;
      const pageEnd =
        browserImageOffset
        + browserImageAssets.length;

      imagesPageInfo.textContent =
        browserImageTotal
          ? `${pageStart}–${pageEnd} / ${browserImageTotal}`
          : "0 / 0";

      imagesPrevPage.disabled =
        browserImageOffset <= 0;
      imagesNextPage.disabled =
        pageEnd >= browserImageTotal;

      if (!browserImageAssets.length) {
        const empty =
          document.createElement("div");
        empty.className =
          "imageManagerEmpty";
        empty.textContent =
          "該当する画像がありません。";
        imageAssetGrid.appendChild(empty);
        return;
      }

      imageThumbObserver =
        new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              if (!entry.isIntersecting) {
                continue;
              }

              const image =
                entry.target.querySelector(
                  ".imageAssetThumb",
                );

              if (image) {
                void loadImageAssetThumb(
                  image,
                  entry.target.dataset.assetId,
                );
              }

              imageThumbObserver.unobserve(
                entry.target,
              );
            }
          },
          {
            root: imageAssetGrid,
            rootMargin: "160px",
          },
        );

      for (const asset of browserImageAssets) {
        const card =
          document.createElement("div");
        card.className =
          "imageAssetCard";
        card.classList.toggle(
          "ccfoliaReady",
          Boolean(asset.ccfolia_registered),
        );
        card.dataset.assetId = asset.id;
        card.title = [
          asset.display_name
          || asset.original_filename
          || "画像",
          asset.ccfolia_registered
            ? "クリックで現在の背景に設定"
            : "CCFOLIA未登録",
        ].join("\n");

        const thumbWrap =
          document.createElement("div");
        thumbWrap.className =
          "imageAssetThumbWrap";

        const placeholder =
          document.createElement("div");
        placeholder.className =
          "imageAssetPlaceholder";
        placeholder.textContent =
          "PREVIEW";

        const image =
          document.createElement("img");
        image.className =
          "imageAssetThumb";
        image.alt = "";
        image.style.display = "none";

        thumbWrap.appendChild(placeholder);
        thumbWrap.appendChild(image);

        if (asset.ccfolia_registered) {
          const badge =
            document.createElement("span");
          badge.className =
            "imageAssetBadge";
          badge.textContent = "CC";
          badge.title =
            "CCFOLIA登録済み";
          thumbWrap.appendChild(badge);
        }

        const name =
          document.createElement("div");
        name.className =
          "imageAssetName";
        name.textContent =
          asset.display_name
          || asset.original_filename
          || "画像";

        card.appendChild(thumbWrap);
        card.appendChild(name);

        card.addEventListener(
          "click",
          () => {
            void applyBrowserImageAsset(
              asset,
              card,
            );
          },
        );

        card.addEventListener(
          "pointerenter",
          () => {
            scheduleImageHover(
              asset,
              card,
            );
          },
        );

        card.addEventListener(
          "pointerleave",
          hideImageHoverPreview,
        );

        imageAssetGrid.appendChild(card);
        imageThumbObserver.observe(card);
      }
    }

    async function loadBrowserImageAssets(
      { resetPage = true } = {},
    ) {
      if (resetPage) {
        browserImageOffset = 0;
      }

      const params =
        new URLSearchParams();

      let searchText = "";

      if (imageSearchMode === "tag") {
        searchText =
          imageTagSearchTerms().join(",");
      } else {
        searchText =
          imagesSearch.value.trim();
      }

      if (searchText) {
        params.set("search", searchText);
      }

      params.set(
        "mode",
        imageSearchMode,
      );

      if (imagesGroupSelect.value) {
        params.set(
          "group",
          imagesGroupSelect.value,
        );
      }

      if (imageTaglessOnly) {
        params.set(
          "tagless",
          "1",
        );
      }

      params.set(
        "limit",
        String(browserImagePageSize),
      );
      params.set(
        "offset",
        String(browserImageOffset),
      );

      setImageStatus(
        "読込中",
      );

      try {
        const data = await apiGet(
          `/api/image-manager/assets?${
            params.toString()
          }`,
        );

        browserImageAssets =
          Array.isArray(data.assets)
            ? data.assets
            : [];

        browserImageTotal = Math.max(
          0,
          Number(data.total || 0),
        );

        if (
          browserImageTotal > 0
          && browserImageOffset
            >= browserImageTotal
        ) {
          browserImageOffset =
            Math.floor(
              (browserImageTotal - 1)
              / browserImagePageSize,
            ) * browserImagePageSize;

          return loadBrowserImageAssets({
            resetPage: false,
          });
        }

        renderBrowserImageAssets();
        imageAssetGrid.scrollTop = 0;
        setImageStatus(
          "ローカル接続",
          "ok",
        );
        setOnline(true);
      } catch (error) {
        browserImageAssets = [];
        browserImageTotal = 0;
        browserImageOffset = 0;
        renderBrowserImageAssets();
        setImageStatus(
          "本体オフライン",
          "error",
        );
        setOnline(false);
      }
    }

    async function refreshImagePanel() {
      setImageStatus("読込中");

      try {
        await Promise.all([
          loadBrowserImageGroups(),
          loadBrowserImageTags(),
        ]);

        await loadBrowserImageAssets();
      } catch (error) {
        setImageStatus(
          "本体オフライン",
          "error",
        );
        setOnline(false);
      }
    }

    function positionModulePanel(surface) {
      const rect =
        button.getBoundingClientRect();

      const panelWidth =
        Math.min(
          390,
          window.innerWidth - 26,
        );
      const panelHeight =
        Math.min(
          window.innerHeight * 0.72,
          720,
        );

      const openRight =
        rect.left
        + rect.width
        + 12
        + panelWidth
        <= window.innerWidth;

      let left = openRight
        ? rect.right + 10
        : rect.left - panelWidth - 10;

      left = clamp(
        left,
        8,
        window.innerWidth
          - panelWidth
          - 8,
      );

      let top =
        rect.top
        + rect.height
        - panelHeight;

      top = clamp(
        top,
        8,
        window.innerHeight
          - panelHeight
          - 8,
      );

      surface.style.left = `${left}px`;
      surface.style.top = `${top}px`;
      surface.style.height =
        `${panelHeight}px`;
    }

    function positionPanel() {
      positionModulePanel(panel);
    }

    function positionToolkitMenu() {
      const rect =
        button.getBoundingClientRect();

      const menuWidth = 168;
      const menuHeight = 132;

      const openRight =
        rect.right
        + 10
        + menuWidth
        <= window.innerWidth;

      let left = openRight
        ? rect.right + 10
        : rect.left - menuWidth - 10;

      let top =
        rect.bottom - menuHeight;

      left = clamp(
        left,
        8,
        window.innerWidth
          - menuWidth
          - 8,
      );

      top = clamp(
        top,
        8,
        window.innerHeight
          - menuHeight
          - 8,
      );

      toolkitMenu.style.left = `${left}px`;
      toolkitMenu.style.top = `${top}px`;
    }

    function closeToolkitMenu() {
      toolkitMenu.classList.remove("open");
    }

    // BGM_BROWSER_PANEL_V1
    function setBgmStatus(text, state = "") {
      if (!bgmProbeStatus) return;
      bgmProbeStatus.textContent = String(text || "");
      bgmProbeStatus.classList.toggle("ok", state === "ok");
      bgmProbeStatus.classList.toggle("error", state === "error");
    }

    function bgmTagKey(value) {
      return String(value || "").trim().toLocaleLowerCase("ja");
    }

    function bgmGroupPath(groupId) {
      const map = new Map(
        browserBgmGroups.map(
          (group) => [String(group.id), group],
        ),
      );
      const seen = new Set();
      const parts = [];
      let id = String(groupId || "");

      while (id && map.has(id) && !seen.has(id)) {
        seen.add(id);
        const group = map.get(id);
        parts.unshift(String(group.name || id));
        id = String(group.parent_group_id || "");
      }
      return parts.join(" / ");
    }

    function renderBgmGroups() {
      const selected = bgmGroupSelect.value;
      bgmGroupSelect.textContent = "";

      const all = document.createElement("option");
      all.value = "";
      all.textContent = "すべて";
      bgmGroupSelect.appendChild(all);

      const ungrouped = document.createElement("option");
      ungrouped.value = "__ungrouped__";
      ungrouped.textContent = "未分類";
      bgmGroupSelect.appendChild(ungrouped);

      const rows = [...browserBgmGroups]
        .map(
          (group) => ({
            id: String(group.id),
            label: bgmGroupPath(group.id),
          }),
        )
        .sort(
          (a, b) => a.label.localeCompare(b.label, "ja"),
        );

      for (const row of rows) {
        const option = document.createElement("option");
        option.value = row.id;
        option.textContent = row.label;
        bgmGroupSelect.appendChild(option);
      }

      if (
        [...bgmGroupSelect.options]
          .some((option) => option.value === selected)
      ) {
        bgmGroupSelect.value = selected;
      }
    }

    function renderBgmTagChips() {
      bgmTagChips.textContent = "";

      for (const tag of browserBgmTags) {
        const name = String(tag.name || "").trim();
        if (!name) continue;

        const button = document.createElement("button");
        button.type = "button";
        button.className = "bgmTagChip";
        button.textContent = name;

        if (
          bgmSearchMode === "tag"
          && bgmTagKey(bgmSearch.value) === bgmTagKey(name)
        ) {
          button.classList.add("active");
        }

        button.addEventListener(
          "click",
          () => {
            bgmSearchMode = "tag";
            bgmKeywordMode.classList.remove("active");
            bgmTagMode.classList.add("active");
            bgmSearch.value = name;
            bgmPage = 1;
            renderBgmTagChips();
            void loadBrowserBgmAssets();
          },
        );

        bgmTagChips.appendChild(button);
      }
    }

    function formatBgmDuration(durationMs) {
      let seconds = Math.max(
        0,
        Math.floor(Number(durationMs || 0) / 1000),
      );
      if (!seconds) return "--:--";

      const hours = Math.floor(seconds / 3600);
      seconds -= hours * 3600;
      const minutes = Math.floor(seconds / 60);
      const rest = seconds % 60;

      if (hours) {
        return `${hours}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
      }
      return `${minutes}:${String(rest).padStart(2, "0")}`;
    }

    async function editBrowserBgm(asset) {
      const result = await showModal({
        title: "BGM編集",
        okText: "保存",
        fields: [
          {
            name: "display_name",
            value: asset.display_name || "",
            placeholder: "表示名",
          },
          {
            name: "volume",
            value: String(asset.default_volume ?? 0.5),
            placeholder: "音量 0〜1",
          },
          {
            type: "select",
            name: "loop",
            value: asset.default_loop ? "1" : "0",
            options: [
              { value: "1", label: "Loop ON" },
              { value: "0", label: "Loop OFF" },
            ],
          },
          {
            type: "select",
            name: "media_kind",
            value: asset.media_kind || "bgm",
            options: [
              { value: "bgm", label: "BGM" },
              { value: "se", label: "SE" },
              { value: "other", label: "その他" },
            ],
          },
          {
            name: "tags",
            value: Array.isArray(asset.tags)
              ? asset.tags.join(", ")
              : "",
            placeholder: "タグ（カンマ区切り）",
          },
        ],
      });

      if (!result) return;

      const volume = Number(result.volume);
      if (!Number.isFinite(volume) || volume < 0 || volume > 1) {
        window.alert("音量は0〜1で指定してください。");
        return;
      }

      const tags = String(result.tags || "")
        .replace(/、/g, ",")
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);

      await apiPost(
        "/api/bgm-manager/update",
        {
          bgm_id: asset.id,
          display_name: String(result.display_name || "").trim(),
          default_volume: volume,
          default_loop: result.loop === "1",
          media_kind: result.media_kind || "bgm",
          tags,
        },
      );

      await refreshBgmPanel();
    }

    function bgmPageMessage(
      type,
      payload,
      responseType,
      timeoutMs = 60000,
    ) {
      return new Promise((resolve, reject) => {
        const requestId =
          `bgm-${Date.now()}-${Math.random().toString(16).slice(2)}`;

        const cleanup = () => {
          window.removeEventListener("message", onMessage);
          window.clearTimeout(timeoutId);
        };

        const onMessage = (event) => {
          if (event.source !== window) return;
          const data = event.data;
          if (
            !data
            || data.source !== "ccfolia-manager-main"
            || data.type !== responseType
            || data.requestId !== requestId
          ) {
            return;
          }

          cleanup();
          if (data.ok) {
            resolve(data.result || {});
          } else {
            reject(
              new Error(data.error || "BGM操作に失敗しました。"),
            );
          }
        };

        const timeoutId = window.setTimeout(
          () => {
            cleanup();
            reject(new Error("BGM操作がタイムアウトしました。"));
          },
          timeoutMs,
        );

        window.addEventListener("message", onMessage);
        window.postMessage(
          {
            source: "ccfolia-manager-panel",
            type,
            requestId,
            ...payload,
          },
          window.location.origin,
        );
      });
    }

    async function ensureBgmRegistered(asset) {
      if (asset.ccfolia_registered && asset.ccfolia_url) {
        return asset;
      }
      if (!asset.has_local) {
        throw new Error(
          "CCFOLIA未登録で、ローカル音源もありません。",
        );
      }

      setBgmStatus("CCFOLIAへ登録中…");

      const sourceData = await apiGet(
        `/api/bgm-manager/upload-source/${encodeURIComponent(asset.id)}`,
      );
      const source = sourceData.source || {};

      const result = await bgmPageMessage(
        "bgm-upload-request",
        {
          filename: source.filename || asset.original_filename || "audio.mp3",
          contentType: source.content_type || "audio/mpeg",
          dataBase64: source.data_base64,
          displayName: asset.display_name,
          volume: asset.default_volume,
          loop: asset.default_loop,
          directory: "bgm01",
        },
        "bgm-upload-result",
        90000,
      );

      const saved = await apiPost(
        "/api/bgm-manager/register",
        {
          bgm_id: asset.id,
          media_id: result.mediaId,
          url: result.url,
          directory: result.directory,
          order: result.order,
          updated_at: result.updatedAt,
        },
      );

      return saved.bgm || {
        ...asset,
        ccfolia_registered: true,
        ccfolia_url: result.url,
        ccfolia_media_id: result.mediaId,
      };
    }

    async function applyBrowserBgm(asset, card) {
      if (bgmApplyBusy) return;

      if (String(asset.media_kind || "") === "se") {
        window.alert("SEのワンクリック再生は後続フェーズで接続します。");
        return;
      }

      bgmApplyBusy = true;
      card?.classList.add("applying");

      try {
        const ready = await ensureBgmRegistered(asset);
        setBgmStatus("BGM変更中…");

        await bgmPageMessage(
          "bgm-apply-room-request",
          {
            name: ready.display_name || asset.display_name,
            url: ready.ccfolia_url,
            volume: ready.default_volume ?? asset.default_volume ?? 0.5,
            loop: ready.default_loop ?? asset.default_loop ?? true,
          },
          "bgm-apply-room-result",
          20000,
        );

        bgmCurrentId = String(asset.id);
        setBgmStatus(
          `再生: ${asset.display_name || "BGM"}`,
          "ok",
        );
        await loadBrowserBgmAssets();
      } catch (error) {
        const message = String(error?.message || error);
        setBgmStatus("BGM変更失敗", "error");
        bgmProbeStatus.title = message;
        window.alert(`BGMを変更できません: ${message}`);
      } finally {
        bgmApplyBusy = false;
        card?.classList.remove("applying");
      }
    }

    function renderBrowserBgmAssets() {
      bgmAssetList.textContent = "";
      bgmCount.textContent = `${bgmTotal}件`;
      bgmPageLabel.textContent = `${bgmPage} / ${bgmPages}`;
      bgmPrev.disabled = bgmPage <= 1;
      bgmNext.disabled = bgmPage >= bgmPages;

      if (!browserBgmAssets.length) {
        const empty = document.createElement("div");
        empty.className = "bgmManagerEmpty";
        empty.textContent = "該当するBGMがありません。";
        bgmAssetList.appendChild(empty);
        return;
      }

      for (const asset of browserBgmAssets) {
        const card = document.createElement("div");
        card.className = "bgmAssetCard";
        if (String(asset.id) === bgmCurrentId) {
          card.classList.add("playing");
        }

        const play = document.createElement("button");
        play.type = "button";
        play.className = "bgmPlayButton";
        play.textContent = "▶";
        play.title = asset.media_kind === "se"
          ? "SE再生は後続フェーズ"
          : "現在のルームBGMに変更";
        if (asset.media_kind === "se") {
          play.disabled = true;
        }
        play.addEventListener(
          "click",
          (event) => {
            event.stopPropagation();
            void applyBrowserBgm(asset, card);
          },
        );

        const body = document.createElement("div");
        const name = document.createElement("div");
        name.className = "bgmAssetName";
        name.textContent =
          asset.display_name || asset.original_filename || "BGM";

        const meta = document.createElement("div");
        meta.className = "bgmAssetMeta";
        const volume = Number(asset.default_volume ?? 0);
        meta.textContent =
          `${String(asset.media_kind || "bgm").toUpperCase()}`
          + ` · ${formatBgmDuration(asset.duration_ms)}`
          + ` · VOL ${Math.round(volume * 100)}%`
          + ` · ${asset.default_loop ? "LOOP" : "1SHOT"}`;

        const flags = document.createElement("div");
        flags.className = "bgmAssetFlags";

        for (const label of [
          asset.has_local ? "LOCAL" : "REMOTE",
          asset.ccfolia_registered ? "CCFOLIA" : "未登録",
        ]) {
          const badge = document.createElement("span");
          badge.textContent = label;
          flags.appendChild(badge);
        }

        for (const tag of (
          Array.isArray(asset.tags) ? asset.tags.slice(0, 3) : []
        )) {
          const badge = document.createElement("span");
          badge.textContent = `#${tag}`;
          flags.appendChild(badge);
        }

        body.appendChild(name);
        body.appendChild(meta);
        body.appendChild(flags);
        card.appendChild(play);
        card.appendChild(body);

        card.addEventListener(
          "contextmenu",
          (event) => {
            event.preventDefault();
            void editBrowserBgm(asset);
          },
        );

        bgmAssetList.appendChild(card);
      }
    }

    async function loadBrowserBgmAssets() {
      const params = new URLSearchParams();
      const search = bgmSearch.value.trim();
      if (search) params.set("search", search);
      params.set("mode", bgmSearchMode);
      params.set("page", String(bgmPage));
      params.set("page_size", "60");

      const group = bgmGroupSelect.value;
      if (group) params.set("group", group);
      if (bgmTaglessOnly) params.set("tagless", "1");

      const kind = bgmKindSelect.value;
      if (kind) params.set("kind", kind);

      setBgmStatus("読込中…");

      try {
        const data = await apiGet(
          `/api/bgm-manager/assets?${params.toString()}`,
        );
        browserBgmAssets = Array.isArray(data.assets)
          ? data.assets
          : [];
        bgmTotal = Number(data.total || 0);
        bgmPage = Number(data.page || 1);
        bgmPages = Number(data.pages || 1);
        renderBrowserBgmAssets();
        setBgmStatus(`${bgmTotal}件`, "ok");
      } catch (error) {
        setBgmStatus("読込失敗", "error");
        bgmProbeStatus.title = String(error?.message || error);
      }
    }

    async function refreshBgmPanel() {
      try {
        const [groupData, tagData] = await Promise.all([
          apiGet("/api/bgm-manager/groups"),
          apiGet("/api/bgm-manager/tags"),
        ]);
        browserBgmGroups = Array.isArray(groupData.groups)
          ? groupData.groups
          : [];
        browserBgmTags = Array.isArray(tagData.tags)
          ? tagData.tags
          : [];
        renderBgmGroups();
        renderBgmTagChips();
        await loadBrowserBgmAssets();
      } catch (error) {
        setBgmStatus("更新失敗", "error");
        bgmProbeStatus.title = String(error?.message || error);
      }
    }



    // BGM_FIXED_TAB_SLOTS_PANEL_V1
    async function runBgmSalvage() {
      if (
        !bgmSalvageButton
        || bgmSalvageButton.disabled
      ) {
        return;
      }

      const originalText =
        bgmSalvageButton.textContent;

      bgmSalvageButton.disabled =
        true;
      bgmSalvageButton.textContent =
        "救出中…";

      setBgmStatus(
        "CCFOLIA読取中…",
      );

      try {
        const scan =
          await bgmPageMessage(
            "bgm-salvage-scan-request",
            {},
            "bgm-salvage-scan-result",
            90000,
          );

        setBgmStatus(
          "Managerへ登録中…",
        );

        const response =
          await apiPost(
            "/api/bgm-manager/salvage",
            {
              items:
                Array.isArray(
                  scan.items,
                )
                  ? scan.items
                  : [],
            },
          );

        const result =
          response.result || {};

        await refreshBgmPanel();

        const errors =
          Array.isArray(
            result.errors,
          )
            ? result.errors.length
            : 0;

        const mapping =
          Array.isArray(
            result.slot_mapping,
          )
            ? result.slot_mapping
            : [];

        const overflow =
          Array.isArray(
            result.overflow_dirs,
          )
            ? result.overflow_dirs
            : [];

        setBgmStatus(
          `救出 ${Number(
            result.created || 0,
          )}新規 / ${Number(
            result.updated || 0,
          )}更新`,
          errors || overflow.length
            ? "error"
            : "ok",
        );

        let message =
          "BGMサルベージが完了しました。\n\n"
          + `新規: ${Number(
            result.created || 0,
          )}件\n`
          + `更新: ${Number(
            result.updated || 0,
          )}件\n`
          + `固定タブタグ付与: ${Number(
            result.tagged || 0,
          )}件\n`
          + `固定タブ割当: ${Number(
            result.slot_count || 0,
          )}/10\n`
          + `アーカイブ除外: ${Number(
            result.skipped_archived
            || 0,
          )}件`;

        if (mapping.length) {
          message +=
            "\n\n現在の対応:\n"
            + mapping
              .map(
                (entry) =>
                  `${entry.tag} ← ${
                    entry.dir_id
                  }`,
              )
              .join("\n");
        }

        if (overflow.length) {
          message +=
            "\n\n10タブを超えたため未割当:\n"
            + overflow.join(", ");
        }

        if (errors) {
          message +=
            `\n\nエラー: ${errors}件`;
        }

        message +=
          "\n\n音源本体はダウンロードしていません。";

        window.alert(message);

      } catch (error) {
        const message =
          String(
            error?.message
            || error,
          );

        setBgmStatus(
          "救出失敗",
          "error",
        );

        if (bgmProbeStatus) {
          bgmProbeStatus.title =
            message;
        }

        window.alert(
          `BGMサルベージに失敗しました: ${message}`,
        );

      } finally {
        bgmSalvageButton.disabled =
          false;
        bgmSalvageButton.textContent =
          originalText;
      }
    }

    function closeImagesPanel() {
      hideImageHoverPreview();
      imagesPanel.classList.remove("open");
    }

    function closeBgmPanel() {
      bgmPanel.classList.remove("open");
    }

    function closeAllModulePanels() {
      closePanel();
      closeImagesPanel();
      closeBgmPanel();
    }

    function toggleToolkitMenu() {
      if (
        toolkitMenu.classList.contains(
          "open"
        )
      ) {
        closeToolkitMenu();
        return;
      }

      closeAllModulePanels();
      positionToolkitMenu();
      toolkitMenu.classList.add("open");
    }

    async function openImagesPanel() {
      closeToolkitMenu();
      closeAllModulePanels();
      positionModulePanel(imagesPanel);
      imagesPanel.classList.add("open");

      if (!imagePanelInitialized) {
        imagePanelInitialized = true;
        await refreshImagePanel();
      }
    }

    async function openBgmPanel() {
      closeToolkitMenu();
      closeAllModulePanels();
      positionModulePanel(bgmPanel);
      bgmPanel.classList.add("open");

      if (!bgmPanelInitialized) {
        bgmPanelInitialized = true;
        await refreshBgmPanel();
      }
    }

    async function openPanel() {
      closeToolkitMenu();
      closeImagesPanel();
      closeBgmPanel();
      positionPanel();
      panel.classList.add("open");

      if (!panelInitialized) {
        panelInitialized = true;
        await refreshAll();
      }
    }

    function closePanel() {
      panel.classList.remove("open");
    }

    function togglePanel() {
      if (panel.classList.contains("open")) {
        closePanel();
      } else {
        openPanel();
      }
    }

    async function restorePosition() {
      const saved =
        await storageGet(STORAGE_KEY);

      if (
        saved
        && Number.isFinite(saved.x)
        && Number.isFinite(saved.y)
      ) {
        button.style.left = `${
          clamp(
            saved.x,
            4,
            window.innerWidth - 48,
          )
        }px`;
        button.style.top = `${
          clamp(
            saved.y,
            4,
            window.innerHeight - 48,
          )
        }px`;
      }
    }

    let pointerState = null;

    button.addEventListener(
      "pointerdown",
      (event) => {
        if (event.button !== 0) {
          return;
        }

        const rect =
          button.getBoundingClientRect();

        pointerState = {
          id: event.pointerId,
          offsetX:
            event.clientX - rect.left,
          offsetY:
            event.clientY - rect.top,
          startX: event.clientX,
          startY: event.clientY,
          moved: false,
        };

        button.setPointerCapture(
          event.pointerId,
        );

        event.preventDefault();
      },
    );

    button.addEventListener(
      "pointermove",
      (event) => {
        if (
          !pointerState
          || pointerState.id
            !== event.pointerId
        ) {
          return;
        }

        const distance =
          Math.hypot(
            event.clientX
              - pointerState.startX,
            event.clientY
              - pointerState.startY,
          );

        if (distance > 4) {
          pointerState.moved = true;
        }

        if (!pointerState.moved) {
          return;
        }

        const x = clamp(
          event.clientX
            - pointerState.offsetX,
          4,
          window.innerWidth - 48,
        );
        const y = clamp(
          event.clientY
            - pointerState.offsetY,
          4,
          window.innerHeight - 48,
        );

        button.style.left = `${x}px`;
        button.style.top = `${y}px`;

        if (
          panel.classList.contains(
            "open"
          )
        ) {
          positionPanel();
        }

        if (
          imagesPanel.classList.contains(
            "open"
          )
        ) {
          positionModulePanel(
            imagesPanel,
          );
        }

        if (
          bgmPanel.classList.contains(
            "open"
          )
        ) {
          positionModulePanel(
            bgmPanel,
          );
        }

        if (
          toolkitMenu.classList.contains(
            "open"
          )
        ) {
          positionToolkitMenu();
        }
      },
    );

    button.addEventListener(
      "pointerup",
      async (event) => {
        if (
          !pointerState
          || pointerState.id
            !== event.pointerId
        ) {
          return;
        }

        const moved =
          pointerState.moved;
        pointerState = null;

        try {
          button.releasePointerCapture(
            event.pointerId,
          );
        } catch (error) {
        }

        if (moved) {
          const rect =
            button.getBoundingClientRect();

          await storageSet({
            [STORAGE_KEY]: {
              x: Math.round(
                rect.left
              ),
              y: Math.round(
                rect.top
              ),
            },
          });
        } else {
          toggleToolkitMenu();
        }
      },
    );

    toolkitCharacter.addEventListener(
      "click",
      () => {
        void openPanel();
      },
    );

    toolkitImages.addEventListener(
      "click",
      () => {
        void openImagesPanel();
      },
    );

    toolkitBgm.addEventListener(
      "click",
      openBgmPanel,
    );

    imagesClose.addEventListener(
      "click",
      closeImagesPanel,
    );

    imagesImport.addEventListener(
      "click",
      () => {
        imagesImportInput.click();
      },
    );

    imagesImportInput.addEventListener(
      "change",
      () => {
        void importBrowserImageFiles(
          imagesImportInput.files,
        );
      },
    );

    imagesSalvage.addEventListener(
      "click",
      () => {
        void salvageCCFOLIAImages();
      },
    );

    installMediaPanelDropTarget(
      imagesPanel,
      imagesDropOverlay,
      importBrowserImageFiles,
    );

    installMediaPanelDropTarget(
      bgmPanel,
      bgmDropOverlay,
      importBrowserBgmFiles,
    );

    imagesRefresh.addEventListener(
      "click",
      () => {
        void refreshImagePanel();
      },
    );

    imagesPrevPage.addEventListener(
      "click",
      () => {
        if (browserImageOffset <= 0) {
          return;
        }

        hideImageHoverPreview();
        browserImageOffset = Math.max(
          0,
          browserImageOffset
          - browserImagePageSize,
        );
        void loadBrowserImageAssets({
          resetPage: false,
        });
      },
    );

    imagesNextPage.addEventListener(
      "click",
      () => {
        const nextOffset =
          browserImageOffset
          + browserImagePageSize;

        if (nextOffset >= browserImageTotal) {
          return;
        }

        hideImageHoverPreview();
        browserImageOffset = nextOffset;
        void loadBrowserImageAssets({
          resetPage: false,
        });
      },
    );

    imagesKeywordMode.addEventListener(
      "click",
      () => {
        imageSearchMode = "keyword";
        imagesKeywordMode.classList.add(
          "active",
        );
        imagesTagMode.classList.remove(
          "active",
        );
        imagesSearch.value = "";
        imagesSearch.placeholder =
          "画像を検索";
        renderImageTagChips();
        void loadBrowserImageAssets();
      },
    );

    imagesTagMode.addEventListener(
      "click",
      () => {
        imageSearchMode = "tag";
        imagesTagMode.classList.add(
          "active",
        );
        imagesKeywordMode.classList.remove(
          "active",
        );
        imagesSearch.value = "";
        imagesSearch.placeholder =
          "タグ名（カンマ区切り）";
        renderImageTagChips();
        void loadBrowserImageAssets();
      },
    );

    imagesSearch.addEventListener(
      "input",
      () => {
        if (imageSearchTimer) {
          clearTimeout(imageSearchTimer);
        }

        imageSearchTimer =
          window.setTimeout(
            () => {
              void loadBrowserImageAssets();
            },
            220,
          );
      },
    );

    imagesSearch.addEventListener(
      "keydown",
      (event) => {
        if (event.key !== "Enter") {
          return;
        }

        event.preventDefault();

        if (imageSearchTimer) {
          clearTimeout(imageSearchTimer);
          imageSearchTimer = null;
        }

        void loadBrowserImageAssets();
      },
    );

    imagesClearSearch.addEventListener(
      "click",
      () => {
        imagesSearch.value = "";
        selectedImageTagFilters = [];
        renderImageTagChips();
        void loadBrowserImageAssets();
      },
    );

    imagesGroupSelect.addEventListener(
      "change",
      () => {
        hideImageHoverPreview();
        void loadBrowserImageAssets();
      },
    );

    imagesTagless.addEventListener(
      "click",
      () => {
        imageTaglessOnly =
          !imageTaglessOnly;

        imagesTagless.classList.toggle(
          "active",
          imageTaglessOnly,
        );

        void loadBrowserImageAssets();
      },
    );

    imagesPreviewToggle.addEventListener(
      "click",
      () => {
        imagePreviewEnabled =
          !imagePreviewEnabled;
        updateImagePreviewUi();
      },
    );


    bgmImportButton.addEventListener(
      "click",
      () => {
        bgmImportInput.click();
      },
    );

    bgmImportInput.addEventListener(
      "change",
      () => {
        void importBrowserBgmFiles(bgmImportInput.files);
        bgmImportInput.value = "";
      },
    );

    bgmRefresh.addEventListener(
      "click",
      () => {
        void refreshBgmPanel();
      },
    );

    bgmKeywordMode.addEventListener(
      "click",
      () => {
        bgmSearchMode = "keyword";
        bgmKeywordMode.classList.add("active");
        bgmTagMode.classList.remove("active");
        bgmPage = 1;
        renderBgmTagChips();
        void loadBrowserBgmAssets();
      },
    );

    bgmTagMode.addEventListener(
      "click",
      () => {
        bgmSearchMode = "tag";
        bgmTagMode.classList.add("active");
        bgmKeywordMode.classList.remove("active");
        bgmPage = 1;
        renderBgmTagChips();
        void loadBrowserBgmAssets();
      },
    );

    bgmSearch.addEventListener(
      "input",
      () => {
        window.clearTimeout(bgmSearchTimer);
        bgmSearchTimer = window.setTimeout(
          () => {
            bgmPage = 1;
            renderBgmTagChips();
            void loadBrowserBgmAssets();
          },
          180,
        );
      },
    );

    bgmGroupSelect.addEventListener(
      "change",
      () => {
        bgmPage = 1;
        void loadBrowserBgmAssets();
      },
    );

    bgmKindSelect.addEventListener(
      "change",
      () => {
        bgmPage = 1;
        void loadBrowserBgmAssets();
      },
    );

    bgmTagless.addEventListener(
      "click",
      () => {
        bgmTaglessOnly = !bgmTaglessOnly;
        bgmTagless.classList.toggle("active", bgmTaglessOnly);
        bgmPage = 1;
        void loadBrowserBgmAssets();
      },
    );

    bgmPrev.addEventListener(
      "click",
      () => {
        if (bgmPage <= 1) return;
        bgmPage -= 1;
        void loadBrowserBgmAssets();
      },
    );

    bgmNext.addEventListener(
      "click",
      () => {
        if (bgmPage >= bgmPages) return;
        bgmPage += 1;
        void loadBrowserBgmAssets();
      },
    );

    bgmSalvageButton.addEventListener(
      "click",
      () => {
        void runBgmSalvage();
      },
    );

    bgmClose.addEventListener(
      "click",
      closeBgmPanel,
    );

    closeButton.addEventListener(
      "click",
      closePanel,
    );

    refreshButton.addEventListener(
      "click",
      refreshAll,
    );

    characterSalvageImport.addEventListener(
      "click",
      () => {
        void runCharacterSalvageImport();
      },
    );

    keywordMode.addEventListener(
      "click",
      () => {
        searchMode = "keyword";
        keywordMode.classList.add(
          "active"
        );
        tagMode.classList.remove(
          "active"
        );
        search.value = "";
        renderTagSearchCards();
        loadCharacters();
      },
    );

    tagMode.addEventListener(
      "click",
      () => {
        searchMode = "tag";
        tagMode.classList.add(
          "active"
        );
        keywordMode.classList.remove(
          "active"
        );
        search.value = "";
        renderTagSearchCards();
        loadCharacters();
      },
    );

    search.addEventListener(
      "input",
      () => {
        if (searchMode === "tag") {
          renderTagSearchCards(false);
          return;
        }

        clearTimeout(
          searchTimer
        );
        searchTimer = setTimeout(
          loadCharacters,
          220,
        );
      },
    );

    search.addEventListener(
      "focus",
      () => {
        if (
          searchMode === "tag"
          && search.value.trim()
        ) {
          renderTagSearchCards(false);
        }
      },
    );

    search.addEventListener(
      "keydown",
      (event) => {
        if (
          searchMode !== "tag"
        ) {
          return;
        }

        if (
          event.key === "Escape"
        ) {
          closeTagSuggestMenu();
          return;
        }

        if (
          event.key === "Enter"
          || event.key === ","
          || event.key === "、"
        ) {
          event.preventDefault();
          commitTagSearchInput();
        }
      },
    );

    // PHASE37_TAGLESS_BROWSER
    taglessSearchButton.addEventListener(
      "click",
      () => {
        taglessOnly = !taglessOnly;

        if (taglessOnly) {
          selectedTagFilters = [];
          search.value = "";
          closeTagSuggestMenu();
        }

        renderSelectedTagFilters();
        void loadCharacters();
      },
    );

    tagDropdownButton.addEventListener(
      "click",
      (event) => {
        event.preventDefault();
        event.stopPropagation();

        if (
          tagSuggestMenu.classList.contains(
            "open"
          )
          && tagDropdownButton.classList.contains(
            "active"
          )
        ) {
          closeTagSuggestMenu();
          return;
        }

        renderTagSearchCards(true);
        search.focus();
      },
    );

    shadow.addEventListener(
      "pointerdown",
      (event) => {
        if (
          !tagSearchRow.contains(
            event.target
          )
        ) {
          closeTagSuggestMenu();
        }
      },
    );

    groupSelect.addEventListener(
      "change",
      loadCharacters,
    );

    selectVisible.addEventListener(
      "click",
      () => {
        const visibleIds =
          characters.map(
            (character) =>
              character.id
          );

        const allSelected =
          visibleIds.length > 0
          && visibleIds.every(
            (id) =>
              selected.has(id)
          );

        for (const id of visibleIds) {
          if (allSelected) {
            selected.delete(id);
          } else {
            selected.add(id);
          }
        }

        renderCharacters();
      },
    );

    clearSelected.addEventListener(
      "click",
      () => {
        selected.clear();
        renderCharacters();
      },
    );

    bulkTags.addEventListener(
      "click",
      () => {
        void bulkAddTags();
      },
    );

    bulkGroup.addEventListener(
      "click",
      () => {
        void bulkAddGroup();
      },
    );

    bulkTrash.addEventListener(
      "click",
      () => {
        void bulkMoveToTrash();
      },
    );

    sendSelected.addEventListener(
      "click",
      sendSelectedCharacters,
    );

    quickMemo.addEventListener(
      "input",
      () => {
        if (!memoCharacterId) return;
        memoStatus.textContent = "未保存";
        clearTimeout(memoSaveTimer);
        memoSaveTimer = setTimeout(
          saveQuickMemoNow,
          650,
        );
      },
    );

    memoBack.addEventListener(
      "click",
      async () => {
        clearTimeout(memoSaveTimer);
        if (memoCharacterId) {
          await saveQuickMemoNow();
        }
        closeQuickMemo();
      },
    );

    createCharacter.addEventListener(
      "click",
      createNewCharacter,
    );

    groupToolsButton.addEventListener(
      "click",
      async () => {
        try {
          await manageGroups();
        } catch (error) {
          window.alert(`グループ操作エラー: ${error?.message || error}`);
        }
      },
    );

    editorClose.addEventListener(
      "click",
      () => closeCharacterEditor(false),
    );

    editorCancel.addEventListener(
      "click",
      () => closeCharacterEditor(false),
    );

    editorSave.addEventListener(
      "click",
      saveCharacterEditor,
    );

    // PHASE33_OUTSIDE_CLICK_HIDE_PANEL
    // IM3_TOOLKIT_SHELL
    document.addEventListener(
      "pointerdown",
      (event) => {
        const anyOpen =
          panel.classList.contains("open")
          || imagesPanel.classList.contains(
            "open"
          )
          || bgmPanel.classList.contains(
            "open"
          )
          || toolkitMenu.classList.contains(
            "open"
          );

        if (!anyOpen) {
          return;
        }

        const path =
          event.composedPath
            ? event.composedPath()
            : [];

        if (
          path.includes(host)
          || path.includes(button)
        ) {
          return;
        }

        closeToolkitMenu();
        closeAllModulePanels();
      },
      true,
    );

    shadow.addEventListener(
      "pointerdown",
      (event) => {
        if (!contextMenu.contains(event.target)) {
          closeContextMenu();
        }
      },
      true,
    );

    modalBackdrop.addEventListener(
      "pointerdown",
      (event) => {
        if (event.target === modalBackdrop) {
          closeModal(null);
        }
      },
    );

    window.addEventListener(
      "resize",
      () => {
        const rect =
          button.getBoundingClientRect();

        button.style.left = `${
          clamp(
            rect.left,
            4,
            window.innerWidth - 48,
          )
        }px`;
        button.style.top = `${
          clamp(
            rect.top,
            4,
            window.innerHeight - 48,
          )
        }px`;

        if (
          panel.classList.contains(
            "open"
          )
        ) {
          positionPanel();
        }

        if (
          imagesPanel.classList.contains(
            "open"
          )
        ) {
          positionModulePanel(
            imagesPanel,
          );
        }

        if (
          bgmPanel.classList.contains(
            "open"
          )
        ) {
          positionModulePanel(
            bgmPanel,
          );
        }

        if (
          toolkitMenu.classList.contains(
            "open"
          )
        ) {
          positionToolkitMenu();
        }
      },
    );

    let editorDragDepth = 0;

    window.addEventListener(
      "message",
      (event) => {
        if (
          event.data?.source !== "ccm-extension-drop-zone"
          || event.data?.type !== "uploaded"
        ) {
          return;
        }

        if (
          !editorCharacterId
          || String(event.data.character_id || "") !== String(editorCharacterId)
        ) {
          return;
        }

        void refreshAfterImageChange();
      },
      false,
    );

    updateImagePreviewUi();
    restorePosition();
    void loadTags()
      .finally(
        () => loadCharacters()
      );
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      install,
      {
        once: true,
      },
    );
  } else {
    install();
  }
})();
