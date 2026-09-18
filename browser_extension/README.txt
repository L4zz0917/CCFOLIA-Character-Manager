CCFOLIA Manager Browser Extension

CCFOLIA Manager 本体と CCFOLIA のルーム画面を連携する、
Chromium系ブラウザ向け拡張機能です。

対応ブラウザ:
- Brave
- Google Chrome
- Microsoft Edge
- その他 Chromium / Manifest V3 対応ブラウザ

主な機能:
- Character
  - Managerで管理しているキャラクターの検索・選択
  - CCFOLIAルームへの送信
  - キャラクター作成・分類補助

- Images
  - Manager画像ライブラリの検索・表示
  - CCFOLIA背景への適用
  - ドラッグ&ドロップによる画像追加
  - CCFOLIAからの画像救出

- BGM
  - Manager BGMライブラリの検索・表示
  - 現在のルームBGMをワンクリックで切り替え
  - 音量・ループ等の管理
  - ドラッグ&ドロップによるBGM追加
  - CCFOLIAからのBGM救出

インストール:
1. CCFOLIA Manager 本体を起動します。
2. ブラウザの拡張機能管理画面を開きます。
   Brave:
     brave://extensions/
   Chrome:
     chrome://extensions/
   Edge:
     edge://extensions/
3. 「デベロッパーモード」を有効にします。
4. 「パッケージ化されていない拡張機能を読み込む」を選びます。
5. この browser_extension フォルダを指定します。
6. CCFOLIAのルーム画面を再読み込みします。

拡張機能を更新した場合:
1. 拡張機能管理画面で CCFOLIA Manager を再読み込みします。
2. 開いている CCFOLIA ルームも再読み込みします。

通信:
- Manager本体との通信は 127.0.0.1:17431 のローカル通信を使用します。
- CCFOLIAの認証情報は、ローカルManagerやSQLiteへ保存する設計ではありません。

注意:
- 一部の連携機能は CCFOLIA の非公開内部仕様に依存しています。
- CCFOLIA側の更新によって、一時的に動作しなくなる場合があります。
- CCFOLIA Manager 本体を起動していない場合、ローカル連携機能は利用できません。
