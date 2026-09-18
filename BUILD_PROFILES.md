# CCFOLIA Manager - Dual EXE Build

## 個人用スナップショット

```powershell
python .\build_personal_snapshot.py
```

現在の `app_data` を含めて、ビルド時点の自分用環境を固めます。

通常含むもの:

- `CCFOLIAManager.exe`
- PyInstaller `_internal`
- `browser_extension`
- 現在の `app_data`
  - SQLite DB
  - キャラクター関連データ
  - 画像
  - BGM

通常含めないもの:

- `backups`
- `exports`
- 開発用PoC / probe
- 古い拡張機能manifestバックアップ

`exports` も欲しい場合:

```powershell
python .\build_personal_snapshot.py --include-exports
```

ZIPが不要なら:

```powershell
python .\build_personal_snapshot.py --no-zip
```

---

## 配布用クリーン版

```powershell
python .\build_public_release.py --version 1.1.0
```

作者個人の `app_data / backups / exports` を一切コピーせず、
配布用フォルダとZIPを作ります。

出力例:

```text
releases/
├─ CCFOLIAManager_v1.1.0_Windows_x64_by_L4zz/
└─ CCFOLIAManager_v1.1.0_Windows_x64_by_L4zz.zip
```

初回起動時に利用者側で `app_data / backups / exports` が作成されます。

---

## 前提

現在のvenvにPyInstallerが必要です。

未導入の場合:

```powershell
python -m pip install pyinstaller
```

ビルド中はCCFOLIA Managerを終了してください。

PyInstaller形式は `onedir` です。
