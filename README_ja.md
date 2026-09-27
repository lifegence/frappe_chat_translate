# Frappe Chat Translate

Frappe v15・v16 の [ClefinCode Chat](https://github.com/clefincode/clefincode_chat) に機能を追加するアプリです。

- **リアルタイム翻訳**：参加者それぞれが、どの言語で書かれたメッセージも自分の言語で読めます。
  メッセージが画面に表示されたときに翻訳し、メッセージと言語の組ごとにキャッシュします。
- **アクセス制御の強化**：ClefinCode Chat の API がデータを返したり変更したりする前に、ログイン中の
  ユーザーがそのチャンネルの参加者かを確認します。
- **チャットのワークスペース**：管理者向けに、ホームのアイコンと、チャットの履歴・設定をまとめた画面を追加します。
- **チャットボタンの見た目**：画面の隅に出るチャットボタンの画像・色・大きさ・位置を変えられます。

ClefinCode Chat 本体は変更しません。本プロジェクトは ClefinCode とは関係ありません。

[English README](README.md)

## 動作環境

| | 動作確認したバージョン |
|---|---|
| Frappe | v16（16.33.1、16.34.2）、v15（15.121.0） |
| ClefinCode Chat | 1.3.913 |
| Python | 3.10 以降（v15 は 3.11、v16 は 3.14 で確認） |
| 翻訳エンジン | Anthropic Claude、Google Gemini、または OpenAI・OpenAI 互換のサービス（API キーが必要） |

## インストール

```bash
bench get-app https://github.com/lifegence/frappe_chat_translate
bench --site your-site install-app frappe_chat_translate
bench build --app frappe_chat_translate
bench restart
```

## 設定

**チャット > 設定 > 翻訳設定**（DocType `Chat Translate Settings`、System Manager のみ）を開きます。

| 項目 | 内容 |
|---|---|
| Enabled | 全員の翻訳を有効にする |
| 翻訳エンジン | `Anthropic Claude`（既定のモデルは `claude-opus-5`）、`Google Gemini`（既定のモデルは `gemini-2.5-flash`）、`OpenAI`（既定のモデルは `gpt-6-sol`） |
| API キー | 暗号化して保存します。空欄なら環境変数 `ANTHROPIC_API_KEY`、`GEMINI_API_KEY` / `GOOGLE_API_KEY`、`OPENAI_API_KEY` を使います |
| Base URL（OpenAI） | 任意。Azure OpenAI や自社サーバーなど、OpenAI 互換の Chat Completions の接続先。指定した場合、モデル欄にはそのサービスのモデル名・デプロイ名を入れます |
| Effort | Claude と、Base URL を指定しない OpenAI で使います。訳のニュアンスが不足する場合に上げます |
| 対象言語の絞り込み | 任意。空欄なら全ユーザーの言語に翻訳します |
| 翻訳の前提 | 任意。誰と誰の会話か。口調や用語の選び方の参考にします |
| 用語集 | 1行に1件。`用語` は訳さずに残し、`用語 => 訳語` は訳語を固定します |
| チャットボタン | 画面の隅に出るチャットボタンの画像・色・位置・大きさ |

各ユーザーの言語は、ユーザー設定の「言語」です。

### 翻訳の仕組み

1. チャットのメッセージが画面に表示されると（履歴も新着も）、ブラウザが表示中のメッセージの訳文を、
   閲覧者の言語で要求します。
2. キャッシュにある訳文はすぐに返します。ないものは1回の要求（最大50件）でまとめて翻訳し、
   メッセージと言語の組ごとにキャッシュします。同じ言語の次の閲覧者には、API を呼びません。
3. 閲覧者の言語で書かれたメッセージは翻訳しません。編集されたメッセージは、次に表示されたときに訳し直します。

訳文は、閲覧者が参加しているチャンネルのメッセージにだけ返します。

### データの扱い

チャットのメッセージ本文は、選んだ翻訳エンジンに送られます。データを学習に使わないなど、
扱うデータに合った条件の API プランを使ってください。API キーはサイトのデータベースに暗号化して保存されます。

ライフジェンスには何も送られません。詳しくは [PRIVACY.md](PRIVACY.md)（英語）を参照してください。

## アクセス制御の強化

ClefinCode Chat 1.3.913 では、外部から呼べる API の多くが、操作するユーザーとチャンネルをリクエストの
引数から受け取り、ログイン中のユーザーと照合していません。そのため、ログインしたユーザー
（ウェブサイトユーザーを含む）が、参加していないチャンネルやメッセージを読める状態でした。

本アプリは、`clefincode_chat.api.*` の外部から呼べる関数すべてを（`override_whitelisted_methods` で）包み、
認証後に次を確認します。

- チャンネル・トピック・メッセージの引数が、ログイン中のユーザーが参加者または協力者であるチャンネルのものか
- 操作するユーザーを指す引数が、ログイン中のユーザー本人か（他人を指すのが正しい使い方の関数は除く）
- ゲストは、ポータルのサポートが有効でない限り、無害な関数しか呼べない

Administrator は確認の対象外です。誤って拒否していないかを調べるときは、`site_config.json` に
`"chat_guard_mode": "log"` を設定してください。拒否せずに記録だけします（`logs/frappe_chat_translate.guard.log`）。

ClefinCode の開発元には報告済みです。本アプリのセキュリティ上の問題の報告は、[SECURITY.md](SECURITY.md) をご覧ください。

## チャットのワークスペース

ホームに **チャット** のアイコン（System Manager と Chat Administrator のみ）が追加され、次をまとめた画面が開きます。

- **チャットを開く**：今の画面でチャットのパネルを開く
- **履歴**：チャンネル、メッセージ、トピック、翻訳キャッシュ（全ユーザーの会話）
- **設定**：ClefinCode Chat の設定、翻訳設定、チャットのプロフィール

ほかのユーザーは、これまでどおり画面の隅のチャットボタンを使います。

## 既知の制約

- プッシュ通知とメール通知は、原文のままです。
- 別のユーザーがメッセージを開いている間にそのメッセージが編集されると、ページを再読み込みするまで古い訳文が表示されます。
- ウェブサイトユーザー向けのポータルのチャットは、API での確認のみで、ブラウザでは確認していません。
- Frappe v15 では、ClefinCode Chat はデスクで画面の隅のボタンの代わりにナビゲーションバーのアイコンを表示します。
  画像の設定はこのアイコンにも反映されますが、色・位置・大きさは反映されません。
- OpenAI 互換のサービスには、構造化出力（JSON スキーマ）で依頼し、サービスが対応していなければ JSON モードで1回だけ再試行します。
  実際の通信で確認したのは OpenAI 本体と Google の OpenAI 互換エンドポイントで、Azure OpenAI・自社サーバーは模擬のクライアントでの確認です。

## 開発

```bash
bench --site your-test-site run-tests --app frappe_chat_translate
```

テストは翻訳エンジンを代わりの処理に差し替えるので、API キーは不要です。テスト用のユーザーと
チャットのグループを作るので、テスト用のサイトでだけ実行してください。

デモデータ（テストユーザー2名と、3か国語のグループの会話。ローカルのサイト専用）：

```bash
bench --site your-test-site execute frappe_chat_translate.demo.seed_demo.seed --kwargs "{'owner': 'you@example.com'}"
```

## ライセンス

GPL-3.0-or-later（ClefinCode Chat と同じ）。[LICENSE](LICENSE) をご覧ください。

Copyright (c) 2026 Lifegence Corporation
