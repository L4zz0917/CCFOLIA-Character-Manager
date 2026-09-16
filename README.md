# CCFOLIA Character Manager

**Version 1.0.0**  
**Author: L4zz**

CCFOLIA Character Manager は、ココフォリア用のローカルキャラクター管理ツールです。

> [!IMPORTANT]
> 本ソフトウェアは非公式ツールです。ココフォリア公式およびその運営とは関係ありません。

## 主な機能

- Windowsローカルアプリ
- Brave / Chromium系ブラウザ用拡張機能
- ローカルbridge (`127.0.0.1:17431`)
- キャラクター管理
- キーワード / タグ検索
- タグ / グループ管理
- Quick Memo
- ブラウザ内キャラクター編集
- 画像管理
- ココフォリアへのキャラクター送信
- バックアップ / 復元
- ゴミ箱 / 完全削除

## ダウンロード

最新版は以下からダウンロードできます。

[Latest Release](https://github.com/L4zz0917/CCFOLIA-Character-Manager/releases/latest)

配布ファイル名の例:

`CCFOLIACharacterManager_v1.0.0_Windows_x64_by_L4zz.zip`

GitHubが自動生成する `Source code (zip)` / `Source code (tar.gz)` は、CCM本体の配布ZIPではありません。  
必ずRelease Assetsにある `CCFOLIACharacterManager_...zip` を使用してください。

## インストール

1. 配布ZIPを任意の書き込み可能なフォルダへ展開します。
2. `CCFOLIACharacterManager.exe` を起動します。
3. Braveで `brave://extensions/` を開きます。
4. 「デベロッパーモード」を有効にします。
5. 「パッケージ化されていない拡張機能を読み込む」を選択します。
6. 配布物内の `browser_extension` フォルダを指定します。
7. ココフォリアのルームを開くとCCMボタンが表示されます。

`Program Files` 直下よりも、Documentsや任意のAppsフォルダなど、通常ユーザーが書き込み可能な場所への展開を推奨します。

## データ保存

ユーザーデータは、CCMを展開したフォルダ内の `app_data` に保存されます。

- `app_data` — キャラクター・設定・画像など
- `backups` — バックアップ
- `exports` — 書き出しデータ

配布ZIPには作者のキャラクターデータ等を含めていません。

## セキュリティ

ブラウザ拡張機能とCCM本体の通信には、`127.0.0.1:17431` のローカルbridgeを使用します。

通常のWebページからbridge APIへアクセスしにくくするため、Host / Origin / 専用ヘッダー検証を行っています。

CCM用bridgeとして外部サーバーは利用しません。

## 配布物の検証

配布ZIP内の `CHECKSUMS-SHA256.txt` に各ファイルのSHA-256を記載しています。

これはファイル破損や変更の確認用です。Windows Authenticodeによるコード署名ではありません。

Windows SmartScreenで「不明な発行元」と表示される場合があります。

## 動作環境

- Windows 10 / 11を想定
- Brave / Chromium系ブラウザ
- ココフォリアのWeb版ルーム

環境やココフォリア側の仕様変更によって動作しなくなる場合があります。

## 更新

更新時はReleaseページから最新版を取得してください。

既存の `app_data` / `backups` / `exports` を保持したままプログラム部分を更新する運用を推奨します。

## 不具合報告

GitHubの **Issues** から報告してください。

可能であれば以下を添えてください。

- CCMのバージョン
- Windowsのバージョン
- 使用ブラウザ
- 発生した操作
- エラーメッセージ
- 再現手順

キャラクターデータや個人情報をそのまま添付しないでください。

## 利用条件

本ソフトウェアは無償で利用できますが、**個人による非商用利用を対象**としています。

商用利用、無断再配布、無断の改変版公開等の詳細は [TERMS_OF_USE.md](TERMS_OF_USE.md) を確認してください。

## 変更履歴

[CHANGELOG.md](CHANGELOG.md) を参照してください。

## 作者

**L4zz**

---

CCFOLIA Character Manager は非公式の第三者ツールです。
