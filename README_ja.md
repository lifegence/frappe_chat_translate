# Frappe Chat Translate

Frappe v16 のチャットアプリ [Raven](https://github.com/The-Commit-Company/raven) に、リアルタイム翻訳を追加するアプリです。参加者それぞれが、どの言語で書かれたメッセージも自分の言語で読めます。メッセージが画面に表示されたときに翻訳し、メッセージと言語の組ごとにキャッシュします。

Raven 本体は変更しません。本プロジェクトは The Commit Company とは関係ありません。

0.3.x までは ClefinCode Chat 向けでした（[ClefinCode Chat からの移行](#clefincode-chat-からの移行)を参照）。

[English README](README.md)

## 動作環境

| | 動作確認したバージョン |
|---|---|
| Frappe | v16（16.55.2） |
| Raven | 3.2.0 |
| Python | 3.10 以降（3.14 で確認） |
| 翻訳エンジン | Anthropic Claude、Google Gemini、または OpenAI・OpenAI 互換のサービス（LiteLLM のゲートウェイなど。API キーが必要） |

## インストール

```bash
bench get-app https://github.com/lifegence/frappe_chat_translate
bench --site your-site install-app frappe_chat_translate
bench restart
```

## 設定

ワークスペース **Chat Translate** の **Translation Settings**（DocType `Chat Translate Settings`、System Manager のみ）で設定します。

| 項目 | 内容 |
|---|---|
| Enabled | 全員に対して翻訳を有効にする |
| Translation Engine | `Anthropic Claude`（既定のモデル `claude-opus-5`）、`Google Gemini`（既定 `gemini-2.5-flash`）、`OpenAI`（既定 `gpt-6-sol`） |
| API キー | 暗号化して保存。空欄なら環境変数 `ANTHROPIC_API_KEY`、`GEMINI_API_KEY`／`GOOGLE_API_KEY`、`OPENAI_API_KEY` を使う |
| Base URL（OpenAI） | 任意。OpenAI 互換の Chat Completions の URL。LiteLLM のゲートウェイ（`https://gateway.example.com/v1`）、Azure OpenAI、自前のサーバーなど。モデル欄にはそのサービスのモデル名を入れる |
| Effort | Claude と、Base URL なしの OpenAI。訳のニュアンスが足りないときに上げる |
| Restrict to Languages | 任意。空欄なら全ユーザーの言語に翻訳する |
| Translation Context | 任意。誰と誰の会話か。口調や用語の手がかりになる |
| Glossary | 1行に1件。`用語` は訳さずに残す、`用語 => 訳語` は訳語を固定する |

各ユーザーの言語は、ユーザー設定の **Language** です。

### 翻訳の流れ

1. Raven の Web アプリ（`/raven`）のページに、このアプリの小さなスクリプトを加えます（ページの HTML に追加するだけで、Raven のファイルは変更しません）。メッセージが画面に出ると（履歴・新着とも）、見えているメッセージの訳を見ている人の言語で問い合わせます。
2. キャッシュ済みの訳はすぐ返します。残りは1回の依頼（最大50件）で翻訳し、メッセージと言語の組ごとにキャッシュするので、同じ言語の次の人には費用がかかりません。
3. 訳はメッセージの下に表示します。見ている人の言語で書かれたメッセージと、原文と同じ訳（URL だけ、コードなど）は表示しません。編集されたメッセージは訳し直し、削除されたメッセージの訳は消します。

訳を返すのは、Raven でそのチャンネルを読める人（Raven 自身の権限の決まり）だけです。ファイル・画像・投票・システム・ボットのメッセージは翻訳しません。

### データの扱い

チャットのメッセージ本文は、選んだ翻訳エンジンに送られます。データの扱いが目的に合う API の契約（学習に使わないものなど）を使ってください。API キーはサイトのデータベースに暗号化して保存します。

Lifegence には何も送りません。詳しくは [PRIVACY.md](PRIVACY.md) を参照してください。

## ClefinCode Chat からの移行

0.4.0 は ClefinCode Chat ではなく Raven を翻訳します。翻訳の設定（エンジン・キー・用語集）はそのまま残ります。キャッシュ済みの訳は、チャットを Raven に変換したときにメッセージについていきます。

1. ClefinCode Chat のデータを Raven に変換し、メッセージの対応表 `private/files/clefincode_raven_map.json`（`{"messages": {旧: 新}, "captions": {旧: 新}}`）を書き出す。
2. `bench --site your-site execute frappe_chat_translate.migrate_from_clefincode.run` を実行する（変換スクリプトから呼んでもよい）。変換したメッセージの訳は付け替え、変換しなかったメッセージの訳は消します。対応表がなければ何もしません。
3. ClefinCode Chat をアンインストールする。このアプリはアンインストールしないこと（訳と設定が消えます）。

0.3.x（ClefinCode Chat 向け。アクセス制御の強化を含む）は `v0.3.3` タグで引き続き使えます。

## 既知の制限

- Raven のモバイルアプリ（iOS／Android）には訳が出ません。訳が出るのは `/raven` の Web アプリだけです。
- プッシュ通知・メール通知は原文のままです。
- Raven 自身の AI 機能は使いません。両方を有効にした場合、それぞれ独立に動きます。
- OpenAI 互換のサービス：構造化出力（JSON スキーマ）で依頼し、拒否されたら JSON モードで1回だけ再試行します。

## 開発

```bash
bench --site your-test-site run-tests --app frappe_chat_translate
```

テストは翻訳エンジンを代わりのものに差し替えるので、API キーは不要です。テスト用のユーザーと Raven のチャンネルを作るので、テスト用のサイトで実行してください。

デモデータ（テスト用ユーザー2人と3言語のチャンネル。ローカルのサイト専用）：

```bash
bench --site your-test-site execute frappe_chat_translate.demo.seed_demo.seed --kwargs "{'owner': 'you@example.com'}"
```

## ライセンス

GPL-3.0-or-later。[LICENSE](LICENSE) を参照してください。

Copyright (c) 2026 Lifegence Corporation
