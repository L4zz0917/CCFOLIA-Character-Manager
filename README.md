# CCFOLIA Manager

**Version 2.0.1**

**Author: L4zz**

CCFOLIA Manager は、ココフォリアで使用するキャラクター・画像・BGMをローカルでまとめて管理し、Windowsアプリとブラウザ拡張機能からCCFOLIAへ連携するための非公式ツールです。

> [!IMPORTANT]
> 本ソフトウェアは非公式の第三者ツールです。ココフォリア株式会社、ココフォリア公式およびその運営とは関係ありません。

## 主な機能

### Character
- キャラクター作成・編集
- キーワード / 複数タグAND検索
- タグ / 階層グループ管理
- キャラクター複製
- Quick Memo
- ブラウザ内キャラクター編集
- 画像登録 / 並び替え / メイン画像選択 / 削除
- ゴミ箱 / 復元 / 完全削除
- バックアップ / 復元
- CCFOLIAへのキャラクター送信
- 複数キャラクターの一括送信 / 一括分類
- 現在のCCFOLIAルームで自分が所有しているキャラクターの取り込み

### Images
- ローカル画像ライブラリ
- デスクトップアプリ / ブラウザパネルからの画像参照
- 画像のドラッグ＆ドロップ追加
- CCFOLIAの背景画像への適用
- CCFOLIA上の既存画像データの取り込み
- 多数の画像を扱うためのページ表示

### BGM
- ローカルBGMライブラリ
- BGMの追加・検索・分類
- 音量 / ループ等の設定
- CCFOLIAルームのBGMをワンクリックで切り替え
- ブラウザからのBGMアップロード・登録
- CCFOLIA上の既存BGMデータの取り込み

### Browser Extension / Local Bridge
- Brave / Google Chrome / Microsoft Edge等のChromium系ブラウザに対応
- CCFOLIA上にCCFOLIA Managerパネルを表示
- Windowsアプリ本体と `127.0.0.1:17431` でローカル通信
- Character / Images / BGMをブラウザ側から操作

## ダウンロード

最新版はGitHubのReleasesからダウンロードしてください。

[Latest Release](https://github.com/L4zz0917/CCFOLIA_Manager/releases/latest)

配布ファイル名の例:

`CCFOLIAManager_v2.0.1_Windows_x64_by_L4zz.zip`

GitHubが自動生成する `Source code (zip)` / `Source code (tar.gz)` は、実行用の配布ZIPではありません。  
Release Assetsにある `CCFOLIAManager_...zip` を使用してください。

## インストール

1. 配布ZIPを任意の書き込み可能なフォルダへ展開します。
2. `CCFOLIAManager.exe` を起動します。
3. 使用するブラウザの拡張機能管理画面を開きます。
   - Brave: `brave://extensions/`
   - Google Chrome: `chrome://extensions/`
   - Microsoft Edge: `edge://extensions/`
4. 「デベロッパーモード」を有効にします。
5. 「パッケージ化されていない拡張機能を読み込む」または「展開済みを読み込む」を選択します。
6. 配布物内の `browser_extension` フォルダを指定します。
7. CCFOLIAのルーム画面を再読み込みします。

`Program Files` 直下ではなく、Documentsや任意のAppsフォルダなど、通常ユーザーが書き込み可能な場所への展開を推奨します。

## データ保存

ユーザーデータは、CCFOLIA Managerを展開したフォルダ内の `app_data` を中心に保存されます。

更新やPC移行の前には、CCFOLIA Managerのフォルダ全体をバックアップすることを推奨します。

公開用配布ZIPには作者個人のキャラクター、画像、BGM、データベース等は含まれていません。

## セキュリティ

ブラウザ拡張機能とCCFOLIA Manager本体の通信には、`127.0.0.1:17431` のローカルbridgeを使用します。

bridgeではHost / Origin / 専用クライアントヘッダー等の検証を行っています。

CCFOLIAとの連携で一時的に利用する認証情報は、ローカルManagerのSQLite等へ永続保存しない設計です。

v2.0.1では、CharacterのCCFOLIA取り込み処理を現在ログイン中のユーザーが `owner` であるキャラクターだけに限定しています。Firestoreへの問い合わせ段階で所有者条件を適用し、ローカル保存前にも再確認します。

詳細は [SECURITY.md](SECURITY.md) を確認してください。

## CCFOLIAとの互換性

本ソフトウェアの一部機能は、CCFOLIAの公開されていない内部仕様に依存しています。

そのため、CCFOLIA側の仕様変更によって一部機能が一時的に動作しなくなる場合があります。

## 動作環境

- Windows 10 / 11を想定
- Brave / Google Chrome / Microsoft Edge等のChromium系ブラウザ
- CCFOLIAのWeb版ルーム

## 更新

新しいバージョンが公開された場合は、GitHubのReleasesから最新版を取得してください。

v2.0.0を利用している場合は、v2.0.1以降の通常版ZIPへ更新してください。

更新前には既存のCCFOLIA Managerフォルダをバックアップし、ユーザーデータが保存されている `app_data` を誤って削除しないよう注意してください。

更新後はブラウザの拡張機能管理画面からCCFOLIA Manager拡張を再読み込みし、CCFOLIAのルーム画面も再読み込みしてください。

## 使い方
詳しい操作方法は [USAGE.md](USAGE.md) を確認してください。

## 変更履歴
[CHANGELOG.md](CHANGELOG.md) を参照してください。

## 利用条件
詳細は [TERMS_OF_USE.md](TERMS_OF_USE.md) を確認してください。

## 不具合報告

GitHubの **Issues** から報告してください。

可能であれば以下を添えてください。

- CCFOLIA Managerのバージョン
- Windowsのバージョン
- 使用ブラウザ
- 発生した操作
- エラーメッセージ
- 再現手順

キャラクターデータ、個人情報、非公開セッションデータ、認証情報等をそのまま添付しないでください。

## 作者

**L4zz**

---

CCFOLIA Manager は非公式の第三者ツールです。

開発には生成AIによるコーディング支援を一部利用しています。最終的な動作確認・配布判断は作者が行っています。
